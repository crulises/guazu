"""Capa minima compartida por todos los ETL: conexion y fusion al catalogo global.

Cada ETL (uno por fuente) transforma su formato a filas `Producto`, y aca se fusionan en bloque
con SQL (staging temporal y sentencias por conjuntos), que es lo que aguanta millones de filas.
Idempotente: correrlo de nuevo no cambia nada.

Reglas de fusion por EAN, con `fuente` = la fuente que se esta cargando:
- Siempre se guarda el dato crudo en `producto_fuentes` (ean, fuente).
- EAN nuevo: se crea en `catalogo_global` con `origen = fuente`.
- El catalogo ya viene de esta misma fuente: se refresca (salvo campos bloqueados).
- El catalogo viene de otra fuente: si la que se carga tiene mas prioridad (config global
  `catalogo_prioridad_fuentes`, por defecto manual > sepa > off) pisa los campos no
  bloqueados; si no, solo completa los vacios. Lo que discrepa de verdad queda en
  `conflictos_catalogo`.

El normalizador de nombres, marcas y tamanos (Doc 7, issue de calidad) se enchufa en
`fusionar_lote` antes de fusionar; este modulo ya deja ese lugar.
"""

import os
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal

import asyncpg

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
            f"Filas leidas:                  {self.leidas}",
            f"Productos nuevos en catalogo:  {self.catalogo_nuevos}",
            f"Productos del catalogo actualizados: {self.catalogo_actualizados}",
            f"Nuevos en producto_fuentes:    {self.fuente_nuevas}",
            f"Actualizados en producto_fuentes: {self.fuente_actualizadas}",
            f"Cargados sin tamano usable:    {self.sin_tamano}",
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
    tamano_valor numeric, tamano_unidad text, imagen_url text, datos jsonb not null
) on commit delete rows
"""

_COLUMNAS = [
    "ean",
    "nombre",
    "marca",
    "tamano_valor",
    "tamano_unidad",
    "imagen_url",
    "datos",
]

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

# 2. EAN que el catalogo no conoce.
_SQL_NUEVOS = """
with ins as (
    insert into catalogo_global
        (ean, nombre, marca, tamano_valor, tamano_unidad, imagen_url, origen)
    select ean, nombre, marca, tamano_valor, tamano_unidad, imagen_url, $1::text from etl_stg
    on conflict (ean) do nothing
    returning 1
)
select count(*) from ins
"""

# 3. EAN que ya estaban: refrescar / completar / pisar segun prioridad.
#    `propio` = el catalogo ya venia de esta fuente; `gana` = esta fuente tiene mas
#    prioridad que la del catalogo (y el catalogo no es manual).
_SQL_EXISTENTES = """
with cand as (
    select p.id, p.origen, p.campos_bloqueados as bl,
           p.nombre as n0, p.marca as m0, p.tamano_valor as tv0, p.tamano_unidad as tu0,
           p.imagen_url as i0,
           s.nombre as n1, s.marca as m1, s.tamano_valor as tv1, s.tamano_unidad as tu1,
           s.imagen_url as i1,
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
        case when gana then $1::text else origen end as o,
        n0, m0, tv0, tu0, i0, origen as o0
      from cand
),
upd as (
    update catalogo_global p
       set nombre = nuevo.n, marca = nuevo.m, tamano_valor = nuevo.tv,
           tamano_unidad = nuevo.tu, imagen_url = nuevo.i, origen = nuevo.o
      from nuevo
     where p.id = nuevo.id
       and (nuevo.n, nuevo.m, nuevo.tv, nuevo.tu, nuevo.i, nuevo.o)
           is distinct from
           (nuevo.n0, nuevo.m0, nuevo.tv0, nuevo.tu0, nuevo.i0, nuevo.o0)
    returning 1
)
select count(*) from upd
"""

# 4. Discrepancias reales con un catalogo que NO viene de esta fuente (tras el paso 3, si esta
#    fuente gano, el catalogo ya es de ella y no hay nada que comparar).
#    Entre fuentes automaticas el nombre y la marca los resuelve la prioridad (sus textos
#    siempre difieren: "ACEITE OLIVA NUCETE BOT 250 CC" vs "Aceite de oliva"); contra lo
#    cargado a mano si se avisa. El tamano es un dato duro: se avisa si discrepan dentro de la
#    misma familia (masa, volumen, unidades); "50 u" contra "75 g" no se compara.
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


async def fusionar_lote(
    conn: asyncpg.Connection, fuente: str, productos: list[Producto], reporte: Reporte
) -> None:
    """Fusiona un lote (una transaccion). EAN repetidos en el lote: gana el ultimo."""
    unicos = {p.ean: p for p in productos}
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
        await conn.execute("truncate etl_stg")
