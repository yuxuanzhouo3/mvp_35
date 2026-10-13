"""WeChat Open Platform and Mini Program login. Missing AppId or AppSecret stays closed."""

import hashlib
import hmac
import json
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from urllib.parse import quote

import httpx

from app.core.errors import AppError
from app.modules.auth import _issue
from app.services.identity import bootstrap
from config.settings import Settings
from db.store import DocumentStore


def authorize_url(settings: Settings) -> dict:
    app_id = settings.wechat_app_id
    if not app_id or not settings.wechat_app_secret:
        raise AppError("NOT_ENABLED", "auth.oauth 未开通", 501, {"flag": "auth.oauth", "placeholder": True})
    state = _sign_state(settings, "open")
    redirect = quote(settings.wechat_oauth_redirect, safe="")
    query = (
        f"appid={app_id}&redirect_uri={redirect}"
        f"&response_type=code&scope=snsapi_login&state={quote(state, safe='')}#wechat_redirect"
    )
    return {"url": f"https://open.weixin.qq.com/connect/qrconnect?{query}", "state": state}


def login_open(store: DocumentStore, settings: Settings, *, code: str, state: str) -> dict:
    if not settings.wechat_app_id or not settings.wechat_app_secret:
        raise AppError("NOT_ENABLED", "auth.oauth 未开通", 501, {"flag": "auth.oauth", "placeholder": True})
    if _read_state(settings, state) != "open":
        raise AppError("INVALID_STATE", "微信登录状态无效", 400)
    if not code:
        raise AppError("MISSING_CODE", "缺少微信授权码", 400)
    identity = _get_json(
        "https://api.weixin.qq.com/sns/oauth2/access_token",
        {
            "appid": settings.wechat_app_id,
            "secret": settings.wechat_app_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    profile = _get_json(
        "https://api.weixin.qq.com/sns/userinfo",
        {"access_token": identity.get("access_token") or "", "openid": identity.get("openid") or "", "lang": "zh_CN"},
    )
    return _enter(
        store,
        settings,
        openid=identity.get("openid") or "",
        unionid=identity.get("unionid") or profile.get("unionid"),
        nickname=profile.get("nickname"),
    )


def login_miniprogram(store: DocumentStore, settings: Settings, *, code: str) -> dict:
    if not settings.wechat_miniprogram_app_id or not settings.wechat_miniprogram_app_secret:
        raise AppError("NOT_ENABLED", "auth.miniprogram 未开通", 501, {"flag": "auth.miniprogram", "placeholder": True})
    if not code:
        raise AppError("MISSING_CODE", "缺少小程序登录凭证", 400)
    identity = _get_json(
        "https://api.weixin.qq.com/sns/jscode2session",
        {
            "appid": settings.wechat_miniprogram_app_id,
            "secret": settings.wechat_miniprogram_app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        },
    )
    return _enter(store, settings, openid=identity.get("openid") or "", unionid=identity.get("unionid"), nickname=None)


def _enter(store: DocumentStore, settings: Settings, *, openid: str, unionid: str | None, nickname: str | None) -> dict:
    if not openid:
        raise AppError("WECHAT_LOGIN_FAILED", "微信没有返回用户标识", 401)
    user = store.find_global("users", wechat_unionid=unionid) if unionid else None
    if not user:
        user = store.find_global("users", wechat_openid=openid)
    if not user:
        prof = bootstrap(
            store,
            f"wechat:{unionid or openid}",
            nickname or "微信用户",
            status="active",
            username=unionid or openid,
        )
        store.touch(
            "users",
            prof["user"]["id"],
            {"wechat_openid": openid, "wechat_unionid": unionid, "display_name": nickname or "微信用户"},
        )
        user = store.get("users", prof["user"]["id"])
    return _issue(store, settings, user)


def _get_json(url: str, params: dict) -> dict:
    try:
        response = httpx.get(url, params=params, timeout=20)
        body = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise AppError("WECHAT_LOGIN_FAILED", "微信登录没有完成", 502) from exc
    if body.get("errcode"):
        raise AppError("WECHAT_LOGIN_FAILED", "微信登录没有完成", 401)
    return body


def _sign_state(settings: Settings, kind: str) -> str:
    payload = urlsafe_b64encode(json.dumps({"t": kind, "exp": int(time.time()) + 600}).encode()).decode().rstrip("=")
    secret = settings.wechat_oauth_state_secret or settings.session_secret
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _read_state(settings: Settings, state: str) -> str:
    payload, _, signature = (state or "").partition(".")
    secret = settings.wechat_oauth_state_secret or settings.session_secret
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not payload or not hmac.compare_digest(expected, signature):
        return ""
    padded = payload + "=" * (-len(payload) % 4)
    try:
        data = json.loads(urlsafe_b64decode(padded.encode()))
    except (json.JSONDecodeError, ValueError):
        return ""
    if int(data.get("exp") or 0) < int(time.time()):
        return ""
    return data.get("t") or ""
