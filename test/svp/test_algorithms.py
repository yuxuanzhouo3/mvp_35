from decimal import Decimal

from fastapi.testclient import TestClient

from app.services.profit import calculate


def auth():
    return {"Authorization": "Bearer demo"}


def test_repricer_uses_frankfurter_and_global_pricer(monkeypatch):
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, params=None, headers=None, timeout=None, follow_redirects=None):
        del params, headers, timeout, follow_redirects
        if "frankfurter" in url:
            return Response({"rates": {"CNY": 7.1}})
        return Response(
            {
                "currency": "USD",
                "sellers": [
                    {"domain": "amazon.com", "price": 50},
                    {"domain": "walmart.com", "price": 46},
                ],
            }
        )

    monkeypatch.setattr("algorithm.feeds.httpx.get", fake_get)
    from algorithm.feeds import prepare_market
    from algorithm.product_pricer import compare_product

    class Settings:
        fx_api_url = "https://api.frankfurter.dev/v1/latest"
        pricer_api_url = "https://pricer.example/lookup"
        pricer_api_key = "test-key"

    product = {
        "name": "样品杯",
        "sku": "CUP-1",
        "cost_cny": "72",
        "target_price_usd": "40",
        "international_freight_usd": "2",
        "fx_usd_cny": "7.20",
        "target_market": "US",
        "tax_regime": "cn_us",
    }
    priced, overseas, feed = prepare_market(product, Settings())
    quote = compare_product(priced, overseas_quotes=overseas, feed=feed)
    assert quote["market_feed"]["strategy"] == "competitor-median-with-cost-plus-floor"
    assert quote["market_feed"]["fx"]["provider"] == "frankfurter"
    assert quote["market_feed"]["fx"]["rate"] == "7.10"
    assert quote["market_feed"]["offers"]["provider"] == "global-pricer"
    assert quote["overseas"]["count"] == 2
    assert quote["recommended_price_usd"] == "48.00"
    checked = calculate({**priced, "target_price_usd": quote["recommended_price_usd"]})
    assert Decimal(checked["net_margin"]) >= Decimal("0.15")


def test_price_compare_uses_domestic_and_overseas_sources(client: TestClient):
    domestic = client.get("/api/v1/sources/pricer/domestic", headers=auth(), params={"q": "杯"})
    overseas = client.get("/api/v1/sources/pricer/overseas", headers=auth(), params={"q": "杯", "market": "US"})
    assert domestic.status_code == 200
    assert overseas.status_code == 200
    assert domestic.json()["data"]["source"] == "/api/v1/sources/pricer/domestic"
    assert overseas.json()["data"]["source"] == "/api/v1/sources/pricer/overseas"
    assert {row["currency"] for row in domestic.json()["data"]["items"]} == {"CNY"}
    assert {row["market"] for row in overseas.json()["data"]["items"]} == {"US"}

    priced = client.post(
        "/api/v1/algorithms/product-pricer",
        headers=auth(),
        json={
            "csv": "sku,name,cost_cny,target_price_usd,international_freight_usd\nCUP-1,样品杯,72,40,2\n",
        },
    )
    assert priced.status_code == 200, priced.text
    quote = priced.json()["data"]["items"][0]
    assert quote["algorithm"] == "product-pricer"
    assert quote["listed_price_usd"] == "40.00"
    assert quote["domestic"]["count"] >= 1
    assert quote["overseas"]["count"] >= 1
    assert quote["position"] == "below_market"
    assert Decimal(quote["recommended_price_usd"]) >= Decimal(quote["floor_price_usd"])
    checked = calculate(
        {
            "sku": "CUP-1",
            "name": "样品杯",
            "cost_cny": "72",
            "target_price_usd": quote["recommended_price_usd"],
            "international_freight_usd": "2",
            "fx_usd_cny": "7.20",
            "target_market": "US",
            "tax_regime": "cn_us",
        }
    )
    assert Decimal(checked["net_margin"]) >= Decimal("0.15")
    assert quote["report"]["profit"]["net_margin"]
    assert quote["report"]["tax"]["tax_usd"]
    assert quote["report"]["time"]["transit_days_max"] >= quote["report"]["time"]["transit_days_min"]
    assert quote["report"]["risk"]["risk_level"] in {"低", "中", "高"}


def test_csv_import_runs_only_the_pricer(client: TestClient):
    rejected = client.post(
        "/api/v1/products/imports",
        headers=auth(),
        json={"csv": "sku,name,cost_cny,target_price_usd\nX-1,样品,10,20\n", "algorithm": "selection-assist"},
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "UNKNOWN_ALGORITHM"

    created = client.post(
        "/api/v1/products/imports",
        headers=auth(),
        json={
            "csv": "sku,name,cost_cny,target_price_usd,international_freight_usd\nCUP-9,样品杯,72,40,2\n",
            "algorithm": "product-pricer",
        },
    )
    assert created.status_code == 202, created.text
    job = client.get(f"/api/v1/jobs/{created.json()['data']['job_id']}", headers=auth()).json()["data"]
    assert job["status"] == "succeeded"
    assert job["result"]["imported"] == 1
    assert job["result"]["algorithm"] == "product-pricer"
    assert job["result"]["quotes"][0]["sku"] == "CUP-9"
    assert job["result"]["sources"]["domestic"] == "/api/v1/sources/pricer/domestic"


def test_selection_assist_ranks_catalog_source(client: TestClient):
    source = client.get("/api/v1/sources/catalog", headers=auth(), params={"q": "杯"})
    assert source.status_code == 200
    assert source.json()["data"]["source"] == "/api/v1/sources/catalog"
    assert "selection" not in source.json()["data"]["items"][0]

    rejected = client.get("/api/v1/catalog/search", headers=auth(), params={"q": "杯", "algorithm": "product-pricer"})
    assert rejected.status_code == 400

    ranked = client.get("/api/v1/catalog/search", headers=auth(), params={"q": "", "algorithm": "selection-assist"})
    assert ranked.status_code == 200, ranked.text
    body = ranked.json()["data"]
    assert body["algorithm"] == "selection-assist"
    assert body["sources"]["catalog"] == "/api/v1/sources/catalog"
    assert body["items"]
    assert body["items"][0]["selection"]["reason"]
    scores = [item["selection"]["score"] for item in body["items"]]
    assert scores == sorted(scores, reverse=True)

    posted = client.post("/api/v1/algorithms/selection-assist", headers=auth(), json={"q": "宠物"})
    assert posted.status_code == 200
    assert posted.json()["data"]["items"][0]["sku"] == "CN-PET-02"
    plain = client.get("/api/v1/catalog/search", headers=auth(), params={"q": "露营"})
    assert "algorithm" not in plain.json()["data"]
    assert "selection" not in plain.json()["data"]["items"][0]
