"""Catálogo global: búsqueda por EAN y resolución de conflictos entre fuentes.

El catálogo global lo escriben solo el ETL y la plataforma; ningún negocio lo modifica. Acá vive
la lectura (la usa cualquier sesión, incluido el escáner del cliente) y la resolución de
conflictos, que bloquea el campo para que ningún ETL lo vuelva a tocar (Doc 7).
"""

from decimal import Decimal, InvalidOperation
from uuid import UUID

import asyncpg

from app.services import auditoria
from app.services.ean import candidatos, normalizar_ean
from app.services.reglas import ReglaError

COLUMNAS = "ean, nombre, marca, tamano_valor, tamano_unidad, imagen_url, origen"
UNIDADES = {"g", "kg", "ml", "l", "u"}


def ean_valido(crudo: str) -> str:
    """El EAN normalizado, o `ReglaError` con el motivo (balanza, dígito, largo...)."""
    ean, motivo = normalizar_ean(crudo)
    if ean is None:
        raise ReglaError(motivo if motivo != "ean_vacio" else "ean_no_numerico")
    return ean


async def buscar(pool: asyncpg.Pool, crudo: str) -> dict:
    """Producto del catálogo global por EAN (8, 12, 13 o 14 dígitos), por la clave primaria."""
    ean = ean_valido(crudo)
    fila = await pool.fetchrow(
        f"select {COLUMNAS} from catalogo_global where ean = any($1::text[]) "  # noqa: S608
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
