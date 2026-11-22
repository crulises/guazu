import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    # Postgres real (el del Supabase CLI), sin mocks de base.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
