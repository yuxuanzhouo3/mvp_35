from fastapi.testclient import TestClient

from config.flags import load_flags
from test.support import register


def test_global_surfaces_stay_closed_and_do_not_write(client: TestClient):
    assert load_flags()["global_multi_active"] is False
    health = client.get("/api/v1/global/health")
    assert health.status_code == 200
    assert health.json()["data"]["global_multi_active"] is False
    assert health.json()["data"]["writes"] is False
    headers = register(client, "global@example.com")
    finetune = client.post("/api/v1/ai/finetune", headers=headers, json={})
    assert finetune.status_code == 501
    assert client.get("/api/v1/payments", headers=headers).json()["data"]["items"] == []
