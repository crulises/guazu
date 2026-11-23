"""Lectura de tunables (`config`) con valor por defecto en codigo.

Si la clave falta en la base (una base nueva sin seed), se usa el default: el backend no depende
de que el seed de desarrollo se haya corrido. Una clave puede ser global (negocio_id null) o de un
negocio; la del negocio gana sobre la global.
"""

import json
from typing import Any
from uuid import UUID

import asyncpg

DEFAULTS: dict[str, Any] = {
    # Rate limit (Doc 2, abuso del escaner abierto). Se cuentan todos los intentos.
    "auth_altas_por_hora_ip": 10,
    "auth_refresh_por_hora_ip": 120,
    "auth_login_por_hora_ip": 30,
    "sesion_pedidos_por_minuto": 120,
    "catalogo_busquedas_por_minuto": 240,
    # El superadmin existe solo para pruebas y ultimo recurso (D54): apagado por defecto.
    "superadmin_activo": False,
    # Mensajes de error editados desde el panel: {codigo_de_regla: texto} (services/reglas.py).
    "mensajes_reglas": {},
}


async def leer(
    conn: asyncpg.Pool | asyncpg.Connection, clave: str, negocio_id: UUID | None = None
) -> Any:
    valor = await conn.fetchval(
        """
        select valor::text from config
        where clave = $1 and (negocio_id is null or negocio_id = $2::uuid)
        order by negocio_id nulls last
        limit 1
        """,
        clave,
        negocio_id,
    )
    return DEFAULTS.get(clave) if valor is None else json.loads(valor)
