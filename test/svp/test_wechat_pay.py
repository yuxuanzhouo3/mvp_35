import base64
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient

from test.support import register


def test_wechat_notify_books_subscription_invoice_only_after_rsa(client: TestClient):
    headers = register(client, "wechat-pay@example.com")
    payment = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "wx-growth"},
    ).json()["data"]
    unsigned = client.post("/api/v1/webhooks/wechat-pay", json={"event": "SUCCESS"})
    assert unsigned.status_code == 401
    assert client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"] == []

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    client.app.state.settings.wechat_pay_platform_public_key = public_pem
    client.app.state.settings.wechat_pay_api_v3_key = "12345678901234567890123456789012"
    trade = {
        "trade_state": "SUCCESS",
        "out_trade_no": payment["id"],
        "transaction_id": "wx-txn-1",
        "amount": {"total": payment["amount"]},
    }
    aes = AESGCM(client.app.state.settings.wechat_pay_api_v3_key.encode())
    nonce = "nonce12bytes"
    ciphertext = base64.b64encode(aes.encrypt(nonce.encode(), json.dumps(trade).encode(), b"transaction")).decode()
    body = json.dumps(
        {
            "id": "wx-notify-1",
            "resource": {
                "algorithm": "AEAD_AES_256_GCM",
                "ciphertext": ciphertext,
                "associated_data": "transaction",
                "nonce": nonce,
            },
        },
        separators=(",", ":"),
    )
    timestamp, wx_nonce = "1710000000", "notice-nonce"
    signature = base64.b64encode(
        private_key.sign(
            f"{timestamp}\n{wx_nonce}\n{body}\n".encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    ).decode()
    paid = client.post(
        "/api/v1/webhooks/wechat-pay",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Wechatpay-Timestamp": timestamp,
            "Wechatpay-Nonce": wx_nonce,
            "Wechatpay-Signature": signature,
            "Wechatpay-Serial": "TESTSERIAL",
        },
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["status"] == "succeeded"
    assert len(client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"]) == 1
    assert len(client.get("/api/v1/invoices", headers=headers).json()["data"]["items"]) == 1
    replay = client.post(
        "/api/v1/webhooks/wechat-pay",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Wechatpay-Timestamp": timestamp,
            "Wechatpay-Nonce": wx_nonce,
            "Wechatpay-Signature": signature,
            "Wechatpay-Serial": "TESTSERIAL",
        },
    )
    assert replay.status_code == 200
    assert len(client.get("/api/v1/invoices", headers=headers).json()["data"]["items"]) == 1


def _enable_wechat(client: TestClient):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    settings = client.app.state.settings
    settings.wechat_pay_mode = "live"
    settings.wechat_pay_appid = "wx-web-app"
    settings.wechat_pay_mchid = "1900000001"
    settings.wechat_pay_serial_no = "SERIAL"
    settings.wechat_pay_private_key = private_pem
    settings.wechat_pay_notify_url = "https://pickglobal.mornscience.top/api/v1/webhooks/wechat-pay"
    settings.wechat_miniprogram_app_id = ""
    return private_key


def test_web_checkout_returns_native_code_url(client: TestClient, monkeypatch):
    _enable_wechat(client)

    class Response:
        def json(self):
            return {"code_url": "weixin://wxpay/bizpayurl?pr=web"}

    monkeypatch.setattr("app.modules.wechat_pay.httpx.post", lambda *args, **kwargs: Response())
    headers = register(client, "wechat-web@example.com")
    payment = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "provider": "wechat", "scene": "web", "idempotency_key": "wx-web"},
    )
    assert payment.status_code == 200, payment.text
    data = payment.json()["data"]
    assert data["code_url"] == "weixin://wxpay/bizpayurl?pr=web"
    assert data["jsapi"] is None
    assert data["status"] == "pending"
    assert client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"] == []


def test_miniprogram_checkout_returns_signed_jsapi_params(client: TestClient, monkeypatch):
    private_key = _enable_wechat(client)

    class Response:
        def json(self):
            return {"prepay_id": "wx-prepay-1"}

    monkeypatch.setattr("app.modules.wechat_pay.httpx.post", lambda *args, **kwargs: Response())
    headers = register(client, "wechat-mini@example.com")
    missing = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "provider": "wechat", "scene": "miniprogram", "idempotency_key": "wx-mini-missing"},
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "WECHAT_OPENID_REQUIRED"

    paid = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={
            "plan_id": "growth",
            "provider": "wechat",
            "scene": "miniprogram",
            "openid": "openid-mini",
            "idempotency_key": "wx-mini",
        },
    )
    assert paid.status_code == 200, paid.text
    jsapi = paid.json()["data"]["jsapi"]
    assert jsapi["appId"] == "wx-web-app"
    assert jsapi["package"] == "prepay_id=wx-prepay-1"
    assert jsapi["signType"] == "RSA"
    message = f"{jsapi['appId']}\n{jsapi['timeStamp']}\n{jsapi['nonceStr']}\n{jsapi['package']}\n".encode()
    private_key.public_key().verify(base64.b64decode(jsapi["paySign"]), message, padding.PKCS1v15(), hashes.SHA256())
    assert client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"] == []
