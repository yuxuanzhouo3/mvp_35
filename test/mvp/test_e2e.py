from decimal import Decimal

from fastapi.testclient import TestClient

from test.support import finished_job, register


def test_login_selection_report_acquire_and_mvp_kpis(client: TestClient):
    headers = register(client, "mvp-path@example.com")
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "主链路水杯", "sku": "mvp-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    )
    product_id = created.json()["data"]["id"]
    analysis = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )
    report_id = analysis["result"]["analysis_id"]
    report = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()["data"]
    assert report["metrics"]["rules_version"] == "pg-rules-1.0"
    assert report["explanation_model"] == "rules"
    acquired = client.post(f"/api/v1/reports/{report_id}/acquire", headers=headers)
    assert acquired.status_code == 200
    assert acquired.json()["data"]["seed_analysis_id"] == report_id

    finished_job(
        client,
        headers,
        client.post(
            "/api/v1/acquisition/tasks",
            headers=headers,
            json={"channel": "ecommerce", "platform": "amazon", "query": "cup", "seed_analysis_id": report_id},
        ),
    )
    leads = client.get("/api/v1/leads", headers=headers, params={"seed_analysis_id": report_id}).json()["data"]["items"]
    chosen = [item["id"] for item in leads if item.get("email") and not item["email"].startswith("bounce.")]
    campaign = client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={"name": "主链路", "lead_ids": chosen, "seed_analysis_id": report_id},
    )
    campaign_id = campaign.json()["data"]["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/drafts", headers=headers).status_code == 200
    assert client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=headers).status_code == 200
    finished_job(client, headers, client.post(f"/api/v1/campaigns/{campaign_id}/send", headers=headers))
    assert client.post(f"/api/v1/leads/{chosen[0]}/signals", headers=headers, json={"type": "open"}).status_code == 200
    assert client.post(f"/api/v1/leads/{chosen[1]}/signals", headers=headers, json={"type": "open"}).status_code == 200
    assert client.post(f"/api/v1/leads/{chosen[0]}/signals", headers=headers, json={"type": "won"}).status_code == 200

    board = client.get("/api/v1/kpi/dashboard", headers=headers).json()["data"]
    assert board["timings"]["p50_seconds"]["ana_t"] <= 120
    assert board["timings"]["p50_seconds"]["lead_t"] <= 180
    assert Decimal(board["headline"]["tr"]["value"]) >= Decimal("0.95")
    assert Decimal(board["headline"]["open_r"]["value"]) >= Decimal("0.40")
    assert Decimal(board["headline"]["ar"]["value"]) >= Decimal("0.08")
