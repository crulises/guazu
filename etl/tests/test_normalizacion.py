from decimal import Decimal

import pytest

from etl.comun.ean import normalizar_ean
from etl.comun.tamano import parsear_tamano


@pytest.mark.parametrize(
    "crudo,esperado",
    [
        ("350 g", (Decimal(350), "g")),
        ("1,5 L", (Decimal("1.5"), "l")),
        ("500ml", (Decimal(500), "ml")),
        ("1 kg", (Decimal(1), "kg")),
        ("1000 g", (Decimal(1), "kg")),
        ("75 cl", (Decimal(750), "ml")),
        ("6 x 330 ml", (Decimal("1.98"), "l")),
        ("2×100g", (Decimal(200), "g")),
        ("12 units", (Decimal(12), "u")),
        ("16 oz", (Decimal("453.592"), "g")),
        ("250 g (8.8 oz)", (Decimal(250), "g")),
        ("  0,5 LT. ", (Decimal(500), "ml")),
        ("1 fl oz", (Decimal("29.574"), "ml")),
        ("150 g e", (Decimal(150), "g")),
        ("1 gallon (3.78 L)", (Decimal("3.785"), "l")),
    ],
)
def test_tamano_valido(crudo, esperado):
    assert parsear_tamano(crudo) == esperado


@pytest.mark.parametrize(
    "crudo",
    [None, "", "mucho", "g", "0 g", "-5 g", "5000000 g", "1 bandeja", "3 x", "12"],
)
def test_tamano_invalido(crudo):
    assert parsear_tamano(crudo) is None


def test_ean_validos():
    assert normalizar_ean("7790070411112") == ("7790070411112", None)  # el del aceite
    assert normalizar_ean("4006381333931") == ("4006381333931", None)
    # UPC-A (12 dígitos) pasa a EAN-13
    assert normalizar_ean("036000291452") == ("0036000291452", None)
    # EAN-8 que OFF guarda rellenado con ceros
    assert normalizar_ean("0000096385074") == ("96385074", None)
    assert normalizar_ean(" 96385074 ") == ("96385074", None)


@pytest.mark.parametrize(
    "crudo,motivo",
    [
        (None, "ean_vacio"),
        ("", "ean_vacio"),
        ("abc123456789", "ean_no_numerico"),
        ("12345", "ean_largo_invalido"),
        ("123456789012345", "ean_largo_invalido"),
        ("7790070411113", "ean_digito_verificador"),
        ("2000000000008", "ean_de_balanza"),
    ],
)
def test_ean_invalidos(crudo, motivo):
    assert normalizar_ean(crudo) == (None, motivo)
