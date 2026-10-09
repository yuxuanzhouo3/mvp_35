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
    monkeypatch.setenv("PAYMENT_TEST_AMOUNT_FEN", "0")
    monkeypatch.setenv("DEMO_SIGNING_HELPER", "false")
    monkeypatch.setenv("FX_API_URL", "")
    monkeypatch.setenv("PRICER_API_URL", "")
    monkeypatch.setenv("PRICER_API_KEY", "")
    for key in (
        "ALIBABA_APP_KEY",
        "ALIBABA_APP_SECRET",
        "ALIBABA_ACCESS_TOKEN",
        "ALIBABA_REFRESH_TOKEN",
        "ALIBABA_REFRESH_TOKEN_TIMEOUT",
        "TAOBAO_APP_KEY",
        "TAOBAO_APP_SECRET",
        "TAOBAO_ADZONE_ID",
        "PDD_CLIENT_ID",
        "PDD_CLIENT_SECRET",
        "PDD_PID",
        "JD_APP_KEY",
        "JD_APP_SECRET",
        "AMAZON_ACCESS_KEY",
        "AMAZON_SECRET_KEY",
        "AMAZON_PARTNER_TAG",
        "WALMART_PUBLISHER_ID",
        "WALMART_CONSUMER_ID",
        "EBAY_CLIENT_ID",
        "EBAY_CLIENT_SECRET",
        "AMAZON_SP_CLIENT_ID",
        "AMAZON_SP_CLIENT_SECRET",
        "AMAZON_SP_REFRESH_TOKEN",
        "WALMART_MARKET_CLIENT_ID",
        "WALMART_MARKET_CLIENT_SECRET",
        "TAOBAO_SESSION",
        "PDD_ACCESS_TOKEN",
        "TEMU_APP_KEY",
        "TEMU_APP_SECRET",
        "TEMU_ACCESS_TOKEN",
        "LINKEDIN_CLIENT_ID",
        "LINKEDIN_CLIENT_SECRET",
        "LINKEDIN_ACCESS_TOKEN",
        "LINKEDIN_AD_ACCOUNT_ID",
        "FACEBOOK_APP_ID",
        "FACEBOOK_APP_SECRET",
        "FACEBOOK_PAGE_ID",
        "FACEBOOK_PAGE_ACCESS_TOKEN",
        "WECOM_CORP_ID",
        "WECOM_CONTACT_SECRET",
        "WECOM_FOLLOW_USERID",
        "DOUYIN_CLIENT_KEY",
        "DOUYIN_CLIENT_SECRET",
        "DOUYIN_ACCESS_TOKEN",
        "XHS_APP_ID",
        "XHS_APP_SECRET",
        "XHS_ACCESS_TOKEN",
        "KUAISHOU_APP_ID",
        "KUAISHOU_APP_SECRET",
        "KUAISHOU_ACCESS_TOKEN",
        "ALIBABA_INTL_APP_KEY",
        "ALIBABA_INTL_APP_SECRET",
        "ALIBABA_INTL_ACCESS_TOKEN",
        "QICHACHA_APP_KEY",
        "QICHACHA_SECRET_KEY",
        "TIANYANCHA_TOKEN",
        "QIXIN_APP_KEY",
        "QIXIN_SECRET_KEY",
        "AGENCY_PARENT_ACCOUNT_ID",
    ):
        monkeypatch.setenv(key, "")
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
