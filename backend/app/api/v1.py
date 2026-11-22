from fastapi import APIRouter

from app.api import admin, auth, me, negocios, salud

router = APIRouter(prefix="/v1")
router.include_router(salud.router)
router.include_router(auth.router)
router.include_router(me.router)
router.include_router(negocios.router)
router.include_router(admin.router)
