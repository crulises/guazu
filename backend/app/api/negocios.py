"""Datos de UN negocio: roles, membresías y auditoría. Toda consulta corre en `tx_negocio`
(RLS por `app.negocio_id`) además de filtrar por negocio de forma explícita."""

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.db import get_pool
from app.services import auditoria
from app.services.permisos import Contexto, exigir
from app.services.reglas import ReglaError
from app.tenant import tx_negocio

router = APIRouter(prefix="/negocios/{negocio_id}", tags=["negocios"])


class RolOut(BaseModel):
    clave: str
    nombre: str | None
    de_fabrica: bool
    permisos: list[str]


class MembresiaOut(BaseModel):
    id: UUID
    usuario_id: UUID
    alias: str
    es_anonimo: bool
    sucursal_id: UUID | None
    rol: str


class MembresiaIn(BaseModel):
    usuario_id: UUID
    rol: str
    sucursal_id: UUID | None = None


class AuditoriaOut(BaseModel):
    id: int
    usuario_id: UUID | None
    rol_actuando: str | None
    accion: str
    entidad: str
    entidad_id: str | None
    antes: Any
    despues: Any
    nota: str | None
    creado_en: str


@router.get("/roles", response_model=list[RolOut])
async def roles(
    ctx: Contexto = Depends(exigir("roles.ver")), pool: asyncpg.Pool = Depends(get_pool)
) -> list[RolOut]:
    """Los roles del negocio y qué permisos tiene cada uno."""
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        filas = await conn.fetch(
            """
            select r.clave, r.nombre, r.de_fabrica,
                   coalesce(array_agg(rp.permiso order by rp.permiso)
                            filter (where rp.permiso is not null), '{}') as permisos
            from roles r
            left join roles_permisos rp on rp.rol_id = r.id
            where r.negocio_id = $1
            group by r.id order by r.clave
            """,
            ctx.negocio_id,
        )
    return [RolOut(**dict(f)) for f in filas]


@router.get("/membresias", response_model=list[MembresiaOut])
async def membresias(
    ctx: Contexto = Depends(exigir("usuarios.gestionar")), pool: asyncpg.Pool = Depends(get_pool)
) -> list[MembresiaOut]:
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        filas = await conn.fetch(
            """
            select m.id, m.usuario_id, u.alias, u.es_anonimo, m.sucursal_id, r.clave as rol
            from membresias m
            join usuarios u on u.id = m.usuario_id
            join roles r on r.id = m.rol_id
            where m.negocio_id = $1
            order by u.alias, r.clave
            """,
            ctx.negocio_id,
        )
    return [MembresiaOut(**dict(f)) for f in filas]


@router.post("/membresias", response_model=MembresiaOut, status_code=201)
async def dar_rol(
    body: MembresiaIn,
    ctx: Contexto = Depends(exigir("usuarios.gestionar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> MembresiaOut:
    """Asigna un rol a una persona (en todo el negocio o en una sucursal). La escritura de
    membresías está protegida por trigger: solo se habilita acá, con el permiso comprobado."""
    if body.usuario_id == ctx.usuario.id:
        raise ReglaError("no_cambiar_rol_propio")
    async with tx_negocio(pool, ctx.negocio_id, escritura="membresia") as conn:
        rol_id = await conn.fetchval(
            "select id from roles where negocio_id = $1 and clave = $2", ctx.negocio_id, body.rol
        )
        if rol_id is None:
            raise ReglaError("rol_invalido")
        if body.sucursal_id is not None and not await conn.fetchval(
            "select true from sucursales where id = $1 and negocio_id = $2",
            body.sucursal_id,
            ctx.negocio_id,
        ):
            raise ReglaError("sucursal_invalida")
        usuario = await conn.fetchrow(
            "select alias, es_anonimo from usuarios where id = $1", body.usuario_id
        )
        if usuario is None:
            raise ReglaError("usuario_inexistente")
        membresia_id = await conn.fetchval(
            """
            insert into membresias (usuario_id, negocio_id, sucursal_id, rol_id)
            values ($1, $2, $3, $4) returning id
            """,
            body.usuario_id,
            ctx.negocio_id,
            body.sucursal_id,
            rol_id,
        )
        await auditoria.registrar(
            conn,
            usuario_id=ctx.usuario.id,
            rol=ctx.rol,
            accion="membresia.crear",
            entidad="membresia",
            entidad_id=membresia_id,
            negocio_id=ctx.negocio_id,
            sucursal_id=body.sucursal_id,
            despues={"usuario_id": body.usuario_id, "rol": body.rol},
        )
    return MembresiaOut(
        id=membresia_id,
        usuario_id=body.usuario_id,
        alias=usuario["alias"],
        es_anonimo=usuario["es_anonimo"],
        sucursal_id=body.sucursal_id,
        rol=body.rol,
    )


@router.delete("/membresias/{membresia_id}", status_code=204)
async def quitar_rol(
    membresia_id: UUID,
    ctx: Contexto = Depends(exigir("usuarios.gestionar")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> None:
    async with tx_negocio(pool, ctx.negocio_id, escritura="membresia") as conn:
        m = await conn.fetchrow(
            """
            select m.usuario_id, m.sucursal_id, r.clave as rol
            from membresias m join roles r on r.id = m.rol_id
            where m.id = $1 and m.negocio_id = $2
            """,
            membresia_id,
            ctx.negocio_id,
        )
        if m is None:
            raise ReglaError("membresia_inexistente")
        if m["usuario_id"] == ctx.usuario.id:
            raise ReglaError("no_cambiar_rol_propio")
        await conn.execute("delete from membresias where id = $1", membresia_id)
        await auditoria.registrar(
            conn,
            usuario_id=ctx.usuario.id,
            rol=ctx.rol,
            accion="membresia.quitar",
            entidad="membresia",
            entidad_id=membresia_id,
            negocio_id=ctx.negocio_id,
            sucursal_id=m["sucursal_id"],
            antes={"usuario_id": m["usuario_id"], "rol": m["rol"]},
        )


@router.get("/auditoria", response_model=list[AuditoriaOut])
async def ver_auditoria(
    limite: int = Query(default=50, ge=1, le=500),
    ctx: Contexto = Depends(exigir("auditoria.ver")),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[AuditoriaOut]:
    async with tx_negocio(pool, ctx.negocio_id) as conn:
        filas = await conn.fetch(
            """
            select id, usuario_id, rol_actuando, accion, entidad, entidad_id,
                   antes::text as antes, despues::text as despues, nota, creado_en::text
            from auditoria where negocio_id = $1 order by id desc limit $2
            """,
            ctx.negocio_id,
            limite,
        )
    return [_auditoria(f) for f in filas]


def _auditoria(f: asyncpg.Record) -> AuditoriaOut:
    import json

    d = dict(f)
    for k in ("antes", "despues"):
        d[k] = json.loads(d[k]) if d[k] is not None else None
    return AuditoriaOut(**d)
