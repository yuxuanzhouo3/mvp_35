from decimal import Decimal

from fastapi.testclient import TestClient

from app.modules.scale import margin_drift_points, needs_rule_fallback
from test.support import finished_job, register


def test_one_margin_experiment_falls_back_to_rules(client: TestClient):
    assert needs_rule_fallback(Decimal("0.50"), Decimal("0.40")) is True
    assert needs_rule_fallback(Decimal("0.50"), Decimal("0.48")) is False
    assert margin_drift_points(Decimal("0.50"), Decimal("0.44")) == Decimal("6.00")
    headers = register(client, "ab@example.com")
    product_id = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "实验水杯", "sku": "ab-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    ).json()["data"]["id"]
    report_id = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )["result"]["analysis_id"]
    before = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()["data"]["metrics"]["net_margin"]
    client.post("/api/v1/ai/chat", headers=headers, json={"content": "实验组把利润率改成 0.10", "context_id": report_id})
    assert client.get(f"/api/v1/reports/{report_id}", headers=headers).json()["data"]["metrics"]["net_margin"] == before
