"""Re-normalización del catálogo ya cargado (Doc 7): respeta lo bloqueado, limpia el nombre que
puso una persona y es idempotente. Contra Postgres local real."""

import asyncio
import uuid

from etl.comun.catalogo import conectar
from etl.renormalizar import _COLUMNAS, _clave, nueva_fila, renormalizar
from etl.tests.test_off_db import db, ean, limpio  # noqa: F401


def fila(**kw):
    base = {
        "id": uuid.uuid4(), "ean": ean(1), "nombre": "Aceite Girasol", "marca": None,
        "tamano_valor": None, "tamano_unidad": None, "imagen_url": None, "presentacion": None,
        "pack_cantidad": None, "origen": "manual", "campos_bloqueados": ["nombre"],
        "calidad": 0, "estado_calidad": "parcial", "calidad_motivos": [],
        "normalizador_version": 1,
    }  # fmt: skip
    return {**base, **kw}


def test_el_nombre_de_una_persona_con_todo_adentro_se_limpia_y_completa():
    n = nueva_fila(fila(nombre="Aceite Cocinero Girasol 900 ml Botella"))
    assert n["nombre"] == "Aceite Girasol"
    assert n["marca"] == "Cocinero"
    assert (float(n["tamano_valor"]), n["tamano_unidad"]) == (900.0, "ml")
    assert n["presentacion"] == "botella"
    assert "nombre" in n["campos_bloqueados"]  # sigue bloqueado


def test_nunca_pisa_un_campo_ya_cargado_por_la_persona():
    r = fila(
        nombre="Aceite Cocinero Girasol 900 ml",
        marca="Cañuelas",
        campos_bloqueados=["nombre", "marca"],
    )
    assert nueva_fila(r)["marca"] == "Cañuelas"
    r = fila(
        nombre="Aceite Girasol 900 ml",
        tamano_valor=1,
        tamano_unidad="l",
        campos_bloqueados=["nombre", "tamano"],
    )
    n = nueva_fila(r)
    assert (float(n["tamano_valor"]), n["tamano_unidad"]) == (1.0, "l")


def test_es_idempotente_sobre_lo_ya_normalizado():
    n = nueva_fila(fila(nombre="Aceite Cocinero Girasol 900 ml Botella"))
    segunda = nueva_fila({**n, "id": n["id"]})
    assert segunda["nombre"] == n["nombre"] and _clave(segunda) == _clave(n)


def test_un_nombre_inservible_de_una_persona_no_se_reemplaza():
    assert nueva_fila(fila(nombre="12345"))["nombre"] == "12345"


def test_renormalizar_el_catalogo_repetido_no_cambia_nada():
    e = ean(1)

    async def preparar(c):
        # un producto de SEPA con el nombre crudo, de antes del normalizador
        await c.execute(
            "insert into catalogo_global (ean, nombre, marca, origen) "
            "values ($1, 'ACEITE NUCETE OLIVA BOT-250-ml.', 'NUCETE', 'sepa')",
            e,
        )

    db(preparar)

    async def correr_y_leer():
        # Ojo: corre sobre TODO el catálogo de la base de desarrollo; solo se mira el de prueba.
        await renormalizar(aplicar=True)
        c = await conectar()
        try:
            a = await c.fetchrow(f"select {_COLUMNAS} from catalogo_global where ean = $1", e)
        finally:
            await c.close()
        return a

    antes = asyncio.run(correr_y_leer())
    assert antes["nombre"] == "Aceite Oliva" and antes["estado_calidad"] == "completo"
    # una segunda pasada deja la fila exactamente igual
    despues = asyncio.run(correr_y_leer())
    assert _clave(antes) == _clave(despues)
