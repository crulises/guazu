import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.ratelimit import limitador
from tests import db


def make_token(sub: str | None = None, *, email: str | None = None, anonimo: bool = True) -> str:
    """JWT HS256 firmado como el proveedor (los de GoTrue real se prueban en test_auth)."""
    s = get_settings()
    now = int(time.time())
    claims = {
        "sub": sub or str(uuid.uuid4()),
        "aud": s.jwt_audience,
        "iat": now,
        "exp": now + 3600,
        "is_anonymous": anonimo,
    }
    if email:
        claims["email"] = email
    return jwt.encode(claims, s.jwt_secret, algorithm="HS256")


@pytest.fixture(scope="session")
def client():
    # Postgres real (el del Supabase CLI), sin mocks de base.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(autouse=True)
def _limitador_limpio():
    """El rate limit vive en memoria: que un test no gaste el cupo de otro."""
    limitador.reiniciar()


class Persona:
    """Un usuario de prueba: se crea con su primer pedido (alta perezosa) y se limpia solo."""

    def __init__(self, client: TestClient, registrado: bool = False):
        self.auth_id = str(uuid.uuid4())
        self.token = make_token(self.auth_id)
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.client = client
        self.id = client.get("/v1/me", headers=self.headers).json()["id"]
        if registrado:
            db.marcar_registrado(self.id)

    def get(self, ruta, **kw):
        return self.client.get(ruta, headers=self.headers, **kw)

    def post(self, ruta, **kw):
        return self.client.post(ruta, headers=self.headers, **kw)

    def patch(self, ruta, **kw):
        return self.client.patch(ruta, headers=self.headers, **kw)

    def delete(self, ruta, **kw):
        return self.client.delete(ruta, headers=self.headers, **kw)


@pytest.fixture
def persona(client):
    creadas: list[Persona] = []

    def nueva(registrado: bool = False) -> Persona:
        p = Persona(client, registrado)
        creadas.append(p)
        return p

    yield nueva
    if creadas:
        db.borrar_usuarios([p.id for p in creadas])


@pytest.fixture
def negocio():
    """Un negocio con sucursal y roles de fabrica. Devuelve (negocio_id, sucursal_id)."""
    creados = []

    def nuevo():
        n = db.crear_negocio()
        creados.append(n[0])
        return n

    yield nuevo
    for negocio_id in creados:
        db.borrar_negocio(negocio_id)
