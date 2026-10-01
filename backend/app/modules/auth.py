import hashlib
import secrets
from datetime import timedelta

from config.settings import Settings
from db.store import DocumentStore

from app.core.errors import AppError
from app.core.timeutil import iso, parse_iso, utcnow
from app.modules.events import emit
from app.modules.passwords import hash_password, verify_password
from app.modules.tokens import hash_refresh, issue_access, new_refresh, read_access
from app.services.common import base_doc, new_id
from app.services.identity import bootstrap

OAUTH_PROVIDERS = {"google", "linkedin", "facebook", "wechat", "apple"}


def _email(value: str | None) -> str | None:
    if not value:
        return None
    email = value.strip().lower()
    if "@" not in email or "." not in email.split("@", 1)[1]:
        raise AppError("INVALID_EMAIL", "邮箱格式不正确")
    return email


def _phone(value: str | None) -> str | None:
    if not value:
        return None
    phone = "".join(ch for ch in value.strip() if ch.isdigit() or ch == "+")
    digits = phone[1:] if phone.startswith("+") else phone
    if not digits.isdigit() or not 6 <= len(digits) <= 20:
        raise AppError("INVALID_PHONE", "手机号格式不正确")
    return phone


def _audit(store, tenant_id: str, user_id: str, action: str, resource: str) -> None:
    store.insert(
        "audit_logs",
        base_doc(tenant_id, user_id, id=new_id("audit"), user_id=user_id, action=action, resource=resource, ip=None),
    )


def register(
    store: DocumentStore,
    *,
    email: str | None,
    phone: str | None,
    password: str,
    display_name: str | None,
) -> dict:
    email_n = _email(email)
    phone_n = _phone(phone)
    if not email_n and not phone_n:
        raise AppError("INVALID_ACCOUNT", "请填写邮箱或手机号")
    if email_n and store.find_global("users", email=email_n):
        raise AppError("ACCOUNT_EXISTS", "这个邮箱已经注册", 409)
    if phone_n and store.find_global("users", phone=phone_n):
        raise AppError("ACCOUNT_EXISTS", "这个手机号已经注册", 409)
    name = (display_name or (email_n or phone_n) or "卖家").split("@")[0]
    principal = f"local:{email_n or phone_n}"
    prof = bootstrap(
        store,
        principal,
        name,
        email=email_n,
        phone=phone_n,
        password_hash=hash_password(password),
        status="active",
    )
    _audit(store, prof["tenant"]["id"], prof["user"]["id"], "user.registered", "user")
    emit(store, prof["tenant"]["id"], "user.registered", {"user_id": prof["user"]["id"]}, prof["user"]["id"])
    return prof


def _find_login(store: DocumentStore, email: str | None, phone: str | None) -> dict | None:
    if email:
        return store.find_global("users", email=email)
    if phone:
        return store.find_global("users", phone=phone)
    return None


def _issue(store: DocumentStore, settings: Settings, user: dict) -> dict:
    refresh = new_refresh()
    session = base_doc(
        user["tenant_id"],
        user["id"],
        id=new_id("ses"),
        user_id=user["id"],
        principal=user["cloudbase_user_id"],
        refresh_hash=hash_refresh(refresh),
        expires_at=iso(utcnow() + timedelta(seconds=settings.refresh_ttl_seconds)),
        revoked_at=None,
    )
    store.insert("sessions", session)
    access = issue_access(
        settings.session_secret,
        sub=user["cloudbase_user_id"],
        sid=session["id"],
        ttl_seconds=settings.access_ttl_seconds,
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "expires_in": settings.access_ttl_seconds,
        "user_id": user["id"],
    }


def login(store: DocumentStore, settings: Settings, *, email: str | None, phone: str | None, password: str) -> dict:
    email_n = _email(email)
    phone_n = _phone(phone)
    if not email_n and not phone_n:
        raise AppError("INVALID_ACCOUNT", "请填写邮箱或手机号")
    user = _find_login(store, email_n, phone_n)
    if not user or not verify_password(password, user.get("password_hash")):
        raise AppError("UNAUTHENTICATED", "邮箱、手机或密码不正确", 401)
    if user.get("status") not in {None, "active"}:
        raise AppError("ACCOUNT_INACTIVE", "账号未激活或已停用", 403)
    tokens = _issue(store, settings, user)
    _audit(store, user["tenant_id"], user["id"], "user.login", "session")
    emit(store, user["tenant_id"], "user.login", {"user_id": user["id"]}, user["id"])
    return tokens


def refresh(store: DocumentStore, settings: Settings, refresh_token: str) -> dict:
    session = store.find_global("sessions", refresh_hash=hash_refresh(refresh_token))
    if not session or session.get("revoked_at"):
        raise AppError("UNAUTHENTICATED", "刷新凭证无效", 401)
    if parse_iso(session["expires_at"]) <= utcnow():
        raise AppError("UNAUTHENTICATED", "刷新凭证已过期", 401)
    user = store.get("users", session["user_id"])
    if not user:
        raise AppError("UNAUTHENTICATED", "刷新凭证无效", 401)
    rotated = new_refresh()
    store.touch("sessions", session["id"], {"refresh_hash": hash_refresh(rotated)})
    access = issue_access(
        settings.session_secret,
        sub=user["cloudbase_user_id"],
        sid=session["id"],
        ttl_seconds=settings.access_ttl_seconds,
    )
    return {
        "access_token": access,
        "refresh_token": rotated,
        "token_type": "Bearer",
        "expires_in": settings.access_ttl_seconds,
        "user_id": user["id"],
    }


def revoke_bearer(store: DocumentStore, authorization: str | None, settings: Settings) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return
    token = authorization.split(" ", 1)[1].strip()
    if not token.startswith("pg1."):
        return
    payload = read_access(settings.session_secret, token)
    session = store.get("sessions", payload["sid"])
    if session and not session.get("revoked_at"):
        store.touch("sessions", session["id"], {"revoked_at": iso()})


def forgot_password(store: DocumentStore, settings: Settings, *, email: str | None, phone: str | None) -> dict:
    email_n = _email(email)
    phone_n = _phone(phone)
    user = _find_login(store, email_n, phone_n)
    body = {"accepted": True}
    if not user:
        return body
    token = secrets.token_urlsafe(24)
    store.insert(
        "password_resets",
        base_doc(
            user["tenant_id"],
            user["id"],
            id=new_id("rst"),
            user_id=user["id"],
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=iso(utcnow() + timedelta(hours=1)),
            used_at=None,
        ),
    )
    if settings.auth_mode == "demo":
        body["reset_token"] = token
    return body


def reset_password(store: DocumentStore, token: str, password: str) -> dict:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = store.find_global("password_resets", token_hash=token_hash)
    if not row or row.get("used_at") or parse_iso(row["expires_at"]) <= utcnow():
        raise AppError("RESET_INVALID", "重置凭证无效或已使用", 400)
    user = store.get("users", row["user_id"])
    if not user:
        raise AppError("RESET_INVALID", "重置凭证无效或已使用", 400)
    store.touch("users", user["id"], {"password_hash": hash_password(password)})
    store.touch("password_resets", row["id"], {"used_at": iso()})
    sessions = store.query("sessions", tenant_id=user["tenant_id"], filters={"user_id": user["id"]}, limit=100)["items"]
    for session in sessions:
        if not session.get("revoked_at"):
            store.touch("sessions", session["id"], {"revoked_at": iso()})
    return {"reset": True}


def assert_oauth_provider(provider: str) -> None:
    if provider not in OAUTH_PROVIDERS:
        raise AppError("UNKNOWN_PROVIDER", "不支持的登录提供方", 400, {"provider": provider})


def _issue_code(store: DocumentStore, user: dict, purpose: str) -> str:
    prior = store.query(
        "verification_codes",
        tenant_id=user["tenant_id"],
        filters={"user_id": user["id"], "purpose": purpose},
        limit=20,
    )["items"]
    now = iso()
    for row in prior:
        if not row.get("used_at"):
            store.touch("verification_codes", row["id"], {"used_at": now})
    code = f"{secrets.randbelow(1_000_000):06d}"
    store.insert(
        "verification_codes",
        base_doc(
            user["tenant_id"],
            user["id"],
            id=new_id("vcode"),
            user_id=user["id"],
            purpose=purpose,
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            expires_at=iso(utcnow() + timedelta(minutes=5)),
            used_at=None,
        ),
    )
    return code


def send_login_code(store: DocumentStore, settings: Settings, *, email: str | None, phone: str | None) -> dict:
    email_n = _email(email)
    phone_n = _phone(phone)
    if not email_n and not phone_n:
        raise AppError("INVALID_ACCOUNT", "请填写邮箱或手机号")
    user = _find_login(store, email_n, phone_n)
    body = {"sent": True}
    if not user or user.get("status") not in {None, "active"}:
        return body
    code = _issue_code(store, user, "login")
    if settings.auth_mode == "demo":
        body["code"] = code
    return body


def login_with_code(
    store: DocumentStore,
    settings: Settings,
    *,
    email: str | None,
    phone: str | None,
    code: str,
) -> dict:
    email_n = _email(email)
    phone_n = _phone(phone)
    if not email_n and not phone_n:
        raise AppError("INVALID_ACCOUNT", "请填写邮箱或手机号")
    user = _find_login(store, email_n, phone_n)
    digest = hashlib.sha256((code or "").strip().encode()).hexdigest()
    row = None
    if user:
        row = store.find_global(
            "verification_codes",
            user_id=user["id"],
            purpose="login",
            code_hash=digest,
        )
    if (
        not user
        or user.get("status") not in {None, "active"}
        or not row
        or row.get("used_at")
        or parse_iso(row["expires_at"]) <= utcnow()
    ):
        raise AppError("UNAUTHENTICATED", "验证码不正确或已过期", 401)
    store.touch("verification_codes", row["id"], {"used_at": iso()})
    tokens = _issue(store, settings, user)
    _audit(store, user["tenant_id"], user["id"], "user.login", "session")
    emit(store, user["tenant_id"], "user.login", {"user_id": user["id"], "method": "code"}, user["id"])
    return tokens
