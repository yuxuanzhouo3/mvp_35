from decimal import Decimal, ROUND_HALF_UP

from fastapi.testclient import TestClient

RATE = Decimal("0.0001")


def show_rate(numerator: int, denominator: int) -> str:
    return str((Decimal(numerator) / Decimal(denominator)).quantize(RATE, rounding=ROUND_HALF_UP))


def register(client: TestClient, email: str) -> dict:
    created = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secret-pass", "display_name": "林海"},
    )
    assert created.status_code == 200, created.text
    logged = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret-pass"},
    )
    assert logged.status_code == 200, logged.text
    return {"Authorization": f"Bearer {logged.json()['data']['access_token']}"}


def finished_job(client: TestClient, headers: dict, response) -> dict:
    assert response.status_code == 202, response.text
    job = client.get(f"/api/v1/jobs/{response.json()['data']['job_id']}", headers=headers)
    assert job.status_code == 200, job.text
    data = job.json()["data"]
    assert data["status"] == "succeeded", data
    return data
