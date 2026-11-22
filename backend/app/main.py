import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import errores
from app.api.v1 import router as v1_router
from app.config import get_settings
from app.db import create_pool
from app.logging import setup_logging

log = logging.getLogger("guazu")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(get_settings().log_level)
    app.state.pool = await create_pool()
    app.state.http = httpx.AsyncClient()
    log.info("backend iniciado")
    try:
        yield
    finally:
        await app.state.http.aclose()
        await app.state.pool.close()


app = FastAPI(title="Guazú API", version=get_settings().app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(v1_router)
errores.registrar(app)
