from decimal import Decimal, ROUND_HALF_UP

from fastapi.testclient import TestClient

from test.support import finished_job, register, show_rate

MONEY = Decimal("0.01")
RATE = Decimal("0.0001")

# project.md §2 S2 floors. Denominator 0 stays blank, so these apply only when the sample exists.
RATE_FLOORS = {
    "net_margin": Decimal("0.15"),
    "act_r": Decimal("0.50"),
    "tr": Decimal("0.95"),
    "open_r": Decimal("0.40"),
    "ar": Decimal("0.08"),
    "qr": Decimal("0.60"),
    "act_r_cold": Decimal("0.25"),
    "rec_r": Decimal("0.10"),
}
TIMING_CEILINGS = {
    "ana_t": 120,
    "lead_t": 180,
    "acq_t": 3 * 86400,
    "act_t": 86400,
    "rec_t": 86400,
}
RATE_CODES = {
    "net_margin": "N%",
    "act_r": "ActR",
    "tr": "TR",
    "open_r": "OR",
    "ar": "AR",
    "qr": "QR",
    "act_r_cold": "ActR_cold",
    "rec_r": "RecR",
}


def _product(client: TestClient, headers: dict) -> str:
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "智能温控水杯",
            "sku": "cup-500",
            "cost_cny": "72",
            "packaging_cny": "0",
            "domestic_freight_cny": "0",
            "international_freight_usd": "2",
            "target_price_usd": "40",
            "fx_usd_cny": "7.2",
        },
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]["id"]


def _analyze(client: TestClient, headers: dict, product_id: str) -> dict:
    job = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )
    report_id = job["result"]["analysis_id"]
    report = client.get(f"/api/v1/reports/{report_id}", headers=headers)
    assert report.status_code == 200, report.text
    return report.json()["data"]


def test_profit_formula_and_market_must_be_recalculated(client: TestClient):
    headers = register(client, "kpi-profit@example.com")
    catalog = client.post("/api/v1/catalog/search", headers=headers, json={"q": "宠物"})
    assert catalog.status_code == 200
    assert catalog.json()["data"]["items"]

    imported = finished_job(
        client,
        headers,
        client.post(
            "/api/v1/products/import",
            headers=headers,
            json={"csv": "name,sku,target_price_usd,cost_cny\n折叠灯,lamp-9,29,45\n"},
        ),
    )
    assert imported["result"]["imported"] == 1
    assert imported["result"]["total"] == 1

    product_id = _product(client, headers)
    report = _analyze(client, headers, product_id)
    metrics = report["metrics"]
    price = Decimal(metrics["target_price_usd"])
    landed = Decimal(metrics["landed_cost_usd"])
    fee = Decimal(metrics["channel_fee_usd"])
    tax = Decimal(metrics["tax_usd"])
    profit = Decimal(metrics["net_profit_usd"])
    assert profit == (price - landed - fee - tax).quantize(MONEY, rounding=ROUND_HALF_UP)
    assert Decimal(metrics["net_margin"]) == (profit / price).quantize(RATE, rounding=ROUND_HALF_UP)
    assert metrics["net_margin"] == "0.4985"
    assert metrics["fx_usd_cny"] == "7.20"
    assert metrics["rules_version"] == "pg-rules-1.0"
    assert metrics["explanation_model"] == "rules"
    assert report["market_snapshot"]["target_market"] == "US"
    assert report["market_snapshot"]["route"] == "CN-US"
    assert Decimal(metrics["net_margin"]) >= RATE_FLOORS["net_margin"]

    changed = client.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"target_market": "AU", "tax_regime": "cn_au"},
    )
    assert changed.status_code == 200
    blocked = client.post(f"/api/v1/reports/{report['id']}/acquire", headers=headers)
    assert blocked.status_code == 409
    fresh = _analyze(client, headers, product_id)
    assert fresh["id"] != report["id"]
    assert fresh["market_snapshot"]["target_market"] == "AU"
    assert fresh["metrics"]["net_margin"] != metrics["net_margin"]


def test_zero_denominator_rates_are_blank(client: TestClient):
    headers = register(client, "kpi-empty@example.com")
    board = client.get("/api/v1/kpi/dashboard", headers=headers)
    assert board.status_code == 200, board.text
    data = board.json()["data"]
    assert data["north_star"] == "ar"
    assert data["screen"] == "四率 + 北星 AR"
    assert data["timings"]["folded"] is True
    for key in ("net_margin", "act_r", "tr", "open_r", "ar"):
        assert data["headline"][key]["value"] is None
        assert data["headline"][key]["display"] == "—"
        assert data["headline"][key]["code"] == RATE_CODES[key]
    for key in ("qr", "act_r_cold", "rec_r"):
        assert data["lifecycle"][key]["value"] is None
        assert data["lifecycle"][key]["display"] == "—"
    for key, ceiling in TIMING_CEILINGS.items():
        assert data["timings"]["p50_seconds"][key] is None
        assert data["timings"]["targets_seconds"][key] == ceiling


def test_eight_rates_five_timings_and_redlines(client: TestClient):
    headers = register(client, "kpi-funnel@example.com")
    product_id = _product(client, headers)
    report = _analyze(client, headers, product_id)
    acquired = client.post(f"/api/v1/reports/{report['id']}/acquire", headers=headers)
    assert acquired.status_code == 200
    assert acquired.json()["data"]["seed_analysis_id"] == report["id"]

    discovery = finished_job(
        client,
        headers,
        client.post(
            "/api/v1/acquisition/tasks",
            headers=headers,
            json={"channel": "ecommerce", "platform": "amazon", "query": "cup", "seed_analysis_id": report["id"]},
        ),
    )
    assert discovery["status"] == "succeeded"
    leads = client.get("/api/v1/leads", headers=headers, params={"seed_analysis_id": report["id"]}).json()["data"]["items"]
    assert len(leads) == 5
    qualified = [item for item in leads if item["quality_score"] >= 60]
    reachable = sorted(
        (item for item in leads if item.get("email") and not item["email"].startswith("bounce.")),
        key=lambda item: item["quality_score"],
        reverse=True,
    )
    assert len(qualified) == 3
    assert len(reachable) == 3
    lead_a, lead_b, lead_c = reachable

    campaign = client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={
            "name": "美国水杯首轮",
            "lead_ids": [item["id"] for item in reachable],
            "seed_analysis_id": report["id"],
            "market_pack": "cn_us",
        },
    )
    campaign_id = campaign.json()["data"]["id"]
    assert client.post(f"/api/v1/campaigns/{campaign_id}/send", headers=headers).status_code == 409
    assert client.post(f"/api/v1/campaigns/{campaign_id}/drafts", headers=headers).status_code == 200
    assert client.post(f"/api/v1/campaigns/{campaign_id}/approve", headers=headers).status_code == 200
    finished_job(client, headers, client.post(f"/api/v1/campaigns/{campaign_id}/send", headers=headers))

    assert client.post(f"/api/v1/leads/{lead_a['id']}/signals", headers=headers, json={"type": "open"}).status_code == 200
    assert client.post(f"/api/v1/leads/{lead_b['id']}/signals", headers=headers, json={"type": "open"}).status_code == 200
    assert client.post(f"/api/v1/leads/{lead_a['id']}/signals", headers=headers, json={"type": "won"}).status_code == 200

    cold = client.post("/api/v1/recall", headers=headers, json={"lead_id": lead_b["id"], "trigger": "cold_start"})
    assert cold.status_code == 200, cold.text
    cold_id = cold.json()["data"]["id"]
    assert client.post(f"/api/v1/activation/jobs/{cold_id}/approve", headers=headers).status_code == 200
    finished_job(client, headers, client.post(f"/api/v1/activation/jobs/{cold_id}/send", headers=headers))
    assert client.post(f"/api/v1/leads/{lead_b['id']}/signals", headers=headers, json={"type": "open"}).status_code == 200

    recall = client.post("/api/v1/recall", headers=headers, json={"lead_id": lead_c["id"], "trigger": "churn"})
    assert recall.status_code == 200, recall.text
    recall_id = recall.json()["data"]["id"]
    assert client.post(f"/api/v1/recall/jobs/{recall_id}/approve", headers=headers).status_code == 200
    finished_job(client, headers, client.post(f"/api/v1/recall/jobs/{recall_id}/send", headers=headers))
    assert client.post(f"/api/v1/leads/{lead_c['id']}/signals", headers=headers, json={"type": "reply"}).status_code == 200

    board = client.get("/api/v1/kpi/dashboard", headers=headers).json()["data"]
    expected = {
        "net_margin": report["metrics"]["net_margin"],
        "act_r": show_rate(1, 1),
        "tr": show_rate(3, 3),
        "open_r": show_rate(2, 3),
        "ar": show_rate(2, 3),
        "qr": show_rate(3, 5),
        "act_r_cold": show_rate(1, 1),
        "rec_r": show_rate(1, 1),
    }
    rows = {**board["headline"], **board["lifecycle"]}
    for key, value in expected.items():
        assert rows[key]["code"] == RATE_CODES[key]
        assert rows[key]["value"] == value
        assert rows[key]["display"] == value
        assert Decimal(value) >= RATE_FLOORS[key]
    assert board["north_star"] == "ar"
    assert board["headline"]["ar"]["value"] == "0.6667"
    assert board["timings"]["folded"] is True
    for key, ceiling in TIMING_CEILINGS.items():
        measured = board["timings"]["p50_seconds"][key]
        assert measured is not None
        assert measured <= ceiling
        assert board["timings"]["targets_seconds"][key] == ceiling
    assert board["alerts"]["act_or_rec_p95_over_72h"] is False
    redlines = board["redlines"]
    assert Decimal(redlines["delivery_rate"]) >= Decimal("0.95")
    assert Decimal(redlines["bounce_rate"]) < Decimal("0.015")
    assert Decimal(redlines["complaint_rate"]) < Decimal("0.001")
    assert redlines["tripped"] is False

    snap = client.get("/api/v1/metrics", headers=headers).json()["data"]
    assert snap["import_success_rate"] is None or Decimal(snap["import_success_rate"]) <= Decimal("1")
    assert snap["rates"]["ar"]["north_star"] is True
