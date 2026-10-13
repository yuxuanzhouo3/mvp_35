import json
from pathlib import Path

from fastapi.testclient import TestClient

from config.flags import load_flags
from test.support import register

S4 = json.loads((Path(__file__).resolve().parents[2] / "backend" / "config" / "s4-v1.0.0.json").read_text())


def test_dark_flags_keep_new_surfaces_off_the_main_path(client: TestClient):
    assert S4["stage"] == "mvp"
    flags = load_flags()
    assert flags["digital_human"] is False
    assert flags["acquisition.social"] is False
    assert flags["payment.raas"] is False
    headers = register(client, "canary@example.com")
    before = client.get("/api/v1/payments", headers=headers).json()["data"]["items"]
    for path in ("/api/v1/digital-human/generate", "/api/v1/acquisition/social", "/api/v1/payments/raas"):
        response = client.post(path, headers=headers, json={})
        assert response.status_code == 501
    assert client.get("/api/v1/payments", headers=headers).json()["data"]["items"] == before
    assert client.get("/api/v1/health/live").status_code == 200
