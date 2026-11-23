"""ETL de SEPA / Precios Claros (Argentina) -> catálogo global.

El zip diario de SEPA es un zip de zips (uno por comercio) con `comercio.csv`,
`sucursales.csv` y `productos.csv` (separador `|`). Acá solo se usa `productos.csv`
como fuente de catálogo: EAN, descripción, marca y presentación. Los PRECIOS de SEPA
no se cargan (los precios los define cada negocio).

Las cadenas repiten el mismo EAN (millones de filas para ~80 mil EAN): se agrupan por
EAN y se queda la variante más frecuente de nombre, marca y tamaño.

    python -m etl.sepa ARCHIVO.zip [ARCHIVO2.zip ...]

Datos: Secretaría de Comercio / Precios Claros (SEPA), CC BY 4.0.
"""

import argparse
import asyncio
import csv
import io
import json
import sys
import zipfile
from collections import Counter
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

from etl.comun.catalogo import Producto, Reporte, conectar, fusionar_lote
from etl.comun.ean import normalizar_ean
from etl.comun.tamano import parsear_tamano

FUENTE = "sepa"
MAX_NOMBRE = 200
MAX_MARCA = 100
# SEPA escribe el nombre en MAYÚSCULAS. Estas siglas se dejan como están al pasar a
# «Título» (las demás palabras quedan en minúscula salvo la primera letra).
_SIGLAS = {"ml", "cc", "kg", "gr", "lt", "sa", "srl", "pet", "uht", "sin", "tacc"}


def _filas_csv(binario: io.BufferedIOBase) -> Iterator[dict[str, str]]:
    """Filas de un CSV con `|`: tolera BOM (utf-8-sig) y caracteres NUL."""
    csv.field_size_limit(10**9)
    texto = io.TextIOWrapper(binario, encoding="utf-8-sig", errors="replace", newline="")
    yield from csv.DictReader((linea.replace("\0", "") for linea in texto), delimiter="|")


def iniciales(texto: str) -> str:
    """«ACEITE OLIVA NUCETE 250 CC» -> «Aceite Oliva Nucete 250 cc». Si ya trae
    minúsculas, se respeta lo que escribió el comercio."""
    texto = " ".join(texto.split())
    if texto != texto.upper():
        return texto
    palabras = [p.lower() if p.lower() in _SIGLAS else p.capitalize() for p in texto.split(" ")]
    return " ".join(palabras)


def _cantidad(valor: str | None) -> str:
    """«250», «250.00», «0,5» -> texto sin ceros de más."""
    valor = (valor or "").strip().replace(",", ".")
    if "." in valor:
        valor = valor.rstrip("0").rstrip(".")
    return valor


def leer_productos_zip(
    binario: io.BufferedIOBase, invalidos: Counter | None = None
) -> Iterator[dict[str, str]]:
    """Todas las filas de `productos.csv` del zip diario (zip de zips) o de un zip
    de un solo comercio. Un zip interno vacío o roto (pasa en SEPA) se salta y se
    cuenta en `invalidos`."""
    try:
        z = zipfile.ZipFile(binario)
    except zipfile.BadZipFile:
        if invalidos is not None:
            invalidos["zip_interno_invalido"] += 1
        return
    with z:
        for nombre in z.namelist():
            if nombre.endswith("/"):
                continue
            if nombre.endswith(".zip"):
                with z.open(nombre) as interno:
                    yield from leer_productos_zip(io.BytesIO(interno.read()), invalidos)
            elif nombre.endswith("productos.csv"):
                with z.open(nombre) as csv_productos:
                    yield from _filas_csv(csv_productos)


class Agrupador:
    """Junta las variantes de cada EAN y elige la más frecuente."""

    def __init__(self, reporte: Reporte):
        self.reporte = reporte
        self.variantes: dict[str, Counter] = {}

    def agregar(self, fila: dict[str, str]) -> None:
        self.reporte.leidas += 1
        if (fila.get("productos_ean") or "").strip() != "1":
            self.reporte.descartadas["no_es_ean"] += 1
            return
        ean, motivo = normalizar_ean(fila.get("id_producto"))
        if motivo:
            self.reporte.descartadas[motivo] += 1
            return
        nombre = (fila.get("productos_descripcion") or "").strip()
        if len(nombre) < 2:
            self.reporte.descartadas["sin_nombre"] += 1
            return
        marca = (fila.get("productos_marca") or "").strip()
        cantidad = _cantidad(fila.get("productos_cantidad_presentacion"))
        unidad = (fila.get("productos_unidad_medida_presentacion") or "").strip()
        self.variantes.setdefault(ean, Counter())[(nombre, marca, cantidad, unidad)] += 1

    def productos(self) -> Iterator[Producto]:
        for ean, cuenta in self.variantes.items():
            # Más frecuente; a igualdad, la de nombre más largo (suele ser más completa).
            (nombre, marca, cantidad, unidad), veces = max(
                cuenta.items(), key=lambda kv: (kv[1], len(kv[0][0]))
            )
            tamano = parsear_tamano(f"{cantidad} {unidad}") if cantidad and unidad else None
            if tamano is not None and tamano == (Decimal(1), "u"):
                # «1 unidad» es el conteo del envase, no un tamaño: no aporta nada y
                # taparía el tamaño real que pueda traer otra fuente.
                tamano = None
            if tamano is None:
                self.reporte.sin_tamano += 1
            datos = {
                "nombre": nombre,
                "marca": marca or None,
                "cantidad": cantidad or None,
                "unidad": unidad or None,
                "filas": sum(cuenta.values()),
            }
            nombre_norm = iniciales(nombre)[:MAX_NOMBRE]
            marca_norm = iniciales(marca)[:MAX_MARCA] if marca else None
            yield Producto(
                ean=ean,
                nombre=nombre_norm,
                marca=marca_norm,
                tamano_valor=tamano[0] if tamano else None,
                tamano_unidad=tamano[1] if tamano else None,
                imagen_url=None,
                datos=json.dumps(datos, ensure_ascii=False),
            )


async def cargar(rutas: list[Path], lote: int = 20_000) -> Reporte:
    reporte = Reporte()
    agrupador = Agrupador(reporte)
    for ruta in rutas:
        with open(ruta, "rb") as f:
            for fila in leer_productos_zip(f, reporte.descartadas):
                agrupador.agregar(fila)
        print(f"  ... {ruta.name}: {reporte.leidas} filas", file=sys.stderr, flush=True)
    conn = await conectar()
    try:
        buffer: list[Producto] = []
        for producto in agrupador.productos():
            buffer.append(producto)
            if len(buffer) >= lote:
                await fusionar_lote(conn, FUENTE, buffer, reporte)
                buffer = []
        await fusionar_lote(conn, FUENTE, buffer, reporte)
    finally:
        await conn.close()
    return reporte


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("archivos", type=Path, nargs="+", help="zip(s) diario(s) de SEPA")
    ap.add_argument("--lote", type=int, default=20_000)
    args = ap.parse_args()
    for a in args.archivos:
        if not a.exists():
            raise SystemExit(f"No existe {a}. Ver `make etl-sepa-descargar`.")
    print(asyncio.run(cargar(args.archivos, args.lote)).texto())


if __name__ == "__main__":
    main()
