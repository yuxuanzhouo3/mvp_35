from fastapi.testclient import TestClient

from test.support import register


def test_health_login_and_catalog_still_work(client: TestClient):
    assert client.get("/api/v1/health/live").json()["data"]["status"] == "live"
    headers = register(client, "speed-regress@example.com")
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200
    assert client.post("/api/v1/catalog/search", headers=headers, json={"q": "杯"}).json()["data"]["items"]
