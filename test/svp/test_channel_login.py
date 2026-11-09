from fastapi.testclient import TestClient

from app.modules.channel_login import _state
from app.services.common import CHANNELS, CHANNEL_LAUNCH
from test.support import register


def test_b1_login_is_pending_launch(client: TestClient):
    headers = register(client, "b1-login@example.com")
    pending = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "ecommerce", "platform": "amazon", "mode": "half"},
    )
    assert pending.status_code == 503, pending.text
    assert pending.json()["error"]["code"] == "B1_PENDING_LAUNCH"
    catalog = client.get("/api/v1/channels", headers=headers)
    assert catalog.json()["data"]["launch"]["ecommerce"] == "pending"
    assert catalog.json()["data"]["priority"] == ["social"]
    assert CHANNEL_LAUNCH["ecommerce"] == "pending"


def test_b2_login_requires_invent_or_remix(client: TestClient):
    headers = register(client, "b2-mode@example.com")
    missing = client.post("/api/v1/channel-accounts/login", headers=headers, json={"channel": "social", "platform": "douyin"})
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "B2_MODE_REQUIRED"

    client.app.state.settings.douyin_client_key = "dy-key"
    opened = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "social", "platform": "douyin", "mode": "invent"},
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["mode"] == "invent"
    assert "open.douyin.com" in opened.json()["data"]["authorize_url"]


def test_b2_covers_cn_and_intl_seeding_platforms(client: TestClient):
    headers = register(client, "b2-expand@example.com")
    assert "weibo" in CHANNELS["social"]
    assert "tiktok" in CHANNELS["social"]
    assert "youtube" in CHANNELS["social"]
    client.app.state.settings.weibo_app_key = "wb-key"
    client.app.state.settings.tiktok_client_key = "tt-key"
    client.app.state.settings.youtube_client_id = "yt-id"
    weibo = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "social", "platform": "weibo", "mode": "invent"},
    )
    assert "api.weibo.com/oauth2/authorize" in weibo.json()["data"]["authorize_url"]
    tiktok = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "social", "platform": "tiktok", "mode": "remix"},
    )
    assert "tiktok.com/v2/auth/authorize" in tiktok.json()["data"]["authorize_url"]
    youtube = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "social", "platform": "youtube", "mode": "invent"},
    )
    assert "accounts.google.com/o/oauth2" in youtube.json()["data"]["authorize_url"]


def test_seller_callback_exchanges_code_and_stores_tenant_token(client: TestClient, monkeypatch):
    headers = register(client, "b1-callback@example.com")
    me = client.get("/api/v1/me", headers=headers)
    tenant_id = me.json()["data"]["tenant"]["id"]
    state = _state(client.app.state.settings, tenant_id, "social", "xiaohongshu", "invent")

    def fake_exchange(settings, platform, code):
        assert platform == "xiaohongshu"
        assert code == "auth-code"
        return {"access_token": "sess-1", "refresh_token": "ref-1", "account_label": "笔记号", "token_meta": {}}

    monkeypatch.setattr("app.modules.channel_login._exchange_code", fake_exchange)
    saved = client.post("/api/v1/channel-accounts/callback", headers=headers, json={"state": state, "code": "auth-code"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["status"] == "connected"
    assert saved.json()["data"]["mode"] == "invent"
    assert saved.json()["data"]["has_token"] is True
    listed = client.get("/api/v1/channel-accounts?channel=social", headers=headers)
    item = listed.json()["data"]["items"][0]
    assert item["platform"] == "xiaohongshu"
    assert "access_token" not in item


def test_xhs_and_kuaishou_login_urls(client: TestClient):
    headers = register(client, "b2-social-urls@example.com")
    client.app.state.settings.xhs_app_id = "xhs-app"
    client.app.state.settings.kuaishou_app_id = "ks-app"

    xhs = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "social", "platform": "xiaohongshu", "mode": "remix"},
    )
    assert "ark.xiaohongshu.com/ark/authorization" in xhs.json()["data"]["authorize_url"]

    ks = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "social", "platform": "kuaishou", "mode": "invent"},
    )
    assert "open.kuaishou.com/oauth2/authorize" in ks.json()["data"]["authorize_url"]


def test_wecom_paste_credentials_connects(client: TestClient):
    headers = register(client, "b2-wecom@example.com")
    client.app.state.settings.wecom_corp_id = "ww-demo"
    opened = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "social", "platform": "wechat_mini", "mode": "invent"},
    )
    assert opened.json()["data"]["needs_credentials"] is True
    saved = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={
            "channel": "social",
            "platform": "wechat_mini",
            "mode": "invent",
            "credentials": {"corp_id": "ww1", "contact_secret": "sec", "follow_userid": "zhang"},
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["status"] == "connected"
    assert saved.json()["data"]["has_token"] is True
    assert saved.json()["data"]["mode"] == "invent"


def test_agency_slot_requires_mode_then_connects(client: TestClient):
    headers = register(client, "b4-login@example.com")
    denied = client.post("/api/v1/channel-accounts/login", headers=headers, json={"channel": "agency", "platform": "agent_3"})
    assert denied.status_code == 400
    assert denied.json()["error"]["code"] == "B4_MODE_REQUIRED"
    saved = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "agency", "platform": "agent_3", "mode": "outreach"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["status"] == "connected"
    assert saved.json()["data"]["mode"] == "outreach"
    assert saved.json()["data"]["authorize_url"] == ""


def test_enrichment_requires_mode_and_key(client: TestClient):
    headers = register(client, "b5-login@example.com")
    denied = client.post("/api/v1/channel-accounts/login", headers=headers, json={"channel": "enrichment", "platform": "qichacha"})
    assert denied.status_code == 400
    assert denied.json()["error"]["code"] == "B5_MODE_REQUIRED"
    saved = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "enrichment", "platform": "qichacha", "mode": "search"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["status"] == "pending"
    assert saved.json()["data"]["missing"] == "QICHACHA_APP_KEY"
    client.app.state.settings.qichacha_app_key = "key"
    opened = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "enrichment", "platform": "qichacha", "mode": "search"},
    )
    assert opened.json()["data"]["status"] == "connected"
    assert opened.json()["data"]["mode"] == "search"
