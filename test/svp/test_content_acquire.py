from algorithm.content_acquire import enrich_lead_contacts, intent_band, mock_landing_leads
from test.support import register


def test_intent_band_and_contact_enrichment():
    assert intent_band(80, wechat="wx1") == "high"
    assert intent_band(50, phone="13800001111") == "mid"
    assert intent_band(40) == "low"
    row = enrich_lead_contacts({"company": "甲", "email": "a@b.c", "quality_score": 40, "note": ""})
    assert row["quality_score"] >= 70
    assert row["intent_band"] in {"high", "mid"}
    assert row["qualified"] is True


def test_mock_landing_leads_include_wechat_email_or_phone():
    rows = mock_landing_leads("social", "douyin", "invent", "杯")
    assert len(rows) == 3
    assert any(row.get("wechat") for row in rows)
    assert any(row.get("phone") for row in rows)
    assert any(row.get("email") for row in rows)


def test_seed_draft_approve_flow(client):
    headers = register(client, "seed-draft@example.com")
    created = client.post(
        "/api/v1/content/seed-drafts",
        headers=headers,
        json={
            "channel": "social",
            "platform": "xiaohongshu",
            "mode": "invent",
            "seed_text": "保温杯",
            "landing_path": "/workspace/acquire/social",
        },
    )
    assert created.status_code == 200, created.text
    job = created.json()["data"]
    assert job["status"] == "pending_approve"
    assert "保温杯" in job["body"]
    assert "微信" in job["body"] or "手机" in job["body"]

    approved = client.post(f"/api/v1/content/seed-drafts/{job['id']}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"
    assert approved.json()["data"]["published"] is False

    listed = client.get("/api/v1/content/seed-drafts?channel=social", headers=headers)
    assert listed.status_code == 200
    assert any(item["id"] == job["id"] for item in listed.json()["data"]["items"])


def test_discovery_uses_b2_landing_mock_when_mode_invent(client, monkeypatch):
    headers = register(client, "b2-discover@example.com")
    client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={
            "channel": "social",
            "platform": "wechat_mini",
            "mode": "invent",
            "credentials": {"corp_id": "ww1", "contact_secret": "sec", "follow_userid": "zhang"},
        },
    )

    from algorithm.lead_feeds import discover

    class Keys:
        pass

    store = client.app.state.store
    me = client.get("/api/v1/me", headers=headers).json()["data"]["tenant"]["id"]
    rows, provider = discover(
        store,
        Keys(),
        {"channel": "social", "platform": "wechat_mini", "query": "杯", "mode": "invent"},
        me,
    )
    assert provider == "mock"
    assert any(row.get("wechat") or row.get("phone") or row.get("email") for row in rows)


def test_draft_seed_rejects_enrichment_publish(client):
    headers = register(client, "b5-no-seed@example.com")
    denied = client.post(
        "/api/v1/content/seed-drafts",
        headers=headers,
        json={"channel": "enrichment", "platform": "qichacha", "mode": "search", "seed_text": "贸"},
    )
    assert denied.status_code == 400
    assert denied.json()["error"]["code"] == "CONTENT_CHANNEL_DENIED"
