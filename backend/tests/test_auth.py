"""Auth contra el GoTrue real del Supabase CLI: anonimo, vinculacion, login y renovacion.
Al menos un test usa un token del proveedor real (no firmado por nosotros): el CLI firma con
ES256 y un test con HS256 propio no lo habria detectado."""

import uuid

import jwt

from app.services.ratelimit import limitador
from tests import db
from tests.conftest import make_token


def _anonima(client):
    r = client.post("/v1/auth/anonymous")
    assert r.status_code == 200, r.text
    return r.json()


def _id_de(sesion):
    return jwt.decode(sesion["access_token"], options={"verify_signature": False})["sub"]


def test_sesion_anonima_real_y_alta_perezosa(client):
    sesion = _anonima(client)
    alg = jwt.get_unverified_header(sesion["access_token"])["alg"]
    assert alg in ("ES256", "RS256", "HS256")
    r = client.get("/v1/me", headers={"Authorization": f"Bearer {sesion['access_token']}"})
    assert r.status_code == 200
    me = r.json()
    assert me["es_anonimo"] is True and me["email"] is None
    assert me["plataforma"] is None and me["membresias"] == []
    assert me["alias"].startswith("anon-")
    db.borrar_usuarios([me["id"]])


def test_vincular_conserva_el_id_y_registra_la_cuenta(client):
    sesion = _anonima(client)
    auth_id = _id_de(sesion)
    headers = {"Authorization": f"Bearer {sesion['access_token']}"}
    antes = client.get("/v1/me", headers=headers).json()
    email = f"{uuid.uuid4().hex[:10]}@test.local"

    r = client.post(
        "/v1/auth/vincular",
        headers=headers,
        json={
            "email": email,
            "password": "clave-segura-1",
            "refresh_token": sesion["refresh_token"],
        },
    )
    assert r.status_code == 200, r.text
    nueva = r.json()
    assert _id_de(nueva) == auth_id  # el mismo id: lo cargado sigue atado a la persona

    despues = client.get(
        "/v1/me", headers={"Authorization": f"Bearer {nueva['access_token']}"}
    ).json()
    assert despues["id"] == antes["id"]
    assert despues["es_anonimo"] is False and despues["email"] == email

    # El token anonimo viejo sigue vigente un rato: no debe volver a marcar la cuenta anonima.
    client.get("/v1/me", headers=headers)
    assert (
        client.get("/v1/me", headers={"Authorization": f"Bearer {nueva['access_token']}"}).json()[
            "es_anonimo"
        ]
        is False
    )

    # Login con el email y renovacion.
    login = client.post("/v1/auth/login", json={"email": email, "password": "clave-segura-1"})
    assert login.status_code == 200 and _id_de(login.json()) == auth_id
    ref = client.post("/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert ref.status_code == 200
    db.borrar_usuarios([antes["id"]])


def test_login_con_clave_mala_explica_la_regla(client):
    r = client.post("/v1/auth/login", json={"email": "nadie@test.local", "password": "incorrecta"})
    assert r.status_code == 401
    assert r.json()["detail"]["codigo"] == "credenciales_invalidas"


def test_email_repetido_al_vincular_es_409(client):
    email = f"{uuid.uuid4().hex[:10]}@test.local"
    ids = []
    for esperado in (200, 409):
        sesion = _anonima(client)
        headers = {"Authorization": f"Bearer {sesion['access_token']}"}
        ids.append(client.get("/v1/me", headers=headers).json()["id"])
        r = client.post(
            "/v1/auth/vincular",
            headers=headers,
            json={
                "email": email,
                "password": "clave-segura-1",
                "refresh_token": sesion["refresh_token"],
            },
        )
        assert r.status_code == esperado, r.text
    assert r.json()["detail"]["codigo"] == "email_en_uso"
    db.borrar_usuarios(ids)


def test_vincular_exige_sesion(client):
    r = client.post(
        "/v1/auth/vincular",
        json={"email": "a@test.local", "password": "clave-segura-1", "refresh_token": "x"},
    )
    assert r.status_code == 401 and r.json()["detail"]["codigo"] == "no_autenticado"


# --- tokens ---------------------------------------------------------------------------------


def test_sin_token_y_con_token_roto(client):
    r = client.get("/v1/me")
    assert r.status_code == 401 and r.json()["detail"]["codigo"] == "no_autenticado"
    r = client.get("/v1/me", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401 and r.json()["detail"]["codigo"] == "token_invalido"


def test_token_hs256_firmado_con_otro_secreto_se_rechaza(client):
    malo = jwt.encode(
        {"sub": str(uuid.uuid4()), "aud": "authenticated", "exp": 9999999999},
        "otro-secreto-que-no-es-el-del-proveedor-123456",
        algorithm="HS256",
    )
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {malo}"}).status_code == 401


def test_token_con_audiencia_equivocada_se_rechaza(client):
    from app.config import get_settings

    malo = jwt.encode(
        {"sub": str(uuid.uuid4()), "aud": "otra", "exp": 9999999999},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {malo}"}).status_code == 401


def test_cuenta_suspendida_es_403_y_no_401(client, persona):
    p = persona()
    db.sql("update usuarios set estado = 'suspendido' where id = $1::uuid", p.id)
    r = p.get("/v1/me")
    assert r.status_code == 403 and r.json()["detail"]["codigo"] == "cuenta_suspendida"


# --- rate limit -----------------------------------------------------------------------------


def test_rate_limit_en_el_alta_anonima(client):
    db.poner_config("auth_altas_por_hora_ip", "2")
    try:
        ids = []
        for esperado in (200, 200, 429):
            r = client.post("/v1/auth/anonymous")
            assert r.status_code == esperado, r.text
            if r.status_code == 200:
                ids.append(_id_de(r.json()))
        assert r.json()["detail"]["codigo"] == "demasiados_intentos"
        assert int(r.headers["retry-after"]) >= 1
    finally:
        db.quitar_config("auth_altas_por_hora_ip")


def test_rate_limit_por_sesion(client, persona):
    p = persona()
    db.poner_config("sesion_pedidos_por_minuto", "3")
    limitador.reiniciar()  # crear la persona ya gasto un pedido
    try:
        codigos = [p.get("/v1/me").status_code for _ in range(5)]
        assert codigos[:3] == [200, 200, 200] and 429 in codigos[3:]
        # Otra sesion no se ve afectada por el cupo de la primera.
        assert persona().get("/v1/me").status_code == 200
    finally:
        db.quitar_config("sesion_pedidos_por_minuto")


def test_token_sin_claim_de_anonimo_con_email_es_registrado(client):
    token = make_token(email="x@test.local", anonimo=False)
    r = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["es_anonimo"] is False
    db.borrar_usuarios([r.json()["id"]])
