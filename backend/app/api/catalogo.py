"""Catálogo global (`/v1/catalogo`): lectura para cualquier sesión, incluido el escáner."""

import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import Usuario, current_user
from app.db import get_pool
from app.services import auditoria, catalogo, config
from app.services.catalogo import CAMPOS, Cambios
from app.services.permisos import exigir_plataforma
from app.services.ratelimit import limitar
from app.services.reglas import ReglaError

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


class ProductoGlobalOut(BaseModel):
    ean: str
    ean_buscado: str
    nombre: str
    marca: str | None
    tamano_valor: Decimal | None
    tamano_unidad: str | None
    imagen_url: str | None
    origen: str


@router.get("/ean/{ean}", response_model=ProductoGlobalOut)
async def por_ean(
    ean: str,
    user: Usuario = Depends(current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProductoGlobalOut:
    """Busca un producto por EAN: acepta 8, 12 (UPC-A), 13 y 14 dígitos y lo normaliza en el
    backend (UPC-A pasa a EAN-13). Rechaza un dígito verificador malo y los EAN de balanza.
    El escáner abierto tiene un tope por sesión para que no sirva de raspador del catálogo."""
    limite = int(await config.leer(pool, "catalogo_busquedas_por_minuto"))
    limitar(f"catalogo:{user.id}", limite, 60)
    return ProductoGlobalOut(**await catalogo.buscar(pool, ean))


# ------------------------------------------------------------------------- sugerencias
class SugerenciaIn(Cambios):
    """Los mismos campos que una corrección directa, más el EAN y el porqué."""

    ean: str = Field(max_length=14)
    motivo: str | None = Field(default=None, max_length=300)


class SugerenciaOut(BaseModel):
    id: UUID
    ean: str
    tipo: str  # alta | correccion
    cambios: dict
    motivo: str | None
    estado: str
    nota_resolucion: str | None
    created_at: datetime
    resuelto_en: datetime | None


_SELECT = """
    select s.id, s.ean, s.cambios::text as cambios, s.motivo, s.estado, s.nota_resolucion,
           s.created_at, s.resuelto_en, (p.id is not null) as existe
    from sugerencias_catalogo s left join catalogo_global p on p.ean = s.ean
"""


def _salida(r: asyncpg.Record) -> SugerenciaOut:
    return SugerenciaOut(
        id=r["id"],
        ean=r["ean"],
        tipo="correccion" if r["existe"] else "alta",
        cambios=json.loads(r["cambios"]),
        motivo=r["motivo"],
        estado=r["estado"],
        nota_resolucion=r["nota_resolucion"],
        created_at=r["created_at"],
        resuelto_en=r["resuelto_en"],
    )


@router.post("/sugerencias", response_model=SugerenciaOut, status_code=201)
async def sugerir(
    body: SugerenciaIn,
    user: Usuario = Depends(exigir_plataforma("catalogo.sugerir")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> SugerenciaOut:
    """Propone cambios para un EAN. Si el producto existe (aunque esté descartado) es una
    corrección y solo cuentan los campos que de verdad cambian; si no existe, es un alta y
    hace falta el nombre. No toca el catálogo: la aprueba otra persona de la plataforma. Una
    sugerencia nueva reemplaza a la pendiente anterior del mismo autor para ese EAN."""
    ean = catalogo.ean_valido(body.ean)
    cambios = body.a_dict()
    if not cambios:
        raise ReglaError("sin_cambios")
    async with pool.acquire() as conn, conn.transaction():
        actual = await conn.fetchrow(
            f"select id, {', '.join(CAMPOS)} from catalogo_global where ean = $1",  # noqa: S608
            ean,
        )
        if actual is None:
            if not cambios.get("nombre"):
                raise ReglaError("alta_requiere_nombre")
        else:
            cambios = {k: v for k, v in cambios.items() if catalogo.distinto(actual[k], v)}
            if not cambios:
                raise ReglaError("ya_es_lo_que_dice")
        await conn.execute(
            "update sugerencias_catalogo set estado = 'reemplazada', resuelto_en = now() "
            "where ean = $1 and usuario_id = $2 and estado = 'pendiente'",
            ean,
            user.id,
        )
        fila = await conn.fetchrow(
            "insert into sugerencias_catalogo (producto_id, ean, usuario_id, cambios, motivo) "
            "values ($1, $2, $3, $4::jsonb, $5) returning id",
            actual["id"] if actual else None,
            ean,
            user.id,
            auditoria.a_json(cambios),
            (body.motivo or "").strip() or None,
        )
        salida = await conn.fetchrow(f"{_SELECT} where s.id = $1", fila["id"])
    return _salida(salida)


@router.get("/sugerencias/mias", response_model=list[SugerenciaOut])
async def mis_sugerencias(
    estado: str | None = Query(None, pattern="^(pendiente|aprobada|rechazada|reemplazada)$"),
    limite: int = Query(50, ge=1, le=100),
    user: Usuario = Depends(exigir_plataforma("catalogo.sugerir")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[SugerenciaOut]:
    filas = await pool.fetch(
        f"{_SELECT} where s.usuario_id = $1 and ($2::text is null or s.estado = $2) "
        "order by s.created_at desc limit $3",
        user.id,
        estado,
        limite,
    )
    return [_salida(r) for r in filas]
