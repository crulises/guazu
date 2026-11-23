"""Capa mínima compartida por todos los ETL: conexión y fusión al catálogo canónico.

Cada ETL (uno por fuente) transforma su formato a filas `Producto`, y acá se
fusionan en bloque con SQL (staging temporal + sentencias por conjuntos), que es
lo que aguanta millones de filas. Idempotente: correrlo de nuevo no cambia nada.

Reglas de fusión por EAN, con `fuente` = la fuente que se está cargando:
- Siempre se guarda el dato crudo en `producto_fuentes` (ean, fuente). Lo que llega al
  catálogo ya pasó por el normalizador (Doc 7): nombre limpio, marca canónica (los
  placeholders como «S/d» son NULL, no marca), tamaño y presentación extraídos del nombre.
- Tras fusionar, se recalcula la calidad (puntaje, estado, motivos) de cada EAN del lote
  sobre la fila FINAL, respetando los campos bloqueados.
- EAN nuevo: se crea en `catalogo_global` con `origen = fuente`.
- El catálogo ya viene de esta misma fuente: se refresca (salvo campos bloqueados).
- El catálogo viene de otra fuente: si la que se carga tiene más prioridad (config
  `catalogo_prioridad_fuentes`, por defecto manual > sepa > off) pisa los campos no
  bloqueados; si no, solo completa los vacíos. Lo que discrepa de verdad queda en
  `conflictos_catalogo`.
"""

import os
from collections import Counter
from dataclasses import dataclass, field, replace
from decimal import Decimal

import asyncpg

from etl.comun.normalizar import NORMALIZADOR_VERSION, Entrada, normalizar, puntuar

DATABASE_URL_LOCAL = "postgresql://postgres:postgres@127.0.0.1:55322/postgres"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DATABASE_URL_LOCAL)


@dataclass
class Producto:
    ean: str
    nombre: str
    marca: str | None = None
    tamano_valor: Decimal | None = None
    tamano_unidad: str | None = None
    imagen_url: str | None = None
    datos: str = "{}"  # JSON crudo de la fuente, para `producto_fuentes`
    pack_cantidad: int | None = None  # los llena el normalizador, no la fuente
    presentacion: str | None = None


@dataclass
class Reporte:
    leidas: int = 0
    descartadas: Counter = field(default_factory=Counter)
    sin_tamano: int = 0
    fuente_nuevas: int = 0
    fuente_actualizadas: int = 0
    catalogo_nuevos: int = 0
    catalogo_actualizados: int = 0
    conflictos_nuevos: int = 0

    @property
    def total_descartadas(self) -> int:
        return sum(self.descartadas.values())

    def texto(self) -> str:
        lineas = [
            f"Filas leídas:                  {self.leidas}",
            f"Productos nuevos en catálogo:  {self.catalogo_nuevos}",
            f"Productos del catálogo actualizados: {self.catalogo_actualizados}",
            f"Nuevos en producto_fuentes:    {self.fuente_nuevas}",
            f"Actualizados en producto_fuentes: {self.fuente_actualizadas}",
            f"Cargados sin tamaño usable:    {self.sin_tamano}",
            f"Conflictos nuevos a revisar:   {self.conflictos_nuevos}",
            f"Descartadas:                   {self.total_descartadas}",
        ]
        for motivo, n in self.descartadas.most_common():
            lineas.append(f"    {motivo}: {n}")
        return "\n".join(lineas)


async def conectar() -> asyncpg.Connection:
    return await asyncpg.connect(database_url())


_CREAR_STAGING = """
create temp table if not exists etl_stg (
    ean text primary key, nombre text not null, marca text,
    tamano_valor numeric, tamano_unidad text, imagen_url text, datos jsonb not null,
    pack_cantidad integer, presentacion text
) on commit delete rows
"""

_COLUMNAS = [
    "ean", "nombre", "marca", "tamano_valor", "tamano_unidad", "imagen_url", "datos",
    "pack_cantidad", "presentacion",
]  # fmt: skip

_CREAR_CALIDAD = """
create temp table if not exists etl_cal (
    ean text primary key, calidad smallint not null, estado text not null,
    motivos text[] not null, version integer not null
) on commit delete rows
"""

# Columnas con las que se evalúa la calidad de la fila FINAL del catálogo.
_SQL_FILAS = """
select ean, nombre, marca, tamano_valor, tamano_unidad, imagen_url, presentacion,
       campos_bloqueados, calidad_motivos, origen
  from catalogo_global where ean = any ($1::text[])
"""

_SQL_CALIDAD = """
with upd as (
    update catalogo_global p
       set calidad = c.calidad, estado_calidad = c.estado, calidad_motivos = c.motivos,
           normalizador_version = c.version
      from etl_cal c
     where p.ean = c.ean
       and (p.calidad, p.estado_calidad, p.calidad_motivos, p.normalizador_version)
           is distinct from (c.calidad, c.estado, c.motivos, c.version)
    returning 1
)
select count(*) from upd
"""

# 1. Dato crudo por fuente.
_SQL_FUENTES = """
with up as (
    insert into producto_fuentes (ean, fuente, datos)
    select ean, $1::text, datos from etl_stg
    on conflict (ean, fuente) do update
        set datos = excluded.datos, cargado_en = now()
        where producto_fuentes.datos is distinct from excluded.datos
    returning (xmax = 0) as nueva
)
select count(*) filter (where nueva), count(*) filter (where not nueva) from up
"""

# 2. EAN que el catálogo no conoce.
_SQL_NUEVOS = """
with ins as (
    insert into catalogo_global
        (ean, nombre, marca, tamano_valor, tamano_unidad, imagen_url, origen,
         pack_cantidad, presentacion)
    select ean, nombre, marca, tamano_valor, tamano_unidad, imagen_url, $1::text,
           pack_cantidad, presentacion from etl_stg
    on conflict (ean) do nothing
    returning 1
)
select count(*) from ins
"""

# 3. EAN que ya estaban: refrescar / completar / pisar según prioridad.
#    `propio` = el catálogo ya venía de esta fuente; `gana` = esta fuente tiene más
#    prioridad que la del catálogo (y el catálogo no es manual).
_SQL_EXISTENTES = """
with cand as (
    select p.id, p.origen, p.campos_bloqueados as bl,
           p.nombre as n0, p.marca as m0, p.tamano_valor as tv0, p.tamano_unidad as tu0,
           p.imagen_url as i0, p.pack_cantidad as pk0, p.presentacion as pr0,
           s.pack_cantidad as pk1, s.presentacion as pr1, s.nombre as n1, s.marca as m1,
           s.tamano_valor as tv1, s.tamano_unidad as tu1, s.imagen_url as i1,
           (p.origen = $1::text) as propio,
           (p.origen <> $1 and prioridad_fuente($1::text) < prioridad_fuente(p.origen)) as gana
      from catalogo_global p join etl_stg s using (ean)
),
nuevo as (
    select id, origen, propio, gana,
        case when 'nombre' = any (bl) then n0
             when propio or gana then n1 else n0 end as n,
        case when 'marca' = any (bl) then m0
             when (propio or gana) and m1 is not null then m1
             else coalesce(m0, m1) end as m,
        case when 'tamano' = any (bl) then tv0
             when (propio or gana) and tv1 is not null then tv1
             else coalesce(tv0, tv1) end as tv,
        case when 'tamano' = any (bl) then tu0
             when (propio or gana) and tu1 is not null then tu1
             else coalesce(tu0, tu1) end as tu,
        case when (propio or gana) and i1 is not null then i1
             else coalesce(i0, i1) end as i,
        case when 'tamano' = any (bl) then pk0
             when (propio or gana) and pk1 is not null then pk1
             else coalesce(pk0, pk1) end as pk,
        case when 'presentacion' = any (bl) then pr0
             when (propio or gana) and pr1 is not null then pr1
             else coalesce(pr0, pr1) end as pr,
        case when gana then $1::text else origen end as o,
        n0, m0, tv0, tu0, i0, origen as o0, pk0, pr0
      from cand
),
upd as (
    update catalogo_global p
       set nombre = nuevo.n, marca = nuevo.m, tamano_valor = nuevo.tv,
           tamano_unidad = nuevo.tu, imagen_url = nuevo.i, origen = nuevo.o,
           pack_cantidad = nuevo.pk, presentacion = nuevo.pr
      from nuevo
     where p.id = nuevo.id
       and (nuevo.n, nuevo.m, nuevo.tv, nuevo.tu, nuevo.i, nuevo.o, nuevo.pk, nuevo.pr)
           is distinct from
           (nuevo.n0, nuevo.m0, nuevo.tv0, nuevo.tu0, nuevo.i0, nuevo.o0, nuevo.pk0, nuevo.pr0)
    returning 1
)
select count(*) from upd
"""

# 4. Discrepancias reales con un catálogo que NO viene de esta fuente (tras el paso 3,
#    si esta fuente ganó, el catálogo ya es de ella y no hay nada que comparar).
#    Entre fuentes automáticas el nombre y la marca los resuelve la prioridad (sus
#    textos siempre difieren: «ACEITE OLIVA NUCETE BOT 250 CC» vs «Aceite de oliva»);
#    contra lo cargado a mano sí se avisa. El tamaño es un dato duro: se avisa si
#    discrepan dentro de la misma familia (masa, volumen, unidades); «50 u» contra
#    «75 g» no se compara.
_SQL_CONFLICTOS = """
with par as (
    select p.ean, p.origen, p.campos_bloqueados as bl,
           p.nombre as n0, p.marca as m0, p.tamano_valor as tv0, p.tamano_unidad as tu0,
           s.nombre as n1, s.marca as m1, s.tamano_valor as tv1, s.tamano_unidad as tu1
      from catalogo_global p join etl_stg s using (ean)
     where p.origen <> $1::text
),
cand as (
    select ean, 'nombre' as campo, n0 as va, origen as fa, n1 as vb
      from par where origen = 'manual' and not 'nombre' = any (bl)
                 and not textos_similares(n0, n1)
    union all
    select ean, 'marca', m0, origen, m1
      from par where origen = 'manual' and not 'marca' = any (bl)
                 and m0 is not null and m1 is not null and not textos_similares(m0, m1)
    union all
    select ean, 'tamano', tv0::text || ' ' || tu0, origen, tv1::text || ' ' || tu1
      from par where not 'tamano' = any (bl) and tv0 is not null and tv1 is not null
                 and tamano_familia(tu0) = tamano_familia(tu1)
                 and not tamanos_equivalentes(tv0, tu0, tv1, tu1)
),
ins as (
    insert into conflictos_catalogo (ean, campo, valor_a, fuente_a, valor_b, fuente_b)
    select ean, campo, va, fa, vb, $1::text from cand
    on conflict do nothing
    returning 1
)
select count(*) from ins
"""


# Motivos que se detectan comparando el dato crudo con el nombre: al normalizar de nuevo la
# fila ya limpia no se vuelven a ver, así que viajan con la fila (mientras el nombre sea el
# mismo que los generó).
_PEGAJOSOS = {"tamano_en_conflicto", "abreviado", "marca_en_nombre", "tamano_ambiguo"}


def normalizar_producto(p: Producto) -> tuple[Producto, frozenset[str]]:
    """Pasa lo que dice la fuente por el normalizador. El dato crudo sigue en `datos`.
    -> (producto normalizado, motivos pegajosos que detectó)."""
    tam = (p.tamano_valor, p.tamano_unidad) if p.tamano_valor and p.tamano_unidad else None
    s = normalizar(Entrada(p.nombre, p.marca, tam, bool(p.imagen_url)))
    nuevo = replace(
        p,
        nombre=s.nombre,
        marca=s.marca,
        tamano_valor=s.tamano[0] if s.tamano else None,
        tamano_unidad=s.tamano[1] if s.tamano else None,
        pack_cantidad=s.pack_cantidad,
        presentacion=s.presentacion,
    )
    return nuevo, frozenset(s.motivos) & _PEGAJOSOS


# Motivos que una persona resuelve al corregir (y bloquear) ese campo: dejan de restar.
_RESUELTOS_POR = {
    "nombre": {"abreviado", "marca_en_nombre", "tamano_en_conflicto", "nombre_corto"},
    "marca": {"marca_en_nombre", "fabricante_como_marca"},
    "tamano": {"tamano_en_conflicto"},
    "presentacion": set(),
}
_ESTRUCTURALES = {"sin_marca", "sin_tamano", "nombre_corto", "muy_incompleto"}


def evaluar_fila(r, pegajosos: frozenset[str] = frozenset()) -> tuple[int, str, list[str], int]:
    """(puntaje, estado, motivos, versión) de una fila del catálogo, tal como está.
    `pegajosos`: motivos que detectó el normalizador al leer el dato crudo.
    Lo que una persona corrigió y bloqueó no se vuelve a juzgar."""
    tam = (r["tamano_valor"], r["tamano_unidad"]) if r["tamano_valor"] is not None else None
    bloqueados = set(r["campos_bloqueados"])
    s = normalizar(Entrada(r["nombre"], r["marca"], tam, bool(r["imagen_url"]), r["presentacion"]))
    if "nombre_inservible" in s.motivos and "nombre" not in bloqueados:
        return s.calidad, s.estado, list(s.motivos), NORMALIZADOR_VERSION
    resueltos = set().union(*(_RESUELTOS_POR[c] for c in bloqueados)) if bloqueados else set()
    motivos = [
        m
        for m in (*s.motivos, *pegajosos)
        if m not in _ESTRUCTURALES | resueltos | {"nombre_inservible"}
    ]
    # Lo que una persona cargó o corrigió no se descarta (Doc 7 §5.1).
    revisado = bool(bloqueados) or r["origen"] == "manual"
    calidad, estado, motivos_finales = puntuar(
        r["nombre"], r["marca"], tam, bool(r["imagen_url"]), r["presentacion"], motivos, revisado
    )
    return calidad, estado, list(motivos_finales), NORMALIZADOR_VERSION


def _vigentes(r, pegajoso: tuple[str, frozenset[str]] | None) -> frozenset[str]:
    """Si el nombre final es el que acaba de normalizarse, valen sus motivos; si ganó otro
    dato (otra fuente, o lo bloqueado), se conservan los que la fila ya tenía."""
    if pegajoso and pegajoso[0] == r["nombre"]:
        return pegajoso[1]
    return frozenset(r["calidad_motivos"] or ()) & _PEGAJOSOS


async def recalcular_calidad(
    conn: asyncpg.Connection,
    eans: list[str],
    pegajosos: dict[str, tuple[str, frozenset[str]]] | None = None,
) -> int:
    """Recalcula la calidad de estos EAN sobre su fila final (dentro de la transacción).
    `pegajosos[ean] = (nombre normalizado, motivos)`: valen si el nombre final es ese."""
    pegajosos = pegajosos or {}
    filas = await conn.fetch(_SQL_FILAS, eans)
    await conn.execute(_CREAR_CALIDAD)
    await conn.copy_records_to_table(
        "etl_cal",
        records=[
            (r["ean"], *evaluar_fila(r, _vigentes(r, pegajosos.get(r["ean"])))) for r in filas
        ],
        columns=["ean", "calidad", "estado", "motivos", "version"],
    )
    n = await conn.fetchval(_SQL_CALIDAD)
    await conn.execute("truncate etl_cal")
    return n


async def fusionar_lote(
    conn: asyncpg.Connection, fuente: str, productos: list[Producto], reporte: Reporte
) -> None:
    """Fusiona un lote (una transacción). EAN repetidos en el lote: gana el último."""
    normalizados = {p.ean: normalizar_producto(p) for p in productos}
    unicos = {ean: n[0] for ean, n in normalizados.items()}
    pegajosos = {ean: (n[0].nombre, n[1]) for ean, n in normalizados.items()}
    if not unicos:
        return
    async with conn.transaction():
        await conn.execute(_CREAR_STAGING)
        await conn.copy_records_to_table(
            "etl_stg",
            records=[
                (
                    p.ean,
                    p.nombre,
                    p.marca,
                    p.tamano_valor,
                    p.tamano_unidad,
                    p.imagen_url,
                    p.datos,
                    p.pack_cantidad,
                    p.presentacion,
                )
                for p in unicos.values()
            ],
            columns=_COLUMNAS,
        )
        nuevas, actualizadas = await conn.fetchrow(_SQL_FUENTES, fuente)
        reporte.fuente_nuevas += nuevas
        reporte.fuente_actualizadas += actualizadas
        reporte.catalogo_nuevos += await conn.fetchval(_SQL_NUEVOS, fuente)
        reporte.catalogo_actualizados += await conn.fetchval(_SQL_EXISTENTES, fuente)
        reporte.conflictos_nuevos += await conn.fetchval(_SQL_CONFLICTOS, fuente)
        await recalcular_calidad(conn, list(unicos), pegajosos)
        await conn.execute("truncate etl_stg")
