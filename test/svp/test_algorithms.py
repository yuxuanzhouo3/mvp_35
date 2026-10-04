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
    assert ranked.json()["data"]["sources"]["provider"] == "local-book"
    assert {row["id"] for row in ranked.json()["data"]["sources"]["platforms"]} >= {"1688", "taobao", "amazon", "ebay"}


def test_selection_ranks_china_supply_against_us_shelf(client: TestClient, monkeypatch):
    live = {
        "id": "1688:99",
        "name": "双层玻璃杯",
        "sku": "99",
        "category": "家居",
        "cost_cny": "20.00",
        "packaging_cny": "4.00",
        "domestic_freight_cny": "6.00",
        "international_freight_usd": "3.20",
        "target_price_usd": "40.00",
        "supplier": "义乌杯厂",
        "platform": "1688",
        "external_id": "99",
        "fx_usd_cny": "7.20",
        "target_market": "US",
        "tax_regime": "cn_us",
        "price_basis": "us_shelf",
    }
    platforms = [
        {"id": "1688", "name": "1688", "region": "CN", "status": "ok", "count": 1},
        {"id": "ebay", "name": "eBay", "region": "US", "status": "ok", "count": 1},
    ]
    monkeypatch.setattr(
        "algorithm.selection_assist.cached_collect",
        lambda *_args, **_kwargs: ([live], platforms, {"fresh": True, "at": 0}),
    )
    ranked = client.get("/api/v1/catalog/search", headers=auth(), params={"q": "杯", "algorithm": "selection-assist"})
    assert ranked.status_code == 200, ranked.text
    body = ranked.json()["data"]
    assert body["sources"]["provider"] == "live"
    assert body["items"][0]["platform"] == "1688"
    assert body["items"][0]["price_basis"] == "us_shelf"
    assert body["items"][0]["selection"]["pick"] is True
    adopted = client.post("/api/v1/catalog/adopt", headers=auth(), json={"catalog_id": "1688:99"})
    assert adopted.status_code == 200, adopted.text
    assert adopted.json()["data"]["sku"] == "99"


def test_alibaba_refresh_replaces_a_rejected_access_token(monkeypatch):
    from algorithm.shelf import _alibaba, clear_alibaba_session

    clear_alibaba_session()
    calls = []

    class Settings:
        alibaba_app_key = "4140001"
        alibaba_app_secret = "secret"
        alibaba_access_token = "old-access"
        alibaba_refresh_token = "refresh-1"
        alibaba_refresh_token_timeout = "20261014200339000+0800"

    def fake_http(url, data):
        calls.append(url)
        if "getToken" in url:
            assert data["grant_type"] == "refresh_token"
            assert data["refresh_token"] == "refresh-1"
            return {"access_token": "new-access", "expires_in": "3600", "refresh_token_timeout": "20261014200339000+0800"}, 200
        if data["access_token"] == "old-access":
            return {"error_code": "401", "error_message": "Request need user authorized"}, 200
        return {"result": {"toReturn": [{"subject": "玻璃杯", "offerId": "9", "price": "12.50", "companyName": "杯厂"}]}}, 200

    monkeypatch.setattr("algorithm.shelf._alibaba_http", fake_http)
    rows, status = _alibaba("杯", Settings())
    assert status["status"] == "ok"
    assert rows[0]["cost_cny"] == "12.50"
    assert sum("getToken" in url for url in calls) == 1
    _alibaba("杯", Settings())
    assert sum("getToken" in url for url in calls) == 1
    clear_alibaba_session()


def test_alibaba_refresh_deadline_requires_a_new_authorization(monkeypatch):
    from algorithm.shelf import _alibaba, clear_alibaba_session

    clear_alibaba_session()

    class Settings:
        alibaba_app_key = "4140001"
        alibaba_app_secret = "secret"
        alibaba_access_token = "old-access"
        alibaba_refresh_token = "refresh-1"
        alibaba_refresh_token_timeout = "20200101000000000+0800"

    def fail_http(url, data):
        del url, data
        raise AssertionError("expired refresh token must not call 1688")

    monkeypatch.setattr("algorithm.shelf._alibaba_http", fail_http)
    rows, status = _alibaba("杯", Settings())
    assert rows == []
    assert status["status"] == "reauth"
    clear_alibaba_session()


def test_alibaba_missing_permission_is_a_failure(monkeypatch):
    from algorithm.shelf import _alibaba, clear_alibaba_session

    clear_alibaba_session()
    calls = []

    class Settings:
        alibaba_app_key = "4140001"
        alibaba_app_secret = "secret"
        alibaba_access_token = "access"
        alibaba_refresh_token = ""
        alibaba_refresh_token_timeout = ""

    def fake_http(url, data):
        del data
        calls.append(url)
        return {"error_code": "gw.APIACLDecline", "error_message": "AppKey is not allowed(acl)"}, 400

    monkeypatch.setattr("algorithm.shelf._alibaba_http", fake_http)
    rows, status = _alibaba("杯", Settings())
    assert rows == []
    assert status["status"] == "failed"
    assert len(calls) == 2
    _alibaba("杯", Settings())
    assert len(calls) == 2
    clear_alibaba_session()


def test_free_prices_stay_cached_for_one_hour(monkeypatch):
    from algorithm.shelf import cached_collect, clear_goods_cache

    clear_goods_cache()
    calls = {"n": 0}
    clock = {"now": 1_700_000_000.0}

    def fake(*_args, **_kwargs):
        calls["n"] += 1
        return [{"id": "1688:1"}], [{"id": "1688", "status": "ok"}]

    monkeypatch.setattr("algorithm.shelf.collect_goods", fake)
    monkeypatch.setattr("algorithm.shelf.time.time", lambda: clock["now"])
    cached_collect("杯", None, "US", interval=3600)
    cached_collect("杯", None, "US", interval=3600)
    assert calls["n"] == 1
    clock["now"] += 900
    cached_collect("杯", None, "US", interval=900)
    assert calls["n"] == 2
    clock["now"] += 3601
    cached_collect("杯", None, "US", interval=3600)
    assert calls["n"] == 3
    clear_goods_cache()


def test_paid_plan_starts_with_ten_manual_refreshes():
    from datetime import timedelta

    from app.core.timeutil import iso, utcnow
    from app.modules.shelf_refresh import grant, policy, spend

    class Store:
        def __init__(self):
            self.tenants = {}
            self.subs = []

        def get(self, collection, doc_id, _tenant=None):
            return self.tenants.get(doc_id) if collection == "tenants" else None

        def touch(self, collection, doc_id, patch):
            row = self.tenants.setdefault(doc_id, {"id": doc_id})
            row.update(patch)
            return row

        def query(self, collection, tenant_id, limit=20, **_kwargs):
            del collection, limit
            return {"items": [row for row in self.subs if row["tenant_id"] == tenant_id]}

    store = Store()
    assert policy(store, "ten")["interval_seconds"] == 3600
    store.subs.append({"tenant_id": "ten", "status": "active", "plan_id": "growth", "period_end": iso(utcnow() + timedelta(days=20))})
    paid = policy(store, "ten")
    assert paid["premium"] is True
    assert paid["interval_seconds"] == 900
    assert paid["manual_left"] == 10
    grant(store, "ten")
    assert spend(store, "ten") == 9


def test_free_refresh_waits_and_paid_refresh_spends_one(client: TestClient, monkeypatch):
    from datetime import timedelta

    from app.core.timeutil import iso, utcnow
    from app.modules.shelf_refresh import grant
    from app.services.common import base_doc, new_id
    from algorithm.shelf import cached_collect, clear_goods_cache

    clear_goods_cache()
    live = {
        "id": "1688:99",
        "name": "双层玻璃杯",
        "sku": "99",
        "category": "家居",
        "cost_cny": "20.00",
        "packaging_cny": "4.00",
        "domestic_freight_cny": "6.00",
        "international_freight_usd": "3.20",
        "target_price_usd": "40.00",
        "supplier": "义乌杯厂",
        "platform": "1688",
        "external_id": "99",
        "fx_usd_cny": "7.20",
        "target_market": "US",
        "tax_regime": "cn_us",
    }
    monkeypatch.setattr(
        "algorithm.shelf.collect_goods",
        lambda *_args, **_kwargs: ([live], [{"id": "1688", "name": "1688", "region": "CN", "status": "ok", "count": 1}]),
    )
    cached_collect("杯", None, "US", interval=3600)
    waited = client.post("/api/v1/catalog/refresh", headers=auth(), params={"q": "杯", "route": "cn_us"})
    assert waited.status_code == 403, waited.text
    tenant = client.get("/api/v1/tenants/current", headers=auth()).json()["data"]["id"]
    store = client.app.state.store
    store.insert(
        "subscriptions",
        base_doc(
            tenant,
            "test",
            id=new_id("sub"),
            plan_id="growth",
            plan="growth",
            status="active",
            period_end=iso(utcnow() + timedelta(days=30)),
            payment_id="pay-shelf",
        ),
    )
    grant(store, tenant)
    pulled = client.post("/api/v1/catalog/refresh", headers=auth(), params={"q": "杯", "route": "cn_us"})
    assert pulled.status_code == 200, pulled.text
    assert pulled.json()["data"]["sources"]["refresh"]["manual_left"] == 9
    assert pulled.json()["data"]["sources"]["refresh"]["interval_seconds"] == 900
    clear_goods_cache()


def test_platform_status_carries_sample_prices():
    from algorithm.shelf import _attach_offers

    cn = _attach_offers([{"name": "玻璃杯", "cost_cny": "12.50"}], {"id": "1688", "region": "CN", "status": "ok"})
    us = _attach_offers([{"name": "Glass", "usd": Decimal("9.99")}], {"id": "amazon", "region": "US", "status": "ok"})
    assert cn["offers"] == [{"name": "玻璃杯", "price": "12.50", "currency": "CNY"}]
    assert us["offers"][0]["currency"] == "USD"
    assert us["offers"][0]["price"] == "9.99"


def test_pdd_price_is_converted_from_fen(monkeypatch):
    from algorithm.shelf import _pinduoduo

    class Settings:
        pdd_client_id = "id"
        pdd_client_secret = "secret"
        pdd_pid = "pid"

    def fake_post(url, data=None, content=None, headers=None):
        del url, content, headers
        assert data["type"] == "pdd.ddk.goods.search"
        return {
            "goods_search_response": {
                "goods_list": [{"goods_name": "玻璃杯", "goods_id": "7", "min_group_price": 1990, "mall_name": "杯店"}]
            }
        }

    monkeypatch.setattr("algorithm.shelf._post", fake_post)
    rows, status = _pinduoduo("杯", Settings())
    assert status["status"] == "ok"
    assert rows[0]["cost_cny"] == "19.90"
    assert rows[0]["platform"] == "pinduoduo"
