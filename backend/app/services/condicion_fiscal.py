"""Cambio de condición fiscal sin recargar nada (Doc 2 §Cambio de condición, D22, D42).

El costo se guarda siempre como neto + IVA de compra + si dio crédito fiscal, así que pasar de
Monotributo a Responsable Inscripto (o al revés) es mecánico. El asistente ofrece tres modos:

- `mantener_precio` (por defecto): el cliente ve el mismo precio; el margen real se corrige.
- `mantener_margen`: el margen no cambia y los precios se mueven lo necesario.
- `manual`: se aplica la condición y se ajusta el margen de cada categoría a mano.

La vista previa corre exactamente el mismo camino que la aplicación y revierte al final, así que
lo que se ve es lo que se va a guardar. **Sin validar** hasta que responda el contador.
"""

from dataclasses import asdict, dataclass
from datetime import date
from uuid import UUID

import asyncpg

from app.services import auditoria, precios, productos
from app.services.precios import Entrada
from app.services.reglas import ReglaError

MARGEN_MAXIMO_BP = 100_000


class _Revertir(Exception):
    """Corta la transacción interna para que la vista previa no guarde nada."""


@dataclass
class Item:
    producto_id: UUID
    ean: str
    nombre: str
    precio_antes_centavos: int | None
    precio_despues_centavos: int | None
    margen_antes_bp: int | None
    margen_despues_bp: int | None
    ajuste: str | None  # 'margen' (se ajustó el del producto) | 'precio_fijado' (a mano)


async def _antes(conn: asyncpg.Connection, negocio_id: UUID) -> dict[UUID, asyncpg.Record]:
    filas = await conn.fetch(
        "select producto_id, precio_centavos, margen_bp from precios_vigentes"
        " where negocio_id = $1",
        negocio_id,
    )
    return {f["producto_id"]: f for f in filas}


async def _mantener_precio(
    conn: asyncpg.Connection,
    negocio_id: UUID,
    filas: list[asyncpg.Record],
    antes: dict[UUID, asyncpg.Record],
    fiscal: productos.Fiscal,
) -> dict[UUID, str]:
    """Deja el precio final como estaba. Primero intenta con el margen que lo reproduce; si el
    redondeo impide llegar exacto, fija el precio a mano. Devuelve qué se hizo por producto."""
    hecho: dict[UUID, str] = {}
    for f in filas:
        previo = antes.get(f["id"])
        costo = productos.costo_de(f)
        if (
            previo is None
            or previo["precio_centavos"] is None
            or f["precio_manual_centavos"] is not None
            or costo is None
            or fiscal.regla is None
        ):
            continue
        objetivo = previo["precio_centavos"]
        iva_bp = productos.alicuota_de(fiscal, productos.impuesto_efectivo(f, fiscal))
        margen = precios.margen_real_bp(
            objetivo, precios.costo_base(costo, fiscal.regla), fiscal.regla, iva_bp
        )
        if margen is not None and 0 <= margen <= MARGEN_MAXIMO_BP:
            llega = precios.calcular(
                Entrada(costo, margen, iva_bp, None, fiscal.redondeo_centavos), fiscal.regla
            )
            if llega.precio_centavos == objetivo:
                if margen != productos.margen_efectivo(f, fiscal):
                    await conn.execute(
                        "update productos set margen_bp = $3 where id = $1 and negocio_id = $2",
                        f["id"],
                        negocio_id,
                        margen,
                    )
                    hecho[f["id"]] = "margen"
                continue
        await conn.execute(
            "update productos set precio_manual_centavos = $3 where id = $1 and negocio_id = $2",
            f["id"],
            negocio_id,
            objetivo,
        )
        hecho[f["id"]] = "precio_fijado"
    return hecho


async def _cambiar(
    conn: asyncpg.Connection,
    *,
    negocio_id: UUID,
    usuario_id: UUID,
    condicion: str,
    desde: date | None,
    modo: str,
    ajustes: list[tuple[UUID, int]],
    discrimina_iva: bool | None,
    cuit: str | None,
) -> tuple[date, list[Item], dict[str, int]]:
    anterior = await productos.cargar_fiscal(conn, negocio_id)
    vigente = anterior.condicion
    if vigente is not None and vigente["condicion"] == condicion:
        raise ReglaError("condicion_sin_cambios")
    if not await conn.fetchval("select true from condiciones_fiscales where clave = $1", condicion):
        raise ReglaError("condicion_invalida")
    hoy = await productos.hoy(conn)
    desde = desde or hoy
    if desde > hoy or (vigente is not None and desde < vigente["desde"]):
        raise ReglaError("fecha_condicion_invalida")

    antes = await _antes(conn, negocio_id)
    await conn.execute(
        """
        insert into negocio_condicion_fiscal
            (negocio_id, condicion, desde, discrimina_iva, cuit, creado_por)
        values ($1, $2, $3, $4, $5, $6)
        """,
        negocio_id,
        condicion,
        desde,
        discrimina_iva,
        cuit if cuit is not None else (vigente["cuit"] if vigente else None),
        usuario_id,
    )
    for categoria_id, margen_bp in ajustes:
        await productos.validar_categoria(conn, negocio_id, categoria_id)
        await conn.execute(
            "update categorias set margen_bp = $3 where id = $1 and negocio_id = $2",
            categoria_id,
            negocio_id,
            margen_bp,
        )

    fiscal = await productos.cargar_fiscal(conn, negocio_id)
    hecho: dict[UUID, str] = {}
    if modo == "mantener_precio":
        hecho = await _mantener_precio(
            conn, negocio_id, await productos.filas_entrada(conn, negocio_id), antes, fiscal
        )
    filas = await productos.filas_entrada(conn, negocio_id)
    resultados = [productos.calcular_fila(f, fiscal) for f in filas]
    await productos.guardar_precios(conn, negocio_id, filas, resultados, fiscal)

    items: list[Item] = []
    for f, r in zip(filas, resultados, strict=True):
        previo = antes.get(f["id"])
        antes_p = previo["precio_centavos"] if previo else None
        antes_m = previo["margen_bp"] if previo else None
        if (antes_p, antes_m) != (r.precio_centavos, r.margen_bp):
            items.append(
                Item(
                    f["id"],
                    f["ean"],
                    f["nombre"],
                    antes_p,
                    r.precio_centavos,
                    antes_m,
                    r.margen_bp,
                    hecho.get(f["id"]),
                )  # fmt: skip
            )
    resumen = {
        "productos": len(filas),
        "cambian": len(items),
        "suben": sum(
            1
            for i in items
            if i.precio_antes_centavos is not None
            and i.precio_despues_centavos is not None
            and i.precio_despues_centavos > i.precio_antes_centavos
        ),
        "bajan": sum(
            1
            for i in items
            if i.precio_antes_centavos is not None
            and i.precio_despues_centavos is not None
            and i.precio_despues_centavos < i.precio_antes_centavos
        ),
        "sin_precio": sum(1 for r in resultados if r.precio_centavos is None),
        "margen_ajustado": sum(1 for v in hecho.values() if v == "margen"),
        "precio_fijado": sum(1 for v in hecho.values() if v == "precio_fijado"),
    }
    return desde, items, resumen


async def cambiar(
    conn: asyncpg.Connection,
    *,
    negocio_id: UUID,
    usuario_id: UUID,
    rol: str,
    condicion: str,
    desde: date | None,
    modo: str,
    ajustes: list[tuple[UUID, int]],
    discrimina_iva: bool | None,
    cuit: str | None,
    aplicar: bool,
) -> dict:
    """Vista previa (`aplicar=False`: no guarda nada) o aplicación del cambio de condición."""
    try:
        async with conn.transaction():
            desde_real, items, resumen = await _cambiar(
                conn,
                negocio_id=negocio_id,
                usuario_id=usuario_id,
                condicion=condicion,
                desde=desde,
                modo=modo,
                ajustes=ajustes,
                discrimina_iva=discrimina_iva,
                cuit=cuit,
            )
            if not aplicar:
                raise _Revertir
    except _Revertir:
        pass
    validada = await conn.fetchval(
        "select validada from condiciones_fiscales where clave = $1", condicion
    )
    if aplicar:
        await auditoria.registrar(
            conn,
            usuario_id=usuario_id,
            rol=rol,
            accion="condicion_fiscal.cambiar",
            entidad="condicion_fiscal",
            entidad_id=negocio_id,
            negocio_id=negocio_id,
            despues={"condicion": condicion, "desde": desde_real, "modo": modo, **resumen},
        )
    return {
        "aplicado": aplicar,
        "condicion": condicion,
        "desde": desde_real,
        "modo": modo,
        "resumen": resumen,
        "items": [asdict(i) for i in items],
        "sin_validar": not validada,
    }
