"""Medidor de calidad del catálogo (Doc 7): corre el normalizador sobre `catalogo_global`
SIN escribir nada y muestra cómo quedaría (antes -> después).

    python -m etl.calidad [--muestra N] [--estado dudoso] [--semilla S]
"""

import argparse
import asyncio
import random
from collections import Counter
from decimal import Decimal

from etl.comun.catalogo import conectar
from etl.comun.normalizar import Entrada, Salida, normalizar


async def medir(muestra: int, estado: str | None) -> str:
    conn = await conectar()
    total = 0
    estados: Counter = Counter()
    motivos: Counter = Counter()
    antes: Counter = Counter()
    despues: Counter = Counter()
    marcas_antes: set[str] = set()
    marcas_despues: set[str] = set()
    ejemplos: list[tuple[str, str | None, Salida]] = []
    rng = random.Random(7)
    try:
        async with conn.transaction():
            cur = conn.cursor(
                "select nombre, marca, tamano_valor, tamano_unidad, imagen_url from catalogo_global"
            )
            async for r in cur:
                total += 1
                tam = (
                    (Decimal(r["tamano_valor"]), r["tamano_unidad"]) if r["tamano_valor"] else None
                )
                s = normalizar(Entrada(r["nombre"], r["marca"], tam, bool(r["imagen_url"])))
                estados[s.estado] += 1
                motivos.update(s.motivos)
                antes["sin_tamano"] += tam is None
                despues["sin_tamano"] += s.tamano is None
                antes["sin_marca"] += not r["marca"]
                despues["sin_marca"] += s.marca is None
                if r["marca"]:
                    marcas_antes.add(r["marca"])
                if s.marca:
                    marcas_despues.add(s.marca)
                if (estado is None or s.estado == estado) and (r["nombre"] != s.nombre):
                    if len(ejemplos) < muestra:
                        ejemplos.append((r["nombre"], r["marca"], s))
                    elif rng.random() < muestra / total:
                        ejemplos[rng.randrange(muestra)] = (r["nombre"], r["marca"], s)
    finally:
        await conn.close()

    def pct(n: int) -> str:
        return f"{n:>7}  {100 * n / max(total, 1):5.1f} %"

    out = [f"Productos: {total}", "", "Estado (según el normalizador):"]
    out += [f"  {e:<11}{pct(estados[e])}" for e in ("completo", "parcial", "dudoso", "descartado")]
    out += ["", "                antes     después"]
    out.append(f"  sin tamaño   {antes['sin_tamano']:>7}  {despues['sin_tamano']:>7}")
    out.append(f"  sin marca    {antes['sin_marca']:>7}  {despues['sin_marca']:>7}")
    out.append(f"  marcas dist. {len(marcas_antes):>7}  {len(marcas_despues):>7}")
    out += ["", "Motivos:"] + [f"  {m:<26}{pct(n)}" for m, n in motivos.most_common()]
    if ejemplos:
        out += ["", "Ejemplos (antes -> después):"]
        for nombre, marca, s in ejemplos:
            out.append(
                f"  {nombre!r} [{marca}]\n    -> {s.nombre!r} [{s.marca}] {s.tamano} {s.estado}"
            )
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--muestra", type=int, default=0, help="cuántos ejemplos mostrar")
    ap.add_argument("--estado", choices=["completo", "parcial", "dudoso", "descartado"])
    args = ap.parse_args()
    print(asyncio.run(medir(args.muestra, args.estado)))


if __name__ == "__main__":
    main()
