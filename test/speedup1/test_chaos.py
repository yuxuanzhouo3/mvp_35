from fastapi.testclient import TestClient

from app.modules.scale import rollback_signal
from test.support import finished_job, register


def test_bad_payment_and_a_dead_model_leave_the_api_up(client: TestClient):
    headers = register(client, "chaos@example.com")
    payment_id = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "chaos-pay"},
    ).json()["data"]["id"]
    rejected = client.post(
        "/api/v1/payments/webhook",
        json={"event_id": "evt-chaos", "payment_id": payment_id, "status": "succeeded", "signature": "nope"},
    )
    assert rejected.status_code == 401
    assert client.get("/api/v1/subscriptions", headers=headers).json()["data"]["items"] == []
    product_id = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "故障水杯", "sku": "chaos-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    ).json()["data"]["id"]
    report_id = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )["result"]["analysis_id"]
    report = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()["data"]
    assert report["explanation_model"] == "rules"
    assert report["metrics"]["net_margin"] == "0.4985"
    assert client.get("/api/v1/health/ready").status_code == 200
    assert rollback_signal(error_rate=0.02) == "s2_error_rate"
