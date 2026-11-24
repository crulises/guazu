"""Cálculo del precio: casos fijados como datos (`casos_precio.json`) y paridad con la base.

SIN VALIDAR: los casos usan la hipótesis del Doc 2 hasta que responda el contador
(docs/validar-profesional/contador.md). Si una regla cambia, se cambia un dato de la migración y
del JSON, y se agrega un caso.
"""

import json
from pathlib import Path

import pytest

from app.services import precios
from app.services.precios import Costo, Entrada, ReglaCondicion
from tests import db

DATOS = json.loads((Path(__file__).parent / "casos_precio.json").read_text(encoding="utf-8"))
REGLAS = {k: ReglaCondicion(k, **v) for k, v in DATOS["reglas"].items()}


def _entrada(e: dict) -> Entrada:
    return Entrada(
        Costo(**e["costo"]) if e["costo"] else None,
        e["margen_bp"],
        e["iva_venta_bp"],
        e["precio_manual_centavos"],
        e["redondeo_centavos"],
    )


@pytest.mark.parametrize("caso", DATOS["calculo"], ids=lambda c: c["nombre"])
def test_calculo_fijado(caso):
    r = precios.calcular(_entrada(caso["entrada"]), REGLAS[caso["condicion"]])
    assert r.__dict__ == caso["esperado"]


@pytest.mark.parametrize("caso", DATOS["cambio_de_condicion"], ids=lambda c: c["nombre"])
def test_cambio_de_condicion_fijado(caso):
    costo, margen, iva = Costo(**caso["costo"]), caso["margen_bp"], caso["iva_venta_bp"]
    de, a = REGLAS[caso["de"]], REGLAS[caso["a"]]
    esperado = caso["esperado"]
    antes = precios.calcular(Entrada(costo, margen, iva), de)
    assert antes.precio_centavos == esperado["precio_antes_centavos"]
    # mantener el precio final: el margen real se corrige y el precio no se mueve
    nuevo = precios.margen_real_bp(antes.precio_centavos, precios.costo_base(costo, a), a, iva)
    assert nuevo == esperado["margen_real_nuevo_bp"]
    despues = precios.calcular(Entrada(costo, nuevo, iva), a)
    assert despues.precio_centavos == esperado["precio_mantener_precio_centavos"]
    assert despues.precio_centavos == antes.precio_centavos
    # mantener el margen: el precio se mueve lo necesario
    assert (
        precios.calcular(Entrada(costo, margen, iva), a).precio_centavos
        == esperado["precio_mantener_margen_centavos"]
    )


def test_half_up_y_redondeo_comercial():
    assert [precios.mitad_arriba(n, 2) for n in (0, 1, 2, 3, 5)] == [0, 1, 1, 2, 3]
    assert precios.redondeo_comercial(15500, 1000) == 16000
    assert precios.redondeo_comercial(15499, 1000) == 15000
    assert precios.redondeo_comercial(15499, 0) == 15499
    assert precios.redondeo_comercial(15499, 1) == 15499


def test_costo_desde_total_y_neto():
    assert precios.costo_desde_total(12100, 2100) == (10000, 2100)
    assert precios.costo_desde_total(1000, 0) == (1000, 0)
    assert precios.costo_desde_neto(10000, 1050) == (10000, 1050)
    neto, iva = precios.costo_desde_total(9999, 2100)
    assert neto + iva == 9999


def test_las_reglas_de_la_base_son_las_del_json():
    """Las reglas por condición son datos de la migración: si se separan de los casos fijados,
    los casos dejan de probar lo que corre."""
    filas = db.fetch(
        "select clave, suma_iva_venta, iva_compra_es_credito, discrimina_iva from"
        " condiciones_fiscales"
    )
    en_base = {f["clave"]: {k: v for k, v in dict(f).items() if k != "clave"} for f in filas}
    assert en_base == DATOS["reglas"]


def test_todo_lo_fiscal_arranca_sin_validar():
    assert not any(f["validada"] for f in db.fetch("select validada from condiciones_fiscales"))


def test_las_alicuotas_de_fabrica():
    filas = db.fetch("select clave, porcentaje_bp from alicuotas_impuesto order by clave")
    assert {f["clave"]: f["porcentaje_bp"] for f in filas} == {
        "exento": 0, "iva_0": 0, "iva_10_5": 1050, "iva_21": 2100, "iva_27": 2700,
    }  # fmt: skip
