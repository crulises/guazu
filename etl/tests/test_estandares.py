"""Los ids de estándares que usa el ETL existen en el catálogo del backend y en el Doc 10."""

import re
from pathlib import Path

from app.services.estandares import ESTANDARES, POR_ID

RAIZ = Path(__file__).resolve().parents[2]
USADOS = {"nombre", "marca", "tamano", "presentacion", "abreviaturas", "mayusculas", "limpieza"}


def test_el_etl_solo_usa_estandares_que_existen():
    assert USADOS <= set(POR_ID)
    fuente = (RAIZ / "etl" / "renormalizar.py").read_text()
    for usado in re.findall(r'ids(?:\.insert\(0,|\.append\() ?"(\w+)"', fuente):
        assert usado in POR_ID


def test_el_doc_10_lista_todos_los_estandares():
    doc = (RAIZ / "docs" / "10-estandares-de-carga.md").read_text()
    for e in ESTANDARES:
        assert f"`{e.id}`" in doc and e.titulo in doc, e.id
