import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.errors import AppError


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(raw: str) -> bytes:
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def issue_access(secret: str, *, sub: str, sid: str, ttl_seconds: int) -> str:
    payload = {"sub": sub, "sid": sid, "exp": int(time.time()) + int(ttl_seconds)}
    encoded = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"pg1.{encoded}.{signature}"


def read_access(secret: str, token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "pg1":
        raise AppError("UNAUTHENTICATED", "登录凭证无效", 401)
    encoded, signature = parts[1], parts[2]
    expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise AppError("UNAUTHENTICATED", "登录凭证无效", 401)
    try:
        payload = json.loads(_decode(encoded))
    except (json.JSONDecodeError, ValueError) as exc:
        raise AppError("UNAUTHENTICATED", "登录凭证无效", 401) from exc
    if int(payload.get("exp") or 0) < int(time.time()):
        raise AppError("UNAUTHENTICATED", "登录已过期", 401)
    if not payload.get("sub") or not payload.get("sid"):
        raise AppError("UNAUTHENTICATED", "登录凭证无效", 401)
    return payload


def new_refresh() -> str:
    return f"pgr_{secrets.token_urlsafe(32)}"


def hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
