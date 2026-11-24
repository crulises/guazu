"""Acceso directo a la base desde los tests (para preparar y limpiar estado)."""

import asyncio
import uuid
from contextlib import asynccontextmanager

import asyncpg

from app.config import get_settings


@asynccontextmanager
async def conexion():
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        yield conn
    finally:
        await conn.close()


def correr(coro):
    return asyncio.run(coro)


def sql(query: str, *args):
    async def run():
        async with conexion() as conn:
            return await conn.execute(query, *args)

    return correr(run())


def fetch(query: str, *args):
    async def run():
        async with conexion() as conn:
            return await conn.fetch(query, *args)

    return correr(run())


def fetchval(query: str, *args):
    async def run():
        async with conexion() as conn:
            return await conn.fetchval(query, *args)

    return correr(run())


def escribir(variable: str, *consultas: tuple):
    """Ejecuta consultas con una escritura protegida habilitada, solo en esa transaccion
    (como lo hace el backend o un target del Makefile)."""

    async def run():
        async with conexion() as conn, conn.transaction():
            await conn.execute("select set_config($1, 'on', true)", f"app.{variable}_write")
            for q, *args in consultas:
                await conn.execute(q, *args)

    correr(run())


def crear_negocio(nombre: str | None = None) -> tuple[uuid.UUID, uuid.UUID]:
    """Un negocio con una sucursal y los roles de fabrica. Devuelve (negocio_id, sucursal_id)."""
    nombre = nombre or f"test-{uuid.uuid4().hex[:8]}"

    async def run():
        async with conexion() as conn, conn.transaction():
            negocio = await conn.fetchval(
                "insert into negocios (nombre) values ($1) returning id", nombre
            )
            sucursal = await conn.fetchval(
                "insert into sucursales (negocio_id, nombre) values ($1, 'Central') returning id",
                negocio,
            )
            await conn.execute("select instalar_roles_de_fabrica($1)", negocio)
            return negocio, sucursal

    return correr(run())


def dar_rol(usuario_id, negocio_id, clave: str, sucursal_id=None) -> None:
    escribir(
        "membresia",
        (
            """
            insert into membresias (usuario_id, negocio_id, sucursal_id, rol_id)
            select $1::uuid, $2::uuid, $3::uuid, id from roles
            where negocio_id = $2::uuid and clave = $4
            """,
            usuario_id,
            negocio_id,
            sucursal_id,
            clave,
        ),
    )


def marcar_registrado(usuario_id) -> None:
    sql(
        "update usuarios set es_anonimo = false, email = $2 where id = $1::uuid",
        usuario_id,
        f"{uuid.uuid4().hex[:8]}@test.local",
    )


def poner_plataforma(usuario_id, rol: str | None) -> None:
    if rol is None:
        escribir(
            "plataforma",
            ("delete from plataforma_miembros where usuario_id = $1::uuid", usuario_id),
        )
    else:
        marcar_registrado(usuario_id)
        escribir(
            "plataforma",
            (
                "insert into plataforma_miembros (usuario_id, rol) values ($1::uuid, $2) "
                "on conflict (usuario_id) do update set rol = excluded.rol",
                usuario_id,
                rol,
            ),
        )


def borrar_negocio(negocio_id) -> None:
    """Limpieza. La auditoria no se borra (es solo-agregar): los tests filtran por id."""

    async def run():
        async with conexion() as conn, conn.transaction():
            await conn.execute("select set_config('app.membresia_write', 'on', true)")
            await conn.execute("select set_config('app.rol_write', 'on', true)")
            await conn.execute("select set_config('app.historial_write', 'on', true)")
            for tabla in (
                "precios_vigentes", "precios_costos", "productos", "categorias",
                "negocio_condicion_fiscal",
            ):  # fmt: skip
                await conn.execute(f"delete from {tabla} where negocio_id = $1", negocio_id)  # noqa: S608
            await conn.execute("delete from membresias where negocio_id = $1", negocio_id)
            await conn.execute("delete from config where negocio_id = $1", negocio_id)
            await conn.execute("delete from roles where negocio_id = $1", negocio_id)
            await conn.execute("delete from sucursales where negocio_id = $1", negocio_id)
            await conn.execute("delete from negocios where id = $1", negocio_id)

    correr(run())


def borrar_usuarios(ids) -> None:
    async def run():
        async with conexion() as conn, conn.transaction():
            await conn.execute("select set_config('app.plataforma_write', 'on', true)")
            await conn.execute("select set_config('app.membresia_write', 'on', true)")
            await conn.execute("delete from plataforma_miembros where usuario_id = any($1)", ids)
            await conn.execute("delete from membresias where usuario_id = any($1)", ids)
            await conn.execute("delete from aceptaciones where usuario_id = any($1)", ids)
            await conn.execute("delete from dispositivos where usuario_id = any($1)", ids)
            await conn.execute("delete from usuarios where id = any($1)", ids)

    correr(run())


def poner_config(clave: str, valor_json: str, negocio_id=None) -> None:
    sql(
        """
        insert into config (negocio_id, clave, valor) values ($1::uuid, $2, $3::jsonb)
        on conflict (coalesce(negocio_id, '00000000-0000-0000-0000-000000000000'), clave)
        do update set valor = excluded.valor
        """,
        negocio_id,
        clave,
        valor_json,
    )


def quitar_config(clave: str, negocio_id=None) -> None:
    sql(
        "delete from config where clave = $1 and negocio_id is not distinct from $2::uuid",
        clave,
        negocio_id,
    )
