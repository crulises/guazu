"""Catálogo global desde el panel de plataforma (`/v1/admin/catalogo`): ficha por EAN, alta
simple, corrección directa, cola de sugerencias y resumen con el globito de pendientes.

Corrección, alta y aprobación de una sugerencia pasan por el mismo camino
(`services/catalogo.py`: `aplicar` y `crear`): bloquean contra el ETL, recalculan la calidad
y auditan igual. Los conflictos entre fuentes están en `admin.py`.
"""

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.catalogo import SugerenciaOut
from app.auth import Usuario
from app.db import get_pool
from app.services import auditoria, catalogo
from app.services.catalogo import Cambios
from app.services.permisos import exigir_plataforma
from app.services.reglas import ReglaError

router = APIRouter(prefix="/admin/catalogo", tags=["admin"])

_SELECT_PRODUCTO = (
    "select id, ean, nombre, marca, tamano_valor, tamano_unidad, pack_cantidad, presentacion, "
    "imagen_url, origen, campos_bloqueados, calidad, estado_calidad, calidad_motivos, created_at "
    "from catalogo_global"
)


class ProductoAdminOut(BaseModel):
    id: UUID
    ean: str
    nombre: str
    marca: str | None
    tamano_valor: float | None
    tamano_unidad: str | None
    pack_cantidad: int | None
    presentacion: str | None
    imagen_url: str | None
    origen: str
    campos_bloqueados: list[str]
    calidad: int | None
    estado_calidad: str | None
    calidad_motivos: list[str]
    created_at: datetime


def _producto(r: asyncpg.Record) -> ProductoAdminOut:
    return ProductoAdminOut(**dict(r))


async def _por_ean(conn: asyncpg.Pool | asyncpg.Connection, ean: str) -> asyncpg.Record:
    fila = await conn.fetchrow(f"{_SELECT_PRODUCTO} where ean = $1", ean)  # noqa: S608
    if fila is None:
        raise ReglaError("producto_inexistente")
    return fila


class AltaIn(Cambios):
    ean: str = Field(max_length=14)


class CorreccionIn(Cambios):
    nota: str | None = Field(default=None, max_length=300)


@router.get("/resumen")
async def resumen(
    _: Usuario = Depends(exigir_plataforma("admin.acceder")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict[str, int]:
    """Los globitos del panel: qué espera una decisión, y cómo está la calidad del catálogo."""
    pendientes = await pool.fetchrow(
        "select (select count(*) from sugerencias_catalogo where estado = 'pendiente') as s, "
        "(select count(*) from conflictos_catalogo where estado = 'pendiente') as c"
    )
    calidad = await pool.fetch(
        "select coalesce(estado_calidad, 'sin_evaluar') as e, count(*) as n "
        "from catalogo_global group by 1"
    )
    return {
        "sugerencias_pendientes": pendientes["s"],
        "conflictos_pendientes": pendientes["c"],
        **{f"calidad_{f['e']}": f["n"] for f in calidad},
    }


@router.get("/productos/{ean}")
async def ficha(
    ean: str,
    _: Usuario = Depends(exigir_plataforma("catalogo.ver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """La ficha completa de un EAN: el producto (aunque esté descartado), lo que dijo cada
    fuente, sus conflictos y sugerencias, y su historia en la auditoría."""
    ean = catalogo.ean_valido(ean)
    producto = _producto(await _por_ean(pool, ean))
    fuentes = await pool.fetch(
        "select fuente, datos::text as datos, cargado_en from producto_fuentes where ean = $1",
        ean,
    )
    conflictos = await catalogo.listar_conflictos(pool, None, 50, ean)
    sugerencias = await pool.fetch(
        f"{_SELECT_SUGERENCIA} where s.ean = $1 order by s.created_at desc", ean
    )
    historia = await pool.fetch(
        "select id, usuario_id, rol_actuando, accion, antes::text as antes, "
        "despues::text as despues, nota, creado_en from auditoria "
        "where entidad = 'catalogo_producto' and entidad_id = $1 order by id desc limit 50",
        ean,
    )
    return {
        "producto": producto,
        "fuentes": [
            {"fuente": f["fuente"], "datos": json.loads(f["datos"]), "cargado_en": f["cargado_en"]}
            for f in fuentes
        ],
        "conflictos": conflictos,
        "sugerencias": [_sugerencia_admin(r) for r in sugerencias],
        "historia": [
            {
                **{k: h[k] for k in ("usuario_id", "rol_actuando", "accion", "nota", "creado_en")},
                "id": int(h["id"]),
                "antes": json.loads(h["antes"]) if h["antes"] else None,
                "despues": json.loads(h["despues"]) if h["despues"] else None,
            }
            for h in historia
        ],
    }


@router.post("/productos", response_model=ProductoAdminOut, status_code=201)
async def alta(
    body: AltaIn,
    actor: Usuario = Depends(exigir_plataforma("catalogo.crear")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProductoAdminOut:
    """Alta simple de un EAN que no está: origen `manual`, todo lo cargado queda bloqueado."""
    ean = catalogo.ean_valido(body.ean)
    cambios = body.a_dict()
    if not cambios.get("nombre"):
        raise ReglaError("alta_requiere_nombre")
    async with pool.acquire() as conn, conn.transaction():
        if await conn.fetchval("select true from catalogo_global where ean = $1", ean):
            raise ReglaError("producto_ya_existe")
        producto_id = await catalogo.crear(conn, ean, cambios)
        await auditoria.registrar(
            conn,
            usuario_id=actor.id,
            rol=actor.plataforma_rol or "plataforma",
            accion="catalogo_producto.crear",
            entidad="catalogo_producto",
            entidad_id=ean,
            despues=cambios,
        )
        fila = await conn.fetchrow(f"{_SELECT_PRODUCTO} where id = $1", producto_id)  # noqa: S608
    return _producto(fila)


@router.patch("/productos/{ean}", response_model=ProductoAdminOut)
async def corregir(
    ean: str,
    body: CorreccionIn,
    actor: Usuario = Depends(exigir_plataforma("catalogo.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProductoAdminOut:
    """Corrección directa: lo que se manda se aplica, se bloquea contra el ETL y se audita."""
    ean = catalogo.ean_valido(ean)
    cambios = body.a_dict()
    if not cambios:
        raise ReglaError("sin_cambios")
    async with pool.acquire() as conn, conn.transaction():
        actual = await _por_ean(conn, ean)
        if all(not catalogo.distinto(actual[k], v) for k, v in cambios.items()):
            raise ReglaError("ya_es_lo_que_dice")
        antes, despues = await catalogo.aplicar(conn, actual["id"], cambios)
        await auditoria.registrar(
            conn,
            usuario_id=actor.id,
            rol=actor.plataforma_rol or "plataforma",
            accion="catalogo_producto.corregir",
            entidad="catalogo_producto",
            entidad_id=ean,
            antes=antes,
            despues=despues,
            nota=body.nota,
        )
        fila = await _por_ean(conn, ean)
    return _producto(fila)


# ------------------------------------------------------------------- cola de sugerencias
class SugerenciaAdminOut(SugerenciaOut):
    producto_nombre: str | None
    usuario_id: UUID
    usuario_alias: str
    actual: dict | None  # lo que hay hoy en el catálogo en esos mismos campos
    resuelto_por_alias: str | None


class RechazoIn(BaseModel):
    nota: str = Field(min_length=3, max_length=300)


class AprobacionIn(BaseModel):
    nota: str | None = Field(default=None, max_length=300)


_SELECT_SUGERENCIA = """
    select s.id, s.ean, s.cambios::text as cambios, s.motivo, s.estado, s.nota_resolucion,
           s.created_at, s.resuelto_en, s.usuario_id, u.alias as usuario_alias,
           r.alias as resuelto_por_alias, p.id as pid, p.nombre, p.marca, p.tamano_valor,
           p.tamano_unidad, p.pack_cantidad, p.presentacion
    from sugerencias_catalogo s
    join usuarios u on u.id = s.usuario_id
    left join usuarios r on r.id = s.resuelto_por
    left join catalogo_global p on p.ean = s.ean
"""


def _sugerencia_admin(r: asyncpg.Record) -> SugerenciaAdminOut:
    cambios = json.loads(r["cambios"])
    existe = r["pid"] is not None
    actual = {k: (str(r[k]) if k == "tamano_valor" and r[k] is not None else r[k]) for k in cambios}
    return SugerenciaAdminOut(
        id=r["id"],
        ean=r["ean"],
        tipo="correccion" if existe else "alta",
        cambios=cambios,
        motivo=r["motivo"],
        estado=r["estado"],
        nota_resolucion=r["nota_resolucion"],
        created_at=r["created_at"],
        resuelto_en=r["resuelto_en"],
        producto_nombre=r["nombre"],
        usuario_id=r["usuario_id"],
        usuario_alias=r["usuario_alias"],
        actual=actual if existe else None,
        resuelto_por_alias=r["resuelto_por_alias"],
    )


@router.get("/sugerencias")
async def cola_de_sugerencias(
    estado: Literal["pendiente", "aprobada", "rechazada", "reemplazada"] = "pendiente",
    limite: int = Query(default=50, ge=1, le=200),
    _: Usuario = Depends(exigir_plataforma("catalogo.sugerencias.resolver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    total = await pool.fetchval(
        "select count(*) from sugerencias_catalogo where estado = $1", estado
    )
    filas = await pool.fetch(
        f"{_SELECT_SUGERENCIA} where s.estado = $1 order by s.created_at, s.id limit $2",
        estado,
        limite,
    )
    return {"total": total, "items": [_sugerencia_admin(r) for r in filas]}


async def _resolver(
    pool: asyncpg.Pool, actor: Usuario, sugerencia_id: UUID, accion: str, nota: str | None
) -> SugerenciaAdminOut:
    rol = actor.plataforma_rol or "plataforma"
    async with pool.acquire() as conn, conn.transaction():
        s = await conn.fetchrow(
            "select id, ean, usuario_id, estado, cambios::text as cambios "
            "from sugerencias_catalogo where id = $1 for update",
            sugerencia_id,
        )
        if s is None:
            raise ReglaError("sugerencia_inexistente")
        if s["estado"] != "pendiente":
            raise ReglaError("sugerencia_resuelta")
        if s["usuario_id"] == actor.id:
            raise ReglaError("no_resolver_lo_propio")
        if accion == "rechazar":
            await conn.execute(
                "update sugerencias_catalogo set estado = 'rechazada', resuelto_por = $2, "
                "resuelto_en = now(), nota_resolucion = $3 where id = $1",
                s["id"],
                actor.id,
                nota,
            )
            await auditoria.registrar(
                conn, usuario_id=actor.id, rol=rol, accion="sugerencia.rechazar",
                entidad="sugerencia", entidad_id=s["id"], nota=nota,
            )  # fmt: skip
        else:
            cambios = Cambios(**json.loads(s["cambios"])).a_dict()
            producto_id = await conn.fetchval(
                "select id from catalogo_global where ean = $1 for update", s["ean"]
            )
            if producto_id is None:  # alta: se crea (origen manual, todo bloqueado)
                if "nombre" not in cambios:
                    raise ReglaError("alta_requiere_nombre")
                producto_id = await catalogo.crear(conn, s["ean"], cambios)
                antes: dict = {}
            else:  # correccion (tambien un alta cuyo EAN aparecio mientras tanto)
                antes, _ = await catalogo.aplicar(conn, producto_id, cambios)
            await conn.execute(
                "update sugerencias_catalogo set estado = 'aprobada', resuelto_por = $2, "
                "resuelto_en = now(), nota_resolucion = $3, producto_id = $4 where id = $1",
                s["id"],
                actor.id,
                nota,
                producto_id,
            )
            await auditoria.registrar(
                conn, usuario_id=actor.id, rol=rol, accion="sugerencia.aprobar",
                entidad="sugerencia", entidad_id=s["id"], antes={"ean": s["ean"], **antes},
                despues=cambios, nota=f"producto {producto_id}",
            )  # fmt: skip
            await auditoria.registrar(
                conn, usuario_id=actor.id, rol=rol, accion="catalogo_producto.corregir",
                entidad="catalogo_producto", entidad_id=s["ean"], antes=antes, despues=cambios,
                nota=f"sugerencia {s['id']} de {s['usuario_id']}",
            )  # fmt: skip
        fila = await conn.fetchrow(f"{_SELECT_SUGERENCIA} where s.id = $1", sugerencia_id)
    return _sugerencia_admin(fila)


@router.post("/sugerencias/{sugerencia_id}/aprobar", response_model=SugerenciaAdminOut)
async def aprobar(
    sugerencia_id: UUID,
    body: AprobacionIn | None = None,
    actor: Usuario = Depends(exigir_plataforma("catalogo.sugerencias.resolver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> SugerenciaAdminOut:
    """Aplica los cambios por el mismo camino que la corrección directa. No se aprueba lo propio."""
    nota = (body.nota or "").strip() or None if body else None
    return await _resolver(pool, actor, sugerencia_id, "aprobar", nota)


@router.post("/sugerencias/{sugerencia_id}/rechazar", response_model=SugerenciaAdminOut)
async def rechazar(
    sugerencia_id: UUID,
    body: RechazoIn,
    actor: Usuario = Depends(exigir_plataforma("catalogo.sugerencias.resolver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> SugerenciaAdminOut:
    nota = body.nota.strip()
    if len(nota) < 3:
        raise ReglaError("rechazo_requiere_nota")
    return await _resolver(pool, actor, sugerencia_id, "rechazar", nota)
