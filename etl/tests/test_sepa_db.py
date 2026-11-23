# ruff: noqa: E501
"""ETL de SEPA y convivencia con OFF, contra Postgres local real.

Los EAN de prueba empiezan con 79999 (ver test_off_db.py): se limpian solos.
"""

import asyncio
import io
import zipfile
from pathlib import Path

from etl.off.__main__ import cargar as cargar_off
from etl.sepa.__main__ import cargar, iniciales
from etl.tests.test_off_db import csv_off, db, ean, fila, limpio, producto  # noqa: F401

CABECERA = "|".join(
    ["id_comercio", "id_bandera", "id_sucursal", "id_producto", "productos_ean"]
    + ["productos_descripcion", "productos_cantidad_presentacion"]
    + [
        "productos_unidad_medida_presentacion",
        "productos_marca",
        "productos_precio_lista",
    ]
)


def fila_sepa(e, nombre, cantidad="", unidad="", marca="", flag="1", sucursal="1"):
    return f"1|1|{sucursal}|{e}|{flag}|{nombre}|{cantidad}|{unidad}|{marca}|100.5"


def zip_sepa(tmp_path: Path, *filas: str, bom: bool = True) -> Path:
    """Zip diario de SEPA: un zip por comercio con su `productos.csv`."""
    contenido = ("﻿" if bom else "") + "\n".join([CABECERA, *filas]) + "\n"
    interno = io.BytesIO()
    with zipfile.ZipFile(interno, "w") as z:
        z.writestr("comercio.csv", "id_comercio|x\n1|y\n")
        z.writestr("productos.csv", contenido.encode("utf-8"))
    ruta = tmp_path / "sepa_domingo.zip"
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("2026-11-15/", "")
        z.writestr("2026-11-15/sepa_1_comercio-sepa-1.zip", interno.getvalue())
    return ruta


def test_iniciales():
    assert (
        iniciales("ACEITE OLIVA NUCETE EXTRA BOT 250 CC") == "Aceite Oliva Nucete Extra Bot 250 cc"
    )
    assert iniciales("Aceite de girasol") == "Aceite de girasol"  # ya trae minúsculas


def test_carga_agrupa_y_normaliza(tmp_path):
    a, b, c = ean(1), ean(2), ean(3)
    ruta = zip_sepa(
        tmp_path,
        fila_sepa(a, "ACEITE NUCETE 250 CC", "250", "cmq", "NUCETE", sucursal="1"),
        fila_sepa(a, "ACEITE NUCETE 250 CC", "250.00", "CM3", "NUCETE", sucursal="2"),
        fila_sepa(a, "Aceite de oliva", "250", "ml", "Nucete", sucursal="3"),  # minoritaria
        fila_sepa(b, "FIDEOS TIRABUZON", "500", "gr.", "LUCCHETTI"),
        fila_sepa(c, "GASEOSA", "1", "UNI"),  # «1 unidad» no es un tamaño: se carga sin él
        fila_sepa("2000000000008", "BALANZA", "1", "kg"),
        fila_sepa("7790070411113", "MAL DV", "1", "kg"),
        fila_sepa("12345", "CORTO", "1", "kg", flag="0"),
        fila_sepa(ean(4), "", "1", "kg"),
    )
    rep = asyncio.run(cargar([ruta]))
    assert rep.leidas == 9
    assert rep.catalogo_nuevos == 3
    assert rep.descartadas["ean_de_balanza"] == 1
    assert rep.descartadas["ean_digito_verificador"] == 1
    assert rep.descartadas["no_es_ean"] == 1
    assert rep.descartadas["sin_nombre"] == 1
    p = producto(a)
    assert (p["nombre"], p["marca"], p["origen"]) == (
        "Aceite Nucete 250 cc",
        "Nucete",
        "sepa",
    )
    assert (float(p["tamano_valor"]), p["tamano_unidad"]) == (250.0, "ml")
    assert producto(b)["tamano_unidad"] == "g"
    assert producto(c)["tamano_valor"] is None
    assert asyncio.run(cargar([ruta])).catalogo_nuevos == 0  # idempotente
    again = asyncio.run(cargar([ruta]))
    assert (
        again.catalogo_actualizados,
        again.fuente_actualizadas,
        again.conflictos_nuevos,
    ) == (
        0,
        0,
        0,
    )


def test_sepa_gana_a_off_y_queda_la_traza(tmp_path):
    e = ean(1)
    asyncio.run(
        cargar_off(
            csv_off(tmp_path, fila(e, "Aceite", "Cocinero", "900 ml", img="https://i/a.jpg"))
        )
    )
    assert producto(e)["origen"] == "off"
    asyncio.run(
        cargar(
            [
                zip_sepa(
                    tmp_path,
                    fila_sepa(e, "ACEITE GIRASOL COCINERO", "900", "ml", "COCINERO"),
                )
            ]
        )
    )
    p = producto(e)
    assert (p["origen"], p["nombre"]) == ("sepa", "Aceite Girasol Cocinero")
    assert p["imagen_url"] == "https://i/a.jpg"  # SEPA no trae imagen: se conserva la de OFF
    fuentes = db(
        lambda c: c.fetch("select fuente from producto_fuentes where ean = $1 order by 1", e)
    )
    assert [f["fuente"] for f in fuentes] == ["off", "sepa"]


def test_off_despues_de_sepa_completa_y_avisa_solo_el_tamano(tmp_path):
    e = ean(1)
    asyncio.run(cargar([zip_sepa(tmp_path, fila_sepa(e, "FIDEOS TIRABUZON", "500", "gr"))]))
    rep = asyncio.run(
        cargar_off(
            csv_off(
                tmp_path,
                fila(e, "Tirabuzón de trigo", "Lucchetti", "1 kg", img="https://i/f.jpg"),
            )
        )
    )
    p = producto(e)
    # sigue siendo de SEPA; OFF solo completó marca e imagen; el nombre no es conflicto
    assert (p["origen"], p["nombre"], p["marca"], p["imagen_url"]) == (
        "sepa",
        "Fideos Tirabuzon",
        "Lucchetti",
        "https://i/f.jpg",
    )
    assert float(p["tamano_valor"]) == 500.0
    assert rep.conflictos_nuevos == 1  # el tamaño (500 g vs 1 kg)
    campos = db(
        lambda c: c.fetch(
            "select campo, fuente_a, fuente_b from conflictos_catalogo where ean = $1",
            e,
        )
    )
    assert [(r["campo"], r["fuente_a"], r["fuente_b"]) for r in campos] == [
        ("tamano", "sepa", "off")
    ]


def test_off_filtra_por_paises(tmp_path):
    ar, fr = ean(1), ean(2)
    ruta = csv_off(
        tmp_path,
        fila(ar, "Yerba", "Taragüí", "1 kg", paises="en:argentina,en:uruguay"),
        fila(fr, "Baguette", "X", "250 g", paises="en:france"),
    )
    rep = asyncio.run(cargar_off(ruta, paises=frozenset({"en:argentina", "en:paraguay"})))
    assert rep.catalogo_nuevos == 1
    assert rep.descartadas["fuera_de_paises"] == 1
    assert producto(ar) is not None
    assert producto(fr) is None
