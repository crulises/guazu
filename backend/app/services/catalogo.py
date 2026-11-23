"""Catálogo global: búsqueda por EAN, escritura a mano y resolución de conflictos.

El catálogo global lo escriben solo el ETL y la plataforma; ningún negocio lo modifica. Acá vive
la lectura (la usa cualquier sesión, incluido el escáner del cliente) y el **único camino de
escritura a mano** (`aplicar` y `crear`): lo usan la corrección directa, el alta simple y la
aprobación de una sugerencia, así que lo corregido queda **bloqueado contra el ETL** y la
calidad se recalcula siempre (Doc 7). Resolver un conflicto también bloquea el campo.
"""

from decimal import Decimal, InvalidOperation
from uuid import UUID

import asyncpg
from pydantic import BaseModel, Field, model_validator

from app.services import auditoria, calidad
from app.services.ean import candidatos, normalizar_ean
from app.services.reglas import ReglaError

COLUMNAS = "ean, nombre, marca, tamano_valor, tamano_unidad, imagen_url, origen"
UNIDADES = {"g", "kg", "ml", "l", "u"}
CAMPOS = ("nombre", "marca", "tamano_valor", "tamano_unidad", "pack_cantidad", "presentacion")


def ean_valido(crudo: str) -> str:
    """El EAN normalizado, o `ReglaError` con el motivo (balanza, dígito, largo...)."""
    ean, motivo = normalizar_ean(crudo)
    if ean is None:
        raise ReglaError(motivo if motivo != "ean_vacio" else "ean_no_numerico")
    return ean


async def buscar(pool: asyncpg.Pool, crudo: str) -> dict:
    """Producto del catálogo global por EAN (8, 12, 13 o 14 dígitos), por la clave primaria.
    Un producto `descartado` (muy incompleto o inservible) se conserva pero no se muestra:
    responde como no encontrado hasta que alguien lo complete (Doc 7)."""
    ean = ean_valido(crudo)
    fila = await pool.fetchrow(
        f"select {COLUMNAS} from catalogo_global where ean = any($1::text[]) "  # noqa: S608
        "and estado_calidad is distinct from 'descartado' "
        "order by (ean = $2) desc limit 1",
        candidatos(ean),
        ean,
    )
    if fila is None:
        raise ReglaError("producto_no_encontrado", ean=ean)
    return {**dict(fila), "ean_buscado": crudo.strip()}


async def listar_conflictos(
    pool: asyncpg.Pool, estado: str | None, limite: int, ean: str | None
) -> list[dict]:
    filas = await pool.fetch(
        """
        select c.id, c.ean, c.campo, c.valor_a, c.fuente_a, c.valor_b, c.fuente_b, c.estado,
               c.elegido, c.resuelto_por, c.resuelto_en, c.created_at, p.nombre
        from conflictos_catalogo c left join catalogo_global p using (ean)
        where ($1::text is null or c.estado = $1)
          and ($2::text is null or c.ean = $2)
        order by c.created_at, c.ean limit $3
        """,
        estado,
        ean,
        limite,
    )
    return [dict(f) for f in filas]


def _parsear_tamano(valor: str) -> tuple[Decimal, str]:
    """El valor de un conflicto de tamaño se guarda como «<numero> <unidad>» (ej. «500 g»)."""
    partes = valor.split()
    try:
        numero, unidad = Decimal(partes[0]), partes[1]
        if len(partes) != 2 or unidad not in UNIDADES or numero <= 0:
            raise ValueError
    except (IndexError, InvalidOperation, ValueError):
        raise ReglaError("tamano_ilegible", valor=valor) from None
    return numero, unidad


async def resolver_conflicto(
    pool: asyncpg.Pool, conflicto_id: UUID, elegido: str, actor_id: UUID, rol: str
) -> dict:
    """`a` deja lo que hay en el catálogo; `b` toma el valor de la otra fuente. En ambos casos
    el campo queda bloqueado contra el ETL. Todo en una transacción, con auditoría."""
    async with pool.acquire() as conn, conn.transaction():
        c = await conn.fetchrow(
            "select * from conflictos_catalogo where id = $1 for update", conflicto_id
        )
        if c is None:
            raise ReglaError("conflicto_inexistente")
        if c["estado"] != "pendiente":
            raise ReglaError("conflicto_resuelto")
        antes = await conn.fetchrow(
            f"select {COLUMNAS}, campos_bloqueados from catalogo_global where ean = $1",  # noqa: S608
            c["ean"],
        )
        await conn.execute("select set_config('app.catalogo_write', 'on', true)")
        campo = c["campo"]
        if elegido == "b":
            if campo == "tamano":
                valor, unidad = _parsear_tamano(c["valor_b"])
                await conn.execute(
                    "update catalogo_global set tamano_valor = $2, tamano_unidad = $3 "
                    "where ean = $1",
                    c["ean"],
                    valor,
                    unidad,
                )
            else:
                col = {"nombre": "nombre", "marca": "marca"}[campo]
                await conn.execute(
                    f"update catalogo_global set {col} = $2 where ean = $1",  # noqa: S608
                    c["ean"],
                    c["valor_b"],
                )
        await conn.execute(
            "update catalogo_global set campos_bloqueados = "
            "array(select distinct unnest(campos_bloqueados || $2::text)) where ean = $1",
            c["ean"],
            campo,
        )
        # lo que resuelve una persona ya no resta calidad (Doc 7 §6)
        await calidad.recalcular(conn, ean=c["ean"])
        fila = await conn.fetchrow(
            """
            update conflictos_catalogo
               set estado = 'resuelto', elegido = $2, resuelto_por = $3, resuelto_en = now()
             where id = $1
            returning id, ean, campo, valor_a, fuente_a, valor_b, fuente_b, estado, elegido,
                      resuelto_por, resuelto_en, created_at
            """,
            conflicto_id,
            elegido,
            actor_id,
        )
        despues = await conn.fetchrow(
            f"select {COLUMNAS}, campos_bloqueados from catalogo_global where ean = $1",  # noqa: S608
            c["ean"],
        )
        await auditoria.registrar(
            conn,
            usuario_id=actor_id,
            rol=rol,
            accion="catalogo_conflicto.resolver",
            entidad="catalogo_conflicto",
            entidad_id=conflicto_id,
            antes=antes,
            despues=despues,
            nota=f"{campo}: elegido {elegido}",
        )
    return {**dict(fila), "nombre": despues["nombre"] if despues else None}


# ---------------------------------------------------------------- escritura a mano
class Cambios(BaseModel):
    """Lo que una persona puede decir de un producto. Solo viajan los campos presentes:
    un campo ausente no se toca; presente y vacío, se borra."""

    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    marca: str | None = Field(default=None, max_length=100)
    tamano_valor: Decimal | None = Field(default=None, gt=0)
    tamano_unidad: str | None = Field(default=None, pattern="^(g|kg|ml|l|u)$")
    # La base exige > 1: "pack de 1" no es un pack, se guarda como "sin pack" (None).
    pack_cantidad: int | None = Field(default=None, ge=1, le=1000)
    presentacion: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def _validar(self):
        if "nombre" in self.model_fields_set and (self.nombre is None or not self.nombre.strip()):
            raise ValueError("el nombre no puede estar vacío")
        if self.pack_cantidad == 1:
            self.pack_cantidad = None
        toca_tamano = {"tamano_valor", "tamano_unidad"} & self.model_fields_set
        if toca_tamano and (self.tamano_valor is None) != (self.tamano_unidad is None):
            raise ValueError("tamaño y unidad van juntos (o los dos vacíos)")
        return self

    def a_dict(self) -> dict:
        """Solo los campos presentes, con el texto limpio (vacío = borrar)."""
        d: dict = {}
        for campo in CAMPOS:
            if campo not in self.model_fields_set:
                continue
            v = getattr(self, campo)
            if isinstance(v, str):
                v = v.strip() or None
                if campo == "presentacion" and v:
                    v = v.lower()
            d[campo] = v
        return d


def bloqueos(cambios: dict) -> list[str]:
    """Qué campos del catálogo quedan bloqueados contra el ETL al aplicar estos cambios."""
    b = [c for c in ("nombre", "marca", "presentacion") if c in cambios]
    if {"tamano_valor", "tamano_unidad", "pack_cantidad"} & cambios.keys():
        b.append("tamano")
    return b


def distinto(actual, nuevo) -> bool:
    if isinstance(actual, Decimal) and nuevo is not None:
        return actual != Decimal(str(nuevo))
    return actual != nuevo


async def aplicar(conn: asyncpg.Connection, producto_id: UUID, cambios: dict) -> tuple[dict, dict]:
    """Aplica `cambios` a un producto y lo bloquea. -> (antes, despues) de esos campos.
    Dentro de la transacción de quien llama (que también audita). `({}, {})` si no existe."""
    antes = await conn.fetchrow(
        f"select {', '.join(CAMPOS)} from catalogo_global where id = $1 for update",  # noqa: S608
        producto_id,
    )
    if antes is None:
        return {}, {}
    await conn.execute("select set_config('app.catalogo_write', 'on', true)")
    sets = [f"{k} = ${i + 2}" for i, k in enumerate(cambios)]
    await conn.execute(
        f"update catalogo_global set {', '.join(sets)}, campos_bloqueados = "  # noqa: S608
        f"array(select distinct unnest(campos_bloqueados || ${len(cambios) + 2}::text[])) "
        "where id = $1",
        producto_id,
        *cambios.values(),
        bloqueos(cambios),
    )
    await calidad.recalcular(conn, producto_id=producto_id)
    return {k: antes[k] for k in cambios}, dict(cambios)


async def crear(conn: asyncpg.Connection, ean: str, cambios: dict) -> UUID:
    """Alta de un producto nuevo: origen `manual` y todo lo que se dio queda bloqueado. Lo que
    se dejó vacío no se bloquea: un ETL todavía puede completarlo."""
    cambios = {k: v for k, v in cambios.items() if v is not None}
    await conn.execute("select set_config('app.catalogo_write', 'on', true)")
    cols = list(cambios)
    producto_id = await conn.fetchval(
        f"insert into catalogo_global (ean, origen, campos_bloqueados, {', '.join(cols)}) "  # noqa: S608
        f"values ($1, 'manual', $2::text[], {', '.join(f'${i + 3}' for i in range(len(cols)))}) "
        "returning id",
        ean,
        bloqueos(cambios),
        *cambios.values(),
    )
    await calidad.recalcular(conn, producto_id=producto_id)
    return producto_id
