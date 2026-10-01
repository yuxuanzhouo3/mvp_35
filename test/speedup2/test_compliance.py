from fastapi.testclient import TestClient

from test.support import register


def test_suppression_audit_and_delete_are_recorded(client: TestClient):
    headers = register(client, "privacy@example.com")
    events = {item["event"] for item in client.get("/api/v1/events", headers=headers).json()["data"]["items"]}
    assert {"user.registered", "user.login"} <= events
    suppressed = client.post("/api/v1/suppressions", headers=headers, json={"email": "Buyer@Example.com"})
    assert suppressed.status_code == 200
    assert suppressed.json()["data"]["email"] == "buyer@example.com"
    product_id = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "删除水杯", "sku": "privacy-cup", "cost_cny": "10", "target_price_usd": "20"},
    ).json()["data"]["id"]
    assert client.delete(f"/api/v1/products/{product_id}", headers=headers).status_code == 200
    listed = client.get("/api/v1/products", headers=headers).json()["data"]["items"]
    assert all(item["id"] != product_id for item in listed)
    assert client.get(f"/api/v1/products/{product_id}", headers=headers).status_code == 404
