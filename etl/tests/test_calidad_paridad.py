"""La fórmula de calidad existe dos veces a propósito (el backend no importa de `etl/`):
este test las compara en una grilla para que no se separen."""

import itertools
from decimal import Decimal

from app.services.calidad import evaluar

from etl.comun.normalizar import puntuar

NOMBRES = ["Aceite", "Aceite Oliva", "Aceite Oliva Extra Virgen"]
MOTIVOS = [[], ["abreviado"], ["tamano_en_conflicto"], ["marca_en_nombre"], ["no_latino"]]


def test_puntuar_y_evaluar_dan_lo_mismo():
    for nombre, marca, tam, img, pres, motivos, rev in itertools.product(
        NOMBRES,
        [None, "Cañuelas"],
        [None, Decimal(500)],
        [False, True],
        [None, "botella"],
        MOTIVOS,
        [False, True],
    ):
        etl = puntuar(nombre, marca, (tam, "g") if tam else None, img, pres, motivos, rev)
        app = evaluar(nombre, marca, tam, "x" if img else None, pres, list(motivos), [], rev)
        assert (etl[0], etl[1], list(etl[2])) == app, (nombre, marca, tam, img, pres, motivos)
