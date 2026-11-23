"""Pasa el normalizador (Doc 7) por TODO el catálogo ya cargado y recalcula la calidad.

    python -m etl.renormalizar            # simulacro: cuenta qué cambiaría, no escribe
    python -m etl.renormalizar --aplicar  # escribe

Hace falta una vez tras instalar la migración de calidad (el catálogo viejo tiene los
nombres crudos de las fuentes), y de nuevo cada vez que sube `NORMALIZADOR_VERSION` o se
edita un diccionario (`etl/comun/datos/`). Es idempotente: sobre lo ya normalizado no
cambia nada. Respeta los campos bloqueados, salvo el nombre cuando lo cargó una persona
fuera del estándar (Doc 10): ahí se limpia el nombre y se completan los campos vacíos con lo
que traía adentro (el aviso a quien lo cargó llega con el hito de estándares). El dato
crudo de cada fuente está en `producto_fuentes`.
"""

import argparse
import asyncio
from collections import Counter
from decimal import Decimal

from etl.comun.catalogo import _PEGAJOSOS, conectar, evaluar_fila
from etl.comun.normalizar import Entrada, normalizar

_LOTE = 5000

_COLUMNAS = (
    "id, ean, nombre, marca, tamano_valor, tamano_unidad, imagen_url, presentacion, "
    "pack_cantidad, origen, campos_bloqueados, calidad, estado_calidad, calidad_motivos, "
    "normalizador_version"
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
    return fila


def _clave(f) -> tuple:
    tv = None if f["tamano_valor"] is None else Decimal(f["tamano_valor"]).normalize()
    return (
        f["nombre"], f["marca"], tv, f["tamano_unidad"], f["pack_cantidad"], f["presentacion"],
        f["calidad"], f["estado_calidad"], list(f["calidad_motivos"]), f["normalizador_version"],
    )  # fmt: skip


async def renormalizar(aplicar: bool) -> str:
    lectura, escritura = await conectar(), await conectar()
    total = cambian = 0
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
                for r in lote:
                    total += 1
                    n = nueva_fila(r)
                    estados[n["estado_calidad"]] += 1
                    if _clave(n) != _clave(r):
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
    finally:
        await lectura.close()
        await escritura.close()
    out = [
        f"Productos: {total}",
        f"{'Actualizados' if aplicar else 'Cambiarían'}: {cambian}",
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
