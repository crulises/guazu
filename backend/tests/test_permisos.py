"""Permisos por negocio: quien puede ver y cambiar que, y que un negocio no toca a otro."""

import uuid

from tests import db


def _rol(client_persona, negocio_id):
    return client_persona.get(f"/v1/negocios/{negocio_id}/roles")


def test_me_muestra_que_permisos_tiene_cada_rol(negocio, persona):
    negocio_id, sucursal_id = negocio()
    p = persona()
    db.dar_rol(p.id, negocio_id, "cajero")
    db.dar_rol(p.id, negocio_id, "moderador", sucursal_id)
    me = p.get("/v1/me").json()
    por_rol = {m["rol"]: m for m in me["membresias"]}
    assert set(por_rol) == {"cajero", "moderador"}
    assert "caja.cobrar" in por_rol["cajero"]["permisos"]
    assert "caja.cobrar" not in por_rol["moderador"]["permisos"]
    assert por_rol["cajero"]["sucursal_id"] is None
    assert por_rol["moderador"]["sucursal_id"] == str(sucursal_id) and por_rol["moderador"][
        "negocio_id"
    ] == str(negocio_id)


def test_roles_los_ve_quien_tiene_roles_ver(negocio, persona):
    negocio_id, _ = negocio()
    cajero, moderador = persona(), persona()
    db.dar_rol(cajero.id, negocio_id, "cajero")
    db.dar_rol(moderador.id, negocio_id, "moderador")
    assert _rol(cajero, negocio_id).status_code == 403
    r = _rol(moderador, negocio_id)
    assert r.status_code == 200
    claves = {x["clave"]: x for x in r.json()}
    assert set(claves) == {"dueno", "moderador", "cajero"}
    assert claves["dueno"]["de_fabrica"] and "usuarios.gestionar" in claves["dueno"]["permisos"]
    assert "stock.ver_costos" not in claves["moderador"]["permisos"]


def test_sin_membresia_no_se_ve_nada_y_negocio_inexistente_da_lo_mismo(negocio, persona):
    negocio_id, _ = negocio()
    ajeno = persona()
    r1 = _rol(ajeno, negocio_id)
    r2 = _rol(ajeno, uuid.uuid4())
    assert r1.status_code == r2.status_code == 403
    assert r1.json() == r2.json()  # no se revela que negocios existen
    assert ajeno.get(f"/v1/negocios/{negocio_id}/membresias").status_code == 403
    assert ajeno.get(f"/v1/negocios/{negocio_id}/auditoria").status_code == 403


def test_un_negocio_no_ve_datos_de_otro(negocio, persona):
    a, _ = negocio()
    b, _ = negocio()
    duena_de_a, dueno_de_b = persona(), persona()
    db.dar_rol(duena_de_a.id, a, "dueno")
    db.dar_rol(dueno_de_b.id, b, "dueno")
    assert duena_de_a.get(f"/v1/negocios/{a}/membresias").status_code == 200
    assert duena_de_a.get(f"/v1/negocios/{b}/membresias").status_code == 403
    # Y lo que lista cada uno es solo lo suyo.
    de_a = {m["usuario_id"] for m in duena_de_a.get(f"/v1/negocios/{a}/membresias").json()}
    assert de_a == {duena_de_a.id}


def test_un_rol_de_una_sucursal_no_vale_en_otra(negocio, persona):
    negocio_id, sucursal_id = negocio()
    otra = db.fetchval(
        "insert into sucursales (negocio_id, nombre) values ($1, 'Otra') returning id", negocio_id
    )
    p = persona()
    db.dar_rol(p.id, negocio_id, "moderador", sucursal_id)
    base = f"/v1/negocios/{negocio_id}/roles"
    assert p.get(base).status_code == 200  # sin sucursal: vale el rol donde sea
    assert p.get(base, params={"sucursal_id": str(sucursal_id)}).status_code == 200
    assert p.get(base, params={"sucursal_id": str(otra)}).status_code == 403


def test_una_sucursal_de_otro_negocio_es_invalida(negocio, persona):
    a, _ = negocio()
    _, suc_b = negocio()
    p = persona()
    db.dar_rol(p.id, a, "dueno")
    r = p.get(f"/v1/negocios/{a}/roles", params={"sucursal_id": str(suc_b)})
    assert r.status_code == 422 and r.json()["detail"]["codigo"] == "sucursal_invalida"


# --- membresias ---------------------------------------------------------------------------


def test_el_dueno_da_y_quita_roles_y_queda_auditado(negocio, persona):
    negocio_id, sucursal_id = negocio()
    dueno, empleado = persona(), persona()
    db.dar_rol(dueno.id, negocio_id, "dueno")
    base = f"/v1/negocios/{negocio_id}/membresias"

    r = dueno.post(
        base, json={"usuario_id": empleado.id, "rol": "cajero", "sucursal_id": str(sucursal_id)}
    )
    assert r.status_code == 201, r.text
    membresia_id = r.json()["id"]
    assert empleado.get(f"/v1/negocios/{negocio_id}/roles").status_code == 403  # cajero no ve roles
    assert any(m["rol"] == "cajero" for m in empleado.get("/v1/me").json()["membresias"])

    assert dueno.delete(f"{base}/{membresia_id}").status_code == 204
    assert empleado.get("/v1/me").json()["membresias"] == []

    acciones = [a["accion"] for a in dueno.get(f"/v1/negocios/{negocio_id}/auditoria").json()]
    assert acciones[:2] == ["membresia.quitar", "membresia.crear"]
    fila = dueno.get(f"/v1/negocios/{negocio_id}/auditoria").json()[1]
    assert fila["rol_actuando"] == "dueno" and fila["usuario_id"] == dueno.id
    assert fila["despues"]["rol"] == "cajero"


def test_sin_usuarios_gestionar_no_se_tocan_membresias(negocio, persona):
    negocio_id, _ = negocio()
    moderador, otra = persona(), persona()
    db.dar_rol(moderador.id, negocio_id, "moderador")
    r = moderador.post(
        f"/v1/negocios/{negocio_id}/membresias", json={"usuario_id": otra.id, "rol": "cajero"}
    )
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "sin_permiso"
    assert otra.get("/v1/me").json()["membresias"] == []


def test_nadie_cambia_su_propio_rol(negocio, persona):
    negocio_id, _ = negocio()
    dueno, otro = persona(), persona()
    db.dar_rol(dueno.id, negocio_id, "dueno")
    base = f"/v1/negocios/{negocio_id}/membresias"
    r = dueno.post(base, json={"usuario_id": dueno.id, "rol": "cajero"})
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "no_cambiar_rol_propio"
    propia = dueno.get(base).json()[0]["id"]
    r = dueno.delete(f"{base}/{propia}")
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "no_cambiar_rol_propio"
    assert otro.id  # el otro no participa


def test_errores_de_membresia_explican_la_regla(negocio, persona):
    negocio_id, _ = negocio()
    _, suc_ajena = negocio()
    dueno, otro = persona(), persona()
    db.dar_rol(dueno.id, negocio_id, "dueno")
    base = f"/v1/negocios/{negocio_id}/membresias"
    casos = [
        ({"usuario_id": otro.id, "rol": "inexistente"}, 422, "rol_invalido"),
        ({"usuario_id": str(uuid.uuid4()), "rol": "cajero"}, 404, "usuario_inexistente"),
        (
            {"usuario_id": otro.id, "rol": "cajero", "sucursal_id": str(suc_ajena)},
            422,
            "sucursal_invalida",
        ),
    ]
    for cuerpo, status, codigo in casos:
        r = dueno.post(base, json=cuerpo)
        assert r.status_code == status and r.json()["detail"]["codigo"] == codigo, r.text
        assert r.json()["detail"]["como_resolver"]
    assert dueno.post(base, json={"usuario_id": otro.id, "rol": "cajero"}).status_code == 201
    r = dueno.post(base, json={"usuario_id": otro.id, "rol": "cajero"})
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "membresia_duplicada"
    assert (
        dueno.delete(f"{base}/{uuid.uuid4()}").json()["detail"]["codigo"] == "membresia_inexistente"
    )
    r = dueno.post(base, json={"rol": "cajero"})  # falta el usuario
    assert r.status_code == 422 and r.json()["detail"]["campos"]


def test_no_se_quita_la_membresia_de_otro_negocio(negocio, persona):
    a, _ = negocio()
    b, _ = negocio()
    dueno_a, dueno_b, empleado = persona(), persona(), persona()
    db.dar_rol(dueno_a.id, a, "dueno")
    db.dar_rol(dueno_b.id, b, "dueno")
    db.dar_rol(empleado.id, b, "cajero")
    ajena = next(
        m
        for m in dueno_b.get(f"/v1/negocios/{b}/membresias").json()
        if m["usuario_id"] == empleado.id
    )
    r = dueno_a.delete(f"/v1/negocios/{a}/membresias/{ajena['id']}")
    assert r.status_code == 404  # RLS y filtro: para el negocio A esa membresia no existe
    assert any(m["rol"] == "cajero" for m in empleado.get("/v1/me").json()["membresias"])


def test_mensaje_de_regla_editado_desde_el_config(negocio, persona):
    negocio_id, _ = negocio()
    p = persona()
    db.poner_config("mensajes_reglas", '{"sin_permiso": "Esto no es para vos"}')
    try:
        r = p.get(f"/v1/negocios/{negocio_id}/roles")
        assert r.json()["detail"]["mensaje"] == "Esto no es para vos"
        assert r.json()["detail"]["codigo"] == "sin_permiso"  # el codigo no se edita
    finally:
        db.quitar_config("mensajes_reglas")
