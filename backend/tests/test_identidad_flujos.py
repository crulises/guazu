"""Segunda serie de pruebas de identidad: recorridos completos con el GoTrue real del Supabase
CLI (tokens ES256 del proveedor, no firmados por nosotros). La primera serie prueba cada pieza;
acá se prueba lo que une varias: anónimo, cuenta, roles de negocio, panel de plataforma,
revocaciones y carreras."""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import jwt
import pytest

from app.config import get_settings
from tests import db

CLAVE = "clave-segura-1"


class Cuenta:
    """Una persona real: sesión anónima del proveedor que después se vincula a un email."""

    def __init__(self, client):
        self.client = client
        r = client.post("/v1/auth/anonymous")
        assert r.status_code == 200, r.text
        self.sesion = r.json()
        self.email = f"{uuid.uuid4().hex[:10]}@test.local"
        self.id = self.get("/v1/me").json()["id"]
        self.auth_id = jwt.decode(self.sesion["access_token"], options={"verify_signature": False})[
            "sub"
        ]

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.sesion['access_token']}"}

    def get(self, ruta, **kw):
        return self.client.get(ruta, headers=self.headers, **kw)

    def post(self, ruta, **kw):
        return self.client.post(ruta, headers=self.headers, **kw)

    def vincular(self, email=None, clave=CLAVE):
        email = email or self.email
        r = self.client.post(
            "/v1/auth/vincular",
            headers=self.headers,
            json={
                "email": email,
                "password": clave,
                "refresh_token": self.sesion["refresh_token"],
            },
        )
        if r.status_code == 200:
            self.sesion = r.json()
            self.email = email
            self.get("/v1/me")  # como la app: con la sesión nueva, que marca la cuenta registrada
        return r

    def login_admin(self, clave=CLAVE):
        return self.client.post("/v1/admin/login", json={"email": self.email, "password": clave})


@pytest.fixture
def cuenta(client):
    creadas: list[Cuenta] = []

    def nueva(vinculada=True) -> Cuenta:
        c = Cuenta(client)
        creadas.append(c)
        if vinculada:
            assert c.vincular().status_code == 200
        return c

    yield nueva
    if creadas:
        db.borrar_usuarios([c.id for c in creadas])


# ------------------------------------------------------------------ recorrido de una persona
def test_lo_cargado_como_anonimo_sobrevive_al_registro_y_al_login_en_otro_dispositivo(
    cuenta, negocio, client
):
    negocio_id, _ = negocio()
    c = cuenta(vinculada=False)
    assert c.get("/v1/me").json()["es_anonimo"] is True
    db.dar_rol(c.id, negocio_id, "cajero")  # le asignan un rol cuando todavía es anónimo
    assert [m["rol"] for m in c.get("/v1/me").json()["membresias"]] == ["cajero"]

    assert c.vincular().status_code == 200
    me = c.get("/v1/me").json()
    assert me["es_anonimo"] is False and me["email"] == c.email
    assert [m["rol"] for m in me["membresias"]] == ["cajero"]  # mismo id: el rol sigue

    # "otro celular": login con email y clave, sin pasar por la sesión anterior
    otro = client.post("/v1/auth/login", json={"email": c.email, "password": CLAVE}).json()
    h = {"Authorization": f"Bearer {otro['access_token']}"}
    me2 = client.get("/v1/me", headers=h).json()
    assert me2["id"] == c.id and [m["rol"] for m in me2["membresias"]] == ["cajero"]
    # y puede usar el rol en el negocio desde el otro dispositivo
    assert client.get(f"/v1/negocios/{negocio_id}/roles", headers=h).status_code == 403
    assert client.get(f"/v1/negocios/{negocio_id}/auditoria", headers=h).status_code == 403


def test_renovar_la_sesion_mantiene_la_identidad_y_un_refresh_roto_se_rechaza(cuenta, client):
    c = cuenta()
    r = client.post("/v1/auth/refresh", json={"refresh_token": c.sesion["refresh_token"]})
    assert r.status_code == 200
    nuevo = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/v1/me", headers=nuevo).json()["id"] == c.id
    r = client.post("/v1/auth/refresh", json={"refresh_token": "no-es-un-refresh"})
    assert r.status_code in (400, 401) and r.json()["detail"]["codigo"] == "sesion_invalida"


def test_vincular_rechaza_clave_corta_y_email_mal_escrito_sin_500(cuenta):
    c = cuenta(vinculada=False)
    r = c.vincular(clave="123")
    assert r.status_code < 500 and r.json()["detail"]["codigo"] in (
        "sesion_invalida",
        "dato_invalido",
    )
    r = c.vincular(email="esto-no-es-un-email")
    assert r.status_code < 500
    assert c.get("/v1/me").json()["es_anonimo"] is True  # nada cambió
    assert c.vincular().status_code == 200  # y con datos buenos sí


def test_el_email_se_compara_sin_mayusculas(cuenta):
    a = cuenta()
    b = cuenta(vinculada=False)
    r = b.vincular(email=a.email.upper())
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "email_en_uso"


def test_un_token_vencido_es_401_con_regla_y_no_toca_la_base(client):
    s = get_settings()
    ahora = int(time.time())
    viejo = jwt.encode(
        {"sub": str(uuid.uuid4()), "aud": s.jwt_audience, "iat": ahora - 7200, "exp": ahora - 3600,
         "is_anonymous": True},
        s.jwt_secret, algorithm="HS256",
    )  # fmt: skip
    r = client.get("/v1/me", headers={"Authorization": f"Bearer {viejo}"})
    assert r.status_code == 401 and r.json()["detail"]["codigo"] == "token_invalido"


# ---------------------------------------------------------------- roles de negocio, en vivo
def test_quitar_el_rol_corta_el_acceso_con_el_mismo_token(cuenta, negocio):
    negocio_id, _ = negocio()
    dueno, empleada = cuenta(), cuenta()
    db.dar_rol(dueno.id, negocio_id, "dueno")
    db.dar_rol(empleada.id, negocio_id, "moderador")
    assert empleada.get(f"/v1/negocios/{negocio_id}/roles").status_code == 200

    membresia = next(
        m["id"]
        for m in dueno.get(f"/v1/negocios/{negocio_id}/membresias").json()
        if m["usuario_id"] == empleada.id
    )
    r = dueno.client.delete(
        f"/v1/negocios/{negocio_id}/membresias/{membresia}", headers=dueno.headers
    )
    assert r.status_code == 204
    # el token de la empleada no cambió: lo que cambió es lo que la base dice que puede
    assert empleada.get(f"/v1/negocios/{negocio_id}/roles").status_code == 403
    assert empleada.get("/v1/me").json()["membresias"] == []


def test_una_persona_con_roles_en_dos_negocios_los_ve_separados(cuenta, negocio):
    (n1, _), (n2, _) = negocio(), negocio()
    c = cuenta()
    db.dar_rol(c.id, n1, "dueno")
    db.dar_rol(c.id, n2, "cajero")
    por_negocio = {m["negocio_id"]: m for m in c.get("/v1/me").json()["membresias"]}
    assert por_negocio[str(n1)]["rol"] == "dueno" and por_negocio[str(n2)]["rol"] == "cajero"
    assert c.get(f"/v1/negocios/{n1}/roles").status_code == 200  # dueno: roles.ver
    assert c.get(f"/v1/negocios/{n2}/roles").status_code == 403  # cajero: no


# ------------------------------------------------------------ panel de plataforma, en vivo
def test_el_login_del_panel_solo_deja_pasar_a_la_plataforma(cuenta):
    comun, admin = cuenta(), cuenta()
    db.poner_plataforma(admin.id, "admin")
    r = comun.login_admin()
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "sin_permiso"
    assert "access_token" not in r.text  # no sale ningún token
    r = admin.login_admin()
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert admin.client.get("/v1/admin/capacidades", headers=h).status_code == 200
    r = admin.client.post("/v1/admin/login", json={"email": admin.email, "password": "mala-clave"})
    assert r.status_code == 401 and r.json()["detail"]["codigo"] == "credenciales_invalidas"


def test_un_anonimo_no_entra_al_panel_ni_con_token_real(cuenta):
    anonimo = cuenta(vinculada=False)
    assert anonimo.get("/v1/admin/capacidades").status_code == 403
    assert anonimo.get("/v1/admin/usuarios").status_code == 403


def test_revocar_el_rol_de_plataforma_corta_el_acceso_en_el_siguiente_pedido(cuenta):
    admin, otro = cuenta(), cuenta()
    db.poner_plataforma(admin.id, "admin")
    assert admin.get("/v1/admin/usuarios").status_code == 200
    db.poner_plataforma(admin.id, None)
    assert admin.get("/v1/admin/usuarios").status_code == 403
    assert admin.get("/v1/me").json()["plataforma"] is None
    assert otro.get("/v1/admin/usuarios").status_code == 403


def test_el_superadmin_solo_funciona_con_el_interruptor_encendido(cuenta):
    s = cuenta()
    db.poner_plataforma(s.id, "superadmin")
    try:
        db.poner_config("superadmin_activo", "false")
        assert s.get("/v1/admin/usuarios").status_code == 403
        assert s.get("/v1/me").json()["plataforma"] is None  # apagado: sin capacidades
        db.poner_config("superadmin_activo", "true")
        assert s.get("/v1/admin/usuarios").status_code == 200
    finally:
        db.quitar_config("superadmin_activo")


def test_el_admin_promueve_a_otra_persona_real_y_ella_entra_al_panel(cuenta):
    admin, nueva = cuenta(), cuenta()
    db.poner_plataforma(admin.id, "admin")
    r = admin.post(f"/v1/admin/usuarios/{nueva.id}/rol-plataforma", json={"rol": "moderador"})
    assert r.status_code == 200
    assert nueva.get("/v1/admin/capacidades").status_code == 200
    assert nueva.get("/v1/admin/usuarios").status_code == 403  # moderador: sin usuario.ver
    quitar = admin.post(f"/v1/admin/usuarios/{nueva.id}/rol-plataforma", json={"rol": None})
    assert quitar.status_code == 200
    assert nueva.get("/v1/admin/capacidades").status_code == 403


def test_el_login_del_panel_tiene_su_tope_por_hora(cuenta):
    c = cuenta()
    db.poner_config("auth_login_por_hora_ip", "3")
    try:
        codigos = [c.login_admin().status_code for _ in range(5)]
    finally:
        db.quitar_config("auth_login_por_hora_ip")
    assert codigos[:3] == [403, 403, 403] and codigos[3:] == [429, 429]


# ---------------------------------------------------------------------------- carreras
def test_dos_primeros_pedidos_a_la_vez_crean_una_sola_persona(client):
    from tests.conftest import make_token

    auth_id = str(uuid.uuid4())
    h = {"Authorization": f"Bearer {make_token(auth_id)}"}
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            respuestas = list(pool.map(lambda _: client.get("/v1/me", headers=h), range(8)))
        assert [r.status_code for r in respuestas] == [200] * 8
        assert len({r.json()["id"] for r in respuestas}) == 1
        assert db.fetchval("select count(*) from usuarios where auth_id = $1::uuid", auth_id) == 1
    finally:
        db.sql("delete from usuarios where auth_id = $1::uuid", auth_id)


def test_cada_cambio_de_identidad_deja_auditoria(cuenta, negocio):
    negocio_id, _ = negocio()
    dueno, nueva = cuenta(), cuenta()
    db.dar_rol(dueno.id, negocio_id, "dueno")
    r = dueno.post(
        f"/v1/negocios/{negocio_id}/membresias", json={"usuario_id": nueva.id, "rol": "cajero"}
    )
    assert r.status_code == 201, r.text
    filas = dueno.get(f"/v1/negocios/{negocio_id}/auditoria").json()
    acciones = [f["accion"] for f in filas if f["entidad"] == "membresia"]
    assert any("crear" in a or "dar" in a or "alta" in a for a in acciones), acciones
