"""Quién puede hacer qué.

Los endpoints no preguntan "es admin?": piden un **permiso** (negocio) o una **capacidad**
(plataforma) con nombre. El catálogo vive acá, en código y versionado; la base solo guarda qué
rol tiene cuáles (`roles_permisos`). Mover el modelo a Casbin o a otro motor se hace cambiando
ESTE módulo (Doc 2, Roles y permisos).

Dos ámbitos distintos:
- **Negocio**: roles por negocio y sucursal (`membresias`). Un negocio nunca ve datos de otro.
- **Plataforma**: el equipo del servicio (`plataforma_miembros`): `admin`, `moderador` y
  `superadmin`. El superadmin es solo para pruebas y último recurso (D54): está apagado salvo
  que la config `superadmin_activo` lo encienda.
"""

from dataclasses import dataclass
from uuid import UUID

import asyncpg
from fastapi import Depends

from app.auth import Usuario, current_user
from app.db import get_pool
from app.services import config
from app.services.reglas import ReglaError

# --- Negocio ------------------------------------------------------------------------------

PERMISOS_NEGOCIO: frozenset[str] = frozenset(
    {
        "negocio.ver",
        "sucursales.gestionar",
        "usuarios.gestionar",  # alta y baja de membresías
        "roles.ver",
        "auditoria.ver",
        "config.editar",
        "productos.ver",
        "productos.editar",
        "precios.editar",
        "stock.ver",
        "stock.ajustar",
        "stock.ver_costos",
        "caja.cobrar",
        "caja.cerrar",
        "fiado.aprobar",
    }
)

# Roles de fábrica. La migración (`instalar_roles_de_fabrica`) guarda lo mismo en la base; una
# prueba de paridad exige que no se separen.
ROLES_DE_FABRICA: dict[str, frozenset[str]] = {
    "dueno": PERMISOS_NEGOCIO,
    "moderador": frozenset(
        {
            "negocio.ver",
            "roles.ver",
            "auditoria.ver",
            "productos.ver",
            "productos.editar",
            "precios.editar",
            "stock.ver",
            "stock.ajustar",
        }
    ),
    "cajero": frozenset(
        {"negocio.ver", "productos.ver", "stock.ver", "caja.cobrar", "caja.cerrar"}
    ),
}

# --- Plataforma ---------------------------------------------------------------------------

_ADMIN = frozenset(
    {
        "admin.acceder",
        "usuario.ver",
        "usuario.cambiar_rol",
        "negocios.ver",
        "catalogo.ver",
        "catalogo.editar",
        "catalogo.crear",
        "catalogo.sugerir",
        "catalogo.sugerencias.resolver",
        "conflictos.resolver",
        "config.editar",
        "auditoria.ver",
    }
)

CAPACIDADES_PLATAFORMA: dict[str, frozenset[str]] = {
    # El moderador de plataforma ve el catálogo y propone cambios: no entra a configuración.
    "moderador": frozenset({"admin.acceder", "catalogo.ver", "catalogo.sugerir"}),
    "admin": _ADMIN,
    "superadmin": _ADMIN | {"superadmin.todo"},
}


async def capacidades_de(pool: asyncpg.Pool, usuario: Usuario) -> frozenset[str]:
    """Capacidades de plataforma vigentes. Un superadmin con el interruptor apagado no tiene
    ninguna: es una cuenta de pruebas, no un acceso permanente."""
    rol = usuario.plataforma_rol
    if rol is None:
        return frozenset()
    if rol == "superadmin" and not await config.leer(pool, "superadmin_activo"):
        return frozenset()
    return CAPACIDADES_PLATAFORMA.get(rol, frozenset())


def exigir_plataforma(capacidad: str):
    """Dependencia de FastAPI: 403 si el usuario no tiene la capacidad de plataforma."""

    async def dependencia(
        user: Usuario = Depends(current_user), pool: asyncpg.Pool = Depends(get_pool)
    ) -> Usuario:
        if capacidad not in await capacidades_de(pool, user):
            raise ReglaError("sin_permiso")
        return user

    return dependencia


@dataclass
class Contexto:
    """Quién actúa, sobre qué negocio (y sucursal) y con qué rol."""

    usuario: Usuario
    negocio_id: UUID
    sucursal_id: UUID | None
    rol: str


async def permisos_en(
    pool: asyncpg.Pool, usuario_id: UUID, negocio_id: UUID, sucursal_id: UUID | None
) -> dict[str, frozenset[str]]:
    """Rol -> permisos que el usuario tiene en el negocio. Con sucursal, solo valen las
    membresías de todo el negocio o de esa sucursal; sin sucursal, cualquiera del negocio."""
    filas = await pool.fetch(
        """
        select r.clave, array_agg(distinct rp.permiso) as permisos
        from membresias m
        join roles r on r.id = m.rol_id and r.negocio_id = m.negocio_id
        join roles_permisos rp on rp.rol_id = r.id
        where m.usuario_id = $1 and m.negocio_id = $2
          and ($3::uuid is null or m.sucursal_id is null or m.sucursal_id = $3)
        group by r.clave
        """,
        usuario_id,
        negocio_id,
        sucursal_id,
    )
    return {f["clave"]: frozenset(f["permisos"]) for f in filas}


def exigir(permiso: str):
    """Dependencia de FastAPI para rutas con `{negocio_id}` en el path (y `?sucursal_id=`
    opcional): 403 si el usuario no tiene el permiso en ese negocio. Un negocio inexistente y
    uno ajeno dan el mismo 403: no se revela cuáles existen."""
    if permiso not in PERMISOS_NEGOCIO:
        raise ValueError(f"permiso desconocido: {permiso}")

    async def dependencia(
        negocio_id: UUID,
        sucursal_id: UUID | None = None,
        user: Usuario = Depends(current_user),
        pool: asyncpg.Pool = Depends(get_pool),
    ) -> Contexto:
        roles = await permisos_en(pool, user.id, negocio_id, sucursal_id)
        con_permiso = sorted(clave for clave, permisos in roles.items() if permiso in permisos)
        if not con_permiso:
            raise ReglaError("sin_permiso")
        if sucursal_id is not None and not await pool.fetchval(
            "select true from sucursales where id = $1 and negocio_id = $2", sucursal_id, negocio_id
        ):
            raise ReglaError("sucursal_invalida")
        return Contexto(user, negocio_id, sucursal_id, con_permiso[0])

    return dependencia
