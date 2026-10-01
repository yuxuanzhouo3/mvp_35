from fastapi import APIRouter

from app.api.v1.ai_routes import router as ai_router
from app.api.v1.auth_routes import router as auth_router
from app.api.v1.core_routes import router as core_router
from app.api.v1.pay_routes import router as pay_router


def create_contract_router() -> APIRouter:
    router = APIRouter()
    router.include_router(auth_router)
    router.include_router(pay_router)
    router.include_router(core_router)
    router.include_router(ai_router)
    return router
