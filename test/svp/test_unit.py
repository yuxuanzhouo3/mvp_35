import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.modules.acquisition import rule_score
from app.modules.events import CURRENT_VERSION, NAMES, PREVIOUS_VERSION, classify
from app.modules.passwords import hash_password, verify_password
from app.modules.payment import sign_payment_event
from app.modules.providers import search_channel
from app.modules.scale import margin_drift_points, needs_rule_fallback, rollback_signal
from app.modules.state import can_transition, transition
from app.modules.tokens import issue_access, read_access
from app.services.common import CHANNELS
from app.modules.auth import login_with_code, register, send_login_code
from app.services.identity import require_permission, require_write
from app.services.metrics import snapshot
from config.flags import SPEC_FLAGS, load_flags, require_flag
from config.settings import Settings
from db.store import DocumentStore

ROOT = Path(__file__).resolve().parents[2] / "backend"
SECTION_7 = {
    "auth.sso",
    "auth.mfa",
    "payment.raas",
    "selection.auto_deal",
    "acquisition.social",
    "acquisition.ecommerce",
    "acquisition.expo",
    "acquisition.agency",
    "ai.agent",
    "ai.finetune",
    "digital_human",
    "geo_seo",
    "raas",
    "global_multi_active",
}


def test_flags_default_off_and_match_s4():
    flags = load_flags()
    assert SECTION_7 <= set(flags)
    assert all(flags[key] is False for key in SECTION_7)
    assert flags["auth.oauth"] is False
    s4 = (ROOT / "config" / "s4-v1.0.0.json").read_text()
    for key in SPEC_FLAGS:
        assert f'"{key}": false' in s4
    with pytest.raises(AppError) as caught:
        require_flag("digital_human")
    assert caught.value.status_code == 501
    assert caught.value.details["placeholder"] is True


def test_state_machine_blocks_illegal_payment_and_recall_moves():
    assert can_transition("Payment", "pending", "succeeded")
    assert transition("Recall", "triggered", "queued") == "queued"
    with pytest.raises(AppError) as caught:
        transition("Payment", "refunded", "succeeded")
    assert caught.value.status_code == 409


def test_password_roundtrip_and_weak_password():
    stored = hash_password("secret-pass")
    assert verify_password("secret-pass", stored)
    assert verify_password("other-pass", stored) is False
    with pytest.raises(AppError):
        hash_password("short")


def test_payment_signature_and_access_token():
    signature = sign_payment_event("test-secret", "evt-1", "pay-1", "succeeded")
    assert signature == sign_payment_event("test-secret", "evt-1", "pay-1", "succeeded")
    assert signature != sign_payment_event("test-secret", "evt-1", "pay-1", "failed")
    token = issue_access("session-secret", sub="local:a@b.c", sid="ses_1", ttl_seconds=60)
    payload = read_access("session-secret", token)
    assert payload["sub"] == "local:a@b.c"
    assert payload["sid"] == "ses_1"


def test_rule_score_ignores_model_suggestion():
    scored = rule_score(88, 60, "new", model_suggestion=1)
    assert scored["quality_score"] == 88
    assert scored["qualified"] is True
    assert scored["status"] == "qualified"
    assert scored["scored_by"] == "rules"
    assert scored["model_score"] is None
    held = rule_score(40, 60, "contacted", model_suggestion=99)
    assert held["status"] == "contacted"
    assert held["qualified"] is False


def test_rollback_and_margin_drift():
    assert rollback_signal(error_rate=0.02) == "s2_error_rate"
    assert rollback_signal(p95_ratio=2.1) == "s2_latency"
    assert rollback_signal(payment_failure_rate=0.01) == "payment"
    assert rollback_signal(delivery_rate=0.9) == "delivery"
    assert rollback_signal(bounce_rate=0.02) == "bounce"
    assert rollback_signal(complaint_rate=0.002) == "complaint"
    assert rollback_signal(error_rate=0.001, delivery_rate=0.99) is None
    assert needs_rule_fallback(Decimal("0.50"), Decimal("0.40")) is True
    assert needs_rule_fallback(Decimal("0.50"), Decimal("0.48")) is False
    assert margin_drift_points(Decimal("0.50"), Decimal("0.48")) == Decimal("2.00")


def test_events_accept_current_and_previous_versions():
    assert classify({"event": "lead.discovered", "version": CURRENT_VERSION}) == "accept"
    assert classify({"event": "lead.discovered", "version": PREVIOUS_VERSION}) == "accept"
    assert classify({"event": "lead.discovered", "version": "9.9.9"}) == "dead_letter"
    assert classify({"event": "not.real", "version": CURRENT_VERSION}) == "dead_letter"
    assert "payment.succeeded" in NAMES
    assert "raas.settled" in NAMES


def test_nine_channels_and_cross_border_mix():
    assert len(CHANNELS["agency"]) == 12
    assert set(CHANNELS) == {
        "ecommerce",
        "social",
        "expo",
        "agency",
        "enrichment",
        "geo_seo",
        "content_dh",
        "cross_border",
        "raas",
    }
    rows = search_channel("cross_border", None, "cup", None)
    inland = [row for row in rows if row["market"] == "CN"]
    assert len(inland) / len(rows) == 0.2
    raas = search_channel("raas", None, "site", None)
    assert all(row["exclude_from_ar"] for row in raas)


def test_sql_up_and_down_cover_the_same_tables():
    up = (ROOT / "db" / "sql" / "0001_postgres_shape" / "up.sql").read_text()
    down = (ROOT / "db" / "sql" / "0001_postgres_shape" / "down.sql").read_text()
    created = set(re.findall(r"CREATE TABLE ([a-z_]+)", up))
    dropped = set(re.findall(r"DROP TABLE IF EXISTS ([a-z_]+)", down))
    assert created
    assert created == dropped
    for name in (
        "tenants",
        "users",
        "payments",
        "selection_reports",
        "leads",
        "campaigns",
        "deliveries",
        "deals",
        "recalls",
        "kpi_metrics",
        "ai_calls",
        "audit_logs",
    ):
        assert name in created
    assert "ENABLE ROW LEVEL SECURITY" in up
    assert "users_tenant_email" in up
    assert "leads_tenant_email" in up


def test_middle_average_drops_both_tails_and_demo_users():
    from decimal import Decimal

    from app.services.metrics import _invalid_reason, middle_band, middle_mean

    assert middle_band([1, 2, 3, 4, 5, 6, 7, 8]) == [3, 4, 5, 6]
    assert middle_band([1, 2, 3]) == [2]
    assert middle_mean([Decimal(str(item)) for item in range(1, 9)]) == Decimal("4.5")
    from app.services.metrics import percentile_band

    wide = percentile_band(list(range(1, 11)), 0.1, 0.9)
    tight = percentile_band(list(range(1, 11)), 0.3, 0.7)
    assert len(tight) < len(wide)
    assert percentile_band([1, 2], 0.3, 0.7) == [1, 2]
    assert _invalid_reason({"status": "disabled", "tenant_id": "t"}) == "inactive"
    assert _invalid_reason({"status": "active", "email": "a@example.com", "tenant_id": "t"}) == "example"
    assert _invalid_reason({"status": "active", "cloudbase_user_id": "demo", "tenant_id": "t"}) == "demo"
    assert _invalid_reason({"status": "active", "email": "seller@shop.test", "tenant_id": "t", "cloudbase_user_id": "usr"}) is None


def test_empty_dashboard_denominator_is_blank(tmp_path):
    store = DocumentStore(tmp_path / "store.json")
    snap = snapshot(store, "tenant_missing", Settings(), 30)
    from app.modules.kpi_view import dashboard_view

    view = dashboard_view(snap)
    assert view["headline"]["ar"]["value"] is None
    assert view["headline"]["ar"]["display"] == "—"
    assert view["timings"]["folded"] is True
    assert view["north_star"] == "ar"


def test_viewer_cannot_write():
    require_write("owner")
    with pytest.raises(AppError) as caught:
        require_write("viewer")
    assert caught.value.status_code == 403
    require_permission("analyst", "analysis.write")
    with pytest.raises(AppError) as denied:
        require_permission("analyst", "billing.write")
    assert denied.value.status_code == 403
    assert denied.value.details["permission"] == "billing.write"
    with pytest.raises(AppError) as viewer:
        require_permission("viewer", "campaigns.send")
    assert viewer.value.status_code == 403


def test_login_code_is_single_use(tmp_path):
    store = DocumentStore(tmp_path / "store.json")
    settings = Settings(auth_mode="demo", session_secret="test-secret", data_path=str(tmp_path / "store.json"))
    register(store, email="seller@example.com", phone=None, password="secret-pass", display_name="林海")
    sent = send_login_code(store, settings, email="seller@example.com", phone=None)
    assert sent["sent"] is True
    assert len(sent["code"]) == 6
    missing = send_login_code(store, settings, email="nobody@example.com", phone=None)
    assert missing == {"sent": True}
    tokens = login_with_code(store, settings, email="seller@example.com", phone=None, code=sent["code"])
    assert tokens["token_type"] == "Bearer"
    with pytest.raises(AppError) as caught:
        login_with_code(store, settings, email="seller@example.com", phone=None, code=sent["code"])
    assert caught.value.status_code == 401


def test_sms_quota_warns_after_five_sends(tmp_path, monkeypatch):
    store = DocumentStore(tmp_path / "store.json")
    settings = Settings(auth_mode="demo", session_secret="test-secret", data_path=str(tmp_path / "store.json"))
    register(store, email="sms-quota@example.com", phone=None, password="secret-pass", display_name="甲")
    user = store.find_global("users", email="sms-quota@example.com")
    store.touch("users", user["id"], {"phone": "+8618800001111"})
    monkeypatch.setattr("app.modules.messages.deliver_code", lambda *args, **kwargs: "sms")
    last = {}
    for _ in range(9):
        last = send_login_code(store, settings, email=None, phone="18800001111")
        assert last["sms_quota_warning"] is False
    assert last["sms_sent_today"] == 9
    tenth = send_login_code(store, settings, email=None, phone="18800001111")
    assert tenth["sms_sent_today"] == 10
    assert tenth["sms_daily_cap"] == 10
    assert tenth["sms_quota_warning"] is True


def test_qichacha_search_replaces_demo_leads(monkeypatch):
    from algorithm.lead_feeds import discover

    def fake_get(url, params=None, headers=None):
        assert "FuzzySearch" in url
        assert params["searchKey"] == "北辰"
        assert headers["Token"]
        return {"Result": [{"Name": "北辰贸易有限公司", "OperName": "张三", "CreditCode": "91310000MA1"}]}

    monkeypatch.setattr("algorithm.lead_feeds._get", fake_get)

    class Keys:
        qichacha_app_key = "app"
        qichacha_secret_key = "sec"

    rows, provider = discover(None, Keys(), {"channel": "enrichment", "platform": "qichacha", "query": "北辰"})
    assert provider == "live"
    assert rows[0]["company"] == "北辰贸易有限公司"
    assert rows[0]["external_id"] == "91310000MA1"
    assert rows[0]["market"] == "CN"
    assert rows[0]["quality_score"] == 47

    demo, demo_provider = discover(None, Keys(), {"channel": "expo", "platform": "canton_fair", "query": "杯"})
    assert demo_provider == "mock"
    assert len(demo) == 5


def test_agency_push_needs_a_parent_then_discovery_uses_it(client):
    denied = client.post(
        "/api/v1/agency/leads",
        headers={"Authorization": "Bearer demo"},
        json={"platform": "agent_1", "items": [{"company": "甲公司"}]},
    )
    assert denied.status_code == 400
    assert denied.json()["error"]["code"] == "AGENCY_PARENT_REQUIRED"
    saved = client.post(
        "/api/v1/agency/leads",
        headers={"Authorization": "Bearer demo"},
        json={
            "platform": "agent_1",
            "parent_channel_account_id": "parent-1",
            "items": [{"company": "甲公司", "contact_name": "李", "email": "li@buyer.example", "market": "US", "external_id": "ext-1"}],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["saved"] == 1
    created = client.post(
        "/api/v1/lead-searches",
        headers={"Authorization": "Bearer demo"},
        json={"channel": "agency", "platform": "agent_1", "query": ""},
    )
    assert created.status_code == 202
    job = client.get(f"/api/v1/jobs/{created.json()['data']['job_id']}", headers={"Authorization": "Bearer demo"}).json()["data"]
    assert job["status"] == "succeeded"
    assert job["result"]["provider"] == "live"
    assert job["result"]["inserted"] == 1
    again = client.post(
        "/api/v1/lead-searches",
        headers={"Authorization": "Bearer demo"},
        json={"channel": "agency", "platform": "agent_1", "query": ""},
    )
    second = client.get(f"/api/v1/jobs/{again.json()['data']['job_id']}", headers={"Authorization": "Bearer demo"}).json()["data"]
    assert second["result"]["inserted"] == 0
    assert second["result"]["updated"] == 1


def test_sms_daily_limit_is_explained():
    from app.modules.messages import sms_failure_message

    assert "今天的短信次数已用完" in sms_failure_message("LimitExceeded.PhoneNumberDailyLimit")
    assert sms_failure_message("LimitExceeded.PhoneNumberThirtySecondLimit").startswith("短信发送太频繁")
    assert sms_failure_message("FailedOperation.SignatureIncorrectOrUnapproved") == "验证码短信没有发出"
