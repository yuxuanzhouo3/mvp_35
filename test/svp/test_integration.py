from fastapi.testclient import TestClient

from app.modules.payment import sign_payment_event
from test.support import finished_job, register


def test_user_roundtrip_is_stored(client: TestClient):
    headers = register(client, "integrate-user@example.com")
    me = client.get("/api/v1/users/me", headers=headers).json()["data"]
    assert me["user"]["email"] == "integrate-user@example.com"
    assert me["tenant"]["id"]
    assert "password_hash" not in me["user"]


def test_signed_webhook_grants_one_subscription(client: TestClient):
    headers = register(client, "integrate-pay@example.com")
    payment_id = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "integrate-pay"},
    ).json()["data"]["id"]
    signature = sign_payment_event("test-secret", "evt-integrate", payment_id, "succeeded")
    paid = client.post(
        "/api/v1/payments/webhook",
        json={"event_id": "evt-integrate", "payment_id": payment_id, "status": "succeeded", "signature": signature},
    )
    assert paid.status_code == 200
    assert len(client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"]) == 1
    assert len(client.get("/api/v1/invoices", headers=headers).json()["data"]["items"]) == 1


def test_selection_still_scores_when_the_model_is_off(client: TestClient):
    headers = register(client, "integrate-ai@example.com")
    product_id = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "集成水杯", "sku": "int-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    ).json()["data"]["id"]
    job = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )
    report = client.get(f"/api/v1/reports/{job['result']['analysis_id']}", headers=headers).json()["data"]
    assert report["explanation_model"] == "rules"
    assert report["numbers_locked"] is True
    assert report["metrics"]["net_margin"] == "0.4985"
