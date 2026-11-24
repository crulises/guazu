"""Productos del negocio, costos y precios calculados al escribir (Doc 2 §Precio e impuestos).

Todo corre dentro de la transacción de un negocio (`tx_negocio`). El cálculo es la función pura
de `services/precios.py`; acá solo se reúnen sus datos (condición fiscal vigente, margen,
alícuota, último costo) y se guarda el resultado en `precios_vigentes`. **Sin validar** hasta que
responda el contador: cada precio lleva la marca `sin_validar` mientras la condición no esté
validada.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

import asyncpg

from app.services import auditoria, config, precios
from app.services.precios import Costo, Entrada, Precio, ReglaCondicion
from app.services.reglas import ReglaError

MODOS = ("mantener_precio", "mantener_margen", "manual")


@dataclass
class Fiscal:
    """Lo que hace falta para calcular cualquier precio del negocio, hoy."""

    condicion: asyncpg.Record | None  # fila vigente de negocio_condicion_fiscal
    regla: ReglaCondicion | None
    margen_defecto_bp: int | None
    iva_defecto: str
    redondeo_centavos: int
    alicuotas: dict[str, int]  # clave -> bp vigente hoy


async def hoy(conn: asyncpg.Connection) -> date:
    return await conn.fetchval("select (now() at time zone 'America/Argentina/Buenos_Aires')::date")


def _regla(fila: asyncpg.Record) -> ReglaCondicion:
    return ReglaCondicion(
        clave=fila["clave"],
        suma_iva_venta=fila["suma_iva_venta"],
        iva_compra_es_credito=fila["iva_compra_es_credito"],
        discrimina_iva=fila["discrimina_iva"],
        validada=fila["validada"],
    )


async def alicuotas_vigentes(conn: asyncpg.Connection) -> dict[str, int]:
    filas = await conn.fetch(
        """
        select distinct on (clave) clave, porcentaje_bp from alicuotas_impuesto
        where vigente_desde <= (now() at time zone 'America/Argentina/Buenos_Aires')::date
        order by clave, vigente_desde desc
        """
    )
    return {f["clave"]: f["porcentaje_bp"] for f in filas}


async def condicion_vigente(conn: asyncpg.Connection, negocio_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        select n.id, n.condicion, n.desde, n.discrimina_iva, n.cuit, c.nombre, c.suma_iva_venta,
               c.iva_compra_es_credito, c.discrimina_iva as discrimina_por_defecto,
               c.comprobante, c.validada, c.nota, c.clave
        from negocio_condicion_fiscal n join condiciones_fiscales c on c.clave = n.condicion
        where n.negocio_id = $1
          and n.desde <= (now() at time zone 'America/Argentina/Buenos_Aires')::date
        order by n.desde desc, n.created_at desc limit 1
        """,
        negocio_id,
    )


async def cargar_fiscal(conn: asyncpg.Connection, negocio_id: UUID) -> Fiscal:
    fila = await condicion_vigente(conn, negocio_id)
    return Fiscal(
        condicion=fila,
        regla=_regla({**dict(fila), "discrimina_iva": fila["discrimina_por_defecto"]})
        if fila
        else None,
        margen_defecto_bp=await config.leer(conn, "margen_defecto_bp", negocio_id),
        iva_defecto=await config.leer(conn, "iva_defecto", negocio_id),
        redondeo_centavos=await config.leer(conn, "precio_redondeo_centavos", negocio_id),
        alicuotas=await alicuotas_vigentes(conn),
    )


def alicuota_de(fiscal: Fiscal, clave: str) -> int:
    if clave not in fiscal.alicuotas:
        raise ReglaError("impuesto_invalido")
    return fiscal.alicuotas[clave]


async def validar_impuesto(conn: asyncpg.Connection, clave: str | None) -> None:
    if clave is not None and not await conn.fetchval(
        "select true from tipos_impuesto where clave = $1", clave
    ):
        raise ReglaError("impuesto_invalido")


# --------------------------------------------------------------------------- cálculo y guardado

_SELECT_ENTRADA = """
    select p.id, p.ean, p.nombre, p.margen_bp, p.impuesto, p.precio_manual_centavos,
           p.categoria_id, c.margen_bp as cat_margen_bp, c.impuesto as cat_impuesto,
           k.id as costo_id, k.neto_centavos, k.iva_compra_centavos, k.es_credito_fiscal
    from productos p
    left join categorias c on c.id = p.categoria_id and c.negocio_id = p.negocio_id
    left join lateral (
        select id, neto_centavos, iva_compra_centavos, es_credito_fiscal
        from precios_costos where producto_id = p.id and negocio_id = p.negocio_id
        order by created_at desc, id desc limit 1
    ) k on true
    where p.negocio_id = $1 and ($2::uuid[] is null or p.id = any($2))
"""


async def filas_entrada(
    conn: asyncpg.Connection, negocio_id: UUID, ids: list[UUID] | None = None
) -> list[asyncpg.Record]:
    return await conn.fetch(_SELECT_ENTRADA, negocio_id, ids)


def margen_efectivo(fila: asyncpg.Record, fiscal: Fiscal) -> int | None:
    """Producto, si no categoría, si no negocio."""
    for valor in (fila["margen_bp"], fila["cat_margen_bp"], fiscal.margen_defecto_bp):
        if valor is not None:
            return valor
    return None


def impuesto_efectivo(fila: asyncpg.Record, fiscal: Fiscal) -> str:
    return fila["impuesto"] or fila["cat_impuesto"] or fiscal.iva_defecto


def costo_de(fila: asyncpg.Record) -> Costo | None:
    if fila["costo_id"] is None:
        return None
    return Costo(fila["neto_centavos"], fila["iva_compra_centavos"], fila["es_credito_fiscal"])


def calcular_fila(fila: asyncpg.Record, fiscal: Fiscal) -> Precio:
    """El precio de una fila de `filas_entrada` con la condición y config de `fiscal`."""
    if fiscal.regla is None:
        return Precio(None, None, "sin_condicion_fiscal", None, None, None, None)
    return precios.calcular(
        Entrada(
            costo_de(fila),
            margen_efectivo(fila, fiscal),
            alicuota_de(fiscal, impuesto_efectivo(fila, fiscal)),
            fila["precio_manual_centavos"],
            fiscal.redondeo_centavos,
        ),
        fiscal.regla,
    )


async def guardar_precios(
    conn: asyncpg.Connection,
    negocio_id: UUID,
    filas: list[asyncpg.Record],
    resultados: list[Precio],
    fiscal: Fiscal,
) -> None:
    condicion = fiscal.regla.clave if fiscal.regla else None
    sin_validar = not (fiscal.regla and fiscal.regla.validada)
    await conn.executemany(
        """
        insert into precios_vigentes
            (producto_id, negocio_id, precio_centavos, origen, motivo_sin_precio,
             costo_base_centavos, margen_bp, iva_venta_bp, iva_incluido_centavos, costo_id,
             condicion, sin_validar, calculado_en)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, now())
        on conflict (producto_id) do update set
            precio_centavos = excluded.precio_centavos, origen = excluded.origen,
            motivo_sin_precio = excluded.motivo_sin_precio,
            costo_base_centavos = excluded.costo_base_centavos, margen_bp = excluded.margen_bp,
            iva_venta_bp = excluded.iva_venta_bp,
            iva_incluido_centavos = excluded.iva_incluido_centavos, costo_id = excluded.costo_id,
            condicion = excluded.condicion, sin_validar = excluded.sin_validar,
            calculado_en = now()
        """,
        [
            (
                f["id"], negocio_id, r.precio_centavos, r.origen, r.motivo_sin_precio,
                r.costo_base_centavos, r.margen_bp, r.iva_venta_bp, r.iva_incluido_centavos,
                f["costo_id"], condicion, sin_validar,
            )
            for f, r in zip(filas, resultados, strict=True)
        ],
    )  # fmt: skip


async def recalcular(
    conn: asyncpg.Connection,
    negocio_id: UUID,
    ids: list[UUID] | None = None,
    fiscal: Fiscal | None = None,
) -> list[Precio]:
    """Recalcula y guarda el precio vigente de los productos dados (o de todos)."""
    fiscal = fiscal or await cargar_fiscal(conn, negocio_id)
    filas = await filas_entrada(conn, negocio_id, ids)
    resultados = [calcular_fila(f, fiscal) for f in filas]
    await guardar_precios(conn, negocio_id, filas, resultados, fiscal)
    return resultados


# --------------------------------------------------------------------------------- productos


async def catalogo_por_ean(conn: asyncpg.Connection, ean: str) -> asyncpg.Record | None:
    from app.services.ean import candidatos

    return await conn.fetchrow(
        """
        select id, ean, nombre, marca from catalogo_global
        where ean = any($1::text[]) and estado_calidad is distinct from 'descartado'
        order by (ean = $2) desc limit 1
        """,
        candidatos(ean),
        ean,
    )


async def validar_categoria(conn: asyncpg.Connection, negocio_id: UUID, categoria_id: UUID | None):
    if categoria_id is not None and not await conn.fetchval(
        "select true from categorias where id = $1 and negocio_id = $2", categoria_id, negocio_id
    ):
        raise ReglaError("categoria_inexistente")


async def producto_o_404(conn: asyncpg.Connection, negocio_id: UUID, producto_id: UUID):
    fila = await conn.fetchrow(
        "select * from productos where id = $1 and negocio_id = $2", producto_id, negocio_id
    )
    if fila is None:
        raise ReglaError("producto_negocio_inexistente")
    return fila


async def crear_producto(
    conn: asyncpg.Connection,
    *,
    negocio_id: UUID,
    usuario_id: UUID,
    rol: str,
    ean: str,
    campos: dict[str, Any],
) -> UUID:
    """Alta por EAN: toma nombre y marca del catálogo global si está; si no, hacen falta."""
    catalogo = await catalogo_por_ean(conn, ean)
    nombre = campos.get("nombre") or (catalogo["nombre"] if catalogo else None)
    if not nombre:
        raise ReglaError("producto_requiere_nombre", ean=ean)
    marca = campos.get("marca") or (catalogo["marca"] if catalogo else None)
    await validar_categoria(conn, negocio_id, campos.get("categoria_id"))
    await validar_impuesto(conn, campos.get("impuesto"))
    producto_id = await conn.fetchval(
        """
        insert into productos (negocio_id, ean, catalogo_id, nombre, marca, categoria_id,
                               margen_bp, impuesto, precio_manual_centavos)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9) returning id
        """,
        negocio_id,
        ean,
        catalogo["id"] if catalogo else None,
        nombre,
        marca,
        campos.get("categoria_id"),
        campos.get("margen_bp"),
        campos.get("impuesto"),
        campos.get("precio_manual_centavos"),
    )
    await recalcular(conn, negocio_id, [producto_id])
    await auditoria.registrar(
        conn,
        usuario_id=usuario_id,
        rol=rol,
        accion="producto.crear",
        entidad="producto",
        entidad_id=producto_id,
        negocio_id=negocio_id,
        despues={"ean": ean, "nombre": nombre, "del_catalogo": catalogo is not None},
    )
    return producto_id


CAMPOS_EDITABLES = (
    "nombre", "marca", "categoria_id", "margen_bp", "impuesto", "precio_manual_centavos", "activo",
)  # fmt: skip
CAMPOS_DE_PRECIO = ("margen_bp", "impuesto", "precio_manual_centavos")


async def actualizar_producto(
    conn: asyncpg.Connection,
    *,
    negocio_id: UUID,
    usuario_id: UUID,
    rol: str,
    producto_id: UUID,
    cambios: dict[str, Any],
) -> None:
    antes = await producto_o_404(conn, negocio_id, producto_id)
    if "categoria_id" in cambios:
        await validar_categoria(conn, negocio_id, cambios["categoria_id"])
    if "impuesto" in cambios:
        await validar_impuesto(conn, cambios["impuesto"])
    reales = {k: v for k, v in cambios.items() if antes[k] != v}
    if not reales:
        return
    sets = ", ".join(f"{k} = ${i}" for i, k in enumerate(reales, start=3))
    await conn.execute(
        f"update productos set {sets} where id = $1 and negocio_id = $2",  # noqa: S608
        producto_id,
        negocio_id,
        *reales.values(),
    )
    await recalcular(conn, negocio_id, [producto_id])
    await auditoria.registrar(
        conn,
        usuario_id=usuario_id,
        rol=rol,
        accion="producto.editar",
        entidad="producto",
        entidad_id=producto_id,
        negocio_id=negocio_id,
        antes={k: antes[k] for k in reales},
        despues=reales,
    )


async def registrar_costo(
    conn: asyncpg.Connection,
    *,
    negocio_id: UUID,
    usuario_id: UUID,
    rol: str,
    producto_id: UUID,
    neto_centavos: int | None,
    total_centavos: int | None,
    iva_compra_centavos: int | None,
    impuesto: str | None,
    comprobante: str | None,
    es_credito_fiscal: bool | None,
    proveedor: str | None,
) -> UUID:
    """Un costo nuevo (el historial no se edita). Se guarda como neto + IVA de compra + si dio
    crédito fiscal. Con el total solo, se asume la alícuota del producto y queda a revisar."""
    if (neto_centavos is None) == (total_centavos is None):
        raise ReglaError("costo_incompleto")
    producto = await producto_o_404(conn, negocio_id, producto_id)
    fiscal = await cargar_fiscal(conn, negocio_id)
    if impuesto is None:
        cat = await conn.fetchval(
            "select impuesto from categorias where id = $1", producto["categoria_id"]
        )
        impuesto = producto["impuesto"] or cat or fiscal.iva_defecto
    alicuota = alicuota_de(fiscal, impuesto)
    a_revisar = False
    if total_centavos is not None:
        neto, iva = precios.costo_desde_total(total_centavos, alicuota)
        a_revisar = True
    elif iva_compra_centavos is not None:
        neto, iva = neto_centavos, iva_compra_centavos
    else:
        neto, iva = precios.costo_desde_neto(neto_centavos, alicuota)
    if es_credito_fiscal is None:
        es_credito_fiscal = comprobante == "factura_a"
    costo_id = await conn.fetchval(
        """
        insert into precios_costos (negocio_id, producto_id, neto_centavos, iva_compra_centavos,
                                    es_credito_fiscal, comprobante, proveedor, a_revisar,
                                    creado_por)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9) returning id
        """,
        negocio_id,
        producto_id,
        neto,
        iva,
        es_credito_fiscal,
        comprobante,
        proveedor,
        a_revisar,
        usuario_id,
    )
    await recalcular(conn, negocio_id, [producto_id], fiscal)
    await auditoria.registrar(
        conn,
        usuario_id=usuario_id,
        rol=rol,
        accion="costo.registrar",
        entidad="costo",
        entidad_id=costo_id,
        negocio_id=negocio_id,
        despues={
            "producto_id": producto_id,
            "neto_centavos": neto,
            "iva_compra_centavos": iva,
            "es_credito_fiscal": es_credito_fiscal,
            "a_revisar": a_revisar,
        },
    )
    return costo_id
