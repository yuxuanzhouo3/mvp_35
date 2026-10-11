import json
from pathlib import Path

from app.modules.auth import SMS_DAILY_CAP
from config.settings import Settings
from redis.cache import Cache
from redis.errors import CacheError
from redis.keys import KEY_PREFIX, LIMITS, SESSION_TTL, SMS_DAILY_CAP as CACHE_SMS_CAP
from redis.resp import encode


class Clock:
    def __init__(self):
        self.now = 1_700_000_000.0

    def __call__(self):
        return self.now


def cache(clock: Clock | None = None) -> Cache:
    return Cache.memory(clock=clock or Clock(), pepper="test-pepper")


def test_catalog_matches_session_ttl_rate_limits_and_sms_cap():
    s4 = json.loads((Path(__file__).resolve().parents[2] / "backend" / "config" / "s4-v1.0.0.json").read_text())
    assert LIMITS["tenant"] == s4["rate_limit_per_minute"]["tenant"]
    assert LIMITS["ip"] == s4["rate_limit_per_minute"]["ip"]
    assert LIMITS["send"] == s4["rate_limit_per_minute"]["send"]
    assert SESSION_TTL == Settings.model_fields["refresh_ttl_seconds"].default
    assert CACHE_SMS_CAP == SMS_DAILY_CAP
    assert encode(["PING"]) == b"*1\r\n$4\r\nPING\r\n"


def test_session_otp_and_tenant_report_stay_scoped():
    store = cache()
    store.put_session(tenant_id="t1", user_id="u1", session_id="ses_1")
    assert store.get_session("ses_1", tenant_id="t1")["user_id"] == "u1"
    assert store.get_session("ses_1", tenant_id="t2") is None
    store.revoke_session(tenant_id="t1", user_id="u1", session_id="ses_1")
    assert store.get_session("ses_1") is None

    store.issue_otp("login", "Buyer@Example.com", "123456")
    assert not any("buyer@example.com" in key or "123456" in key for key in store.kv.keys())
    stored = next(store.kv.get(key) for key in store.kv.keys() if ":otp:login:" in key)
    assert "123456" not in stored
    try:
        store.check_otp("login", "buyer@example.com", "000000")
        raise AssertionError("wrong code was accepted")
    except CacheError as exc:
        assert exc.code == "OTP_MISMATCH"
    assert store.check_otp("login", "buyer@example.com", "123456") is True

    store.put_report("t1", "an_1", {"net_margin": "0.4985"})
    assert store.get_report("t1", "an_1")["net_margin"] == "0.4985"
    assert store.get_report("t2", "an_1") is None
    try:
        store.put_report("t1", "an_2", {"net_margin": 0.5})
        raise AssertionError("float was cached")
    except CacheError as exc:
        assert exc.code == "INVALID_AMOUNT"
    try:
        store.put_kpi("", "30d", {"AR": "0.08"})
        raise AssertionError("missing tenant was cached")
    except CacheError as exc:
        assert exc.code == "TENANT_REQUIRED"

    keys = store.kv.keys()
    assert any(key.startswith(f"{KEY_PREFIX}:report:t1:") for key in keys)
    assert any(key.startswith(f"{KEY_PREFIX}:sess:user:t1:") for key in keys)


def test_otp_locks_and_prompt_version_splits_ai_cache():
    store = cache()
    store.issue_otp("register", "13800000000", "111111")
    for _ in range(4):
        try:
            store.check_otp("register", "13800000000", "000000")
        except CacheError as exc:
            assert exc.code == "OTP_MISMATCH"
    try:
        store.check_otp("register", "13800000000", "000000")
        raise AssertionError("fifth miss was not locked")
    except CacheError as exc:
        assert exc.code == "OTP_LOCKED"

    store.put_ai("t1", "hunyuan", "prompt-v1", "mail_1", {"text": "你好"})
    assert store.get_ai("t1", "hunyuan", "prompt-v2", "mail_1") is None
    assert store.get_ai("t1", "hunyuan", "prompt-v1", "mail_1")["text"] == "你好"


def test_rate_limit_window_hold_and_job_lock():
    clock = Clock()
    store = cache(clock)
    for _ in range(LIMITS["tenant"]):
        decision = store.hit("tenant", tenant_id="t1")
        assert decision.allowed
    blocked = store.hit("tenant", tenant_id="t1")
    assert blocked.allowed is False
    assert blocked.retry_after > 0
    clock.now += 60
    assert store.hit("tenant", tenant_id="t1").allowed

    store.hold("t2")
    assert store.hit("send", tenant_id="t2").allowed is False
    store.hold("t1", channel="email")
    assert store.hit("channel", tenant_id="t1", channel="ecommerce").allowed
    assert store.hit("channel", tenant_id="t1", channel="email").allowed is False

    token = store.acquire_job("t1", "job_1")
    assert token
    assert store.acquire_job("t1", "job_1") is None
    assert store.release_job("t1", "job_1", "other") is False
    assert store.release_job("t2", "job_1", token) is False
    assert store.release_job("t1", "job_1", token) is True
    assert store.acquire_job("t1", "job_1")


def test_sms_cap_and_shared_shelf_key():
    store = cache()
    last = None
    for _ in range(SMS_DAILY_CAP):
        last = store.reserve_sms("13800000000")
        assert last["accepted"]
    assert last is not None
    assert last["sms_quota_warning"]
    blocked = store.reserve_sms("13800000000")
    assert blocked["accepted"] is False
    assert blocked["sms_sent_today"] == SMS_DAILY_CAP

    store.put_shelf("US", "智能水杯", {"price": "12.00"})
    assert store.get_shelf("US", "智能水杯")["price"] == "12.00"
    assert not any("智能水杯" in key for key in store.kv.keys())
