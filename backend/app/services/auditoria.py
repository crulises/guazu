"""Rastro de las acciones sensibles (`auditoria`, solo-agregar en Postgres).

Se registra en la MISMA transacción que la acción: o quedan las dos o ninguna. Cada fila guarda
el rol con el que se actuó, no solo el usuario.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg


def _default(o: Any) -> Any:
    if isinstance(o, Decimal | UUID):
        return str(o)
    if isinstance(o, datetime | date):
        return o.isoformat()
    raise TypeError(f"no serializable: {type(o)}")


def a_json(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, asyncpg.Record):
        valor = dict(valor)
    return json.dumps(valor, default=_default, ensure_ascii=False)


async def registrar(
    conn: asyncpg.Connection,
    *,
    usuario_id: UUID,
    rol: str,
    accion: str,
    entidad: str,
    entidad_id: Any,
    negocio_id: UUID | None = None,
    sucursal_id: UUID | None = None,
    antes: Any = None,
    despues: Any = None,
    nota: str | None = None,
) -> None:
    await conn.execute(
        """
        insert into auditoria (negocio_id, sucursal_id, usuario_id, rol_actuando, accion,
                               entidad, entidad_id, antes, despues, nota)
        values ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10)
        """,
        negocio_id,
        sucursal_id,
        usuario_id,
        rol,
        accion,
        entidad,
        str(entidad_id),
        a_json(antes),
        a_json(despues),
        nota,
    )
