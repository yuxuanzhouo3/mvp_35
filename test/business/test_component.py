from fastapi.testclient import TestClient

from test.support import finished_job, register


def test_selection_acquisition_and_recall_components(client: TestClient):
    headers = register(client, "component@example.com")
    product_id = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "组件水杯", "sku": "cmp-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    ).json()["data"]["id"]
    job = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )
    report_id = job["result"]["analysis_id"]
    report = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()["data"]
    assert report["metrics"]["explanation_model"] == "rules"
    assert client.post(f"/api/v1/reports/{report_id}/acquire", headers=headers).status_code == 200
    finished_job(
        client,
        headers,
        client.post(
            "/api/v1/acquisition/tasks",
            headers=headers,
            json={"channel": "ecommerce", "platform": "amazon", "query": "cup", "seed_analysis_id": report_id},
        ),
    )
    leads = client.get("/api/v1/leads", headers=headers).json()["data"]["items"]
    scored = client.post("/api/v1/leads/score", headers=headers, json={"lead_id": leads[0]["id"]})
    assert scored.json()["data"]["scored_by"] == "rules"
    assert scored.json()["data"]["model_score"] is None
    reachable = next(item for item in leads if item.get("email") and not item["email"].startswith("bounce."))
    campaign = client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={"name": "组件", "lead_ids": [reachable["id"]]},
    ).json()["data"]["id"]
    assert client.post(f"/api/v1/campaigns/{campaign}/send", headers=headers).status_code == 409
    recall = client.post("/api/v1/recall", headers=headers, json={"lead_id": reachable["id"], "trigger": "churn"})
    assert recall.status_code == 200
    assert recall.json()["data"]["status"] == "queued"
