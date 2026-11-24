from fastapi import APIRouter

from app.api import admin, admin_catalogo, auth, avisos, catalogo, me, negocios, productos, salud

router = APIRouter(prefix="/v1")
router.include_router(salud.router)
router.include_router(auth.router)
router.include_router(me.router)
router.include_router(negocios.router)
router.include_router(productos.router)
router.include_router(admin.router)
router.include_router(admin_catalogo.router)
router.include_router(catalogo.router)
router.include_router(avisos.router)
