from fastapi.testclient import TestClient

from test.support import finished_job, register

MARKETS = (
    ("US", "cn_us", "CN-US"),
    ("HK", "cn_hk", "CN-HK"),
    ("AU", "cn_au", "CN-AU"),
    ("CN", "domestic", "CN-CN"),
)


def test_four_markets_analyze_on_the_same_api(client: TestClient):
    headers = register(client, "compat@example.com")
    margins = set()
    for market, regime, route in MARKETS:
        product_id = client.post(
            "/api/v1/products",
            headers=headers,
            json={
                "name": f"{market}水杯",
                "sku": f"compat-{market}",
                "cost_cny": "72",
                "target_price_usd": "40",
                "international_freight_usd": "2",
                "fx_usd_cny": "7.2",
                "target_market": market,
                "tax_regime": regime,
                "route": route,
            },
        ).json()["data"]["id"]
        report_id = finished_job(
            client,
            headers,
            client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
        )["result"]["analysis_id"]
        report = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()["data"]
        assert report["market"] == market
        assert report["route"] == route
        margins.add(report["metrics"]["net_margin"])
    assert len(margins) == 4
