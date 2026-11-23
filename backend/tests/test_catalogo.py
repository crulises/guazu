"""Búsqueda por EAN y administración de conflictos del catálogo global."""

import time
import uuid

import pytest

from tests import db

# EAN de prueba que empiezan con 79999 (los mismos que limpia el ETL).
EAN13 = "7999900000015"
EAN8 = "79999000"
EAN14 = "17999900000012"


def _con_dv(base: str) -> str:
    """Completa un cuerpo con su dígito verificador GS1."""
    suma = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(base)))
    return base + str((10 - suma % 10) % 10)


@pytest.fixture
def producto():
    eans = []

    def nuevo(base: str, **campos):
        ean = _con_dv(base)
        eans.append(ean)
        db.sql(
            "insert into catalogo_global (ean, nombre, marca, origen) values ($1, $2, $3, 'sepa') "
            "on conflict (ean) do nothing",
            ean,
            campos.get("nombre", "Yerba Mate 1 kg"),
            campos.get("marca", "Playadito"),
        )
        return ean

    yield nuevo
    for ean in eans:
        db.sql("delete from conflictos_catalogo where ean = $1", ean)
        db.sql("delete from catalogo_global where ean = $1", ean)


def _admin(persona, rol="admin"):
    p = persona()
    db.poner_plataforma(p.id, rol)
    return p


@pytest.mark.parametrize(
    "largo,base", [(8, "7999900"), (13, "799990000001"), (14, "1799990000001")]
)
def test_busca_con_8_13_y_14_digitos(persona, producto, largo, base):
    ean = producto(base)
    assert len(ean) == largo
    r = persona().get(f"/v1/catalogo/ean/{ean}")
    assert r.status_code == 200 and r.json()["ean"] == ean and r.json()["nombre"]


def test_un_upca_de_12_digitos_se_busca_como_ean13(persona, producto):
    ean13 = producto("079999000001")  # guardado como EAN-13 que empieza con 0
    upc = ean13[1:]
    assert len(upc) == 12
    r = persona().get(f"/v1/catalogo/ean/{upc}")
    assert r.status_code == 200
    assert r.json()["ean"] == ean13 and r.json()["ean_buscado"] == upc


def test_un_gtin14_con_indicador_cero_encuentra_el_ean13(persona, producto):
    ean13 = producto("799990000002")
    r = persona().get(f"/v1/catalogo/ean/0{ean13}")
    assert r.status_code == 200 and r.json()["ean"] == ean13


@pytest.mark.parametrize(
    "codigo,regla",
    [
        ("12ab5678", "ean_no_numerico"),
        ("12345", "ean_largo_invalido"),
        ("12345678901", "ean_largo_invalido"),
        ("7999900000014", "ean_digito_verificador"),
        (_con_dv("200000000000"), "ean_de_balanza"),
    ],
)
def test_rechaza_codigos_invalidos_con_su_regla(persona, codigo, regla):
    r = persona().get(f"/v1/catalogo/ean/{codigo}")
    assert r.status_code == 422 and r.json()["detail"]["codigo"] == regla


def test_ean_inexistente_es_404_y_pide_sesion(persona, client):
    assert persona().get(f"/v1/catalogo/ean/{_con_dv('799990009999')}").status_code == 404
    assert client.get(f"/v1/catalogo/ean/{EAN13}").status_code == 401


def test_la_busqueda_tiene_tope_por_sesion(persona, producto):
    ean = producto("799990000003")
    p = persona()
    db.sql(
        "insert into config (clave, valor, negocio_id) "
        "values ('catalogo_busquedas_por_minuto', '3', null)"
    )
    try:
        codigos = [p.get(f"/v1/catalogo/ean/{ean}").status_code for _ in range(5)]
    finally:
        db.sql("delete from config where clave = 'catalogo_busquedas_por_minuto'")
    assert codigos == [200, 200, 200, 429, 429]


def test_buscar_responde_en_milisegundos(persona, producto):
    ean = producto("799990000004")
    p = persona()
    p.get(f"/v1/catalogo/ean/{ean}")  # calienta
    t0 = time.perf_counter()
    for _ in range(20):
        assert p.get(f"/v1/catalogo/ean/{ean}").status_code == 200
    assert (time.perf_counter() - t0) / 20 < 0.1


# ----------------------------------------------------------------------- conflictos
def _conflicto(ean, campo="nombre", a="Yerba Mate 1 kg", b="Yerba Mate Playadito Suave"):
    cid = uuid.uuid4()
    db.sql(
        "insert into conflictos_catalogo (id, ean, campo, valor_a, fuente_a, valor_b, fuente_b) "
        "values ($1, $2, $3, $4, 'sepa', $5, 'off')",
        cid,
        ean,
        campo,
        a,
        b,
    )
    return cid


def test_listar_conflictos_pide_la_capacidad(persona, producto):
    ean = producto("799990000005")
    cid = _conflicto(ean)
    assert persona().get("/v1/admin/catalogo/conflictos").status_code == 403
    moderador = _admin(persona, "moderador")  # ve el catalogo pero no resuelve
    filas = moderador.get("/v1/admin/catalogo/conflictos", params={"ean": ean}).json()
    assert [f["id"] for f in filas] == [str(cid)]
    assert filas[0]["valor_a"] == "Yerba Mate 1 kg" and filas[0]["nombre"] == "Yerba Mate 1 kg"
    r = moderador.post(f"/v1/admin/catalogo/conflictos/{cid}/resolver", json={"elegido": "b"})
    assert r.status_code == 403


def test_resolver_con_b_cambia_el_catalogo_lo_bloquea_y_audita(persona, producto):
    ean = producto("799990000006")
    cid = _conflicto(ean)
    admin = _admin(persona)
    r = admin.post(f"/v1/admin/catalogo/conflictos/{cid}/resolver", json={"elegido": "b"})
    assert r.status_code == 200
    assert r.json()["estado"] == "resuelto" and r.json()["resuelto_por"] == admin.id
    fila = db.fetch("select nombre, campos_bloqueados from catalogo_global where ean = $1", ean)[0]
    assert fila["nombre"] == "Yerba Mate Playadito Suave"
    assert fila["campos_bloqueados"] == ["nombre"]
    # ya resuelto: no se resuelve dos veces ni aparece entre los pendientes
    r = admin.post(f"/v1/admin/catalogo/conflictos/{cid}/resolver", json={"elegido": "a"})
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "conflicto_resuelto"
    assert admin.get("/v1/admin/catalogo/conflictos", params={"ean": ean}).json() == []
    filas = admin.get("/v1/admin/auditoria", params={"entidad": "catalogo_conflicto"}).json()
    propia = next(f for f in filas if f["entidad_id"] == str(cid))
    assert propia["antes"]["nombre"] == "Yerba Mate 1 kg"
    assert propia["despues"]["nombre"] == "Yerba Mate Playadito Suave"


def test_resolver_con_a_deja_el_catalogo_y_bloquea(persona, producto):
    ean = producto("799990000007")
    cid = _conflicto(ean, campo="marca", a="Playadito", b="Otra")
    r = _admin(persona).post(f"/v1/admin/catalogo/conflictos/{cid}/resolver", json={"elegido": "a"})
    assert r.status_code == 200
    fila = db.fetch("select marca, campos_bloqueados from catalogo_global where ean = $1", ean)[0]
    assert fila["marca"] == "Playadito" and fila["campos_bloqueados"] == ["marca"]


def test_resolver_un_tamano_con_b(persona, producto):
    ean = producto("799990000008")
    cid = _conflicto(ean, campo="tamano", a="1 kg", b="500 g")
    _admin(persona).post(f"/v1/admin/catalogo/conflictos/{cid}/resolver", json={"elegido": "b"})
    fila = db.fetch(
        "select tamano_valor, tamano_unidad, campos_bloqueados from catalogo_global where ean = $1",
        ean,
    )[0]
    assert (int(fila["tamano_valor"]), fila["tamano_unidad"]) == (500, "g")
    assert fila["campos_bloqueados"] == ["tamano"]


def test_un_tamano_ilegible_no_cambia_nada(persona, producto):
    ean = producto("799990000009")
    cid = _conflicto(ean, campo="tamano", a="1 kg", b="mucho")
    admin = _admin(persona)
    r = admin.post(f"/v1/admin/catalogo/conflictos/{cid}/resolver", json={"elegido": "b"})
    assert r.status_code == 422 and r.json()["detail"]["codigo"] == "tamano_ilegible"
    estado = db.fetch("select estado from conflictos_catalogo where id = $1", cid)[0]["estado"]
    assert estado == "pendiente"
    fila = db.fetch("select campos_bloqueados from catalogo_global where ean = $1", ean)[0]
    assert fila["campos_bloqueados"] == []


def test_conflicto_inexistente_y_eleccion_invalida(persona):
    admin = _admin(persona)
    r = admin.post(f"/v1/admin/catalogo/conflictos/{uuid.uuid4()}/resolver", json={"elegido": "a"})
    assert r.status_code == 404 and r.json()["detail"]["codigo"] == "conflicto_inexistente"
    r = admin.post(f"/v1/admin/catalogo/conflictos/{uuid.uuid4()}/resolver", json={"elegido": "c"})
    assert r.status_code == 422
