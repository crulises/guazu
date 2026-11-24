"""Productos, categorías, costos y condición fiscal de UN negocio (Doc 2 §Precio e impuestos).

Los permisos son atómicos: `productos.ver`/`productos.editar` para el catálogo del negocio,
`precios.editar` para margen, alícuota, precio a mano y costos, `stock.ver_costos` para ver lo
que cuesta (un cajero ve el precio, no el costo ni el margen) y `config.editar` para la
condición fiscal. Todo corre en `tx_negocio` (RLS por negocio).
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.db import get_pool
from app.services import auditoria, condicion_fiscal, productos
from app.services.catalogo import ean_valido
from app.services.permisos import Contexto, exigir, permisos_en
from app.services.reglas import ReglaError
from app.tenant import tx_negocio

router = APIRouter(prefix="/negocios/{negocio_id}", tags=["productos"])

Margen = Field(default=None, ge=0, le=100_000)
Centavos = Field(default=None, gt=0, le=100_000_000_000)


async def tiene(pool: asyncpg.Pool, ctx: Contexto, permiso: str) -> bool:
    roles = await permisos_en(pool, ctx.usuario.id, ctx.negocio_id, ctx.sucursal_id)
    return any(permiso in permisos for permisos in roles.values())


async def exigir_tambien(pool: asyncpg.Pool, ctx: Contexto, permiso: str) -> None:
    if not await tiene(pool, ctx, permiso):
        raise ReglaError("sin_permiso")


# ------------------------------------------------------------------------------- categorías


class CategoriaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    margen_bp: int | None = Margen
    impuesto: str | None = None


class CategoriaPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    margen_bp: int | None = Margen
    impuesto: str | None = None


class CategoriaOut(BaseModel):
    id: UUID
    nombre: str
    margen_bp: int | None
    impuesto: str | None
    productos: int


_CATEGORIAS = """
    select c.id, c.nombre, c.margen_bp, c.impuesto,
           (select count(*) from productos p where p.categoria_id = c.id) as productos
    from categorias c where c.negocio_id = $1
"""


@router.get("/categorias", response_model=list[CategoriaOut])
async def categorias(
    ctx: Contexto = Depends(exigir("productos.ver")), pool: asyncpg.Pool = Depends(get_pool)
) -> list[CategoriaOut]:
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        filas = await conn.fetch(f"{_CATEGORIAS} order by lower(c.nombre)", ctx.negocio_id)  # noqa: S608
    return [CategoriaOut(**dict(f)) for f in filas]


@router.post("/categorias", response_model=CategoriaOut, status_code=201)
async def crear_categoria(
    body: CategoriaIn,
    ctx: Contexto = Depends(exigir("productos.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> CategoriaOut:
    if body.margen_bp is not None or body.impuesto is not None:
        await exigir_tambien(pool, ctx, "precios.editar")
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        await productos.validar_impuesto(conn, body.impuesto)
        categoria_id = await conn.fetchval(
            "insert into categorias (negocio_id, nombre, margen_bp, impuesto)"
            " values ($1, $2, $3, $4) returning id",
            ctx.negocio_id,
            body.nombre.strip(),
            body.margen_bp,
            body.impuesto,
        )
        await auditoria.registrar(
            conn,
            usuario_id=ctx.usuario.id,
            rol=ctx.rol,
            accion="categoria.crear",
            entidad="categoria",
            entidad_id=categoria_id,
            negocio_id=ctx.negocio_id,
            despues=body.model_dump(),
        )
        fila = await conn.fetchrow(f"{_CATEGORIAS} and c.id = $2", ctx.negocio_id, categoria_id)  # noqa: S608
    return CategoriaOut(**dict(fila))


@router.patch("/categorias/{categoria_id}", response_model=CategoriaOut)
async def editar_categoria(
    categoria_id: UUID,
    body: CategoriaPatch,
    ctx: Contexto = Depends(exigir("productos.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> CategoriaOut:
    cambios = {k: getattr(body, k) for k in body.model_fields_set}
    if "margen_bp" in cambios or "impuesto" in cambios:
        await exigir_tambien(pool, ctx, "precios.editar")
    if cambios.get("nombre"):
        cambios["nombre"] = cambios["nombre"].strip()
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        antes = await conn.fetchrow(
            "select nombre, margen_bp, impuesto from categorias where id = $1 and negocio_id = $2",
            categoria_id,
            ctx.negocio_id,
        )
        if antes is None:
            raise ReglaError("categoria_inexistente")
        await productos.validar_impuesto(conn, cambios.get("impuesto"))
        if cambios:
            sets = ", ".join(f"{k} = ${i}" for i, k in enumerate(cambios, start=3))
            await conn.execute(
                f"update categorias set {sets} where id = $1 and negocio_id = $2",  # noqa: S608
                categoria_id,
                ctx.negocio_id,
                *cambios.values(),
            )
            if "margen_bp" in cambios or "impuesto" in cambios:
                ids = await conn.fetch(
                    "select id from productos where categoria_id = $1 and negocio_id = $2",
                    categoria_id,
                    ctx.negocio_id,
                )
                await productos.recalcular(conn, ctx.negocio_id, [i["id"] for i in ids])
            await auditoria.registrar(
                conn,
                usuario_id=ctx.usuario.id,
                rol=ctx.rol,
                accion="categoria.editar",
                entidad="categoria",
                entidad_id=categoria_id,
                negocio_id=ctx.negocio_id,
                antes={k: antes[k] for k in cambios},
                despues=cambios,
            )
        fila = await conn.fetchrow(f"{_CATEGORIAS} and c.id = $2", ctx.negocio_id, categoria_id)  # noqa: S608
    return CategoriaOut(**dict(fila))


@router.delete("/categorias/{categoria_id}", status_code=204)
async def borrar_categoria(
    categoria_id: UUID,
    ctx: Contexto = Depends(exigir("productos.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> None:
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        fila = await conn.fetchrow(_CATEGORIAS + " and c.id = $2", ctx.negocio_id, categoria_id)
        if fila is None:
            raise ReglaError("categoria_inexistente")
        if fila["productos"]:
            raise ReglaError("categoria_con_productos", productos=fila["productos"])
        await conn.execute(
            "delete from categorias where id = $1 and negocio_id = $2",
            categoria_id,
            ctx.negocio_id,
        )
        await auditoria.registrar(
            conn,
            usuario_id=ctx.usuario.id,
            rol=ctx.rol,
            accion="categoria.borrar",
            entidad="categoria",
            entidad_id=categoria_id,
            negocio_id=ctx.negocio_id,
            antes={"nombre": fila["nombre"]},
        )


# --------------------------------------------------------------------------------- productos


class ProductoIn(BaseModel):
    ean: str = Field(min_length=1, max_length=20)
    nombre: str | None = Field(default=None, max_length=200)
    marca: str | None = Field(default=None, max_length=100)
    categoria_id: UUID | None = None
    margen_bp: int | None = Margen
    impuesto: str | None = None
    precio_manual_centavos: int | None = Centavos


class ProductoPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    marca: str | None = Field(default=None, max_length=100)
    categoria_id: UUID | None = None
    margen_bp: int | None = Margen
    impuesto: str | None = None
    precio_manual_centavos: int | None = Centavos
    activo: bool | None = None


class CostoIn(BaseModel):
    """Con factura A: `neto_centavos` y la alícuota (`impuesto`, o el IVA exacto de la factura en
    `iva_compra_centavos`). Sin ella: `total_centavos`. Uno de los dos, no los dos."""

    neto_centavos: int | None = Field(default=None, ge=0, le=100_000_000_000)
    total_centavos: int | None = Field(default=None, ge=0, le=100_000_000_000)
    iva_compra_centavos: int | None = Field(default=None, ge=0, le=100_000_000_000)
    impuesto: str | None = None
    comprobante: str | None = Field(
        default=None, pattern="^(factura_a|factura_b|factura_c|ticket|remito|otro)$"
    )
    es_credito_fiscal: bool | None = None
    proveedor: str | None = Field(default=None, max_length=120)


class CostoOut(BaseModel):
    id: UUID
    neto_centavos: int
    iva_compra_centavos: int
    total_centavos: int
    es_credito_fiscal: bool
    comprobante: str | None
    proveedor: str | None
    a_revisar: bool
    creado_en: datetime


class ProductoOut(BaseModel):
    id: UUID
    ean: str
    nombre: str
    marca: str | None
    categoria_id: UUID | None
    activo: bool
    del_catalogo: bool
    impuesto: str | None
    precio_manual_centavos: int | None
    precio_centavos: int | None
    origen_precio: str | None
    motivo_sin_precio: str | None
    iva_incluido_centavos: int | None
    sin_validar: bool | None
    # Solo con `stock.ver_costos`
    margen_bp: int | None = None
    margen_aplicado_bp: int | None = None
    costo_base_centavos: int | None = None
    costo: CostoOut | None = None


_PRODUCTOS = """
    select p.id, p.ean, p.nombre, p.marca, p.categoria_id, p.activo, p.impuesto,
           p.margen_bp, p.precio_manual_centavos, p.catalogo_id is not null as del_catalogo,
           v.precio_centavos, v.origen as origen_precio, v.motivo_sin_precio,
           v.iva_incluido_centavos, v.sin_validar, v.margen_bp as margen_aplicado_bp,
           v.costo_base_centavos
    from productos p left join precios_vigentes v on v.producto_id = p.id
    where p.negocio_id = $1
"""


def _producto(f: asyncpg.Record, costos: bool, costo: CostoOut | None = None) -> ProductoOut:
    d = dict(f)
    if not costos:
        d["margen_bp"] = d["margen_aplicado_bp"] = d["costo_base_centavos"] = None
    return ProductoOut(**d, costo=costo if costos else None)


def _costo(f: asyncpg.Record) -> CostoOut:
    return CostoOut(
        id=f["id"],
        neto_centavos=f["neto_centavos"],
        iva_compra_centavos=f["iva_compra_centavos"],
        total_centavos=f["neto_centavos"] + f["iva_compra_centavos"],
        es_credito_fiscal=f["es_credito_fiscal"],
        comprobante=f["comprobante"],
        proveedor=f["proveedor"],
        a_revisar=f["a_revisar"],
        creado_en=f["created_at"],
    )


_COSTOS = """
    select id, neto_centavos, iva_compra_centavos, es_credito_fiscal, comprobante, proveedor,
           a_revisar, created_at
    from precios_costos where negocio_id = $1 and producto_id = $2
    order by created_at desc, id desc
"""


async def _ficha(conn: asyncpg.Connection, negocio_id: UUID, producto_id: UUID, costos: bool):
    fila = await conn.fetchrow(_PRODUCTOS + " and p.id = $2", negocio_id, producto_id)
    if fila is None:
        raise ReglaError("producto_negocio_inexistente")
    ultimo = await conn.fetchrow(_COSTOS + " limit 1", negocio_id, producto_id) if costos else None
    return _producto(fila, costos, _costo(ultimo) if ultimo else None)


@router.get("/productos", response_model=list[ProductoOut])
async def listar_productos(
    q: str | None = Query(default=None, max_length=100),
    categoria_id: UUID | None = None,
    sin_precio: bool = False,
    inactivos: bool = False,
    limite: int = Query(default=50, ge=1, le=500),
    desde: int = Query(default=0, ge=0),
    ctx: Contexto = Depends(exigir("productos.ver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[ProductoOut]:
    costos = await tiene(pool, ctx, "stock.ver_costos")
    filtros, args = "", [ctx.negocio_id]
    if q:
        args.append(q.strip())
        filtros += (
            f" and (p.ean = ${len(args)}"
            f" or unaccent(lower(p.nombre || ' ' || coalesce(p.marca, '')))"
            f" like '%' || unaccent(lower(${len(args)})) || '%')"
        )
    if categoria_id:
        args.append(categoria_id)
        filtros += f" and p.categoria_id = ${len(args)}"
    if sin_precio:
        filtros += " and v.precio_centavos is null"
    if not inactivos:
        filtros += " and p.activo"
    args += [limite, desde]
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        filas = await conn.fetch(
            f"{_PRODUCTOS}{filtros} order by lower(p.nombre), p.id "  # noqa: S608
            f"limit ${len(args) - 1} offset ${len(args)}",
            *args,
        )
    return [_producto(f, costos) for f in filas]


@router.post("/productos", response_model=ProductoOut, status_code=201)
async def crear_producto(
    body: ProductoIn,
    ctx: Contexto = Depends(exigir("productos.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProductoOut:
    """Alta por EAN. Si está en el catálogo global se toman nombre y marca; si no, hacen falta."""
    if any(v is not None for v in (body.margen_bp, body.impuesto, body.precio_manual_centavos)):
        await exigir_tambien(pool, ctx, "precios.editar")
    ean = ean_valido(body.ean)
    costos = await tiene(pool, ctx, "stock.ver_costos")
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        producto_id = await productos.crear_producto(
            conn,
            negocio_id=ctx.negocio_id,
            usuario_id=ctx.usuario.id,
            rol=ctx.rol,
            ean=ean,
            campos=body.model_dump(exclude={"ean"}),
        )
        return await _ficha(conn, ctx.negocio_id, producto_id, costos)


@router.get("/productos/{producto_id}", response_model=ProductoOut)
async def ver_producto(
    producto_id: UUID,
    ctx: Contexto = Depends(exigir("productos.ver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProductoOut:
    costos = await tiene(pool, ctx, "stock.ver_costos")
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        return await _ficha(conn, ctx.negocio_id, producto_id, costos)


@router.patch("/productos/{producto_id}", response_model=ProductoOut)
async def editar_producto(
    producto_id: UUID,
    body: ProductoPatch,
    ctx: Contexto = Depends(exigir("productos.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProductoOut:
    cambios: dict[str, Any] = {k: getattr(body, k) for k in body.model_fields_set}
    if any(k in cambios for k in productos.CAMPOS_DE_PRECIO):
        await exigir_tambien(pool, ctx, "precios.editar")
    for obligatorio in ("nombre", "activo"):
        if obligatorio in cambios and cambios[obligatorio] is None:
            del cambios[obligatorio]
    costos = await tiene(pool, ctx, "stock.ver_costos")
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        await productos.actualizar_producto(
            conn,
            negocio_id=ctx.negocio_id,
            usuario_id=ctx.usuario.id,
            rol=ctx.rol,
            producto_id=producto_id,
            cambios=cambios,
        )
        return await _ficha(conn, ctx.negocio_id, producto_id, costos)


@router.post("/productos/{producto_id}/costos", response_model=ProductoOut, status_code=201)
async def cargar_costo(
    producto_id: UUID,
    body: CostoIn,
    ctx: Contexto = Depends(exigir("precios.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProductoOut:
    """Un costo nuevo: queda en el historial y se recalcula el precio. Devuelve la ficha."""
    costos = await tiene(pool, ctx, "stock.ver_costos")
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        await productos.registrar_costo(
            conn,
            negocio_id=ctx.negocio_id,
            usuario_id=ctx.usuario.id,
            rol=ctx.rol,
            producto_id=producto_id,
            neto_centavos=body.neto_centavos,
            total_centavos=body.total_centavos,
            iva_compra_centavos=body.iva_compra_centavos,
            impuesto=body.impuesto,
            comprobante=body.comprobante,
            es_credito_fiscal=body.es_credito_fiscal,
            proveedor=body.proveedor,
        )
        return await _ficha(conn, ctx.negocio_id, producto_id, costos)


@router.get("/productos/{producto_id}/costos", response_model=list[CostoOut])
async def historial_de_costos(
    producto_id: UUID,
    ctx: Contexto = Depends(exigir("stock.ver_costos")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[CostoOut]:
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        await productos.producto_o_404(conn, ctx.negocio_id, producto_id)
        filas = await conn.fetch(_COSTOS, ctx.negocio_id, producto_id)
    return [_costo(f) for f in filas]


# ------------------------------------------------------------------------ condición fiscal


class ReglaOut(BaseModel):
    clave: str
    nombre: str
    suma_iva_venta: bool
    iva_compra_es_credito: bool
    discrimina_iva: bool
    comprobante: str
    validada: bool
    nota: str | None


class VigenteOut(BaseModel):
    condicion: str
    nombre: str
    desde: date
    discrimina_iva: bool
    cuit: str | None
    sin_validar: bool


class AlicuotaOut(BaseModel):
    clave: str
    nombre: str
    porcentaje_bp: int


class FiscalOut(BaseModel):
    vigente: VigenteOut | None
    historial: list[dict[str, Any]]
    condiciones: list[ReglaOut]
    alicuotas: list[AlicuotaOut]
    margen_defecto_bp: int | None
    iva_defecto: str
    precio_redondeo_centavos: int
    hoy: date


class FiscalPatch(BaseModel):
    discrimina_iva: bool | None = None
    cuit: str | None = Field(default=None, pattern=r"^[0-9]{11}$")


class CambioIn(BaseModel):
    condicion: str = Field(min_length=1, max_length=40)
    desde: date | None = None
    modo: str = Field(
        default="mantener_precio", pattern="^(mantener_precio|mantener_margen|manual)$"
    )
    ajustes_categorias: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    discrimina_iva: bool | None = None
    cuit: str | None = Field(default=None, pattern=r"^[0-9]{11}$")


class PreciosConfigIn(BaseModel):
    margen_defecto_bp: int | None = Margen
    iva_defecto: str | None = None
    precio_redondeo_centavos: int | None = Field(default=None, ge=0, le=1_000_000)


class PreciosConfigOut(BaseModel):
    margen_defecto_bp: int | None
    iva_defecto: str
    precio_redondeo_centavos: int


@router.get("/fiscal", response_model=FiscalOut)
async def ver_fiscal(
    ctx: Contexto = Depends(exigir("negocio.ver")), pool: asyncpg.Pool = Depends(get_pool)
) -> FiscalOut:
    """Condición vigente, historial, reglas de cada condición y alícuotas. Todo lo fiscal es
    `sin_validar` hasta que lo valide el contador."""
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        fiscal = await productos.cargar_fiscal(conn, ctx.negocio_id)
        historial = await conn.fetch(
            "select condicion, desde, discrimina_iva, cuit, created_at from"
            " negocio_condicion_fiscal where negocio_id = $1"
            " order by desde desc, created_at desc",
            ctx.negocio_id,
        )
        condiciones = await conn.fetch("select * from condiciones_fiscales order by clave")
        tipos = await conn.fetch("select clave, nombre from tipos_impuesto order by clave")
        hoy = await productos.hoy(conn)
    v = fiscal.condicion
    vigente = (
        VigenteOut(
            condicion=v["condicion"],
            nombre=v["nombre"],
            desde=v["desde"],
            discrimina_iva=v["discrimina_por_defecto"]
            if v["discrimina_iva"] is None
            else v["discrimina_iva"],
            cuit=v["cuit"],
            sin_validar=not v["validada"],
        )
        if v
        else None
    )
    return FiscalOut(
        vigente=vigente,
        historial=[{**dict(h), "created_at": h["created_at"].isoformat()} for h in historial],
        condiciones=[ReglaOut(**dict(c)) for c in condiciones],
        alicuotas=[
            AlicuotaOut(
                clave=t["clave"], nombre=t["nombre"], porcentaje_bp=fiscal.alicuotas[t["clave"]]
            )
            for t in tipos
            if t["clave"] in fiscal.alicuotas
        ],
        margen_defecto_bp=fiscal.margen_defecto_bp,
        iva_defecto=fiscal.iva_defecto,
        precio_redondeo_centavos=fiscal.redondeo_centavos,
        hoy=hoy,
    )


@router.patch("/fiscal", response_model=VigenteOut)
async def editar_fiscal(
    body: FiscalPatch,
    ctx: Contexto = Depends(exigir("config.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> VigenteOut:
    """Cómo se muestra el IVA en los comprobantes (discriminado o no) y el CUIT. No cambia la
    condición ni los precios: para eso es el cambio de condición."""
    cambios = {k: getattr(body, k) for k in body.model_fields_set}
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        v = await productos.condicion_vigente(conn, ctx.negocio_id)
        if v is None:
            raise ReglaError("sin_condicion_fiscal")
        if cambios:
            sets = ", ".join(f"{k} = ${i}" for i, k in enumerate(cambios, start=2))
            await conn.execute(
                f"update negocio_condicion_fiscal set {sets} where id = $1",  # noqa: S608
                v["id"],
                *cambios.values(),
            )
            await auditoria.registrar(
                conn,
                usuario_id=ctx.usuario.id,
                rol=ctx.rol,
                accion="condicion_fiscal.editar",
                entidad="condicion_fiscal",
                entidad_id=ctx.negocio_id,
                negocio_id=ctx.negocio_id,
                antes={k: v[k] for k in cambios},
                despues=cambios,
            )
        v = await productos.condicion_vigente(conn, ctx.negocio_id)
    return VigenteOut(
        condicion=v["condicion"],
        nombre=v["nombre"],
        desde=v["desde"],
        discrimina_iva=v["discrimina_por_defecto"]
        if v["discrimina_iva"] is None
        else v["discrimina_iva"],
        cuit=v["cuit"],
        sin_validar=not v["validada"],
    )


def _ajustes(body: CambioIn) -> list[tuple[UUID, int]]:
    salida = []
    for a in body.ajustes_categorias:
        try:
            margen = int(a["margen_bp"])
            if not 0 <= margen <= 100_000:
                raise ValueError
            salida.append((UUID(str(a["categoria_id"])), margen))
        except (KeyError, ValueError, TypeError) as e:
            raise ReglaError("dato_invalido") from e
    return salida


async def _cambio(body: CambioIn, ctx: Contexto, pool: asyncpg.Pool, aplicar: bool) -> dict:
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        return await condicion_fiscal.cambiar(
            conn,
            negocio_id=ctx.negocio_id,
            usuario_id=ctx.usuario.id,
            rol=ctx.rol,
            condicion=body.condicion,
            desde=body.desde,
            modo=body.modo,
            ajustes=_ajustes(body),
            discrimina_iva=body.discrimina_iva,
            cuit=body.cuit,
            aplicar=aplicar,
        )


@router.post("/fiscal/cambio/vista-previa")
async def vista_previa_del_cambio(
    body: CambioIn,
    ctx: Contexto = Depends(exigir("config.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """Antes y después de cambiar de condición, sin guardar nada."""
    return await _cambio(body, ctx, pool, aplicar=False)


@router.post("/fiscal/cambio")
async def cambiar_condicion(
    body: CambioIn,
    ctx: Contexto = Depends(exigir("config.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    """Aplica el cambio de condición desde una fecha y recalcula la lista de precios."""
    return await _cambio(body, ctx, pool, aplicar=True)


@router.get("/precios/config", response_model=PreciosConfigOut)
async def ver_config_de_precios(
    ctx: Contexto = Depends(exigir("productos.ver")), pool: asyncpg.Pool = Depends(get_pool)
) -> PreciosConfigOut:
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        fiscal = await productos.cargar_fiscal(conn, ctx.negocio_id)
    return PreciosConfigOut(
        margen_defecto_bp=fiscal.margen_defecto_bp,
        iva_defecto=fiscal.iva_defecto,
        precio_redondeo_centavos=fiscal.redondeo_centavos,
    )


@router.put("/precios/config", response_model=PreciosConfigOut)
async def editar_config_de_precios(
    body: PreciosConfigIn,
    ctx: Contexto = Depends(exigir("config.editar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> PreciosConfigOut:
    """Margen de respaldo, alícuota de respaldo y redondeo comercial del negocio. Recalcula los
    precios. Mandar `margen_defecto_bp: null` quita el margen de respaldo."""
    cambios = {k: getattr(body, k) for k in body.model_fields_set}
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        await productos.validar_impuesto(conn, cambios.get("iva_defecto"))
        antes = await productos.cargar_fiscal(conn, ctx.negocio_id)
        previos = {
            "margen_defecto_bp": antes.margen_defecto_bp,
            "iva_defecto": antes.iva_defecto,
            "precio_redondeo_centavos": antes.redondeo_centavos,
        }
        for clave, valor in cambios.items():
            if valor is None and clave != "margen_defecto_bp":
                continue
            await conn.execute(
                """
                insert into config (negocio_id, clave, valor) values ($1, $2, $3::jsonb)
                on conflict (coalesce(negocio_id, '00000000-0000-0000-0000-000000000000'), clave)
                do update set valor = excluded.valor, updated_at = now()
                """,
                ctx.negocio_id,
                clave,
                auditoria.a_json(valor),
            )
        fiscal = await productos.cargar_fiscal(conn, ctx.negocio_id)
        if cambios:
            await productos.recalcular(conn, ctx.negocio_id, None, fiscal)
            await auditoria.registrar(
                conn,
                usuario_id=ctx.usuario.id,
                rol=ctx.rol,
                accion="precios.config",
                entidad="config",
                entidad_id=ctx.negocio_id,
                negocio_id=ctx.negocio_id,
                antes={k: previos[k] for k in cambios},
                despues=cambios,
            )
    return PreciosConfigOut(
        margen_defecto_bp=fiscal.margen_defecto_bp,
        iva_defecto=fiscal.iva_defecto,
        precio_redondeo_centavos=fiscal.redondeo_centavos,
    )
