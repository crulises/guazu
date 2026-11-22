from fastapi import APIRouter

from app.api import salud

router = APIRouter(prefix="/v1")
router.include_router(salud.router)
