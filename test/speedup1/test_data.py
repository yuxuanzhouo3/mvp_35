from fastapi.testclient import TestClient

from test.support import register


def test_same_payment_key_stays_one_row(client: TestClient):
    headers = register(client, "consistent@example.com")
    body = {"plan_id": "growth", "idempotency_key": "same-key"}
    first = client.post("/api/v1/payments/checkout", headers=headers, json=body).json()["data"]
    second = client.post("/api/v1/payments/checkout", headers=headers, json=body).json()["data"]
    listed = client.get("/api/v1/payments", headers=headers).json()["data"]["items"]
    assert first["id"] == second["id"]
    assert [item["id"] for item in listed] == [first["id"]]
