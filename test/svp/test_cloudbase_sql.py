"""CloudBase SQL credential selection. No live network calls."""

import json
import time

import httpx

from db import cloudbase_sql


def _clear_env(monkeypatch):
    for name in (
        "CLOUDBASE_SECRET_ID",
        "CLOUDBASE_SECRET_KEY",
        "CLOUDBASE_SECRET_KEY_HEX",
        "CLOUDBASE_TOKEN",
        "TENCENTCLOUD_SECRETID",
        "TENCENTCLOUD_SECRETKEY",
        "TENCENTCLOUD_SESSIONTOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def test_environment_secret_is_used_without_a_session_token(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("TENCENTCLOUD_SECRETID", "id-from-env")
    monkeypatch.setenv("TENCENTCLOUD_SECRETKEY", "key-from-env")
    secret_id, secret_key, token = cloudbase_sql._credential()
    assert (secret_id, secret_key, token) == ("id-from-env", "key-from-env", "")
    headers = cloudbase_sql._signed_headers(secret_id, secret_key, token, "{}", 1_700_000_000, "ap-shanghai")
    assert "X-TC-Token" not in headers


def test_expired_login_file_is_refreshed(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    auth = tmp_path / "auth.json"
    auth.write_text(
        json.dumps(
            {
                "credential": {
                    "tmpSecretId": "old-id",
                    "tmpSecretKey": "old-key",
                    "tmpToken": "old-token",
                    "tmpExpired": int(time.time() - 10) * 1000,
                    "expired": int(time.time() + 86400) * 1000,
                    "refreshToken": "refresh-token",
                    "uin": "100",
                    "tokenId": "token-1",
                    "hash": "device-hash",
                }
            }
        )
    )
    monkeypatch.setattr(cloudbase_sql, "_AUTH", auth)

    def fake_post(url, json=None, timeout=None):
        assert url == cloudbase_sql._REFRESH_URL
        assert json["refreshToken"] == "refresh-token"
        assert json["hash"] == "device-hash"
        assert json["tokenId"] == "token-1"
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "tmpSecretId": "new-id",
                    "tmpSecretKey": "new-key",
                    "tmpToken": "new-token",
                    "tmpExpired": int(time.time() + 7200) * 1000,
                    "expired": int(time.time() + 86400) * 1000,
                    "refreshToken": "refresh-token-2",
                },
            },
            request=request,
        )

    monkeypatch.setattr(cloudbase_sql.httpx, "post", fake_post)
    secret_id, secret_key, token = cloudbase_sql._credential()
    assert (secret_id, secret_key, token) == ("new-id", "new-key", "new-token")
    saved = json.loads(auth.read_text())["credential"]
    assert saved["tmpSecretId"] == "new-id"
    assert saved["refreshToken"] == "refresh-token-2"
    assert saved["hash"] == "device-hash"
    assert saved["tokenId"] == "token-1"
