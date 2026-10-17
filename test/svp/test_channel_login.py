from fastapi.testclient import TestClient

from app.modules.channel_login import _state
from test.support import register


def test_b1_login_requires_a_mode_and_opens_the_seller_page(client: TestClient):
    headers = register(client, "b1-login@example.com")
    missing = client.post("/api/v1/channel-accounts/login", headers=headers, json={"channel": "ecommerce", "platform": "amazon"})
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "B1_MODE_REQUIRED"

    pending = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "ecommerce", "platform": "amazon", "mode": "half"},
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["data"]["status"] == "pending"
    assert pending.json()["data"]["missing"] == "AMAZON_SP_APPLICATION_ID"

    client.app.state.settings.amazon_sp_application_id = "amzn1.sp.solution.test"
    opened = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "ecommerce", "platform": "amazon", "mode": "full"},
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()["data"]
    assert body["mode"] == "full"
    assert "sellercentral.amazon.com/apps/authorize/consent" in body["authorize_url"]
    assert "amzn1.sp.solution.test" in body["authorize_url"]


def test_seller_callback_exchanges_code_and_stores_tenant_token(client: TestClient, monkeypatch):
    headers = register(client, "b1-callback@example.com")
    me = client.get("/api/v1/me", headers=headers)
    tenant_id = me.json()["data"]["tenant"]["id"]
    state = _state(client.app.state.settings, tenant_id, "ecommerce", "taobao", "analyze")

    def fake_exchange(settings, platform, code):
        assert platform == "taobao"
        assert code == "auth-code"
        return {"access_token": "sess-1", "refresh_token": "ref-1", "account_label": "店铺甲", "token_meta": {}}

    monkeypatch.setattr("app.modules.channel_login._exchange_code", fake_exchange)
    saved = client.post("/api/v1/channel-accounts/callback", headers=headers, json={"state": state, "code": "auth-code"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["status"] == "connected"
    assert saved.json()["data"]["mode"] == "analyze"
    assert saved.json()["data"]["has_token"] is True
    listed = client.get("/api/v1/channel-accounts?channel=ecommerce", headers=headers)
    item = listed.json()["data"]["items"][0]
    assert item["platform"] == "taobao"
    assert "access_token" not in item


def test_temu_and_xhs_and_kuaishou_login_urls(client: TestClient):
    headers = register(client, "b1-social-urls@example.com")
    client.app.state.settings.temu_app_key = "temu-key"
    client.app.state.settings.xhs_app_id = "xhs-app"
    client.app.state.settings.kuaishou_app_id = "ks-app"

    temu = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={"channel": "ecommerce", "platform": "temu", "mode": "half"},
    )
    assert "seller.temu.com/open-platform/client-manage/authorization" in temu.json()["data"]["authorize_url"]

    xhs = client.post("/api/v1/channel-accounts/login", headers=headers, json={"channel": "social", "platform": "xiaohongshu"})
    assert "ark.xiaohongshu.com/ark/authorization" in xhs.json()["data"]["authorize_url"]

    ks = client.post("/api/v1/channel-accounts/login", headers=headers, json={"channel": "social", "platform": "kuaishou"})
    assert "open.kuaishou.com/oauth2/authorize" in ks.json()["data"]["authorize_url"]


def test_wecom_paste_credentials_connects(client: TestClient):
    headers = register(client, "b2-wecom@example.com")
    client.app.state.settings.wecom_corp_id = "ww-demo"
    opened = client.post("/api/v1/channel-accounts/login", headers=headers, json={"channel": "social", "platform": "wechat_mini"})
    assert opened.json()["data"]["needs_credentials"] is True
    saved = client.post(
        "/api/v1/channel-accounts/login",
        headers=headers,
        json={
            "channel": "social",
            "platform": "wechat_mini",
            "credentials": {"corp_id": "ww1", "contact_secret": "sec", "follow_userid": "zhang"},
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["status"] == "connected"
    assert saved.json()["data"]["has_token"] is True


def test_agency_slot_connects_without_a_remote_login(client: TestClient):
    headers = register(client, "b4-login@example.com")
    saved = client.post("/api/v1/channel-accounts/login", headers=headers, json={"channel": "agency", "platform": "agent_3"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["status"] == "connected"
    assert saved.json()["data"]["authorize_url"] == ""


def test_enrichment_stays_logged_out_until_the_key_exists(client: TestClient):
    headers = register(client, "b5-login@example.com")
    saved = client.post("/api/v1/channel-accounts/login", headers=headers, json={"channel": "enrichment", "platform": "qichacha"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["status"] == "pending"
    assert saved.json()["data"]["missing"] == "QICHACHA_APP_KEY"
    client.app.state.settings.qichacha_app_key = "key"
    opened = client.post("/api/v1/channel-accounts/login", headers=headers, json={"channel": "enrichment", "platform": "qichacha"})
    assert opened.json()["data"]["status"] == "connected"
