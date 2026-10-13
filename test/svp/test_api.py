import json
from pathlib import Path

from fastapi.testclient import TestClient

from test.support import register

LIMIT = json.loads((Path(__file__).resolve().parents[2] / "backend" / "config" / "s4-v1.0.0.json").read_text())
TENANT_LIMIT = LIMIT["rate_limit_per_minute"]["tenant"]


def test_auth_idempotency_and_burst_under_the_tenant_limit(client: TestClient):
    assert client.get("/api/v1/users/me").status_code == 401
    headers = register(client, "svp-api@example.com")
    first = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "svp-api"},
    )
    second = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "svp-api"},
    )
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    clash = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"kind": "usage", "amount_fen": 100, "idempotency_key": "svp-api"},
    )
    assert clash.status_code == 409
    burst = min(20, TENANT_LIMIT)
    assert burst < TENANT_LIMIT
    for _ in range(burst):
        assert client.get("/api/v1/users/me", headers=headers).status_code == 200
