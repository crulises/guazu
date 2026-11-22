"""Proxy de auth: el cliente habla solo con el backend, nunca con el proveedor de auth.

El backend pide la sesión al proveedor (GoTrue) y la devuelve tal cual. La validación de los
tokens en cada request sigue en `app/auth.py`. Abierto a cualquiera (el escáner es público),
con cupo por IP: se cuentan todos los intentos.
"""

import asyncpg
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.auth import bearer
from app.config import get_settings
from app.db import get_pool
from app.services import config
from app.services.ratelimit import ip_cliente, limitar
from app.services.reglas import ReglaError

router = APIRouter(prefix="/auth", tags=["auth"])


class Sesion(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str


class CredencialesIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=6, max_length=72)


class VincularIn(CredencialesIn):
    refresh_token: str


async def get_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


async def pedir(
    http: httpx.AsyncClient,
    metodo: str,
    path: str,
    body: dict,
    *,
    token: str | None = None,
    errores_4xx: str = "sesion_invalida",
) -> dict:
    """Llama al proveedor de auth. `errores_4xx` es la regla que se informa si rechaza."""
    s = get_settings()
    if not s.auth_url or not s.auth_api_key:
        raise ReglaError("auth_no_configurada")
    cabeceras = {"apikey": s.auth_api_key}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    try:
        r = await http.request(
            metodo, f"{s.auth_url}{path}", json=body, headers=cabeceras, timeout=10
        )
    except httpx.HTTPError as e:
        raise ReglaError("proveedor_no_disponible") from e
    if r.status_code in (400, 401, 403, 422):
        if r.status_code == 422 and "already" in r.text.lower() and "email" in r.text.lower():
            raise ReglaError("email_en_uso")
        raise ReglaError(errores_4xx)
    if r.status_code >= 400:
        raise ReglaError("proveedor_no_disponible")
    return r.json()


def _sesion(d: dict) -> Sesion:
    return Sesion(
        access_token=d["access_token"], refresh_token=d["refresh_token"], expires_in=d["expires_in"]
    )


async def _limitar(request: Request, pool: asyncpg.Pool, accion: str, clave_config: str) -> None:
    limite = int(await config.leer(pool, clave_config))
    limitar(f"{accion}:{ip_cliente(request)}", limite, 3600)


@router.post("/anonymous", response_model=Sesion)
async def sesion_anonima(
    request: Request,
    http: httpx.AsyncClient = Depends(get_http),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Sesion:
    """Crea un usuario anónimo y devuelve su sesión (la app lo llama en el primer arranque)."""
    await _limitar(request, pool, "anonymous", "auth_altas_por_hora_ip")
    return _sesion(await pedir(http, "POST", "/signup", {}))


@router.post("/refresh", response_model=Sesion)
async def renovar_sesion(
    request: Request,
    body: RefreshIn,
    http: httpx.AsyncClient = Depends(get_http),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Sesion:
    await _limitar(request, pool, "refresh", "auth_refresh_por_hora_ip")
    d = await pedir(
        http, "POST", "/token?grant_type=refresh_token", {"refresh_token": body.refresh_token}
    )
    return _sesion(d)


@router.post("/login", response_model=Sesion)
async def iniciar_sesion(
    request: Request,
    body: CredencialesIn,
    http: httpx.AsyncClient = Depends(get_http),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Sesion:
    """Email y contraseña de una cuenta ya registrada."""
    await _limitar(request, pool, "login", "auth_login_por_hora_ip")
    d = await pedir(
        http,
        "POST",
        "/token?grant_type=password",
        {"email": body.email, "password": body.password},
        errores_4xx="credenciales_invalidas",
    )
    return _sesion(d)


@router.post("/vincular", response_model=Sesion)
async def vincular_cuenta(
    request: Request,
    body: VincularIn,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    http: httpx.AsyncClient = Depends(get_http),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Sesion:
    """Convierte la cuenta anónima en una registrada con email y contraseña, **conservando el
    mismo id** (por eso lo ya cargado queda atado a la persona). Devuelve la sesión nueva: la
    anterior sigue diciendo "anónimo" hasta que se renueva."""
    if creds is None:
        raise ReglaError("no_autenticado")
    await _limitar(request, pool, "vincular", "auth_login_por_hora_ip")
    await pedir(
        http,
        "PUT",
        "/user",
        {"email": body.email, "password": body.password},
        token=creds.credentials,
    )
    d = await pedir(
        http, "POST", "/token?grant_type=refresh_token", {"refresh_token": body.refresh_token}
    )
    return _sesion(d)
