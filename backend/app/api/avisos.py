"""Avisos de catálogo y ayuda de estándares de carga (para las apps y el panel).

Un aviso le cuenta a quien cargó un producto que el sistema ajustó lo que cargó y por qué (qué
estándar no se cumplía). Es informativo: acá no hay karma que afectar.
"""

import json
from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth import Usuario, current_user
from app.db import get_pool
from app.services import estandares
from app.services.estandares import ESTANDARES, Estandar

router = APIRouter(tags=["ayuda"])


class AvisoOut(BaseModel):
    id: UUID
    ean: str
    tipo: str
    estandares: list[Estandar]
    mensaje: str
    antes: dict
    despues: dict
    created_at: datetime
    leido: bool


class LeidosIn(BaseModel):
    ids: list[UUID] | None = Field(default=None, max_length=200)  # vacío = todos


def _mensaje(antes: dict, despues: dict, ids: list[str]) -> str:
    if antes.get("nombre") != despues.get("nombre"):
        cambio = f"Ajustamos el nombre «{antes.get('nombre')}» a «{despues.get('nombre')}» "
    else:
        cambio = "Completamos los datos del producto desde el nombre "
    motivos = "; ".join(estandares.titulos(ids))
    return f"{cambio}porque no cumplía los estándares de carga: {motivos}."


@router.get("/ayuda/estandares", response_model=list[Estandar])
async def listar_estandares(_: Usuario = Depends(current_user)) -> list[Estandar]:
    """Los estándares de carga del catálogo (Doc 10). Las apps los muestran tal cual."""
    return ESTANDARES


@router.get("/me/avisos", response_model=list[AvisoOut])
async def mis_avisos(
    no_leidos: bool = False,
    limite: int = Query(default=50, ge=1, le=100),
    user: Usuario = Depends(current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[AvisoOut]:
    filas = await pool.fetch(
        "select id, ean, tipo, estandares, antes::text as antes, despues::text as despues, "
        "created_at, leido_en from avisos_catalogo where usuario_id = $1 "
        "and (not $2 or leido_en is null) order by created_at desc limit $3",
        user.id,
        no_leidos,
        limite,
    )
    salida = []
    for r in filas:
        antes, despues = json.loads(r["antes"]), json.loads(r["despues"])
        ids = list(r["estandares"])
        salida.append(
            AvisoOut(
                id=r["id"],
                ean=r["ean"],
                tipo=r["tipo"],
                estandares=[estandares.POR_ID[i] for i in ids if i in estandares.POR_ID],
                mensaje=_mensaje(antes, despues, ids),
                antes=antes,
                despues=despues,
                created_at=r["created_at"],
                leido=r["leido_en"] is not None,
            )
        )
    return salida


@router.post("/me/avisos/leidos", status_code=204)
async def marcar_leidos(
    body: LeidosIn | None = None,
    user: Usuario = Depends(current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> None:
    ids = body.ids if body else None
    await pool.execute(
        "update avisos_catalogo set leido_en = now() where usuario_id = $1 "
        "and leido_en is null and ($2::uuid[] is null or id = any($2))",
        user.id,
        ids,
    )
