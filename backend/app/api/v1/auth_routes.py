from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.api.deps import bind, respond
from app.modules.auth import (
    assert_oauth_provider,
    forgot_password,
    login,
    login_with_code,
    refresh,
    register,
    reset_password,
    send_login_code,
)
from config.flags import require_flag

router = APIRouter(prefix="/api/v1")


class RegisterIn(BaseModel):
    email: str | None = None
    phone: str | None = None
    password: str
    display_name: str | None = None


class LoginIn(BaseModel):
    email: str | None = None
    phone: str | None = None
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class ForgotIn(BaseModel):
    email: str | None = None
    phone: str | None = None


class ResetIn(BaseModel):
    token: str
    password: str


class CodeSendIn(BaseModel):
    email: str | None = None
    phone: str | None = None


class CodeLoginIn(BaseModel):
    email: str | None = None
    phone: str | None = None
    code: str


class SwitchIn(BaseModel):
    tenant_id: str | None = None


@router.post("/auth/register")
def auth_register(request: Request, body: RegisterIn):
    store = request.app.state.store
    prof = register(
        store,
        email=body.email,
        phone=body.phone,
        password=body.password,
        display_name=body.display_name,
    )
    return respond(request, prof)


@router.post("/auth/login")
def auth_login(request: Request, body: LoginIn):
    settings, store = request.app.state.settings, request.app.state.store
    return respond(request, login(store, settings, email=body.email, phone=body.phone, password=body.password))


@router.post("/auth/refresh")
def auth_refresh(request: Request, body: RefreshIn):
    settings = request.app.state.settings
    return respond(request, refresh(request.app.state.store, settings, body.refresh_token))


@router.post("/auth/forgot-password")
def auth_forgot(request: Request, body: ForgotIn):
    settings = request.app.state.settings
    return respond(request, forgot_password(request.app.state.store, settings, email=body.email, phone=body.phone))


@router.post("/auth/reset-password")
def auth_reset(request: Request, body: ResetIn):
    return respond(request, reset_password(request.app.state.store, body.token, body.password))


@router.get("/users/me")
def users_me(request: Request, authorization: str | None = Header(default=None)):
    _settings, _store, prof = bind(request, authorization)
    return respond(request, prof)


@router.post("/auth/oauth/{provider}")
def auth_oauth(provider: str, request: Request, authorization: str | None = Header(default=None)):
    bind(request, authorization, write=True)
    assert_oauth_provider(provider)
    require_flag("auth.oauth")
    return respond(request, {"provider": provider})


@router.post("/auth/mfa/verify")
def auth_mfa(request: Request, authorization: str | None = Header(default=None)):
    bind(request, authorization, write=True)
    require_flag("auth.mfa")
    return respond(request, {"verified": True})


@router.post("/auth/sso")
def auth_sso(request: Request, authorization: str | None = Header(default=None)):
    bind(request, authorization, write=True)
    require_flag("auth.sso")
    return respond(request, {"ok": True})


@router.post("/auth/code/send")
def auth_code_send(request: Request, body: CodeSendIn):
    settings = request.app.state.settings
    return respond(request, send_login_code(request.app.state.store, settings, email=body.email, phone=body.phone))


@router.post("/auth/code/login")
def auth_code_login(request: Request, body: CodeLoginIn):
    settings = request.app.state.settings
    return respond(
        request,
        login_with_code(
            request.app.state.store,
            settings,
            email=body.email,
            phone=body.phone,
            code=body.code,
        ),
    )


@router.post("/auth/miniprogram")
def auth_miniprogram(request: Request, authorization: str | None = Header(default=None)):
    bind(request, authorization, write=True)
    require_flag("auth.miniprogram")
    return respond(request, {"logged_in": False})


@router.post("/auth/switch-tenant")
def auth_switch_tenant(request: Request, body: SwitchIn, authorization: str | None = Header(default=None)):
    bind(request, authorization, write=True)
    require_flag("auth.tenant_switch")
    return respond(request, {"tenant_id": body.tenant_id, "switched": False})
