"""Corrección de la plataforma, alta simple, sugerencias y avisos del catálogo global.
Contra Postgres real: lo corregido queda bloqueado contra el ETL y auditado."""

import json

import pytest

from app.services.estandares import ESTANDARES
from tests import db

EAN = "7799900000014"  # producto que existe (dudoso)
EAN_ALTA = "7799900000021"  # no existe: se da de alta


def _limpiar():
    for ean in (EAN, EAN_ALTA):
        db.sql("delete from sugerencias_catalogo where ean = $1", ean)
        db.sql("delete from avisos_catalogo where ean = $1", ean)
        db.sql("delete from conflictos_catalogo where ean = $1", ean)
        db.sql("delete from catalogo_global where ean = $1", ean)


@pytest.fixture(autouse=True)
def _catalogo(persona):  # `persona` primero: sus filas se borran antes de los usuarios
    _limpiar()
    db.sql(
        "insert into catalogo_global (ean, nombre, marca, origen, calidad, estado_calidad, "
        "calidad_motivos, presentacion) values ($1, 'Desinfect Amb Origin', 'Lysoform', 'sepa', "
        "40, 'dudoso', '{abreviado,sin_tamano}', 'botella')",
        EAN,
    )
    yield
    _limpiar()


def _con_rol(persona, rol):
    p = persona()
    db.poner_plataforma(p.id, rol)
    return p


@pytest.fixture
def admin(persona):
    return _con_rol(persona, "admin")


@pytest.fixture
def moderador(persona):
    return _con_rol(persona, "moderador")


def _producto(ean=EAN):
    return dict(db.fetch("select * from catalogo_global where ean = $1", ean)[0])


def _sugerir(p, ean=EAN, **cuerpo):
    return p.post("/v1/catalogo/sugerencias", json={"ean": ean, **cuerpo})


# ------------------------------------------------------------------ permisos
def test_un_usuario_comun_no_sugiere_ni_corrige(persona):
    p = persona()
    assert _sugerir(p, nombre="X Y").status_code == 403
    assert p.get("/v1/admin/catalogo/sugerencias").status_code == 403
    assert p.patch(f"/v1/admin/catalogo/productos/{EAN}", json={"marca": "X"}).status_code == 403


def test_el_moderador_sugiere_pero_no_resuelve_ni_corrige(moderador):
    assert _sugerir(moderador, nombre="Desinfectante Ambiental").status_code == 201
    assert moderador.get("/v1/admin/catalogo/sugerencias").status_code == 403
    r = moderador.patch(f"/v1/admin/catalogo/productos/{EAN}", json={"marca": "X"})
    assert r.status_code == 403
    assert moderador.get(f"/v1/admin/catalogo/productos/{EAN}").status_code == 200  # ve la ficha


# --------------------------------------------------------- corrección directa
def test_la_correccion_directa_se_aplica_se_bloquea_y_se_audita(admin):
    r = admin.patch(
        f"/v1/admin/catalogo/productos/{EAN}",
        json={"nombre": "Desinfectante Ambiental", "tamano_valor": "380", "tamano_unidad": "ml",
              "presentacion": "Lata", "nota": "se leyó del envase"},
    )  # fmt: skip
    assert r.status_code == 200, r.text
    p = _producto()
    assert p["nombre"] == "Desinfectante Ambiental" and p["presentacion"] == "lata"
    assert set(p["campos_bloqueados"]) == {"nombre", "tamano", "presentacion"}
    assert p["estado_calidad"] != "dudoso"  # lo corregido ya no resta
    historia = admin.get(f"/v1/admin/catalogo/productos/{EAN}").json()["historia"]
    assert historia[0]["accion"] == "catalogo_producto.corregir"
    assert historia[0]["antes"]["nombre"] == "Desinfect Amb Origin"
    assert historia[0]["despues"]["nombre"] == "Desinfectante Ambiental"
    assert historia[0]["nota"] == "se leyó del envase"


def test_una_segunda_corrida_del_etl_no_pisa_lo_corregido(admin):
    admin.patch(f"/v1/admin/catalogo/productos/{EAN}", json={"nombre": "Desinfectante Ambiental"})
    # el ETL escribe sin habilitar la escritura protegida: la base lo rechaza
    with pytest.raises(Exception, match="nombre bloqueado"):
        db.sql("update catalogo_global set nombre = 'DESINFECT AMB' where ean = $1", EAN)
    # lo que no se corrigió sigue siendo del ETL
    db.sql("update catalogo_global set imagen_url = 'http://i/a.jpg' where ean = $1", EAN)
    assert _producto()["nombre"] == "Desinfectante Ambiental"


def test_correccion_valida_y_errores_que_explican(admin):
    ruta = f"/v1/admin/catalogo/productos/{EAN}"
    assert admin.patch(ruta, json={}).json()["detail"]["codigo"] == "sin_cambios"
    r = admin.patch(ruta, json={"marca": "Lysoform"})
    assert r.status_code == 422 and r.json()["detail"]["codigo"] == "ya_es_lo_que_dice"
    assert admin.patch(ruta, json={"tamano_valor": "5"}).status_code == 422  # sin unidad
    assert admin.patch(ruta, json={"nombre": "  "}).status_code == 422
    r = admin.patch("/v1/admin/catalogo/productos/7799900000038", json={"marca": "X"})
    assert r.status_code == 404 and r.json()["detail"]["codigo"] == "producto_inexistente"
    assert admin.patch("/v1/admin/catalogo/productos/123", json={"marca": "X"}).status_code == 422


def test_alta_simple_es_manual_queda_bloqueada_y_no_se_descarta(admin):
    r = admin.post("/v1/admin/catalogo/productos", json={"ean": EAN_ALTA, "nombre": "Fanta"})
    assert r.status_code == 201, r.text
    p = _producto(EAN_ALTA)
    assert p["origen"] == "manual" and p["campos_bloqueados"] == ["nombre"]
    assert p["estado_calidad"] != "descartado"  # una palabra, sin marca ni tamaño, pero manual
    # el mismo EAN no se da de alta dos veces
    r = admin.post("/v1/admin/catalogo/productos", json={"ean": EAN_ALTA, "nombre": "Otra"})
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "producto_ya_existe"
    r = admin.post("/v1/admin/catalogo/productos", json={"ean": "7799900000038", "marca": "X"})
    assert r.json()["detail"]["codigo"] == "alta_requiere_nombre"


def test_un_producto_descartado_no_se_muestra_pero_la_ficha_lo_ve(admin, persona):
    db.sql(
        "update catalogo_global set calidad = 0, estado_calidad = 'descartado' where ean = $1",
        EAN,
    )
    assert persona().get(f"/v1/catalogo/ean/{EAN}").status_code == 404
    assert admin.get(f"/v1/admin/catalogo/productos/{EAN}").json()["producto"]["ean"] == EAN


# --------------------------------------------------------------- sugerencias
def test_sugerir_no_toca_el_catalogo_y_valida(moderador):
    s = _sugerir(moderador, nombre="Desinfectante Ambiental", motivo="está abreviado")
    assert s.status_code == 201, s.text
    assert (s.json()["tipo"], s.json()["estado"]) == ("correccion", "pendiente")
    assert (
        _producto()["nombre"] == "Desinfect Amb Origin" and _producto()["campos_bloqueados"] == []
    )
    assert [m["id"] for m in moderador.get("/v1/catalogo/sugerencias/mias").json()] == [
        s.json()["id"]
    ]
    assert _sugerir(moderador).json()["detail"]["codigo"] == "sin_cambios"
    assert _sugerir(moderador, marca="Lysoform").json()["detail"]["codigo"] == "ya_es_lo_que_dice"
    r = _sugerir(moderador, ean=EAN_ALTA, marca="Fanta")  # alta sin nombre
    assert r.json()["detail"]["codigo"] == "alta_requiere_nombre"
    assert _sugerir(moderador, ean="123", nombre="X Y").status_code == 422


def test_una_sugerencia_nueva_reemplaza_a_la_pendiente(moderador):
    a = _sugerir(moderador, nombre="Desinfectante").json()
    b = _sugerir(moderador, nombre="Desinfectante Ambiental").json()
    estados = {m["id"]: m["estado"] for m in moderador.get("/v1/catalogo/sugerencias/mias").json()}
    assert estados == {a["id"]: "reemplazada", b["id"]: "pendiente"}


def test_aprobar_una_correccion_la_aplica_la_bloquea_y_audita(moderador, admin):
    s = _sugerir(moderador, nombre="Desinfectante Ambiental", tamano_valor="380",
                 tamano_unidad="ml", pack_cantidad=2, presentacion="Lata").json()  # fmt: skip
    cola = admin.get("/v1/admin/catalogo/sugerencias").json()
    mia = next(x for x in cola["items"] if x["id"] == s["id"])
    assert mia["actual"]["nombre"] == "Desinfect Amb Origin" and mia["usuario_alias"]
    assert admin.get("/v1/admin/catalogo/resumen").json()["sugerencias_pendientes"] >= 1

    r = admin.post(f"/v1/admin/catalogo/sugerencias/{s['id']}/aprobar", json={})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "aprobada" and r.json()["resuelto_por_alias"]
    p = _producto()
    assert p["nombre"] == "Desinfectante Ambiental" and p["pack_cantidad"] == 2
    assert set(p["campos_bloqueados"]) == {"nombre", "tamano", "presentacion"}
    acciones = [
        h["accion"] for h in admin.get(f"/v1/admin/catalogo/productos/{EAN}").json()["historia"]
    ]
    assert "catalogo_producto.corregir" in acciones
    # ya resuelta
    r = admin.post(f"/v1/admin/catalogo/sugerencias/{s['id']}/aprobar", json={})
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "sugerencia_resuelta"


def test_aprobar_un_alta_crea_el_producto_manual(moderador, admin):
    s = _sugerir(moderador, ean=EAN_ALTA, nombre="Gaseosa Naranja", marca="Fanta").json()
    assert s["tipo"] == "alta"
    admin.post(f"/v1/admin/catalogo/sugerencias/{s['id']}/aprobar", json={})
    p = _producto(EAN_ALTA)
    assert (p["nombre"], p["marca"], p["origen"]) == ("Gaseosa Naranja", "Fanta", "manual")
    assert set(p["campos_bloqueados"]) == {"nombre", "marca"}


def test_rechazar_exige_nota_y_no_toca_el_catalogo(moderador, admin):
    s = _sugerir(moderador, nombre="Desinfectante Ambiental").json()
    ruta = f"/v1/admin/catalogo/sugerencias/{s['id']}/rechazar"
    assert admin.post(ruta, json={}).status_code == 422
    assert admin.post(ruta, json={"nota": " "}).status_code == 422
    r = admin.post(ruta, json={"nota": "el envase dice otra cosa"})
    assert r.status_code == 200 and r.json()["estado"] == "rechazada"
    assert r.json()["nota_resolucion"] == "el envase dice otra cosa"
    assert _producto()["nombre"] == "Desinfect Amb Origin"


def test_nadie_resuelve_lo_propio(persona):
    admin = _con_rol(persona, "admin")  # un admin tambien puede sugerir
    s = _sugerir(admin, nombre="Desinfectante Ambiental").json()
    for accion, cuerpo in (("aprobar", {}), ("rechazar", {"nota": "no me gusta"})):
        r = admin.post(f"/v1/admin/catalogo/sugerencias/{s['id']}/{accion}", json=cuerpo)
        assert r.status_code == 403 and r.json()["detail"]["codigo"] == "no_resolver_lo_propio"
    otro = _con_rol(persona, "admin")
    assert (
        otro.post(f"/v1/admin/catalogo/sugerencias/{s['id']}/aprobar", json={}).status_code == 200
    )


def test_el_resumen_cuenta_pendientes(admin, moderador):
    antes = admin.get("/v1/admin/catalogo/resumen").json()
    _sugerir(moderador, nombre="Desinfectante Ambiental")
    despues = admin.get("/v1/admin/catalogo/resumen").json()
    assert despues["sugerencias_pendientes"] == antes["sugerencias_pendientes"] + 1
    assert "conflictos_pendientes" in despues


# --------------------------------------------------------------- avisos y ayuda
def test_la_ayuda_lista_los_estandares_y_pide_sesion(persona, client):
    r = persona().get("/v1/ayuda/estandares")
    assert r.status_code == 200 and [e["id"] for e in r.json()] == [e.id for e in ESTANDARES]
    assert client.get("/v1/ayuda/estandares").status_code == 401


def test_el_aviso_explica_el_porque_y_se_marca_leido(persona):
    p = persona()
    db.sql(
        "insert into avisos_catalogo (usuario_id, ean, tipo, estandares, antes, despues) values "
        "($1::uuid, $2, 'nombre_ajustado', '{nombre,marca}', $3::jsonb, $4::jsonb)",
        p.id,
        EAN,
        json.dumps({"nombre": "Aceite Cocinero Girasol 900 ml"}),
        json.dumps({"nombre": "Aceite Girasol"}),
    )
    avisos = p.get("/v1/me/avisos").json()
    assert len(avisos) == 1 and avisos[0]["leido"] is False
    assert [e["id"] for e in avisos[0]["estandares"]] == ["nombre", "marca"]
    assert "no cumplía los estándares de carga" in avisos[0]["mensaje"]
    assert p.post("/v1/me/avisos/leidos").status_code == 204
    assert p.get("/v1/me/avisos", params={"no_leidos": True}).json() == []
    assert len(p.get("/v1/me/avisos").json()) == 1
    assert persona().get("/v1/me/avisos").json() == []  # los avisos son de cada persona
