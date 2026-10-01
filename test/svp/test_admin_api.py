"""Admin and billing hooks the workspace does not call yet."""

from fastapi.testclient import TestClient

from test.support import register


def test_flags_are_public_and_closed(client: TestClient):
    response = client.get("/api/v1/flags")
    assert response.status_code == 200
    flags = response.json()["data"]
    assert flags["auth.oauth"] is False
    assert flags["payment.raas"] is False
    assert flags["digital_human"] is False


def test_admin_lists_are_empty_until_created_and_recall_stays_separate(client: TestClient):
    denied = client.get("/api/v1/admin/users")
    assert denied.status_code == 401
    headers = register(client, "admin-hook@example.com")
    users = client.get("/api/v1/admin/users", headers=headers)
    assert users.status_code == 200
    row = users.json()["data"]["items"][0]
    assert row["email_masked"] == "ad***@example.com"
    assert "admin-hook@example.com" not in users.text

    summary = client.get("/api/v1/billing/summary", headers=headers)
    assert summary.status_code == 200
    growth = next(item for item in summary.json()["data"]["plans"] if item["id"] == "growth")
    assert growth["amount_fen"] == 29900

    created = client.post(
        "/api/v1/admin/ads",
        headers=headers,
        json={"title": "美国市场分析季", "placement": "dashboard_top", "media_type": "image"},
    )
    assert created.status_code == 200
    assert created.json()["data"]["status"] == "draft"
    listed = client.get("/api/v1/admin/ads", headers=headers)
    assert listed.json()["data"]["items"][0]["id"] == created.json()["data"]["id"]

    recall = client.post("/api/v1/admin/recall", headers=headers, json={"name": "30 日沉默用户"})
    assert recall.status_code == 200
    assert recall.json()["data"]["sent"] is False
    jobs = client.get("/api/v1/recall/jobs", headers=headers)
    assert jobs.json()["data"]["items"] == []

    analytics = client.get("/api/v1/admin/analytics", headers=headers)
    funnel = {item["label"]: item["value"] for item in analytics.json()["data"]["funnel"]}
    assert funnel["完成注册"] == 1
    assert analytics.json()["data"]["retention"] == []


def test_platform_admin_login_and_operator_actions(client: TestClient):
    denied = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong-pass"})
    assert denied.status_code == 401
    logged = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert logged.status_code == 200, logged.text
    headers = {"Authorization": f"Bearer {logged.json()['data']['access_token']}"}
    me = client.get("/api/v1/me", headers=headers)
    assert me.json()["data"]["user"]["username"] == "admin"

    audit = client.get("/api/v1/admin/audit", headers=headers)
    assert audit.status_code == 200
    assert any(item["action"] == "user.login" for item in audit.json()["data"]["items"])

    settings = client.patch(
        "/api/v1/admin/settings",
        headers=headers,
        json={"timezone": "Asia/Shanghai", "window_days": 7, "environment_label": "TEST"},
    )
    assert settings.status_code == 200, settings.text
    assert client.get("/api/v1/admin/settings", headers=headers).json()["data"]["window_days"] == 7
    changed = client.post(
        "/api/v1/admin/settings/password",
        headers=headers,
        json={"current_password": "admin", "new_password": "admin-next"},
    )
    assert changed.status_code == 200, changed.text
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin-next"}).status_code == 200

    created = client.post(
        "/api/v1/admin/ads",
        headers=headers,
        json={"title": "首页横幅", "placement": "home_mid_banner", "media_type": "image"},
    )
    ad_id = created.json()["data"]["id"]
    assert client.get(f"/api/v1/admin/ads/{ad_id}", headers=headers).json()["data"]["title"] == "首页横幅"
    assert client.get("/api/v1/admin/ads/creatives", headers=headers).json()["data"]["items"][0]["id"] == ad_id
    paused = client.post(f"/api/v1/admin/ads/{ad_id}/status", headers=headers, json={"status": "paused"})
    assert paused.json()["data"]["status"] == "paused"

    exported = client.post("/api/v1/admin/users/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "email_masked" in exported.json()["data"]["body"]
    assert "admin@" not in exported.json()["data"]["body"]
    detail = client.get(f"/api/v1/admin/users/{me.json()['data']['user']['id']}", headers=headers)
    assert detail.status_code == 200
    blocked = client.post(
        f"/api/v1/admin/users/{me.json()['data']['user']['id']}/status",
        headers=headers,
        json={"status": "suspended", "reason": "不能停用自己"},
    )
    assert blocked.status_code == 403
    segment = client.post("/api/v1/admin/segments", headers=headers, json={"name": "活跃管理员", "stage": "活跃", "query": "admin"})
    assert segment.status_code == 200, segment.text
    assert client.get("/api/v1/admin/segments", headers=headers).json()["data"]["items"][0]["name"] == "活跃管理员"

    invitation = client.post("/api/v1/admin/invitations", headers=headers, json={"name": "伙伴计划"})
    invitation_id = invitation.json()["data"]["id"]
    assert invitation.json()["data"]["share_path"] == f"/invite/{invitation_id}"
    assert "code_hash" not in invitation.text
    assert client.get(f"/api/v1/admin/invitations/{invitation_id}", headers=headers).status_code == 200

    recall = client.post("/api/v1/admin/recall", headers=headers, json={"name": "沉默召回"})
    recall_id = recall.json()["data"]["id"]
    assert client.post("/api/v1/admin/recall/pause-all", headers=headers).json()["data"]["paused"] == 1
    assert client.get(f"/api/v1/admin/recall/{recall_id}", headers=headers).json()["data"]["status"] == "paused"

    exported_analytics = client.post("/api/v1/admin/analytics/export?window_days=30", headers=headers)
    assert exported_analytics.status_code == 200, exported_analytics.text
    assert exported_analytics.json()["data"]["filename"] == "analytics.json"
    found = client.get("/api/v1/admin/search", headers=headers, params={"q": "首页横幅"})
    assert found.json()["data"]["ads"][0]["id"] == ad_id
