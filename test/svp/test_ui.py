from fastapi.testclient import TestClient

from test.support import finished_job, register


def test_phone_and_miniprogram_clients_get_a_session_shape(client: TestClient):
    headers = register(client, "mobile@example.com")
    me = client.get("/api/v1/users/me", headers=headers).json()["data"]
    assert me["user"]["email"] == "mobile@example.com"
    assert me["tenant"]["id"]
    assert me["role"]
    assert "password_hash" not in me["user"]
    product_id = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "手机水杯", "sku": "mobile-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    ).json()["data"]["id"]
    job = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )
    report = client.get(f"/api/v1/reports/{job['result']['analysis_id']}", headers=headers).json()["data"]
    assert report["metrics"]["net_margin"]
    assert report["market"] == "US"
    mini = client.post("/api/v1/auth/miniprogram", headers=headers, json={})
    assert mini.status_code == 501
    assert mini.json()["error"]["details"]["placeholder"] is True
