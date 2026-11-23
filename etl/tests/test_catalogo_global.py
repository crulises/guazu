"""Reglas del catalogo global propias de guazu: prioridad configurable, aislamiento de lectura y
trazabilidad. Los EAN de prueba empiezan con 79999 (ver test_off_db.py): se limpian solos."""

import asyncio

import asyncpg
import pytest

from etl.off.__main__ import cargar as cargar_off
from etl.sepa.__main__ import cargar as cargar_sepa
from etl.tests.test_off_db import csv_off, db, ean, fila, limpio, producto  # noqa: F401
from etl.tests.test_sepa_db import fila_sepa, zip_sepa


async def _poner_prioridad(conn, lista_json):
    await conn.execute(
        """
        insert into config (negocio_id, clave, valor)
        values (null, 'catalogo_prioridad_fuentes', $1::jsonb)
        on conflict (coalesce(negocio_id, '00000000-0000-0000-0000-000000000000'), clave)
        do update set valor = excluded.valor
        """,
        lista_json,
    )


async def _quitar_prioridad(conn):
    await conn.execute("delete from config where clave = 'catalogo_prioridad_fuentes'")


@pytest.fixture
def prioridad_off_primero():
    """OFF por encima de SEPA, solo durante el test."""
    db(lambda c: _poner_prioridad(c, '["manual", "off", "sepa"]'))
    yield
    db(_quitar_prioridad)


def test_la_prioridad_se_lee_de_la_config(tmp_path, prioridad_off_primero):
    e = ean(1)
    asyncio.run(cargar_sepa([zip_sepa(tmp_path, fila_sepa(e, "FIDEOS TIRABUZON", "500", "gr"))]))
    assert producto(e)["origen"] == "sepa"
    asyncio.run(cargar_off(csv_off(tmp_path, fila(e, "Tirabuzon de trigo", "Lucchetti", "500 g"))))
    p = producto(e)
    # Con OFF por encima de SEPA, OFF pisa el nombre y el catalogo pasa a ser de OFF.
    assert (p["origen"], p["nombre"]) == ("off", "Tirabuzon de trigo")


def test_por_defecto_sepa_gana_a_off(tmp_path):
    e = ean(1)
    asyncio.run(cargar_off(csv_off(tmp_path, fila(e, "Tirabuzon de trigo", "Lucchetti", "500 g"))))
    asyncio.run(cargar_sepa([zip_sepa(tmp_path, fila_sepa(e, "FIDEOS TIRABUZON", "500", "gr"))]))
    assert producto(e)["origen"] == "sepa"


def test_cada_fuente_deja_su_dato_crudo(tmp_path):
    e = ean(1)
    asyncio.run(cargar_off(csv_off(tmp_path, fila(e, "Yerba", "Taragui", "1 kg"))))
    asyncio.run(cargar_sepa([zip_sepa(tmp_path, fila_sepa(e, "YERBA MATE", "1", "kg", "TARAGUI"))]))
    crudos = db(
        lambda c: c.fetch("select fuente, datos from producto_fuentes where ean = $1 order by 1", e)
    )
    assert [r["fuente"] for r in crudos] == ["off", "sepa"]


def test_una_fuente_desconocida_no_entra():
    with pytest.raises(asyncpg.CheckViolationError):
        db(
            lambda c: c.execute(
                "insert into producto_fuentes (ean, fuente, datos) values ($1, 'google', '{}')",
                ean(1),
            )
        )


def test_ean_con_formato_invalido_no_entra():
    with pytest.raises(asyncpg.CheckViolationError):
        db(
            lambda c: c.execute(
                "insert into catalogo_global (ean, nombre) values ('12ab', 'x')",
            )
        )


# --- aislamiento: los negocios leen el catalogo global, nunca lo escriben ---------------------


async def _como_aplicacion(conn, consulta, *args):
    async with conn.transaction():
        await conn.execute("set local role guazu_app")
        return await conn.fetch(consulta, *args)


def test_los_negocios_leen_el_catalogo_pero_no_lo_escriben(tmp_path):
    e = ean(1)
    asyncio.run(cargar_off(csv_off(tmp_path, fila(e, "Yerba", "Taragui", "1 kg"))))
    filas = db(lambda c: _como_aplicacion(c, "select ean from catalogo_global where ean = $1", e))
    assert [f["ean"] for f in filas] == [e]
    for escritura in (
        "update catalogo_global set nombre = 'otro' where ean = $1",
        "delete from catalogo_global where ean = $1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            db(lambda c, q=escritura: _como_aplicacion(c, q, e))
    # Y no ven el dato crudo ni los conflictos: son de la plataforma.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        db(lambda c: _como_aplicacion(c, "select * from producto_fuentes"))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        db(lambda c: _como_aplicacion(c, "select * from conflictos_catalogo"))


def test_dos_ean_repetidos_en_un_lote_gana_el_ultimo(tmp_path):
    e = ean(1)
    ruta = csv_off(tmp_path, fila(e, "Primero", "M", "1 kg"), fila(e, "Segundo", "M", "1 kg"))
    asyncio.run(cargar_off(ruta))
    assert producto(e)["nombre"] == "Segundo"
