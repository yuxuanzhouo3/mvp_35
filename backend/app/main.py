import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.contract import create_contract_router
from app.api.v1.router import create_router
from app.core.errors import AppError
from app.services.identity import ensure_platform_admin
from config.settings import Settings
from db.cloudbase_sql import CloudBaseSqlError
from db.store import open_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    app.state.settings = settings
    try:
        app.state.store = open_store(settings)
        ensure_platform_admin(app.state.store)
    except Exception:
        logging.getLogger("uvicorn.error").exception("platform store failed to open")
        raise
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="PickGlobal API", version="1.0", lifespan=lifespan)
    app.include_router(create_router())
    app.include_router(create_contract_router())

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request.state.request_id = f"req_{uuid.uuid4().hex[:16]}"
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    @app.exception_handler(CloudBaseSqlError)
    async def handle_store_error(request: Request, exc: CloudBaseSqlError):
        del exc
        request_id = getattr(request.state, "request_id", "req_unknown")
        return JSONResponse(
            status_code=503,
            content={
                "error": {"code": "STORE_UNAVAILABLE", "message": "登录数据暂时不可用，请稍后再试", "details": {}},
                "request_id": request_id,
            },
        )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        request_id = getattr(request.state, "request_id", "req_unknown")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}, "request_id": request_id},
        )

    return app


app = create_app()


def _mount_cors() -> None:
    settings = Settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


_mount_cors()
