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
    if digits.startswith("86") and len(digits) > 11:
        digits = digits[2:]
    if not digits.isdigit() or not 6 <= len(digits) <= 20:
        raise AppError("INVALID_PHONE", "手机号格式不正确")
    if len(digits) == 11 and digits.startswith("1"):
        return "+86" + digits
    return "+" + digits if phone.startswith("+") else digits


def _phone_aliases(phone: str) -> list[str]:
    digits = phone[1:] if phone.startswith("+") else phone
    local = digits[2:] if digits.startswith("86") and len(digits) > 11 else digits
    found = []
    for item in (phone, local, "+86" + local, "86" + local, "+" + digits):
        if item and item not in found:
            found.append(item)
    return found


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
    code: str | None = None,
) -> dict:
    email_n = _email(email)
    phone_n = _phone(phone)
    if not email_n and not phone_n:
        raise AppError("INVALID_ACCOUNT", "请填写邮箱或手机号")
    _require_register_code(store, email_n, phone_n, code)
    if email_n and store.find_global("users", email=email_n):
        raise AppError("ACCOUNT_EXISTS", "这个邮箱已经注册", 409)
    if phone_n and _find_phone(store, phone_n):
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
        username=email_n or phone_n,
    )
    _audit(store, prof["tenant"]["id"], prof["user"]["id"], "user.registered", "user")
    emit(store, prof["tenant"]["id"], "user.registered", {"user_id": prof["user"]["id"]}, prof["user"]["id"])
    return prof


def _find_phone(store: DocumentStore, phone: str) -> dict | None:
    for alias in _phone_aliases(phone):
        found = store.find_global("users", phone=alias)
        if found:
            return found
    return None


def _find_login(store: DocumentStore, email: str | None, phone: str | None) -> dict | None:
    if email:
        return store.find_global("users", email=email)
    if phone:
        return _find_phone(store, phone)
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


def login(
    store: DocumentStore,
    settings: Settings,
    *,
    email: str | None,
    phone: str | None,
    password: str,
    username: str | None = None,
) -> dict:
    if username and username.strip():
        user = store.find_global("users", username=username.strip())
    else:
        email_n = _email(email)
        phone_n = _phone(phone)
        if not email_n and not phone_n:
            raise AppError("INVALID_ACCOUNT", "请填写邮箱或手机号")
        user = _find_login(store, email_n, phone_n)
    if not user or not verify_password(password, user.get("password_hash")):
        raise AppError("UNAUTHENTICATED", "用户名、邮箱、手机或密码不正确", 401)
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
    from app.modules.messages import deliver_code, email_ready, send_reset_link, sms_ready

    email_n = _email(email)
    phone_n = _phone(phone)
    user = _find_login(store, email_n, phone_n)
    body = {"accepted": True}
    if email_n and email_ready(settings):
        body["channel"] = "email"
    elif phone_n and sms_ready(settings):
        body["channel"] = "sms"
    if not user:
        return body
    if body.get("channel") == "sms":
        code = _issue_code(store, user, "reset_password", 5)
        deliver_code(settings, email=None, phone=phone_n, code=code, purpose="reset_password")
        _retire_other_codes(store, user, "reset_password", hashlib.sha256(code.encode()).hexdigest())
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
    if body.get("channel") == "email":
        send_reset_link(settings, email_n, token)
        return body
    if settings.auth_mode == "demo":
        body["reset_token"] = token
    return body


def reset_password_with_code(store: DocumentStore, *, phone: str | None, code: str, password: str) -> dict:
    phone_n = _phone(phone)
    user = _find_login(store, None, phone_n) if phone_n else None
    digest = hashlib.sha256((code or "").strip().encode()).hexdigest()
    row = None
    if user:
        row = store.find_global("verification_codes", user_id=user["id"], purpose="reset_password", code_hash=digest)
    if not user or not row or row.get("used_at") or parse_iso(row["expires_at"]) <= utcnow():
        raise AppError("RESET_INVALID", "验证码无效或已使用", 400)
    store.touch("users", user["id"], {"password_hash": hash_password(password)})
    store.touch("verification_codes", row["id"], {"used_at": iso()})
    _revoke_sessions(store, user)
    return {"reset": True}


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
    _revoke_sessions(store, user)
    return {"reset": True}


def _revoke_sessions(store: DocumentStore, user: dict) -> None:
    sessions = store.query("sessions", tenant_id=user["tenant_id"], filters={"user_id": user["id"]}, limit=100)["items"]
    for session in sessions:
        if not session.get("revoked_at"):
            store.touch("sessions", session["id"], {"revoked_at": iso()})


def assert_oauth_provider(provider: str) -> None:
    if provider not in OAUTH_PROVIDERS:
        raise AppError("UNKNOWN_PROVIDER", "不支持的登录提供方", 400, {"provider": provider})


def _issue_code(store: DocumentStore, user: dict, purpose: str, minutes: int = 10) -> str:
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
            expires_at=iso(utcnow() + timedelta(minutes=minutes)),
            used_at=None,
        ),
    )
    return code


def _retire_other_codes(store: DocumentStore, user: dict, purpose: str, keep_hash: str) -> None:
    prior = store.query(
        "verification_codes",
        tenant_id=user["tenant_id"],
        filters={"user_id": user["id"], "purpose": purpose},
        limit=20,
    )["items"]
    now = iso()
    for row in prior:
        if row.get("used_at") or row.get("code_hash") == keep_hash:
            continue
        store.touch("verification_codes", row["id"], {"used_at": now})


def send_login_code(
    store: DocumentStore,
    settings: Settings,
    *,
    email: str | None,
    phone: str | None,
    purpose: str = "login",
) -> dict:
    from app.modules.messages import deliver_code, email_ready, sms_ready

    email_n = _email(email)
    phone_n = _phone(phone)
    if not email_n and not phone_n:
        raise AppError("INVALID_ACCOUNT", "请填写邮箱或手机号")
    if purpose not in {"login", "register", "reset_password"}:
        raise AppError("INVALID_PURPOSE", "验证码用途无效")
    minutes = 5 if phone_n and sms_ready(settings) and not (email_n and email_ready(settings)) else 10
    user = None
    if purpose == "login":
        user = _find_login(store, email_n, phone_n)
        if not user or user.get("status") not in {None, "active"}:
            return {"sent": True}
        code = _issue_code(store, user, "login", minutes)
    else:
        code = _issue_pending_code(store, email_n, phone_n, purpose, minutes)
    body = {"sent": True, "purpose": purpose}
    channel = deliver_code(settings, email=email_n, phone=phone_n, code=code, purpose=purpose)
    if user:
        _retire_other_codes(store, user, purpose, hashlib.sha256(code.encode()).hexdigest())
    if channel:
        body["channel"] = channel
    elif settings.auth_mode == "demo":
        body["code"] = code
    return body


def _issue_pending_code(store: DocumentStore, email: str | None, phone: str | None, purpose: str, minutes: int = 10) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    store.insert(
        "verification_codes",
        base_doc(
            "pending",
            "register",
            id=new_id("vcode"),
            email=email,
            phone=phone,
            purpose=purpose,
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            expires_at=iso(utcnow() + timedelta(minutes=minutes)),
            used_at=None,
        ),
    )
    return code


def _require_register_code(store: DocumentStore, email: str | None, phone: str | None, code: str | None) -> None:
    from app.modules.messages import email_ready, sms_ready
    from config.settings import Settings

    settings = Settings()
    needs_email = bool(email and email_ready(settings))
    needs_phone = bool(phone and sms_ready(settings))
    if not needs_email and not needs_phone:
        return
    digest = hashlib.sha256((code or "").strip().encode()).hexdigest()
    row = None
    if email:
        row = store.find_global("verification_codes", email=email, purpose="register", code_hash=digest)
    if not row and phone:
        row = store.find_global("verification_codes", phone=phone, purpose="register", code_hash=digest)
    if not row or row.get("used_at") or parse_iso(row["expires_at"]) <= utcnow():
        raise AppError("CODE_REQUIRED", "请先完成邮箱或短信验证码", 400)
    store.touch("verification_codes", row["id"], {"used_at": iso()})


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
