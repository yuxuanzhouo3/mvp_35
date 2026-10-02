from decimal import Decimal

from fastapi.testclient import TestClient

from app.services.common import sign_ledger
from app.services.profit import calculate


def test_profit_is_deterministic_without_a_model():
    metrics = calculate(
        {
            "cost_cny": "72",
            "target_price_usd": "40",
            "international_freight_usd": "2",
            "fx_usd_cny": "7.2",
            "target_market": "US",
            "tax_regime": "cn_us",
            "origin_country": "CN",
        }
    )
    assert metrics["landed_cost_usd"] == "12.00"
    assert metrics["channel_fee_usd"] == "7.16"
    assert metrics["tax_usd"] == "0.90"
    assert metrics["net_profit_usd"] == "19.94"
    assert metrics["net_margin"] == "0.4985"
    assert metrics["explanation_model"] == "rules"
    assert metrics["rules_version"] == "pg-rules-1.0"
    assert "19.94" in metrics["explanation"]
    assert Decimal(metrics["net_margin"]) >= Decimal("0.15")


def auth():
    return {"Authorization": "Bearer demo"}


def test_path_a_and_b(client: TestClient):
    created = client.post(
        "/api/v1/products",
        headers=auth(),
        json={
            "name": "智能温控水杯",
            "sku": "cup-500",
            "cost_cny": "72",
            "target_price_usd": "40",
            "international_freight_usd": "2",
            "fx_usd_cny": "7.2",
        },
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["data"]["id"]

    catalog = client.get("/api/v1/catalog/search", headers=auth(), params={"q": "露营"})
    assert catalog.status_code == 200
    assert catalog.json()["data"]["items"]

    analysis = client.post(f"/api/v1/products/{product_id}/analyses", headers=auth())
    assert analysis.status_code == 202, analysis.text
    job_id = analysis.json()["data"]["job_id"]
    job = client.get(f"/api/v1/jobs/{job_id}", headers=auth())
    assert job.json()["data"]["status"] == "succeeded", job.text
    report_id = job.json()["data"]["result"]["analysis_id"]
    report = client.get(f"/api/v1/analyses/{report_id}", headers=auth()).json()["data"]
    assert report["metrics"]["net_profit_usd"] == "19.94"
    assert report["explanation_model"] == "rules"
    assert report["stale"] is False

    changed = client.patch(
        f"/api/v1/products/{product_id}",
        headers=auth(),
        json={"target_market": "AU", "tax_regime": "cn_au"},
    )
    assert changed.status_code == 200
    stale = client.get(f"/api/v1/analyses/{report_id}", headers=auth()).json()["data"]
    assert stale["stale"] is True
    blocked = client.post(f"/api/v1/analyses/{report_id}/acquire", headers=auth())
    assert blocked.status_code == 409

    rerun = client.post(f"/api/v1/products/{product_id}/analyses", headers=auth())
    rerun_job = client.get(f"/api/v1/jobs/{rerun.json()['data']['job_id']}", headers=auth()).json()["data"]
    assert rerun_job["status"] == "succeeded"
    fresh_id = rerun_job["result"]["analysis_id"]
    acquired = client.post(f"/api/v1/analyses/{fresh_id}/acquire", headers=auth())
    assert acquired.status_code == 200
    assert acquired.json()["data"]["seed_analysis_id"] == fresh_id

    search = client.post(
        "/api/v1/lead-searches",
        headers=auth(),
        json={"channel": "ecommerce", "platform": "amazon", "query": "cup", "seed_analysis_id": fresh_id},
    )
    assert search.status_code == 202
    search_job = client.get(f"/api/v1/jobs/{search.json()['data']['job_id']}", headers=auth()).json()["data"]
    assert search_job["status"] == "succeeded"
    leads = client.get("/api/v1/leads", headers=auth(), params={"seed_analysis_id": fresh_id}).json()["data"]["items"]
    chosen = [item["id"] for item in leads if item.get("email") and not item["email"].startswith("bounce.")]
    assert chosen

    campaign = client.post(
        "/api/v1/campaigns",
        headers=auth(),
        json={"name": "美国水杯首轮", "lead_ids": chosen, "seed_analysis_id": fresh_id, "market_pack": "cn_us"},
    )
    campaign_id = campaign.json()["data"]["id"]
    early = client.post(f"/api/v1/campaigns/{campaign_id}/send", headers=auth())
    assert early.status_code == 409
    assert client.post(f"/api/v1/campaigns/{campaign_id}/drafts", headers=auth()).status_code == 200
    approved = client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=auth())
    assert approved.status_code == 200
    assert approved.json()["data"]["audience_snapshot"]["lead_ids"]
    sent = client.post(f"/api/v1/campaigns/{campaign_id}/send", headers=auth())
    assert sent.status_code == 202
    sent_job = client.get(f"/api/v1/jobs/{sent.json()['data']['job_id']}", headers=auth()).json()["data"]
    assert sent_job["status"] == "succeeded"

    opened = client.post(f"/api/v1/leads/{chosen[0]}/signals", headers=auth(), json={"type": "open"})
    assert opened.status_code == 200
    won = client.post(f"/api/v1/leads/{chosen[0]}/signals", headers=auth(), json={"type": "won"})
    assert won.json()["data"]["status"] == "won"

    metrics = client.get("/api/v1/metrics", headers=auth()).json()["data"]
    assert metrics["rates"]["net_margin"]["value"] is not None
    assert metrics["rates"]["act_r"]["value"] == "0.5000"
    assert metrics["rates"]["ar"]["value"] is not None
    assert Decimal(metrics["rates"]["ar"]["value"]) >= Decimal("0.08")
    assert metrics["timings_p50_seconds"]["ana_t"] is not None

    unsigned = client.post(
        "/api/v1/billing/agency/commissions",
        headers=auth(),
        json={"amount_fen": 1500, "idempotency_key": "agency-1", "signature": "bad"},
    )
    assert unsigned.status_code == 401
    signature = sign_ledger("test-secret", "agency-1", 1500, "agency_commission")
    body = {"amount_fen": 1500, "idempotency_key": "agency-1", "signature": signature, "channel_account_id": "agent_1"}
    first = client.post("/api/v1/billing/agency/commissions", headers=auth(), json=body)
    second = client.post("/api/v1/billing/agency/commissions", headers=auth(), json=body)
    assert first.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    ledgers = client.get("/api/v1/billing/ledgers", headers=auth()).json()["data"]["agency"]
    assert len(ledgers) == 1

    webhook = client.post("/api/v1/webhooks/wechat-pay", json={"event": "SUCCESS"})
    assert webhook.status_code == 401
    order = client.post("/api/v1/billing/orders", headers=auth(), json={"plan_id": "growth"})
    assert order.status_code == 200
    assert order.json()["data"]["status"] == "pending"
    queried = client.post(f"/api/v1/billing/orders/{order.json()['data']['id']}/query", headers=auth())
    assert queried.json()["data"]["granted"] is False

    empty = client.get("/api/v1/metrics", headers={"Authorization": "Bearer demo:other"}).json()["data"]
    assert empty["rates"]["act_r"]["value"] is None
