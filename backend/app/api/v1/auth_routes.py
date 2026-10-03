from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.api.deps import bind, respond
from app.modules.auth import (
    assert_oauth_provider,
    forgot_password,
    login,
    reset_password_with_code,
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
    code: str | None = None
    invite_code: str | None = None


class LoginIn(BaseModel):
    email: str | None = None
    phone: str | None = None
    username: str | None = None
    password: str
    recall: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str


class ForgotIn(BaseModel):
    email: str | None = None
    phone: str | None = None


class ResetIn(BaseModel):
    token: str | None = None
    phone: str | None = None
    code: str | None = None
    password: str


class CodeSendIn(BaseModel):
    email: str | None = None
    phone: str | None = None
    purpose: str = "login"


class MiniIn(BaseModel):
    code: str | None = None


class OAuthIn(BaseModel):
    code: str | None = None
    state: str | None = None


class CodeLoginIn(BaseModel):
    email: str | None = None
    phone: str | None = None
    code: str
    recall: str | None = None


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
        code=body.code,
        invite_code=body.invite_code,
    )
    return respond(request, prof)


@router.post("/auth/login")
def auth_login(request: Request, body: LoginIn):
    settings, store = request.app.state.settings, request.app.state.store
    return respond(
        request,
        login(
            store,
            settings,
            email=body.email,
            phone=body.phone,
            password=body.password,
            username=body.username,
            recall=body.recall,
        ),
    )


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
    store = request.app.state.store
    if body.token:
        return respond(request, reset_password(store, body.token, body.password))
    if body.phone and body.code:
        return respond(request, reset_password_with_code(store, phone=body.phone, code=body.code, password=body.password))
    from app.core.errors import AppError

    raise AppError("RESET_INVALID", "重置凭证无效或已使用", 400)


@router.get("/users/me")
def users_me(request: Request, authorization: str | None = Header(default=None)):
    _settings, _store, prof = bind(request, authorization)
    return respond(request, prof)


@router.get("/users/me/invite")
def users_me_invite(request: Request, authorization: str | None = Header(default=None)):
    from app.modules.referrals import REFERRAL_RATE, my_invite

    _settings, store, prof = bind(request, authorization)
    user = store.get("users", prof["user"]["id"])
    if not user:
        from app.core.errors import AppError

        raise AppError("USER_NOT_FOUND", "用户不存在", 404)
    payload = my_invite(store, user)
    payload["rate"] = str(REFERRAL_RATE)
    return respond(request, payload)


@router.post("/users/me/invite/cash")
def users_me_invite_cash(request: Request, authorization: str | None = Header(default=None)):
    from app.modules.referrals import request_cash

    _settings, store, prof = bind(request, authorization)
    user = store.get("users", prof["user"]["id"])
    return respond(request, request_cash(store, user or prof["user"]))


@router.post("/users/me/draw")
def users_me_draw(request: Request, authorization: str | None = Header(default=None)):
    from app.modules.presence import draw_cash

    _settings, store, prof = bind(request, authorization)
    user = store.get("users", prof["user"]["id"])
    return respond(request, draw_cash(store, user or prof["user"]))


@router.get("/auth/wechat/authorize")
def wechat_authorize(request: Request):
    from app.modules.wechat_login import authorize_url

    return respond(request, authorize_url(request.app.state.settings))


@router.post("/auth/oauth/{provider}")
def auth_oauth(
    provider: str,
    request: Request,
    body: OAuthIn | None = None,
    authorization: str | None = Header(default=None),
):
    assert_oauth_provider(provider)
    if provider == "wechat":
        from app.modules.wechat_login import login_open

        payload = body or OAuthIn()
        return respond(request, login_open(request.app.state.store, request.app.state.settings, code=payload.code or "", state=payload.state or ""))
    require_flag("auth.oauth")
    bind(request, authorization, write=True)
    return respond(request, {"provider": provider})


@router.post("/auth/mfa/verify")
def auth_mfa(request: Request, authorization: str | None = Header(default=None)):
    require_flag("auth.mfa")
    bind(request, authorization, write=True)
    return respond(request, {"verified": True})


@router.post("/auth/sso")
def auth_sso(request: Request, authorization: str | None = Header(default=None)):
    require_flag("auth.sso")
    bind(request, authorization, write=True)
    return respond(request, {"ok": True})


@router.post("/auth/code/send")
def auth_code_send(request: Request, body: CodeSendIn):
    settings = request.app.state.settings
    return respond(
        request,
        send_login_code(request.app.state.store, settings, email=body.email, phone=body.phone, purpose=body.purpose),
    )


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
            recall=body.recall,
        ),
    )


@router.post("/auth/miniprogram")
def auth_miniprogram(request: Request, body: MiniIn | None = None, authorization: str | None = Header(default=None)):
    from app.modules.wechat_login import login_miniprogram

    payload = body or MiniIn()
    return respond(
        request,
        login_miniprogram(request.app.state.store, request.app.state.settings, code=payload.code or ""),
    )


@router.post("/auth/switch-tenant")
def auth_switch_tenant(request: Request, body: SwitchIn, authorization: str | None = Header(default=None)):
    require_flag("auth.tenant_switch")
    bind(request, authorization, write=True)
    return respond(request, {"tenant_id": body.tenant_id, "switched": False})
