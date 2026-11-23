"""Catálogo global (`/v1/catalogo`): lectura para cualquier sesión, incluido el escáner."""

from decimal import Decimal

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import Usuario, current_user
from app.db import get_pool
from app.services import catalogo, config
from app.services.ratelimit import limitar

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


class ProductoGlobalOut(BaseModel):
    ean: str
    ean_buscado: str
    nombre: str
    marca: str | None
    tamano_valor: Decimal | None
    tamano_unidad: str | None
    imagen_url: str | None
    origen: str


@router.get("/ean/{ean}", response_model=ProductoGlobalOut)
async def por_ean(
    ean: str,
    user: Usuario = Depends(current_user),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProductoGlobalOut:
    """Busca un producto por EAN: acepta 8, 12 (UPC-A), 13 y 14 dígitos y lo normaliza en el
    backend (UPC-A pasa a EAN-13). Rechaza un dígito verificador malo y los EAN de balanza.
    El escáner abierto tiene un tope por sesión para que no sirva de raspador del catálogo."""
    limite = int(await config.leer(pool, "catalogo_busquedas_por_minuto"))
    limitar(f"catalogo:{user.id}", limite, 60)
    return ProductoGlobalOut(**await catalogo.buscar(pool, ean))
