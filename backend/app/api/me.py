from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import Usuario, current_user
from app.db import get_pool
from app.services import config
from app.services.permisos import capacidades_de
from app.services.ratelimit import limitar

router = APIRouter(prefix="/me", tags=["me"])


class MembresiaOut(BaseModel):
    negocio_id: UUID
    sucursal_id: UUID | None
    rol: str
    permisos: list[str]


class PlataformaOut(BaseModel):
    rol: str
    capacidades: list[str]


class MeOut(BaseModel):
    id: UUID
    alias: str
    email: str | None
    es_anonimo: bool
    plataforma: PlataformaOut | None
    membresias: list[MembresiaOut]


@router.get("", response_model=MeOut)
async def yo(
    user: Usuario = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)
) -> MeOut:
    """Quién soy y qué puedo hacer: la app muestra u oculta cosas según esto, pero **el backend
    autoriza cada pedido**: lo de acá es solo informativo."""
    limite = int(await config.leer(pool, "sesion_pedidos_por_minuto"))
    limitar(f"sesion:{user.id}", limite, 60)
    filas = await pool.fetch(
        """
        select m.negocio_id, m.sucursal_id, r.clave as rol,
               coalesce(array_agg(rp.permiso order by rp.permiso)
                        filter (where rp.permiso is not null), '{}') as permisos
        from membresias m
        join roles r on r.id = m.rol_id and r.negocio_id = m.negocio_id
        left join roles_permisos rp on rp.rol_id = r.id
        where m.usuario_id = $1
        group by m.id, r.clave
        order by m.created_at, r.clave
        """,
        user.id,
    )
    capacidades = await capacidades_de(pool, user)
    return MeOut(
        id=user.id,
        alias=user.alias,
        email=user.email,
        es_anonimo=user.es_anonimo,
        plataforma=PlataformaOut(rol=user.plataforma_rol, capacidades=sorted(capacidades))
        if user.plataforma_rol and capacidades
        else None,
        membresias=[MembresiaOut(**dict(f)) for f in filas],
    )
