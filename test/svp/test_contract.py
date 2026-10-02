import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.modules.events import CURRENT_VERSION, NAMES, PREVIOUS_VERSION, classify
from test.support import register

S1 = json.loads((Path(__file__).resolve().parents[2] / "backend" / "config" / "s1-v1.0.0.json").read_text())


def test_event_contract_accepts_current_and_previous_versions():
    assert set(S1["events"]) == NAMES
    assert classify({"event": "lead.discovered", "version": CURRENT_VERSION}) == "accept"
    assert classify({"event": "lead.discovered", "version": PREVIOUS_VERSION}) == "accept"
    assert classify({"event": "lead.discovered", "version": "9.9.9"}) == "dead_letter"


def test_registered_events_carry_a_version(client: TestClient):
    headers = register(client, "contract@example.com")
    rows = client.get("/api/v1/events", headers=headers).json()["data"]["items"]
    found = [item for item in rows if item["event"] in {"user.registered", "user.login"}]
    assert found
    assert all(item["version"] == CURRENT_VERSION for item in found)


def test_closed_contract_routes_stay_not_enabled(client: TestClient):
    headers = register(client, "contract-flag@example.com")
    for path in ("/api/v1/auth/sso", "/api/v1/payments/raas", "/api/v1/ai/agent", "/api/v1/digital-human/generate"):
        response = client.post(path, headers=headers, json={})
        assert response.status_code == 501
        assert response.json()["error"]["code"] == "NOT_ENABLED"
