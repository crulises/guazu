from fastapi import APIRouter, Request

from app.config import get_settings

router = APIRouter()


@router.get("/salud")
async def salud(request: Request) -> dict:
    """Estado del backend y de la base. Lo usa «Acerca de» en las apps y el healthcheck."""
    s = get_settings()
    try:
        async with request.app.state.pool.acquire() as con:
            await con.fetchval("select 1")
        base = "ok"
    except Exception:  # la salud nunca rompe: informa
        base = "caida"
    return {
        "estado": "ok" if base == "ok" else "degradado",
        "base": base,
        "version": s.app_version,
        "commit": s.app_commit,
        "compilado": s.app_built_at,
    }
