"""Plataforma: roles del equipo, salvaguardas y auditoria."""

import uuid

from tests import db


def _admin(persona, rol="admin"):
    p = persona()
    db.poner_plataforma(p.id, rol)
    return p


def _objetivo(persona, registrado=True):
    return persona(registrado=registrado)


def test_me_dice_el_rol_de_plataforma_y_sus_capacidades(persona):
    admin, moderador = _admin(persona), _admin(persona, "moderador")
    me = admin.get("/v1/me").json()["plataforma"]
    assert me["rol"] == "admin" and "usuario.cambiar_rol" in me["capacidades"]
    mod = moderador.get("/v1/me").json()["plataforma"]
    assert mod["rol"] == "moderador"
    assert "catalogo.sugerir" in mod["capacidades"] and "config.editar" not in mod["capacidades"]
    assert persona().get("/v1/me").json()["plataforma"] is None


def test_el_moderador_no_entra_a_configuracion_ni_cambia_roles(persona):
    moderador = _admin(persona, "moderador")
    objetivo = _objetivo(persona)
    assert moderador.get("/v1/admin/capacidades").status_code == 200
    r = moderador.post(f"/v1/admin/usuarios/{objetivo.id}/rol-plataforma", json={"rol": "admin"})
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "sin_permiso"
    assert moderador.get("/v1/admin/usuarios").status_code == 403


def test_un_usuario_comun_no_entra_al_panel(persona):
    comun = persona()
    for ruta in ("/v1/admin/usuarios", "/v1/admin/auditoria", "/v1/admin/capacidades"):
        assert comun.get(ruta).status_code == 403, ruta


def test_el_admin_promueve_y_quita_y_queda_auditado(persona):
    admin, objetivo = _admin(persona), _objetivo(persona)
    ruta = f"/v1/admin/usuarios/{objetivo.id}/rol-plataforma"
    r = admin.post(ruta, json={"rol": "moderador"})
    assert r.status_code == 200 and r.json()["plataforma_rol"] == "moderador"
    assert objetivo.get("/v1/me").json()["plataforma"]["rol"] == "moderador"
    assert admin.post(ruta, json={"rol": None}).status_code == 200
    assert objetivo.get("/v1/me").json()["plataforma"] is None

    filas = admin.get("/v1/admin/auditoria", params={"entidad": "plataforma_rol"}).json()
    propias = [f for f in filas if f["entidad_id"] == objetivo.id]
    assert [f["despues"]["rol"] for f in propias] == [None, "moderador"]
    assert propias[0]["antes"]["rol"] == "moderador" and propias[0]["rol_actuando"] == "admin"
    assert propias[0]["negocio_id"] is None


def test_nadie_cambia_su_propio_rol_de_plataforma(persona):
    admin = _admin(persona)
    r = admin.post(f"/v1/admin/usuarios/{admin.id}/rol-plataforma", json={"rol": "superadmin"})
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "no_cambiar_rol_propio"
    r = admin.post(f"/v1/admin/usuarios/{admin.id}/rol-plataforma", json={"rol": None})
    assert r.json()["detail"]["codigo"] == "no_cambiar_rol_propio"


def test_un_anonimo_no_puede_ser_de_la_plataforma(persona):
    admin, anonimo = _admin(persona), _objetivo(persona, registrado=False)
    r = admin.post(f"/v1/admin/usuarios/{anonimo.id}/rol-plataforma", json={"rol": "admin"})
    assert r.status_code == 409
    assert r.json()["detail"]["codigo"] == "plataforma_requiere_registrado"
    assert anonimo.get("/v1/me").json()["plataforma"] is None


def test_usuario_inexistente_y_rol_invalido(persona):
    admin = _admin(persona)
    r = admin.post(f"/v1/admin/usuarios/{uuid.uuid4()}/rol-plataforma", json={"rol": "admin"})
    assert r.status_code == 404 and r.json()["detail"]["codigo"] == "usuario_inexistente"
    r = admin.post(f"/v1/admin/usuarios/{uuid.uuid4()}/rol-plataforma", json={"rol": "dios"})
    assert r.status_code == 422 and r.json()["detail"]["codigo"] == "dato_invalido"


def test_solo_un_superadmin_toca_a_un_superadmin(persona):
    db.poner_config("superadmin_activo", "true")
    try:
        admin, superadmin = _admin(persona), _admin(persona, "superadmin")
        objetivo = _objetivo(persona)
        ruta = f"/v1/admin/usuarios/{objetivo.id}/rol-plataforma"
        r = admin.post(ruta, json={"rol": "superadmin"})
        assert r.status_code == 403 and r.json()["detail"]["codigo"] == "solo_superadmin"
        assert superadmin.post(ruta, json={"rol": "superadmin"}).status_code == 200
        # Y un admin tampoco puede quitarle el rol a un superadmin.
        r = admin.post(ruta, json={"rol": None})
        assert r.json()["detail"]["codigo"] == "solo_superadmin"
    finally:
        db.quitar_config("superadmin_activo")


def test_el_superadmin_esta_apagado_por_defecto(persona):
    """D54: sin el interruptor de configuracion, un superadmin no tiene capacidades."""
    db.quitar_config("superadmin_activo")
    superadmin = _admin(persona, "superadmin")
    assert superadmin.get("/v1/me").json()["plataforma"] is None
    assert superadmin.get("/v1/admin/usuarios").status_code == 403
    db.poner_config("superadmin_activo", "true")
    try:
        assert superadmin.get("/v1/admin/usuarios").status_code == 200
        assert "superadmin.todo" in superadmin.get("/v1/me").json()["plataforma"]["capacidades"]
    finally:
        db.quitar_config("superadmin_activo")


def test_listado_de_usuarios_filtra_por_tipo(persona):
    admin = _admin(persona)
    anonimo, registrado = persona(), persona(registrado=True)
    ids = lambda r: {u["id"] for u in r.json()}  # noqa: E731
    solo_anonimos = admin.get("/v1/admin/usuarios", params={"tipo": "anonimo", "limite": 200})
    solo_registrados = admin.get("/v1/admin/usuarios", params={"tipo": "registrado", "limite": 200})
    assert anonimo.id in ids(solo_anonimos) and registrado.id not in ids(solo_anonimos)
    assert registrado.id in ids(solo_registrados) and anonimo.id not in ids(solo_registrados)
    r = admin.get(
        "/v1/admin/usuarios", params={"q": registrado.id[:0] or "@test.local", "limite": 200}
    )
    assert registrado.id in ids(r)


def test_auditoria_de_plataforma_ve_la_de_cualquier_negocio(negocio, persona):
    negocio_id, _ = negocio()
    admin, dueno, empleado = _admin(persona), persona(), persona()
    db.dar_rol(dueno.id, negocio_id, "dueno")
    dueno.post(
        f"/v1/negocios/{negocio_id}/membresias", json={"usuario_id": empleado.id, "rol": "cajero"}
    )
    r = admin.get("/v1/admin/auditoria", params={"negocio_id": str(negocio_id)})
    assert [f["accion"] for f in r.json()] == ["membresia.crear"]
    # La auditoria de un negocio no se filtra a otro negocio.
    otro, _ = negocio()
    dueno_otro = persona()
    db.dar_rol(dueno_otro.id, otro, "dueno")
    assert dueno_otro.get(f"/v1/negocios/{otro}/auditoria").json() == []


# --- login de plataforma (GoTrue real) --------------------------------------------------------


def _registrar_con_email(client, email, clave="clave-segura-1"):
    sesion = client.post("/v1/auth/anonymous").json()
    headers = {"Authorization": f"Bearer {sesion['access_token']}"}
    yo = client.get("/v1/me", headers=headers).json()
    client.post(
        "/v1/auth/vincular",
        headers=headers,
        json={"email": email, "password": clave, "refresh_token": sesion["refresh_token"]},
    )
    return yo["id"]


def test_login_de_plataforma_solo_para_quien_tiene_rol(client):
    email = f"{uuid.uuid4().hex[:10]}@test.local"
    usuario_id = _registrar_con_email(client, email)
    try:
        cuerpo = {"email": email, "password": "clave-segura-1"}
        r = client.post("/v1/admin/login", json=cuerpo)
        assert r.status_code == 403 and "access_token" not in r.text  # sin rol, sin token
        db.poner_plataforma(usuario_id, "admin")
        r = client.post("/v1/admin/login", json=cuerpo)
        assert r.status_code == 200 and r.json()["access_token"]
        panel = client.get(
            "/v1/admin/usuarios", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
        )
        assert panel.status_code == 200
        db.poner_plataforma(usuario_id, None)  # revocar vale en el siguiente pedido
        assert (
            client.get(
                "/v1/admin/usuarios",
                headers={"Authorization": f"Bearer {r.json()['access_token']}"},
            ).status_code
            == 403
        )
    finally:
        db.borrar_usuarios([usuario_id])


def test_login_de_plataforma_con_clave_mala(client):
    r = client.post("/v1/admin/login", json={"email": "nadie@test.local", "password": "incorrecta"})
    assert r.status_code == 401 and r.json()["detail"]["codigo"] == "credenciales_invalidas"
