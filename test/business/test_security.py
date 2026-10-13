from fastapi.testclient import TestClient

from app.modules.payment import sign_payment_event
from test.support import register


def test_tenants_cannot_read_each_other(client: TestClient):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")
    created = client.post(
        "/api/v1/products",
        headers=alice,
        json={"name": "甲的水杯", "sku": "alice-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    )
    product_id = created.json()["data"]["id"]
    assert client.get(f"/api/v1/products/{product_id}", headers=alice).status_code == 200
    hidden = client.get(f"/api/v1/products/{product_id}", headers=bob)
    assert hidden.status_code == 404
    bob_list = client.get("/api/v1/products", headers=bob).json()["data"]["items"]
    assert all(item["id"] != product_id for item in bob_list)


def test_unsigned_payment_and_logout_stay_closed(client: TestClient):
    headers = register(client, "reliable@example.com")
    events = {item["event"] for item in client.get("/api/v1/events", headers=headers).json()["data"]["items"]}
    assert "user.registered" in events
    assert "user.login" in events
    checkout = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "reliable-pay"},
    )
    payment_id = checkout.json()["data"]["id"]
    rejected = client.post(
        "/api/v1/payments/webhook",
        json={"event_id": "evt-bad", "payment_id": payment_id, "status": "succeeded", "signature": "nope"},
    )
    assert rejected.status_code == 401
    assert client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"] == []
    signature = sign_payment_event("test-secret", "evt-ok", payment_id, "succeeded")
    paid = client.post(
        "/api/v1/payments/webhook",
        json={"event_id": "evt-ok", "payment_id": payment_id, "status": "succeeded", "signature": signature},
    )
    assert paid.status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
