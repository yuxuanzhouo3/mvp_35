from fastapi.testclient import TestClient

from test.support import finished_job, register


def test_core_routes_respond(client: TestClient):
    assert client.get("/api/v1/health/live").json()["data"]["status"] == "live"
    assert client.get("/api/v1/health/ready").json()["data"]["status"] == "ready"
    headers = register(client, "api@example.com")
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200
    assert client.get("/api/v1/users/me").status_code == 401
    checkout = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "api-pay"},
    )
    assert checkout.status_code == 200
    assert client.get("/api/v1/payments", headers=headers).status_code == 200
    assert client.post("/api/v1/catalog/search", headers=headers, json={"q": ""}).status_code == 200
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "接口水杯", "sku": "api-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    )
    product_id = created.json()["data"]["id"]
    assert client.get("/api/v1/products", headers=headers).status_code == 200
    job = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )
    report_id = job["result"]["analysis_id"]
    assert client.get(f"/api/v1/reports/{report_id}", headers=headers).status_code == 200
    assert client.post(f"/api/v1/reports/{report_id}/acquire", headers=headers).status_code == 200
    task = client.post(
        "/api/v1/acquisition/tasks",
        headers=headers,
        json={"channel": "ecommerce", "query": "cup", "seed_analysis_id": report_id},
    )
    assert task.status_code == 202
    assert client.get("/api/v1/leads", headers=headers).status_code == 200
    assert client.get("/api/v1/kpi/dashboard", headers=headers).status_code == 200
