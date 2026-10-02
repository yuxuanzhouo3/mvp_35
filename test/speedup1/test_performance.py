from decimal import Decimal

from fastapi.testclient import TestClient


def test_ready_probe_meets_99_95_percent(client: TestClient):
    probes = 200
    ok = sum(1 for _ in range(probes) if client.get("/api/v1/health/ready").status_code == 200)
    assert Decimal(ok) / Decimal(probes) >= Decimal("0.9995")
