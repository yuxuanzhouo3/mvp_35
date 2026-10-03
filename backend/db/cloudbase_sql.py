"""Execute SQL on the CloudBase PostgreSQL instance for one environment.

Credentials come from the process environment or the CloudBase CLI login file.
This module never prints them. A baked login file expires after about two hours;
the refresh token in that file is exchanged at https://iaas.cloud.tencent.com/tcb_refresh
so a Cloud Run instance can keep calling SQL after the temporary secret lapses.
"""

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

_HOST = "tcb.tencentcloudapi.com"
_SERVICE = "tcb"
_VERSION = "2018-06-08"
_REFRESH_URL = "https://iaas.cloud.tencent.com/tcb_refresh"
_AUTH = Path.home() / ".config" / ".cloudbase" / "auth.json"
_log = logging.getLogger("pickglobal.cloudbase")
_logged_source: set[str] = set()


class CloudBaseSqlError(RuntimeError):
    pass


def execute_pg_sql(env_id: str, sql: str, *, region: str = "ap-shanghai") -> dict:
    if not env_id:
        raise CloudBaseSqlError("CLOUDBASE_ENV_ID is empty")
    secret_id, secret_key, token = _credential()
    payload = json.dumps({"EnvId": env_id, "Sql": sql}, ensure_ascii=False, separators=(",", ":"))
    timestamp = int(time.time())
    headers = _signed_headers(secret_id, secret_key, token, payload, timestamp, region)
    response = httpx.post(f"https://{_HOST}", content=payload.encode(), headers=headers, timeout=60)
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise CloudBaseSqlError(f"CloudBase SQL returned HTTP {response.status_code}") from exc
    result = body.get("Response") or {}
    error = result.get("Error")
    if error or response.status_code >= 400:
        message = (error or {}).get("Message") or f"HTTP {response.status_code}"
        raise CloudBaseSqlError(message)
    rows = []
    for raw in result.get("Rows") or []:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        rows.append(parsed)
    return {"columns": result.get("Columns") or [], "rows": rows}


def _credential() -> tuple[str, str, str]:
    from_env = _env_credential()
    if from_env:
        _note_source("environment")
        return from_env
    if not _AUTH.exists():
        raise CloudBaseSqlError("CloudBase CLI is not logged in. Run tcb login.")
    data = json.loads(_AUTH.read_text())
    cred = data.get("credential") or {}
    expires = _seconds(cred.get("tmpExpired") or cred.get("accessTokenExpired"))
    refresh_until = _seconds(cred.get("expired"))
    if expires - time.time() < 120:
        if not cred.get("refreshToken") or refresh_until <= time.time():
            raise CloudBaseSqlError("CloudBase temporary secret expired. Run tcb login.")
        cred = _refresh_file(data)
    secret_id = cred.get("tmpSecretId") or cred.get("secretId") or ""
    secret_key = cred.get("tmpSecretKey") or cred.get("secretKey") or ""
    token = cred.get("tmpToken") or cred.get("token") or ""
    if not secret_id or not secret_key or not token:
        raise CloudBaseSqlError("CloudBase CLI login has no temporary secret. Run tcb login.")
    _note_source("login file")
    return secret_id, secret_key, token


def _note_source(source: str) -> None:
    if source in _logged_source:
        return
    _logged_source.add(source)
    _log.info("CloudBase SQL credential source: %s", source)


def _env_credential() -> tuple[str, str, str] | None:
    secret_id = os.environ.get("CLOUDBASE_SECRET_ID", "").strip() or os.environ.get("TENCENTCLOUD_SECRETID", "").strip()
    secret_key = os.environ.get("CLOUDBASE_SECRET_KEY", "").strip() or os.environ.get("TENCENTCLOUD_SECRETKEY", "").strip()
    key_hex = os.environ.get("CLOUDBASE_SECRET_KEY_HEX", "").strip()
    token = os.environ.get("CLOUDBASE_TOKEN", "").strip() or os.environ.get("TENCENTCLOUD_SESSIONTOKEN", "").strip()
    if key_hex and not secret_key:
        secret_key = bytes.fromhex(key_hex).decode()
    if secret_id and secret_key:
        return secret_id, secret_key, token
    return None


def _seconds(value) -> float:
    number = float(value or 0)
    if number > 10_000_000_000:
        return number / 1000
    return number


def _refresh_file(data: dict) -> dict:
    cred = data.get("credential") or {}
    device_hash = _device_hash(cred)
    payload = {
        "tmpSecretId": cred.get("tmpSecretId") or cred.get("secretId") or "",
        "tmpSecretKey": cred.get("tmpSecretKey") or cred.get("secretKey") or "",
        "tmpToken": cred.get("tmpToken") or cred.get("token") or "",
        "tmpExpired": cred.get("tmpExpired") or cred.get("accessTokenExpired"),
        "expired": cred.get("expired"),
        "authTime": cred.get("authTime"),
        "refreshToken": cred.get("refreshToken") or "",
        "uin": cred.get("uin") or "",
        "hash": device_hash,
    }
    if cred.get("tokenId"):
        payload["tokenId"] = cred["tokenId"]
    response = httpx.post(_REFRESH_URL, json=payload, timeout=15)
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise CloudBaseSqlError("CloudBase temporary secret expired. Run tcb login.") from exc
    if body.get("code") != 0 or not isinstance(body.get("data"), dict):
        raise CloudBaseSqlError("CloudBase temporary secret expired. Run tcb login.")
    fresh = body["data"]
    if not (fresh.get("tmpSecretId") or fresh.get("secretId")):
        raise CloudBaseSqlError("CloudBase temporary secret expired. Run tcb login.")
    # The refresh response omits the device hash. Keep it so the next instance can renew.
    fresh.setdefault("hash", device_hash)
    if cred.get("tokenId"):
        fresh.setdefault("tokenId", cred["tokenId"])
    _AUTH.parent.mkdir(parents=True, exist_ok=True)
    _AUTH.write_text(json.dumps({"credential": fresh}, ensure_ascii=False))
    _log.info("CloudBase SQL credential refreshed")
    return fresh


def _device_hash(cred: dict) -> str:
    stored = str(cred.get("hash") or os.environ.get("CLOUDBASE_DEVICE_HASH") or "").strip()
    if stored:
        return stored
    return hashlib.md5(_mac_address().encode()).hexdigest()


def _mac_address() -> str:
    node = uuid.getnode()
    return ":".join(f"{(node >> shift) & 0xFF:02x}" for shift in (40, 32, 24, 16, 8, 0))


def _signed_headers(secret_id: str, secret_key: str, token: str, payload: str, timestamp: int, region: str) -> dict:
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    action = "ExecutePGSql"
    content_type = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{content_type}\nhost:{_HOST}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode()).hexdigest()
    canonical_request = "\n".join(["POST", "/", "", canonical_headers, signed_headers, hashed_payload])
    scope = f"{date}/{_SERVICE}/tc3_request"
    string_to_sign = "\n".join(
        ["TC3-HMAC-SHA256", str(timestamp), scope, hashlib.sha256(canonical_request.encode()).hexdigest()]
    )
    secret_date = hmac.new(("TC3" + secret_key).encode(), date.encode(), hashlib.sha256).digest()
    secret_service = hmac.new(secret_date, _SERVICE.encode(), hashlib.sha256).digest()
    secret_signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
    signature = hmac.new(secret_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
    )
    headers = {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Host": _HOST,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": _VERSION,
        "X-TC-Region": region,
    }
    if token:
        headers["X-TC-Token"] = token
    return headers
