"""Front contract: auth, payment, workspace, and admin against the document store."""

from fastapi.testclient import TestClient


def test_front_modules_roundtrip(client: TestClient):
    flags = client.get("/api/v1/flags")
    assert flags.status_code == 200
    assert flags.json()["data"]["auth.oauth"] is False
    closed = client.post("/api/v1/auth/oauth/google")
    assert closed.status_code == 501

    created = client.post(
        "/api/v1/auth/register",
        json={"email": "front-contract@example.com", "password": "secret-pass", "display_name": "林海"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["user"]["username"] == "front-contract@example.com"
    again = client.post(
        "/api/v1/auth/register",
        json={"email": "front-contract@example.com", "password": "secret-pass"},
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ACCOUNT_EXISTS"

    bad = client.post("/api/v1/auth/login", json={"email": "front-contract@example.com", "password": "wrong-pass"})
    assert bad.status_code == 401

    logged = client.post(
        "/api/v1/auth/login",
        json={"username": "front-contract@example.com", "password": "secret-pass"},
    )
    assert logged.status_code == 200, logged.text
    token = logged.json()["data"]["access_token"]
    refresh = logged.json()["data"]["refresh_token"]
    assert token.startswith("pg1.")
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["user"]["email"] == "front-contract@example.com"
    assert me.json()["data"]["role"] == "owner"

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert rotated.status_code == 200
    headers = {"Authorization": f"Bearer {rotated.json()['data']['access_token']}"}

    summary = client.get("/api/v1/billing/summary", headers=headers)
    assert summary.status_code == 200
    plans = {item["id"]: item["amount_fen"] for item in summary.json()["data"]["plans"]}
    assert plans == {"free": 0, "growth": 29900, "scale": 99900}

    checkout = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json={"plan_id": "growth", "idempotency_key": "front-pay-1"},
    )
    assert checkout.status_code == 200
    payment = checkout.json()["data"]
    assert payment["status"] == "pending"
    assert payment["amount"] == 29900
    queried = client.post(f"/api/v1/payments/{payment['id']}/query", headers=headers)
    assert queried.json()["data"]["status"] == "pending"
    assert queried.json()["data"]["granted"] is False

    product = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "合同水杯",
            "sku": "front-cup",
            "cost_cny": "72",
            "target_price_usd": "40",
            "international_freight_usd": "2",
            "fx_usd_cny": "7.2",
        },
    )
    assert product.status_code == 200, product.text
    analysis = client.post("/api/v1/products/" + product.json()["data"]["id"] + "/analyses", headers=headers)
    assert analysis.status_code == 202
    job = client.get(f"/api/v1/jobs/{analysis.json()['data']['job_id']}", headers=headers)
    assert job.json()["data"]["status"] == "succeeded"
    report_id = job.json()["data"]["result"]["analysis_id"]
    report = client.get(f"/api/v1/analyses/{report_id}", headers=headers)
    assert report.status_code == 200
    assert report.json()["data"]["metrics"]["net_margin"]
    acquired = client.post(f"/api/v1/analyses/{report_id}/acquire", headers=headers)
    assert acquired.status_code == 200
    assert acquired.json()["data"]["seed_analysis_id"] == report_id

    users = client.get("/api/v1/admin/users", headers=headers)
    assert users.json()["data"]["items"][0]["email_masked"] == "fr***@example.com"
    ad = client.post(
        "/api/v1/admin/ads",
        headers=headers,
        json={"title": "增长季", "placement": "pricing_banner", "media_type": "image"},
    )
    assert ad.json()["data"]["status"] == "draft"
    invite = client.post("/api/v1/admin/invitations", headers=headers, json={"name": "伙伴计划"})
    assert invite.status_code == 200
    assert invite.json()["data"]["invite_code"]
    listed = client.get("/api/v1/admin/invitations", headers=headers)
    assert "invite_code" not in listed.json()["data"]["items"][0]
    assert "code_hash" not in listed.json()["data"]["items"][0]
    recall = client.post("/api/v1/admin/recall", headers=headers, json={"name": "沉默用户"})
    assert recall.json()["data"]["sent"] is False
    assert client.get("/api/v1/recall/jobs", headers=headers).json()["data"]["items"] == []

    board = client.get("/api/v1/metrics", headers=headers)
    assert board.status_code == 200
    assert "ar" in board.json()["data"]["rates"]

    out = client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 200
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
