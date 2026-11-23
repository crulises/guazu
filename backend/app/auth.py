"""Validación del JWT del proveedor de auth y alta perezosa del usuario."""

from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import asyncpg
import jwt
from fastapi import Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.db import get_pool
from app.services.reglas import ReglaError

bearer = HTTPBearer(auto_error=False)


@dataclass
class Usuario:
    id: UUID
    auth_id: UUID
    alias: str
    es_anonimo: bool
    estado: str = "activo"
    email: str | None = None
    # Rol del ámbito de plataforma (`admin`, `moderador`, `superadmin`) o None.
    plataforma_rol: str | None = None


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    # Cachea las claves públicas; se refresca solo si aparece un `kid` desconocido.
    return jwt.PyJWKClient(url)


def decode_token(token: str) -> dict:
    """Valida el JWT. Asimétrico (ES256/RS256) contra el JWKS del proveedor de auth;
    HS256 con secreto compartido como alternativa."""
    s = get_settings()
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg == "HS256":
            key, algs = s.jwt_secret, ["HS256"]
        elif alg in ("ES256", "RS256") and s.jwks_url:
            key = _jwks_client(s.jwks_url).get_signing_key_from_jwt(token).key
            algs = [alg]
        else:
            raise ReglaError("token_invalido")
        return jwt.decode(token, key, algorithms=algs, audience=s.jwt_audience)
    except jwt.PyJWTError as e:
        raise ReglaError("token_invalido") from e


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Usuario:
    if creds is None:
        raise ReglaError("no_autenticado")
    # sync (la primera vez baja el JWKS por red): fuera del event loop.
    claims = await run_in_threadpool(decode_token, creds.credentials)
    try:
        auth_id = UUID(claims["sub"])
    except (KeyError, ValueError) as e:
        raise ReglaError("token_invalido") from e

    # `is_anonymous` y `email` vienen del proveedor (GoTrue). Sin el claim, se es anónimo
    # salvo que haya email.
    email = claims.get("email") or None
    es_anonimo = bool(claims.get("is_anonymous", email is None))
    # Una vez registrada, la cuenta no vuelve a ser anónima: un token anónimo viejo (todavía
    # vigente tras vincular el email) no debe pisar el estado.
    row = await pool.fetchrow(
        """
        insert into usuarios (auth_id, alias, email, es_anonimo, anonimo_auth_id)
        values ($1, $2, $3, $4, case when $4::boolean then $1::uuid end)
        on conflict (auth_id) do update
            set email = coalesce(excluded.email, usuarios.email),
                es_anonimo = usuarios.es_anonimo and excluded.es_anonimo
        returning id, auth_id, alias, email, es_anonimo, estado,
                  (select pm.rol from plataforma_miembros pm
                    where pm.usuario_id = usuarios.id) as plataforma_rol
        """,
        auth_id,
        f"anon-{str(auth_id)[:6]}",
        email,
        es_anonimo,
    )
    usuario = Usuario(**dict(row))
    if usuario.estado == "suspendido":
        # 403 y no 401: un 401 haría que la app "empiece de nuevo" con otra cuenta anónima.
        raise ReglaError("cuenta_suspendida")
    return usuario
