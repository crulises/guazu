"""API de administración de la plataforma (`/v1/admin`). Cada ruta pide una capacidad de
plataforma; el rol vive en Postgres, no en el JWT: revocar vale en el siguiente pedido."""

import json
from datetime import datetime
from typing import Literal
from uuid import UUID

import asyncpg
import httpx
import jwt
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.api.auth import CredencialesIn, Sesion, _limitar, _sesion, get_http, pedir
from app.auth import Usuario
from app.db import get_pool
from app.services import auditoria, catalogo
from app.services.permisos import CAPACIDADES_PLATAFORMA, capacidades_de, exigir_plataforma
from app.services.reglas import ReglaError

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=Sesion)
async def login_admin(
    request: Request,
    body: CredencialesIn,
    http: httpx.AsyncClient = Depends(get_http),
    pool: asyncpg.Pool = Depends(get_pool),
) -> Sesion:
    """Email y contraseña de GoTrue, **solo** para quien tenga un rol de plataforma: si no, 403
    y no sale ningún token. Un anónimo promovido no entra: no tiene credenciales."""
    await _limitar(request, pool, "admin-login", "auth_login_por_hora_ip")
    d = await pedir(
        http,
        "POST",
        "/token?grant_type=password",
        {"email": body.email, "password": body.password},
        errores_4xx="credenciales_invalidas",
    )
    sub = jwt.decode(d["access_token"], options={"verify_signature": False})["sub"]
    fila = await pool.fetchrow(
        """
        select u.id, u.auth_id, u.alias, u.email, u.es_anonimo, u.estado, pm.rol as plataforma_rol
        from usuarios u left join plataforma_miembros pm on pm.usuario_id = u.id
        where u.auth_id = $1::uuid
        """,
        sub,
    )
    if fila is None or not await capacidades_de(pool, Usuario(**dict(fila))):
        raise ReglaError("sin_permiso")
    return _sesion(d)


class UsuarioOut(BaseModel):
    id: UUID
    alias: str
    email: str | None
    es_anonimo: bool
    estado: str
    plataforma_rol: str | None


@router.get("/usuarios", response_model=list[UsuarioOut])
async def usuarios(
    tipo: Literal["anonimo", "registrado"] | None = None,
    q: str | None = Query(default=None, max_length=100),
    limite: int = Query(default=50, ge=1, le=200),
    _: Usuario = Depends(exigir_plataforma("usuario.ver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[UsuarioOut]:
    filas = await pool.fetch(
        """
        select u.id, u.alias, u.email, u.es_anonimo, u.estado, pm.rol as plataforma_rol
        from usuarios u left join plataforma_miembros pm on pm.usuario_id = u.id
        where ($1::text is null or (u.es_anonimo = ($1 = 'anonimo')))
          and ($2::text is null or u.alias ilike '%' || $2 || '%' or u.email ilike '%' || $2 || '%')
        order by u.created_at desc limit $3
        """,
        tipo,
        q,
        limite,
    )
    return [UsuarioOut(**dict(f)) for f in filas]


class RolPlataformaIn(BaseModel):
    rol: Literal["admin", "moderador", "superadmin"] | None  # None = quitar


@router.post("/usuarios/{usuario_id}/rol-plataforma", response_model=UsuarioOut)
async def cambiar_rol_plataforma(
    usuario_id: UUID,
    body: RolPlataformaIn,
    actor: Usuario = Depends(exigir_plataforma("usuario.cambiar_rol")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> UsuarioOut:
    """Asigna o quita un rol de plataforma. Reglas (código, no filas): nadie cambia el propio
    rol, el objetivo tiene que estar registrado, y solo un superadmin toca a un superadmin."""
    if usuario_id == actor.id:
        raise ReglaError("no_cambiar_rol_propio")
    async with pool.acquire() as conn, conn.transaction():
        objetivo = await conn.fetchrow(
            """
            select u.id, u.alias, u.email, u.es_anonimo, u.estado, pm.rol as plataforma_rol
            from usuarios u left join plataforma_miembros pm on pm.usuario_id = u.id
            where u.id = $1
            """,
            usuario_id,
        )
        if objetivo is None:
            raise ReglaError("usuario_inexistente")
        antes = objetivo["plataforma_rol"]
        if "superadmin" in (body.rol, antes) and actor.plataforma_rol != "superadmin":
            raise ReglaError("solo_superadmin")
        await conn.execute("select set_config('app.plataforma_write', 'on', true)")
        if body.rol is None:
            await conn.execute("delete from plataforma_miembros where usuario_id = $1", usuario_id)
        else:
            await conn.execute(
                """
                insert into plataforma_miembros (usuario_id, rol) values ($1, $2)
                on conflict (usuario_id) do update set rol = excluded.rol, desde = now()
                """,
                usuario_id,
                body.rol,
            )
        await auditoria.registrar(
            conn,
            usuario_id=actor.id,
            rol=actor.plataforma_rol or "plataforma",
            accion="plataforma_rol.cambiar",
            entidad="plataforma_rol",
            entidad_id=usuario_id,
            antes={"rol": antes},
            despues={"rol": body.rol},
        )
    return UsuarioOut(**{**dict(objetivo), "plataforma_rol": body.rol})


@router.get("/auditoria")
async def auditoria_plataforma(
    entidad: str | None = None,
    negocio_id: UUID | None = None,
    limite: int = Query(default=50, ge=1, le=500),
    _: Usuario = Depends(exigir_plataforma("auditoria.ver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[dict]:
    """Toda la auditoría (la de la plataforma y la de cualquier negocio), filtrable."""
    filas = await pool.fetch(
        """
        select id, negocio_id, usuario_id, rol_actuando, accion, entidad, entidad_id,
               antes::text as antes, despues::text as despues, nota, creado_en::text
        from auditoria
        where ($1::text is null or entidad = $1)
          and ($2::uuid is null or negocio_id = $2)
        order by id desc limit $3
        """,
        entidad,
        negocio_id,
        limite,
    )
    salida = []
    for f in filas:
        d = dict(f)
        for k in ("antes", "despues"):
            d[k] = json.loads(d[k]) if d[k] is not None else None
        d["id"] = int(d["id"])
        salida.append(d)
    return salida


@router.get("/capacidades")
async def catalogo_de_capacidades(
    _: Usuario = Depends(exigir_plataforma("admin.acceder")),
) -> dict[str, list[str]]:
    """Qué capacidades tiene cada rol de plataforma (para la pantalla de roles del panel)."""
    return {rol: sorted(caps) for rol, caps in CAPACIDADES_PLATAFORMA.items()}


class ConflictoOut(BaseModel):
    id: UUID
    ean: str
    nombre: str | None
    campo: str
    valor_a: str
    fuente_a: str
    valor_b: str
    fuente_b: str
    estado: str
    elegido: str | None
    resuelto_por: UUID | None
    resuelto_en: datetime | None
    created_at: datetime


@router.get("/catalogo/conflictos", response_model=list[ConflictoOut])
async def conflictos_del_catalogo(
    estado: Literal["pendiente", "resuelto"] | None = "pendiente",
    ean: str | None = Query(default=None, max_length=14),
    limite: int = Query(default=50, ge=1, le=200),
    _: Usuario = Depends(exigir_plataforma("catalogo.ver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[ConflictoOut]:
    """Desacuerdos entre fuentes: `a` es lo que hay en el catálogo, `b` lo que trae la otra."""
    ean_normal = catalogo.ean_valido(ean) if ean else None
    filas = await catalogo.listar_conflictos(pool, estado, limite, ean_normal)
    return [ConflictoOut(**f) for f in filas]


class ResolverConflictoIn(BaseModel):
    elegido: Literal["a", "b"]


@router.post("/catalogo/conflictos/{conflicto_id}/resolver", response_model=ConflictoOut)
async def resolver_conflicto(
    conflicto_id: UUID,
    body: ResolverConflictoIn,
    actor: Usuario = Depends(exigir_plataforma("conflictos.resolver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ConflictoOut:
    """`a` deja el catálogo como está, `b` toma el valor de la otra fuente. El campo queda
    bloqueado: ningún ETL lo vuelve a pisar. Queda auditado."""
    fila = await catalogo.resolver_conflicto(
        pool, conflicto_id, body.elegido, actor.id, actor.plataforma_rol or "plataforma"
    )
    return ConflictoOut(**fila)
