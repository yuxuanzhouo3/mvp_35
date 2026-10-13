import time

from fastapi.testclient import TestClient

from test.support import finished_job, register

SYNC_P95_SECONDS = 0.5
SAMPLES = 30


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * 0.95))))
    return ordered[index]


def _sample(call, count: int) -> list[float]:
    call()
    samples = []
    for _ in range(count):
        started = time.perf_counter()
        response = call()
        elapsed = time.perf_counter() - started
        assert response.status_code < 500, response.text
        samples.append(elapsed)
    return samples


def test_sync_api_p95_within_500ms(client: TestClient):
    headers = register(client, "speed@example.com")
    client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "时效水杯", "sku": "speed-cup", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    )
    calls = {
        "health": lambda: client.get("/api/v1/health/live"),
        "me": lambda: client.get("/api/v1/users/me", headers=headers),
        "products": lambda: client.get("/api/v1/products", headers=headers),
        "catalog": lambda: client.post("/api/v1/catalog/search", headers=headers, json={"q": "杯"}),
        "dashboard": lambda: client.get("/api/v1/kpi/dashboard", headers=headers),
    }
    for name, call in calls.items():
        measured = _p95(_sample(call, SAMPLES))
        assert measured <= SYNC_P95_SECONDS, f"{name} p95 {measured:.3f}s"


def test_analysis_and_discovery_finish_inside_the_timing_budget(client: TestClient):
    headers = register(client, "speed-jobs@example.com")
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "时效水杯", "sku": "speed-job", "cost_cny": "72", "target_price_usd": "40", "international_freight_usd": "2", "fx_usd_cny": "7.2"},
    )
    product_id = created.json()["data"]["id"]
    started = time.perf_counter()
    analysis = finished_job(
        client,
        headers,
        client.post("/api/v1/selection/analyze", headers=headers, json={"product_id": product_id}),
    )
    assert time.perf_counter() - started <= 120
    report_id = analysis["result"]["analysis_id"]
    client.post(f"/api/v1/reports/{report_id}/acquire", headers=headers)
    started = time.perf_counter()
    finished_job(
        client,
        headers,
        client.post(
            "/api/v1/acquisition/tasks",
            headers=headers,
            json={"channel": "ecommerce", "platform": "amazon", "query": "cup", "seed_analysis_id": report_id},
        ),
    )
    assert time.perf_counter() - started <= 180
    board = client.get("/api/v1/kpi/dashboard", headers=headers).json()["data"]
    assert board["timings"]["p50_seconds"]["ana_t"] <= 120
    assert board["timings"]["p50_seconds"]["lead_t"] <= 180
