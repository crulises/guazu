import asyncpg

from app.config import get_settings
from app.errores import violacion_de_integridad
from app.services import reglas


def test_salud_informa_version_y_base(client):
    r = client.get("/v1/salud")
    assert r.status_code == 200
    j = r.json()
    assert j["estado"] == "ok" and j["base"] == "ok"
    assert j["version"] == get_settings().app_version
    assert {"commit", "compilado"} <= set(j)


def test_ruta_inexistente_es_404_no_500(client):
    assert client.get("/v1/no-existe").status_code == 404


def test_detalle_usa_mensaje_editado_y_extra():
    regla = reglas.REGLAS["dato_invalido"]
    d = reglas.detalle(regla, {"dato_invalido": "Texto propio"}, referencia="abc")
    assert d["mensaje"] == "Texto propio" and d["referencia"] == "abc"
    assert reglas.detalle(regla)["mensaje"] == regla.mensaje


def test_constraint_desconocido_cae_en_dato_invalido():
    exc = asyncpg.CheckViolationError("x")
    assert reglas.regla_de(exc).codigo == "dato_invalido"


def test_unique_es_conflicto_409():
    assert reglas.regla_de(asyncpg.UniqueViolationError("x")).status == 409


def test_500_sale_con_cors_y_referencia(client):
    """Un error inesperado nunca es mudo: lleva regla, referencia y cabeceras CORS."""
    from app.main import app

    @app.get("/v1/_explota")
    async def _explota():  # solo en el test
        raise RuntimeError("boom")

    origen = get_settings().cors_origins.split(",")[0]
    r = client.get("/v1/_explota", headers={"Origin": origen})
    assert r.status_code == 500
    assert r.json()["detail"]["codigo"] == "error_interno"
    assert r.json()["detail"]["referencia"]
    assert r.headers.get("access-control-allow-origin") == origen


def test_violacion_de_integridad_importable():
    assert callable(violacion_de_integridad)
