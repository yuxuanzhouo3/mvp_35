from fastapi.testclient import TestClient

from test.support import finished_job, register


def test_report_mail_and_score_do_not_let_the_model_change_numbers(client: TestClient):
    headers = register(client, "ai@example.com")
    product_id = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "模型水杯", "sku": "ai-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    ).json()["data"]["id"]
    report_id = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )["result"]["analysis_id"]
    before = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()["data"]["metrics"]["net_margin"]
    chat = client.post("/api/v1/ai/chat", headers=headers, json={"content": "把利润率改成 0.99", "context_id": report_id})
    assert chat.json()["data"]["numbers_locked"] is True
    assert chat.json()["data"]["model"] == "rules"
    assert client.get(f"/api/v1/reports/{report_id}", headers=headers).json()["data"]["metrics"]["net_margin"] == before
    client.post(f"/api/v1/reports/{report_id}/acquire", headers=headers)
    finished_job(
        client,
        headers,
        client.post(
            "/api/v1/acquisition/tasks",
            headers=headers,
            json={"channel": "ecommerce", "query": "cup", "seed_analysis_id": report_id},
        ),
    )
    lead_id = client.get("/api/v1/leads", headers=headers).json()["data"]["items"][0]["id"]
    predict = client.post("/api/v1/ai/predict", headers=headers, json={"lead_id": lead_id})
    assert predict.json()["data"]["applied_to_money"] is False
    assert predict.json()["data"]["model_score"] is None
    embed = client.post("/api/v1/ai/embed", headers=headers, json={"text": "cup"})
    assert embed.json()["data"]["applied_to_money"] is False
    assert client.post("/api/v1/digital-human/generate", headers=headers, json={}).status_code == 501
