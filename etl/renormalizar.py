"""Pasa el normalizador (Doc 7) por TODO el catálogo ya cargado y recalcula la calidad.

    python -m etl.renormalizar            # simulacro: cuenta qué cambiaría, no escribe
    python -m etl.renormalizar --aplicar  # escribe

Hace falta una vez tras instalar la migración de calidad (el catálogo viejo tiene los
nombres crudos de las fuentes), y de nuevo cada vez que sube `NORMALIZADOR_VERSION` o se
edita un diccionario (`etl/comun/datos/`). Es idempotente: sobre lo ya normalizado no
cambia nada. Respeta los campos bloqueados, salvo el nombre cuando lo cargó una persona
fuera del estándar (Doc 10): ahí se limpia el nombre y se completan los campos vacíos con lo
que traía adentro (y se le deja un aviso a quien lo cargó, sin consecuencias). El dato
crudo de cada fuente está en `producto_fuentes`.
"""

import argparse
import asyncio
import json
from collections import Counter
from decimal import Decimal

from etl.comun.catalogo import _PEGAJOSOS, conectar, evaluar_fila
from etl.comun.normalizar import Entrada, clave, normalizar

_LOTE = 5000

_COLUMNAS = (
    "id, ean, nombre, marca, tamano_valor, tamano_unidad, imagen_url, presentacion, "
    "pack_cantidad, origen, campos_bloqueados, calidad, estado_calidad, calidad_motivos, "
    "normalizador_version"
)

# Autor de lo que cargó una persona: la última sugerencia aprobada, o el alta o corrección
# directa de la plataforma (en la auditoría; la aprobación de una sugerencia no cuenta: la
# hizo quien la aprobó, no quien la propuso).
_SQL_AUTORES = """
select distinct on (ean) ean, usuario_id from (
    select s.ean, s.usuario_id, s.resuelto_en as t from sugerencias_catalogo s
     where s.estado = 'aprobada' and s.ean = any ($1::text[])
    union all
    select a.entidad_id as ean, a.usuario_id, a.creado_en as t from auditoria a
     where a.entidad = 'catalogo_producto'
       and a.accion in ('catalogo_producto.crear', 'catalogo_producto.corregir')
       and (a.nota is null or a.nota not like 'sugerencia %')
       and a.entidad_id = any ($1::text[])
) x order by ean, t desc
"""

_SQL_AVISO = """
insert into avisos_catalogo (usuario_id, producto_id, ean, tipo, estandares, antes, despues)
values ($1, $2, $3, 'nombre_ajustado', $4, $5::jsonb, $6::jsonb)
"""

_CAMPOS_AVISO = (
    "nombre",
    "marca",
    "tamano_valor",
    "tamano_unidad",
    "pack_cantidad",
    "presentacion",
)

_SQL_ACTUALIZAR = """
update catalogo_global p
   set nombre = c.nombre, marca = c.marca, tamano_valor = c.tv, tamano_unidad = c.tu,
       pack_cantidad = c.pack, presentacion = c.pres, calidad = c.calidad,
       estado_calidad = c.estado, calidad_motivos = c.motivos, normalizador_version = c.version
  from renorm c
 where p.id = c.id
"""


def _humano(r) -> bool:
    """El nombre lo puso una persona (alta manual, o lo corrigió y lo bloqueó)."""
    return r["origen"] == "manual" or "nombre" in r["campos_bloqueados"]


def estandares_incumplidos(r, s, fila: dict) -> list[str]:
    """Ids (backend/app/services/estandares.py) de los estándares de carga que el nombre que
    puso una persona no cumplía, deducidos de qué le cambió el normalizador."""
    ids: list[str] = []
    antes, despues = r["nombre"], fila["nombre"]
    if s.marca and (
        not r["marca"] or (clave(s.marca) in clave(antes) and clave(s.marca) not in clave(despues))
    ):
        ids.append("marca")
    if (r["tamano_valor"] is None and fila["tamano_valor"] is not None) or (
        fila["pack_cantidad"] != r["pack_cantidad"]
    ):
        ids.append("tamano")
    if fila["presentacion"] != r["presentacion"]:
        ids.append("presentacion")
    palabras_antes = {clave(p) for p in antes.split()}
    if any(clave(p) not in palabras_antes for p in despues.split()):
        ids.append("abreviaturas")
    if antes != despues and [p.casefold() for p in antes.split()] == [
        p.casefold() for p in despues.split()
    ]:
        ids.append("mayusculas")
    if antes != despues and not ids:
        ids.append("limpieza")
    # la marca, el tamaño o el envase que salieron del nombre son el estándar "nombre"
    if antes != despues and {"marca", "tamano", "presentacion"} & set(ids):
        ids.insert(0, "nombre")
    return list(dict.fromkeys(ids))


def nueva_fila(r) -> dict:
    """Los valores que debería tener esta fila del catálogo.

    Un campo bloqueado no se toca. La excepción es el **nombre que puso una persona**: si no
    cumple el estándar (marca, tamaño o envase adentro, abreviaturas, mayúsculas) se limpia, y
    lo que traía adentro completa los campos que estaban vacíos (nunca pisa uno ya cargado)."""
    bloqueados = set(r["campos_bloqueados"])
    humano = _humano(r)
    tam = (Decimal(r["tamano_valor"]), r["tamano_unidad"]) if r["tamano_valor"] else None
    s = normalizar(Entrada(r["nombre"], r["marca"], tam, bool(r["imagen_url"]), r["presentacion"]))
    fila = dict(r)
    # Un nombre inservible de una persona no se reemplaza por basura: se deja y se revisa.
    if "nombre" not in bloqueados or (humano and "nombre_inservible" not in s.motivos):
        fila["nombre"] = s.nombre
    if "marca" not in bloqueados or r["marca"] is None:
        fila["marca"] = s.marca if "marca" not in bloqueados else (r["marca"] or s.marca)
    if "tamano" not in bloqueados or r["tamano_valor"] is None:
        fila["tamano_valor"] = s.tamano[0] if s.tamano else None
        fila["tamano_unidad"] = s.tamano[1] if s.tamano else None
    # Lo que vio al leer el dato crudo, más lo que la fila ya traía (la segunda pasada
    # sobre un nombre ya limpio no lo vuelve a ver).
    pegajosos = (frozenset(s.motivos) | frozenset(r["calidad_motivos"] or ())) & _PEGAJOSOS
    if "tamano" not in bloqueados or r["pack_cantidad"] is None:
        fila["pack_cantidad"] = s.pack_cantidad or r["pack_cantidad"]
    if "presentacion" not in bloqueados or r["presentacion"] is None:
        fila["presentacion"] = s.presentacion or r["presentacion"]
    calidad, estado, motivos, version = evaluar_fila(fila, pegajosos)
    fila.update(calidad=calidad, estado_calidad=estado, calidad_motivos=motivos)
    fila["normalizador_version"] = version
    fila["_estandares"] = estandares_incumplidos(r, s, fila) if humano else []
    return fila


def _clave(f) -> tuple:
    tv = None if f["tamano_valor"] is None else Decimal(f["tamano_valor"]).normalize()
    return (
        f["nombre"], f["marca"], tv, f["tamano_unidad"], f["pack_cantidad"], f["presentacion"],
        f["calidad"], f["estado_calidad"], list(f["calidad_motivos"]), f["normalizador_version"],
    )  # fmt: skip


def _json(v):
    return str(v) if isinstance(v, Decimal) else v


async def _avisar(conn, humanos: dict) -> int:
    """Deja un aviso (con el porqué) a quien cargó lo que el normalizador acaba de ajustar.
    Es informativo. Sin autor conocido no hay a quién avisarle."""
    if not humanos:
        return 0
    autores = {r["ean"]: r["usuario_id"] for r in await conn.fetch(_SQL_AUTORES, list(humanos))}
    n = 0
    for ean, (viejo, nuevo) in humanos.items():
        if ean not in autores:
            continue
        antes = {k: _json(viejo[k]) for k in _CAMPOS_AVISO}
        despues = {k: _json(nuevo[k]) for k in _CAMPOS_AVISO}
        await conn.execute(
            _SQL_AVISO,
            autores[ean],
            viejo["id"],
            ean,
            nuevo["_estandares"],
            json.dumps(antes, ensure_ascii=False),
            json.dumps(despues, ensure_ascii=False),
        )
        n += 1
    return n


async def renormalizar(aplicar: bool) -> str:
    lectura, escritura = await conectar(), await conectar()
    total = cambian = avisados = 0
    estados: Counter = Counter()
    try:
        await escritura.execute(
            "create temp table renorm (id uuid primary key, nombre text, marca text, tv numeric,"
            " tu text, pack integer, pres text, calidad smallint, estado text, motivos text[],"
            " version integer)"
        )
        async with lectura.transaction():
            cur = await lectura.cursor(f"select {_COLUMNAS} from catalogo_global")
            while lote := await cur.fetch(_LOTE):
                cambios = []
                humanos: dict = {}  # ean -> (fila vieja, fila nueva) de lo que cargó una persona
                for r in lote:
                    total += 1
                    n = nueva_fila(r)
                    estados[n["estado_calidad"]] += 1
                    if _clave(n) != _clave(r):
                        if n["_estandares"]:
                            humanos[r["ean"]] = (r, n)
                        cambios.append(
                            (
                                r["id"], n["nombre"], n["marca"], n["tamano_valor"],
                                n["tamano_unidad"], n["pack_cantidad"], n["presentacion"],
                                n["calidad"], n["estado_calidad"], n["calidad_motivos"],
                                n["normalizador_version"],
                            )
                        )  # fmt: skip
                cambian += len(cambios)
                if aplicar and cambios:
                    async with escritura.transaction():
                        # el nombre que puso una persona está bloqueado: se habilita el cambio
                        await escritura.execute("select set_config('app.catalogo_write','on',true)")
                        await escritura.copy_records_to_table("renorm", records=cambios)
                        await escritura.execute(_SQL_ACTUALIZAR)
                        await escritura.execute("truncate renorm")
                        avisados += await _avisar(escritura, humanos)
    finally:
        await lectura.close()
        await escritura.close()
    out = [
        f"Productos: {total}",
        f"{'Actualizados' if aplicar else 'Cambiarían'}: {cambian}",
        f"Avisos a quien cargó a mano: {avisados if aplicar else '(solo al aplicar)'}",
        "Estados: "
        + ", ".join(f"{e} {estados[e]}" for e in ("completo", "parcial", "dudoso", "descartado")),
    ]
    if not aplicar:
        out.append("(simulacro: no se escribió nada; agregá --aplicar)")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--aplicar", action="store_true", help="escribir los cambios")
    args = ap.parse_args()
    print(asyncio.run(renormalizar(args.aplicar)))


if __name__ == "__main__":
    main()
