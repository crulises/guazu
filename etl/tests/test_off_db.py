"""ETL de OFF contra Postgres local real (Supabase CLI), sin mocks de la base.

Los EAN de prueba empiezan con 79999: se limpian antes y después de cada test.
"""

import asyncio
from pathlib import Path

import asyncpg
import pytest

from etl.comun.catalogo import database_url
from etl.comun.ean import digito_verificador_ok
from etl.conflictos import listar, resolver
from etl.off.__main__ import cargar

CABECERA = "\t".join(
    ["code", "product_name", "generic_name", "brands", "quantity", "image_url"]
    + ["countries_tags", "last_modified_t"]
)


def ean(n: int) -> str:
    cuerpo = f"79999{n:07d}"
    for dv in range(10):
        if digito_verificador_ok(cuerpo + str(dv)):
            return cuerpo + str(dv)
    raise AssertionError


def fila(code, nombre="", marca="", quantity="", generic="", img="", paises="en:argentina"):
    return f"{code}\t{nombre}\t{generic}\t{marca}\t{quantity}\t{img}\t{paises}\t1700000000"


def csv_off(tmp_path: Path, *filas: str) -> Path:
    ruta = tmp_path / "off.csv"
    ruta.write_text("\n".join([CABECERA, *filas]) + "\n", encoding="utf-8")
    return ruta


def db(coro_fn):
    """Corre `coro_fn(conn)` con una conexión propia."""

    async def run():
        conn = await asyncpg.connect(database_url())
        try:
            return await coro_fn(conn)
        finally:
            await conn.close()

    return asyncio.run(run())


async def _limpiar(conn):
    for tabla in ("conflictos_catalogo", "producto_fuentes", "catalogo_global"):
        await conn.execute(f"delete from {tabla} where ean like '79999%'")


@pytest.fixture(autouse=True)
def limpio():
    db(_limpiar)
    yield
    db(_limpiar)


def producto(e):
    return db(lambda c: c.fetchrow("select * from catalogo_global where ean = $1", e))


def insertar_manual(e, nombre, marca=None, valor=None, unidad=None):
    db(
        lambda c: c.execute(
            "insert into catalogo_global"
            " (ean, nombre, marca, tamano_valor, tamano_unidad, origen)"
            " values ($1, $2, $3, $4, $5, 'manual')",
            e,
            nombre,
            marca,
            valor,
            unidad,
        )
    )


def test_carga_normaliza_y_reporta(tmp_path):
    a, b, c, d = ean(1), ean(2), ean(3), ean(4)
    ruta = csv_off(
        tmp_path,
        fila(a, "Aceite de Girasol", "Cocinero,Molinos", "900 ml", img="https://img/a.jpg"),
        fila(b, "Fideos", "Lucchetti", "mucho"),
        fila(c, "", "Marca", "1 kg"),  # sin nombre
        fila("7790070411113", "Mal dígito", "M", "1 kg"),  # dígito verificador
        fila("2000000000008", "Balanza", "M", "1 kg"),
        fila(d, "Gaseosa 6 pack", "Coca", "6 x 330 ml"),
    )
    rep = asyncio.run(cargar(ruta))
    assert rep.leidas == 6
    assert rep.catalogo_nuevos == 3
    assert rep.sin_tamano == 1
    assert rep.descartadas["sin_nombre"] == 1
    assert rep.descartadas["ean_digito_verificador"] == 1
    assert rep.descartadas["ean_de_balanza"] == 1
    p = producto(a)
    assert (p["nombre"], p["marca"], p["origen"], p["imagen_url"]) == (
        "Aceite de Girasol",
        "Cocinero",
        "off",
        "https://img/a.jpg",
    )
    assert (float(p["tamano_valor"]), p["tamano_unidad"]) == (900.0, "ml")
    assert producto(b)["tamano_valor"] is None
    p = producto(d)
    assert (float(p["tamano_valor"]), p["tamano_unidad"]) == (1.98, "l")
    datos = db(
        lambda cn: cn.fetchval("select datos->>'quantity' from producto_fuentes where ean=$1", a)
    )
    assert datos == "900 ml"


def test_idempotente(tmp_path):
    ruta = csv_off(tmp_path, fila(ean(1), "Aceite", "Cocinero", "900 ml"), fila(ean(2), "Fideos"))
    asyncio.run(cargar(ruta))
    rep = asyncio.run(cargar(ruta))
    assert rep.catalogo_nuevos == 0
    assert rep.catalogo_actualizados == 0
    assert rep.fuente_nuevas == 0
    assert rep.fuente_actualizadas == 0
    assert rep.conflictos_nuevos == 0
    n = db(lambda c: c.fetchval("select count(*) from catalogo_global where ean like '79999%'"))
    assert n == 2


def test_refresca_lo_propio(tmp_path):
    e = ean(1)
    asyncio.run(cargar(csv_off(tmp_path, fila(e, "Aceite", "Cocinero", "900 ml"))))
    rep = asyncio.run(cargar(csv_off(tmp_path, fila(e, "Aceite Girasol", "Cocinero", "1 l"))))
    assert rep.catalogo_actualizados == 1
    p = producto(e)
    assert (p["nombre"], float(p["tamano_valor"]), p["tamano_unidad"]) == (
        "Aceite Girasol",
        1.0,
        "l",
    )


def test_no_pisa_lo_manual_completa_y_marca_conflicto(tmp_path):
    e1, e2 = ean(1), ean(2)
    insertar_manual(e1, "Aceite de girasol", None, 900, "ml")  # sin marca
    insertar_manual(e2, "Fideos tirabuzón", "Lucchetti", 500, "g")
    ruta = csv_off(
        tmp_path,
        # mismo producto, distinta forma: sin conflicto; completa la marca
        fila(e1, "ACEITE GIRASOL", "Cocinero", "0,9 L"),
        # tamaño distinto: conflicto de tamaño. Nombre muy distinto: conflicto de nombre.
        fila(e2, "Galletitas de agua", "Lucchetti", "1 kg"),
    )
    rep = asyncio.run(cargar(ruta))
    assert rep.conflictos_nuevos == 2
    p1 = producto(e1)
    assert (p1["nombre"], p1["marca"], p1["origen"]) == ("Aceite de girasol", "Cocinero", "manual")
    p2 = producto(e2)
    assert (p2["nombre"], float(p2["tamano_valor"]), p2["origen"]) == (
        "Fideos tirabuzón",
        500.0,
        "manual",
    )
    pend = db(listar)
    assert {(r["ean"], r["campo"]) for r in pend if r["ean"].startswith("79999")} == {
        (e2, "nombre"),
        (e2, "tamano"),
    }
    # correrlo de nuevo no duplica conflictos
    assert asyncio.run(cargar(ruta)).conflictos_nuevos == 0


def test_resolver_bloquea_el_campo(tmp_path):
    e = ean(1)
    insertar_manual(e, "Fideos tirabuzón", "Lucchetti", 500, "g")
    asyncio.run(cargar(csv_off(tmp_path, fila(e, "Fideos tirabuzón", "Lucchetti", "1 kg"))))
    (c,) = [r for r in db(listar) if r["ean"] == e]
    assert c["campo"] == "tamano"
    db(lambda cn: resolver(cn, str(c["id"]), "b"))
    p = producto(e)
    assert (float(p["tamano_valor"]), p["tamano_unidad"], list(p["campos_bloqueados"])) == (
        1.0,
        "kg",
        ["tamano"],
    )
    # una carga posterior con otro tamaño no lo toca ni abre conflicto nuevo
    rep = asyncio.run(cargar(csv_off(tmp_path, fila(e, "Fideos tirabuzón", "Lucchetti", "2 kg"))))
    assert rep.conflictos_nuevos == 0
    assert float(producto(e)["tamano_valor"]) == 1.0
    # y la base lo impide aunque alguien lo intente a mano
    with pytest.raises(asyncpg.PostgresError, match="bloqueado"):
        db(lambda cn: cn.execute("update catalogo_global set tamano_valor = 5 where ean = $1", e))
    # un conflicto resuelto no se resuelve dos veces
    with pytest.raises(ValueError):
        db(lambda cn: resolver(cn, str(c["id"]), "a"))


def test_ean_indexado():
    usa_indice = db(
        lambda c: c.fetchval(
            "select count(*) from pg_indexes where tablename in "
            "('catalogo_global', 'producto_fuentes') and indexdef ~ '\\(ean[,)]'"
        )
    )
    assert usa_indice >= 2


def test_tolera_caracteres_nul(tmp_path):
    e = ean(1)
    ruta = csv_off(tmp_path, fila(e, "Aceite\x00 de girasol", "Coci\x00nero", "900 ml"))
    rep = asyncio.run(cargar(ruta))
    assert rep.catalogo_nuevos == 1
    assert producto(e)["nombre"] == "Aceite de girasol"
