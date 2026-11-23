"""Fórmula de calidad del backend (Doc 7 §6): se recalcula al corregir a mano. La paridad con el
normalizador del ETL se verifica en `etl/tests/test_calidad_paridad.py`."""

from decimal import Decimal

from app.services.calidad import evaluar


def test_completo_con_marca_tamano_e_imagen():
    calidad, estado, motivos = evaluar(
        "Aceite Girasol", "Cocinero", Decimal(900), "http://i/a.jpg", "botella", [], []
    )
    assert (calidad, estado, motivos) == (100, "completo", [])


def test_sin_marca_ni_tamano_y_corto_se_descarta_salvo_que_lo_haya_revisado_una_persona():
    assert evaluar("Aceite", None, None, None, None, [], [])[1] == "descartado"
    calidad, estado, motivos = evaluar("Aceite", None, None, None, None, [], [], revisado=True)
    assert estado != "descartado" and "muy_incompleto" not in motivos


def test_corregir_y_bloquear_el_nombre_resuelve_el_abreviado():
    dudoso = evaluar("Desinfect Amb", "Lysoform", Decimal(380), None, None, ["abreviado"], [])
    assert dudoso[1] == "dudoso"
    resuelto = evaluar(
        "Desinfectante Ambiental", "Lysoform", Decimal(380), None, None, ["abreviado"], ["nombre"]
    )
    assert resuelto[1] != "dudoso" and "abreviado" not in resuelto[2]
