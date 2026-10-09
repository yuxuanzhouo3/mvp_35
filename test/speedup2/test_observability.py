from fastapi.testclient import TestClient

from app.modules.events import CURRENT_VERSION
from test.support import register


def test_request_id_health_and_event_version(client: TestClient):
    live = client.get("/api/v1/health/live")
    ready = client.get("/api/v1/health/ready")
    assert live.headers["X-Request-Id"].startswith("req_")
    assert ready.headers["X-Request-Id"].startswith("req_")
    assert live.headers["X-Request-Id"] != ready.headers["X-Request-Id"]
    assert ready.json()["data"]["status"] == "ready"
    headers = register(client, "observe@example.com")
    rows = client.get("/api/v1/events", headers=headers).json()["data"]["items"]
    assert rows
    assert all(item["version"] == CURRENT_VERSION for item in rows)
