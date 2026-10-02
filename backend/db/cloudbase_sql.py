"""Execute SQL on the CloudBase PostgreSQL instance for one environment.

Credentials stay in the CloudBase CLI login file. This module never prints them.
"""

import hashlib
import hmac
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

_HOST = "tcb.tencentcloudapi.com"
_SERVICE = "tcb"
_VERSION = "2018-06-08"
_AUTH = Path.home() / ".config" / ".cloudbase" / "auth.json"


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
    secret_id = os.environ.get("CLOUDBASE_SECRET_ID", "").strip()
    secret_key = os.environ.get("CLOUDBASE_SECRET_KEY", "").strip()
    key_hex = os.environ.get("CLOUDBASE_SECRET_KEY_HEX", "").strip()
    token = os.environ.get("CLOUDBASE_TOKEN", "").strip()
    if key_hex and not secret_key:
        secret_key = bytes.fromhex(key_hex).decode()
    if secret_id and secret_key and token:
        return secret_id, secret_key, token
    if not _AUTH.exists():
        raise CloudBaseSqlError("CloudBase CLI is not logged in. Run tcb login.")
    data = json.loads(_AUTH.read_text())
    cred = data.get("credential") or {}
    expires = _seconds(cred.get("tmpExpired"))
    if expires - time.time() < 120:
        _refresh_cli()
        data = json.loads(_AUTH.read_text())
        cred = data.get("credential") or {}
    secret_id = cred.get("tmpSecretId") or ""
    secret_key = cred.get("tmpSecretKey") or ""
    token = cred.get("tmpToken") or ""
    if not secret_id or not secret_key or not token:
        raise CloudBaseSqlError("CloudBase CLI login has no temporary secret. Run tcb login.")
    return secret_id, secret_key, token


def _seconds(value) -> float:
    number = float(value or 0)
    if number > 10_000_000_000:
        return number / 1000
    return number


def _refresh_cli() -> None:
    binary = shutil.which("tcb")
    if not binary:
        candidate = Path.home() / ".nvm" / "versions" / "node" / "v20.19.5" / "bin" / "tcb"
        binary = str(candidate) if candidate.exists() else ""
    if not binary:
        raise CloudBaseSqlError("CloudBase temporary secret expired and tcb is not on PATH.")
    completed = subprocess.run([binary, "env", "list", "--json"], capture_output=True, text=True, timeout=60)
    if completed.returncode != 0:
        raise CloudBaseSqlError("CloudBase temporary secret expired. Run tcb login.")


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
    return {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Host": _HOST,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": _VERSION,
        "X-TC-Region": region,
        "X-TC-Token": token,
    }
