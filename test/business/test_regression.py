import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.modules.events import NAMES
from app.modules.payment import sign_payment_event
from app.modules.scale import rollback_signal
from test.support import register

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def test_s1_contract_matches_the_versioned_config():
    scenario = json.loads((BACKEND / "config" / "s1-v1.0.0.json").read_text())
    assert scenario["id"] == "s1-v1.0.0"
    assert scenario["kpis"] == ["N%", "ActR", "TR", "OR", "AR", "QR", "ActR_cold", "RecR"]
    assert scenario["timings"] == ["AnaT", "LeadT", "AcqT", "ActT", "RecT"]
    assert scenario["north_star"] == "AR"
    assert set(scenario["events"]) == NAMES
    assert scenario["states"]["Payment"] == ["created", "pending", "succeeded", "failed", "refunded"]
    assert scenario["states"]["Lead"] == ["new", "scored", "qualified", "contacted", "replied", "won", "lost", "recalled"]


def test_repeated_reads_do_not_drift(client: TestClient):
    headers = register(client, "stable@example.com")
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "稳定水杯", "sku": "stable-1", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    )
    product_id = created.json()["data"]["id"]
    first = client.get(f"/api/v1/products/{product_id}", headers=headers).json()["data"]
    for _ in range(20):
        again = client.get(f"/api/v1/products/{product_id}", headers=headers)
        assert again.status_code == 200
        assert again.json()["data"]["sku"] == first["sku"]
        assert again.json()["data"]["target_price_usd"] == first["target_price_usd"]
    probe_errors = 0
    for _ in range(100):
        if client.get("/api/v1/health/live").status_code != 200:
            probe_errors += 1
    assert probe_errors / 100 <= 0.01
    assert rollback_signal(error_rate=probe_errors / 100) is None


def test_payment_replay_does_not_double_post(client: TestClient):
    headers = register(client, "stable-pay@example.com")
    first = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "stable-pay"},
    )
    second = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "stable-pay"},
    )
    payment_id = first.json()["data"]["id"]
    assert second.json()["data"]["id"] == payment_id
    signature = sign_payment_event("test-secret", "evt-stable", payment_id, "succeeded")
    body = {"event_id": "evt-stable", "payment_id": payment_id, "status": "succeeded", "signature": signature}
    for _ in range(5):
        replay = client.post("/api/v1/payments/webhook", json=body)
        assert replay.status_code == 200
        assert replay.json()["data"]["status"] == "succeeded"
    assert len(client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"]) == 1
    assert len(client.get("/api/v1/invoices", headers=headers).json()["data"]["items"]) == 1


def test_a_failed_call_does_not_break_the_next_one(client: TestClient):
    missing = client.get("/api/v1/users/me")
    assert missing.status_code == 401
    live = client.get("/api/v1/health/live")
    assert live.status_code == 200
    assert live.json()["data"]["status"] == "live"
    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
