"""Capa de acceso a datos genérica: asyncpg contra cualquier Postgres."""

import asyncpg
from fastapi import Request

from app.config import get_settings


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(get_settings().database_url, min_size=1, max_size=10)


async def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool
