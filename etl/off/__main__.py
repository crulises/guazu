"""ETL de Open Food Facts (todo el mundo) -> catálogo global.

Lee el volcado CSV (`en.openfoodfacts.org.products.csv.gz`, separado por tabs) en
streaming, valida el EAN, normaliza el tamaño y fusiona por lotes.

    python -m etl.off ARCHIVO [--limite N] [--lote N]
"""

import argparse
import asyncio
import csv
import gzip
import io
import json
import sys
from collections.abc import Iterator
from pathlib import Path

from etl.comun.catalogo import Producto, Reporte, conectar, fusionar_lote
from etl.comun.ean import normalizar_ean
from etl.comun.tamano import parsear_tamano

FUENTE = "off"
COLUMNAS = (
    "code",
    "product_name",
    "generic_name",
    "brands",
    "quantity",
    "image_url",
    "countries_tags",
    "last_modified_t",
)
MAX_NOMBRE = 200
MAX_MARCA = 100


def abrir(ruta: Path) -> io.TextIOBase:
    if ruta.suffix == ".gz":
        crudo = gzip.open(ruta, "rb")
        return io.TextIOWrapper(crudo, encoding="utf-8", errors="replace", newline="")
    return open(ruta, encoding="utf-8", errors="replace", newline="")


def filas(archivo: io.TextIOBase) -> Iterator[dict[str, str]]:
    """Filas del CSV como dict (solo las columnas que usamos). Tolera un .gz truncado
    (p. ej. la muestra bajada por rango): termina sin error al llegar al corte."""
    csv.field_size_limit(10**9)
    # El volcado completo trae caracteres NUL sueltos, que el módulo csv no acepta.
    lineas = (linea.replace("\0", "") for linea in archivo)
    lector = csv.reader(lineas, delimiter="\t", quoting=csv.QUOTE_NONE)
    cabecera = next(lector)
    idx = {c: cabecera.index(c) for c in COLUMNAS if c in cabecera}
    if "code" not in idx:
        raise SystemExit("El archivo no parece un volcado CSV de OFF (falta la columna `code`).")
    try:
        for fila in lector:
            if len(fila) < len(cabecera):  # fila cortada (fin de un archivo truncado)
                continue
            yield {c: fila[i] for c, i in idx.items()}
    except (EOFError, gzip.BadGzipFile):
        return


def transformar(
    fila: dict[str, str], reporte: Reporte, paises: frozenset[str] | None = None
) -> Producto | None:
    """`paises`: si se da, solo pasan los productos vendidos en alguno de esos países
    (tags de OFF, p. ej. `en:argentina`); el resto se cuenta como `fuera_de_paises`."""
    if paises is not None:
        vendido_en = set((fila.get("countries_tags") or "").split(","))
        if not vendido_en & paises:
            reporte.descartadas["fuera_de_paises"] += 1
            return None
    ean, motivo = normalizar_ean(fila.get("code"))
    if motivo:
        reporte.descartadas[motivo] += 1
        return None
    nombre = (fila.get("product_name") or fila.get("generic_name") or "").strip()
    if len(nombre) < 2:
        reporte.descartadas["sin_nombre"] += 1
        return None
    marca = (fila.get("brands") or "").split(",")[0].strip() or None
    tamano = parsear_tamano(fila.get("quantity"))
    if tamano is None:
        reporte.sin_tamano += 1
    paises = [p for p in (fila.get("countries_tags") or "").split(",") if p]
    datos = {
        "nombre": nombre,
        "marca": (fila.get("brands") or "").strip() or None,
        "quantity": (fila.get("quantity") or "").strip() or None,
        "paises": paises,
        "imagen_url": (fila.get("image_url") or "").strip() or None,
    }
    if fila.get("last_modified_t"):
        datos["modificado_t"] = fila["last_modified_t"]
    return Producto(
        ean=ean,
        nombre=nombre[:MAX_NOMBRE],
        marca=marca[:MAX_MARCA] if marca else None,
        tamano_valor=tamano[0] if tamano else None,
        tamano_unidad=tamano[1] if tamano else None,
        imagen_url=(fila.get("image_url") or "").strip() or None,
        datos=json.dumps(datos, ensure_ascii=False),
    )


async def cargar(
    ruta: Path,
    lote: int = 20_000,
    limite: int | None = None,
    paises: frozenset[str] | None = None,
) -> Reporte:
    reporte = Reporte()
    conn = await conectar()
    try:
        buffer: list[Producto] = []
        with abrir(ruta) as archivo:
            for fila in filas(archivo):
                if limite is not None and reporte.leidas >= limite:
                    break
                reporte.leidas += 1
                producto = transformar(fila, reporte, paises)
                if producto:
                    buffer.append(producto)
                if len(buffer) >= lote:
                    await fusionar_lote(conn, FUENTE, buffer, reporte)
                    buffer = []
                    print(f"  ... {reporte.leidas} filas", file=sys.stderr, flush=True)
        await fusionar_lote(conn, FUENTE, buffer, reporte)
    finally:
        await conn.close()
    return reporte


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("archivo", type=Path, help="volcado CSV de OFF (.csv o .csv.gz)")
    ap.add_argument("--limite", type=int, help="procesar solo las primeras N filas")
    ap.add_argument("--lote", type=int, default=20_000)
    ap.add_argument(
        "--paises",
        default="",
        help="solo productos vendidos en estos países (tags de OFF, separados por coma); "
        "vacío = todo el mundo",
    )
    args = ap.parse_args()
    if not args.archivo.exists():
        raise SystemExit(
            f"No existe {args.archivo}. Ver `make etl-off-muestra` / `make etl-off-descargar`."
        )
    paises = frozenset(p.strip() for p in args.paises.split(",") if p.strip()) or None
    print(asyncio.run(cargar(args.archivo, args.lote, args.limite, paises)).texto())


if __name__ == "__main__":
    main()
