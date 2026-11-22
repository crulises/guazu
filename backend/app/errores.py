"""Manejo global de errores: una violación de integridad, una regla violada o una falla
inesperada responde con la regla (o una referencia), nunca con un 500 mudo.

Los 500 sin manejar salen de `ServerErrorMiddleware`, por fuera del CORS: el navegador los
muestra como "Failed to fetch". Por eso acá cada error se arma con las cabeceras CORS.
"""

import logging
import uuid

import asyncpg
import pydantic_core
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.services import reglas

log = logging.getLogger("guazu")


def _cors(request: Request) -> dict[str, str]:
    permitidos = {o.strip() for o in get_settings().cors_origins.split(",") if o.strip()}
    origen = request.headers.get("origin")
    if origen and origen in permitidos:
        return {"Access-Control-Allow-Origin": origen, "Vary": "Origin"}
    return {}


async def _editados(request: Request) -> dict[str, str]:
    try:
        return await reglas.mensajes(request.app.state.pool)
    except Exception:  # los mensajes editados nunca pueden tapar el error original
        return {}


async def regla_violada(request: Request, exc: reglas.ReglaError) -> JSONResponse:
    extra = dict(exc.extra)
    cabeceras = _cors(request)
    if (espera := extra.pop("retry_after", None)) is not None:
        cabeceras["Retry-After"] = str(espera)
    cuerpo = reglas.detalle(exc.regla, await _editados(request), **extra)
    return JSONResponse({"detail": cuerpo}, status_code=exc.regla.status, headers=cabeceras)


async def violacion_de_integridad(request: Request, exc: asyncpg.PostgresError) -> JSONResponse:
    regla = reglas.regla_de(exc)
    restriccion = getattr(exc, "constraint_name", None)
    log.warning(
        "regla %s (%s) en %s %s: %s",
        regla.codigo,
        restriccion,
        request.method,
        request.url.path,
        exc,
    )
    cuerpo = reglas.detalle(regla, await _editados(request), restriccion=restriccion)
    return JSONResponse({"detail": cuerpo}, status_code=regla.status, headers=_cors(request))


async def pedido_mal_formado(request: Request, exc: RequestValidationError) -> JSONResponse:
    """El cuerpo o los parámetros del pedido no cumplen el esquema."""
    campos = [
        {"campo": ".".join(str(p) for p in e["loc"]), "problema": e["msg"]} for e in exc.errors()
    ]
    cuerpo = reglas.detalle(reglas.REGLAS["dato_invalido"], await _editados(request), campos=campos)
    return JSONResponse({"detail": cuerpo}, status_code=422, headers=_cors(request))


async def dato_mal_formado(request: Request, exc: pydantic_core.ValidationError) -> JSONResponse:
    """Datos ya guardados que el modelo actual no acepta."""
    log.warning("dato inválido en %s %s: %s", request.method, request.url.path, exc)
    problemas = reglas.problemas(exc)
    cuerpo = reglas.detalle(
        reglas.REGLAS["dato_invalido"],
        await _editados(request),
        campos=problemas,
        detalle="; ".join(f"{p['campo']} {p['problema']}" for p in problemas),
    )
    return JSONResponse({"detail": cuerpo}, status_code=422, headers=_cors(request))


async def error_inesperado(request: Request, exc: Exception) -> JSONResponse:
    referencia = uuid.uuid4().hex[:8]
    log.exception("error interno %s en %s %s", referencia, request.method, request.url.path)
    cuerpo = reglas.detalle(
        reglas.REGLAS["error_interno"], await _editados(request), referencia=referencia
    )
    return JSONResponse({"detail": cuerpo}, status_code=500, headers=_cors(request))


def registrar(app: FastAPI) -> None:
    app.add_exception_handler(reglas.ReglaError, regla_violada)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, pedido_mal_formado)  # type: ignore[arg-type]
    app.add_exception_handler(asyncpg.CheckViolationError, violacion_de_integridad)  # type: ignore[arg-type]
    app.add_exception_handler(asyncpg.UniqueViolationError, violacion_de_integridad)  # type: ignore[arg-type]
    app.add_exception_handler(asyncpg.RaiseError, violacion_de_integridad)  # type: ignore[arg-type]
    app.add_exception_handler(pydantic_core.ValidationError, dato_mal_formado)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, error_inesperado)
