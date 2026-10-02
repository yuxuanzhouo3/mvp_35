import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

STAGES = ("mvp", "svp", "business", "speedup1", "speedup2", "speedup3")

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for entry in (str(ROOT), str(BACKEND)):
    if entry not in sys.path:
        sys.path.insert(0, entry)


@pytest.fixture(autouse=True)
def _keep_tests_off_real_channels(monkeypatch):
    for key in (
        "AUTH_EMAIL_SMTP_HOST",
        "AUTH_EMAIL_SMTP_USER",
        "AUTH_EMAIL_SMTP_PASS",
        "AUTH_EMAIL_FROM",
        "SMS_SECRET_ID",
        "SMS_SECRET_KEY",
        "SMS_SDK_APP_ID",
        "SMS_SIGN_NAME",
        "SMS_TEMPLATE_ID",
        "TENCENT_SMS_SECRET_ID",
        "TENCENT_SMS_SECRET_KEY",
        "TENCENT_SMS_APP_ID",
        "TENCENT_SMS_SIGN_NAME",
        "TENCENT_SMS_TEMPLATE_ID",
    ):
        monkeypatch.setenv(key, "")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ENGINE", "json")
    monkeypatch.setenv("DATA_PATH", str(tmp_path / "store.json"))
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("LEDGER_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("HUNYUAN_ENABLED", "false")
    monkeypatch.setenv("TONGYI_ENABLED", "false")
    monkeypatch.setenv("WECHAT_PAY_MODE", "disabled")
    monkeypatch.setenv("DEMO_SIGNING_HELPER", "false")
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def pytest_collection_modifyitems(config, items):
    del config
    for item in items:
        path = Path(str(item.fspath))
        for stage in STAGES:
            if stage in path.parts:
                item.add_marker(getattr(pytest.mark, stage))
                break
