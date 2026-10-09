from urllib.parse import urlencode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.modules.alipay_pay import _sign
from test.support import register


def _rsa_pems() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def test_unconfigured_channels_stay_closed(client: TestClient):
    settings = client.app.state.settings
    settings.wechat_app_id = ""
    settings.wechat_app_secret = ""
    settings.wechat_miniprogram_app_id = ""
    settings.wechat_miniprogram_app_secret = ""
    settings.alipay_app_id = ""
    settings.alipay_private_key = ""
    settings.alipay_public_key = ""
    settings.alipay_alipay_public_key = ""
    settings.wechat_pay_mode = "disabled"

    wechat = client.get("/api/v1/auth/wechat/authorize")
    assert wechat.status_code == 501
    assert wechat.json()["error"]["details"]["placeholder"] is True
    mini = client.post("/api/v1/auth/miniprogram", json={})
    assert mini.status_code == 501

    headers = register(client, "channel-closed@example.com")
    order = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "provider": "alipay", "idempotency_key": "ali-closed"},
    )
    assert order.status_code == 200
    assert order.json()["data"]["pay_url"] is None
    assert order.json()["data"]["status"] == "pending"
    assert "不会发放权益" in order.json()["data"]["message"]
    wechat_order = client.post(
        "/api/v1/billing/orders",
        headers=headers,
        json={"plan_id": "growth", "provider": "wechat"},
    )
    assert wechat_order.json()["data"]["code_url"] is None
    queried = client.post(f"/api/v1/billing/orders/{wechat_order.json()['data']['id']}/query", headers=headers)
    assert queried.json()["data"]["granted"] is False


def test_alipay_books_only_after_rsa2(client: TestClient):
    headers = register(client, "alipay@example.com")
    private_pem, public_pem = _rsa_pems()
    settings = client.app.state.settings
    settings.alipay_app_id = "2021000000000000"
    settings.alipay_private_key = private_pem
    settings.alipay_alipay_public_key = public_pem
    payment = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "provider": "alipay", "idempotency_key": "ali-growth"},
    ).json()["data"]
    assert payment["pay_url"].startswith("https://openapi.alipay.com/gateway.do?")
    assert payment["status"] == "pending"
    assert client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"] == []

    unsigned = client.post(
        "/api/v1/webhooks/alipay",
        content=urlencode({"out_trade_no": payment["id"], "trade_status": "TRADE_SUCCESS", "total_amount": "299.00"}),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert unsigned.status_code == 401
    assert client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"] == []

    params = {
        "out_trade_no": payment["id"],
        "trade_no": "ali-txn-1",
        "trade_status": "TRADE_SUCCESS",
        "total_amount": "299.00",
        "sign_type": "RSA2",
    }
    params["sign"] = _sign(private_pem, params)
    paid = client.post(
        "/api/v1/webhooks/alipay",
        content=urlencode(params),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["status"] == "succeeded"
    assert len(client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"]) == 1
    assert len(client.get("/api/v1/invoices", headers=headers).json()["data"]["items"]) == 1


def test_alipay_page_pay_encrypts_biz_content(client: TestClient):
    headers = register(client, "alipay-aes@example.com")
    private_pem, public_pem = _rsa_pems()
    settings = client.app.state.settings
    settings.alipay_app_id = "2021000000000000"
    settings.alipay_private_key = private_pem
    settings.alipay_alipay_public_key = public_pem
    settings.alipay_aes_key = "MDEyMzQ1Njc4OWFiY2RlZg=="
    payment = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "provider": "alipay", "idempotency_key": "ali-aes"},
    ).json()["data"]
    assert "encrypt_type=AES" in payment["pay_url"]
    assert "out_trade_no" not in payment["pay_url"]
    assert payment["status"] == "pending"


def test_payment_test_amount_overrides_paid_plans(client: TestClient):
    headers = register(client, "amount-test@example.com")
    client.app.state.settings.payment_test_amount_fen = 10
    summary = client.get("/api/v1/billing/summary", headers=headers).json()["data"]
    plans = {item["id"]: item["amount_fen"] for item in summary["plans"]}
    assert plans["free"] == 0
    assert plans["growth"] == 10
    assert plans["scale"] == 10
    assert summary["payment_testing"] is True
    payment = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "fen-10"},
    ).json()["data"]
    assert payment["amount"] == 10


def test_wechat_authorize_url_does_not_call_wechat(client: TestClient):
    settings = client.app.state.settings
    settings.wechat_app_id = "wx-test-app"
    settings.wechat_app_secret = "test-secret"
    settings.wechat_oauth_redirect = "https://pickglobal.mornscience.top/login/wechat"
    body = client.get("/api/v1/auth/wechat/authorize").json()["data"]
    assert body["url"].startswith("https://open.weixin.qq.com/connect/qrconnect?")
    assert "wx-test-app" in body["url"]
    assert "redirect_uri=" in body["url"]
