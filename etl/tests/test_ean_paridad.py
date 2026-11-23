"""El backend valida el EAN con la misma regla que el ETL al cargar: no pueden separarse."""

import pytest
from app.services import ean as ean_backend

from etl.comun import ean as ean_etl

CASOS = [
    "", "abc", "123", "79999000", "799990000011", "7999900000015", "17999900000012",
    "2000000000008", "0000079999000", "7999900000014", "123456789012345", " 7999900000015 ",
]  # fmt: skip


@pytest.mark.parametrize("caso", CASOS)
def test_misma_normalizacion_en_backend_y_etl(caso):
    assert ean_backend.normalizar_ean(caso) == ean_etl.normalizar_ean(caso)
