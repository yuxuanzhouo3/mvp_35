from fastapi.testclient import TestClient

from test.support import finished_job, register


def test_login_payment_selection_and_acquisition_start(client: TestClient):
    assert client.get("/api/v1/health/live").status_code == 200
    headers = register(client, "smoke@example.com")
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200

    checkout = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "smoke-pay"},
    )
    assert checkout.status_code == 200
    assert checkout.json()["data"]["status"] == "pending"

    catalog = client.post("/api/v1/catalog/search", headers=headers, json={"q": "杯"})
    assert catalog.status_code == 200
    assert catalog.json()["data"]["items"]

    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "冒烟水杯", "sku": "smoke-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    )
    assert created.status_code == 200
    product_id = created.json()["data"]["id"]
    analysis = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )
    report_id = analysis["result"]["analysis_id"]
    acquired = client.post(f"/api/v1/reports/{report_id}/acquire", headers=headers)
    assert acquired.status_code == 200
    assert acquired.json()["data"]["seed_analysis_id"] == report_id
    discovery = finished_job(
        client,
        headers,
        client.post(
            "/api/v1/acquisition/tasks",
            headers=headers,
            json={"channel": "ecommerce", "platform": "amazon", "query": "cup", "seed_analysis_id": report_id},
        ),
    )
    assert discovery["result"]["inserted"] >= 1
