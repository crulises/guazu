"""Transacciones con el aislamiento por negocio activado.

Un superusuario ignora RLS, así que toda consulta que toca datos de UN negocio corre acá: la
transacción cambia al rol `guazu_app` (sin privilegios) y fija `app.negocio_id`. Si el código
se olvidara de filtrar por `negocio_id`, la base igual devuelve solo lo de ese negocio. Es
defensa en profundidad: el filtro explícito en cada consulta sigue siendo la regla.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg


@asynccontextmanager
async def tx_negocio(
    pool: asyncpg.Pool, negocio_id: UUID, *, escritura: str | None = None
) -> AsyncIterator[asyncpg.Connection]:
    """`escritura` habilita una escritura protegida (p. ej. `membresia`, `rol`) solo dentro de
    esta transacción: el trigger de la tabla la exige."""
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("set local role guazu_app")
        await conn.execute("select set_config('app.negocio_id', $1, true)", str(negocio_id))
        if escritura:
            await conn.execute("select set_config($1, 'on', true)", f"app.{escritura}_write")
        yield conn
