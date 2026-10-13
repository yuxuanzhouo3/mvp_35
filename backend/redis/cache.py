"""Hot-path cache. PostgreSQL and the document store stay authoritative.

Sessions, verification codes, rate limits, hot reports, the KPI board, and
job locks match project.md §3.3. AI replies are keyed by model and prompt
version so a rollback misses. Shelf prices are shared market data.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from redis.errors import CacheError
from redis.keys import (
    AI_TTL,
    CHANNELS,
    HOLD_TTL,
    KEY_PREFIX,
    KPI_TTL,
    LIMITS,
    LOCK_TTL,
    OTP_ATTEMPTS,
    OTP_PURPOSES,
    OTP_TTL,
    REPORT_TTL,
    SESSION_TTL,
    SHELF_TTL,
    SMS_DAILY_CAP,
    WINDOW_SECONDS,
)
from redis.memory import MemoryKv

_SEGMENT = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_BEIJING = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class Cache:
    def __init__(self, kv, *, clock, prefix: str = KEY_PREFIX, pepper: str):
        if not pepper:
            raise CacheError("PEPPER_REQUIRED", "验证码缓存需要 pepper")
        self.kv = kv
        self.clock = clock
        self.prefix = prefix
        self.pepper = pepper

    @classmethod
    def memory(cls, *, clock=None, pepper: str, prefix: str = KEY_PREFIX) -> "Cache":
        clock = clock or _unix
        return cls(MemoryKv(clock), clock=clock, pepper=pepper, prefix=prefix)

    @classmethod
    def connect(cls, url: str, *, pepper: str, prefix: str = KEY_PREFIX) -> "Cache":
        from redis.resp import RedisKv

        return cls(RedisKv(url), clock=_unix, pepper=pepper, prefix=prefix)

    def close(self) -> None:
        closer = getattr(self.kv, "close", None)
        if closer:
            closer()

    def put_session(self, *, tenant_id: str, user_id: str, session_id: str) -> None:
        tenant_id = _tenant(tenant_id)
        user_id = _strict(user_id)
        session_id = _strict(session_id)
        payload = _dump({"tenant_id": tenant_id, "user_id": user_id, "session_id": session_id})
        self.kv.set(self._key("sess", session_id), payload, SESSION_TTL)
        self.kv.sadd(self._key("sess", "user", tenant_id, user_id), session_id, SESSION_TTL)

    def get_session(self, session_id: str, *, tenant_id: str | None = None) -> dict | None:
        raw = self.kv.get(self._key("sess", _strict(session_id)))
        if raw is None:
            return None
        payload = json.loads(raw)
        if tenant_id is not None and payload.get("tenant_id") != tenant_id:
            return None
        return payload

    def revoke_session(self, *, tenant_id: str, user_id: str, session_id: str) -> None:
        tenant_id = _tenant(tenant_id)
        user_id = _strict(user_id)
        session_id = _strict(session_id)
        self.kv.delete(self._key("sess", session_id))
        self.kv.srem(self._key("sess", "user", tenant_id, user_id), session_id)

    def revoke_user(self, *, tenant_id: str, user_id: str) -> int:
        index = self._key("sess", "user", _tenant(tenant_id), _strict(user_id))
        members = self.kv.smembers(index)
        for session_id in members:
            self.kv.delete(self._key("sess", session_id))
        self.kv.delete(index)
        return len(members)

    def issue_otp(self, purpose: str, target: str, code: str, *, ttl: int = OTP_TTL) -> None:
        purpose = _purpose(purpose)
        digest = self._code_hash(code)
        key = self._otp_key(purpose, target)
        self.kv.set(key, digest, ttl)
        self.kv.delete(self._key("otp", "try", purpose, _target_hash(target)))

    def check_otp(self, purpose: str, target: str, code: str) -> bool:
        purpose = _purpose(purpose)
        key = self._otp_key(purpose, target)
        stored = self.kv.get(key)
        if stored is None:
            raise CacheError("OTP_EXPIRED", "验证码已过期")
        if not hmac.compare_digest(stored, self._code_hash(code)):
            tries_key = self._key("otp", "try", purpose, _target_hash(target))
            tries = self.kv.incr(tries_key, max(self.kv.pttl(key), 1))
            if tries >= OTP_ATTEMPTS:
                self.kv.delete(key)
                raise CacheError("OTP_LOCKED", "验证码尝试次数过多")
            raise CacheError("OTP_MISMATCH", "验证码不正确")
        self.kv.delete(key)
        self.kv.delete(self._key("otp", "try", purpose, _target_hash(target)))
        return True

    def reserve_sms(self, phone: str) -> dict:
        key = self._key("otp", "sms", _beijing_day(self.clock), _target_hash(phone))
        current = self.kv.get(key)
        count = int(current) if current else 0
        if count >= SMS_DAILY_CAP:
            return _sms_body(count, accepted=False)
        ttl = _seconds_until_beijing_midnight(self.clock)
        count = self.kv.incr(key, ttl)
        return _sms_body(count, accepted=count <= SMS_DAILY_CAP)

    def hit(
        self,
        scope: str,
        *,
        tenant_id: str | None = None,
        ip: str | None = None,
        route: str | None = None,
        channel: str | None = None,
    ) -> LimitDecision:
        if scope not in LIMITS:
            raise CacheError("UNKNOWN_SCOPE", "未知限流范围")
        limit = LIMITS[scope]
        window = str(int(self.clock()) // WINDOW_SECONDS)
        if scope == "ip":
            subject = _strict(ip or "")
            parts = ("rl", "ip", subject, window)
            hold = 0
        elif scope == "tenant":
            parts = ("rl", "tenant", _tenant(tenant_id), window)
            hold = 0
        elif scope == "api":
            parts = ("rl", "api", _tenant(tenant_id), _route(route or ""), window)
            hold = 0
        elif scope == "channel":
            channel_name = _channel(channel or "")
            tenant = _tenant(tenant_id)
            parts = ("rl", "channel", tenant, channel_name, window)
            hold = self._hold_left(tenant, channel_name)
        else:
            tenant = _tenant(tenant_id)
            parts = ("rl", "send", tenant, window)
            hold = self._hold_left(tenant, None)
        if hold:
            return LimitDecision(False, limit, 0, hold)
        key = self._key(*parts)
        count = self.kv.incr(key, WINDOW_SECONDS)
        remaining = max(limit - count, 0)
        if count <= limit:
            return LimitDecision(True, limit, remaining, 0)
        return LimitDecision(False, limit, 0, self.kv.pttl(key) or WINDOW_SECONDS)

    def hold(self, tenant_id: str, *, channel: str | None = None, ttl: int = HOLD_TTL) -> None:
        tenant_id = _tenant(tenant_id)
        if channel:
            self.kv.set(self._key("rl", "hold", tenant_id, _channel(channel)), "1", ttl)
            return
        self.kv.set(self._key("rl", "hold", tenant_id), "1", ttl)

    def put_report(self, tenant_id: str, report_id: str, payload: dict) -> None:
        self.kv.set(self._key("report", _tenant(tenant_id), _strict(report_id)), _dump(payload), REPORT_TTL)

    def get_report(self, tenant_id: str, report_id: str) -> dict | None:
        return _load(self.kv.get(self._key("report", _tenant(tenant_id), _strict(report_id))))

    def put_kpi(self, tenant_id: str, period: str, payload: dict) -> None:
        self.kv.set(self._key("kpi", _tenant(tenant_id), _strict(period)), _dump(payload), KPI_TTL)

    def get_kpi(self, tenant_id: str, period: str) -> dict | None:
        return _load(self.kv.get(self._key("kpi", _tenant(tenant_id), _strict(period))))

    def acquire_job(self, tenant_id: str, job_id: str) -> str | None:
        token = secrets.token_hex(16)
        value = f"{_tenant(tenant_id)}:{token}"
        if self.kv.set_nx(self._job_key(tenant_id, job_id), value, LOCK_TTL):
            return token
        return None

    def release_job(self, tenant_id: str, job_id: str, token: str) -> bool:
        value = f"{_tenant(tenant_id)}:{token}"
        return self.kv.compare_delete(self._job_key(tenant_id, job_id), value)

    def put_ai(self, tenant_id: str, model: str, prompt_version: str, cache_key: str, payload: dict) -> None:
        key = self._key("ai", _tenant(tenant_id), _strict(model), _strict(prompt_version), _strict(cache_key))
        self.kv.set(key, _dump(payload), AI_TTL)

    def get_ai(self, tenant_id: str, model: str, prompt_version: str, cache_key: str) -> dict | None:
        key = self._key("ai", _tenant(tenant_id), _strict(model), _strict(prompt_version), _strict(cache_key))
        return _load(self.kv.get(key))

    def put_shelf(self, market: str, query: str, payload: dict) -> None:
        self.kv.set(self._shelf_key(market, query), _dump(payload), SHELF_TTL)

    def get_shelf(self, market: str, query: str) -> dict | None:
        return _load(self.kv.get(self._shelf_key(market, query)))

    def _hold_left(self, tenant_id: str, channel: str | None) -> int:
        keys = [self._key("rl", "hold", tenant_id)]
        if channel:
            keys.append(self._key("rl", "hold", tenant_id, channel))
        left = 0
        for key in keys:
            if self.kv.get(key) is None:
                continue
            left = max(left, self.kv.pttl(key) or 1)
        return left

    def _job_key(self, tenant_id: str, job_id: str) -> str:
        return self._key("lock", "job", _tenant(tenant_id), _strict(job_id))

    def _otp_key(self, purpose: str, target: str) -> str:
        return self._key("otp", purpose, _target_hash(target))

    def _shelf_key(self, market: str, query: str) -> str:
        digest = hashlib.sha256(query.strip().lower().encode()).hexdigest()[:32]
        return self._key("shelf", _strict(market), digest)

    def _code_hash(self, code: str) -> str:
        return hmac.new(self.pepper.encode(), code.strip().encode(), hashlib.sha256).hexdigest()

    def _key(self, *parts: str) -> str:
        for part in parts:
            _strict(part)
        return ":".join((self.prefix, *parts))


def _unix() -> float:
    return datetime.now(timezone.utc).timestamp()


def _tenant(value: str | None) -> str:
    if not value:
        raise CacheError("TENANT_REQUIRED", "查询必须带 tenant_id")
    return _strict(value)


def _strict(value: str) -> str:
    if not value or not _SEGMENT.fullmatch(value):
        raise CacheError("INVALID_KEY", "缓存键包含非法字符")
    return value


def _purpose(purpose: str) -> str:
    if purpose not in OTP_PURPOSES:
        raise CacheError("INVALID_PURPOSE", "验证码用途无效")
    return purpose


def _channel(channel: str) -> str:
    if channel not in CHANNELS:
        raise CacheError("UNKNOWN_CHANNEL", "未知获客通道")
    return channel


def _route(route: str) -> str:
    cleaned = route.strip().strip("/").replace("/", ".")
    return _strict(cleaned)


def _target_hash(target: str) -> str:
    normalized = target.strip().lower()
    if not normalized:
        raise CacheError("INVALID_TARGET", "验证码缺少接收方")
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def _beijing_day(clock) -> str:
    return datetime.fromtimestamp(clock(), _BEIJING).strftime("%Y%m%d")


def _seconds_until_beijing_midnight(clock) -> int:
    now = datetime.fromtimestamp(clock(), _BEIJING)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(int((tomorrow - now).total_seconds()), 1)


def _sms_body(count: int, *, accepted: bool) -> dict:
    return {
        "sms_sent_today": count,
        "sms_daily_cap": SMS_DAILY_CAP,
        "sms_quota_warning": count >= SMS_DAILY_CAP,
        "accepted": accepted,
    }


def _dump(payload: dict) -> str:
    _reject_float(payload)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def _load(raw: str | None) -> dict | None:
    if raw is None:
        return None
    return json.loads(raw)


def _json_default(value):
    from decimal import Decimal

    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(f"无法缓存 {type(value).__name__}")


def _reject_float(value) -> None:
    if isinstance(value, float):
        raise CacheError("INVALID_AMOUNT", "缓存不能写入二进制浮点")
    if isinstance(value, dict):
        for item in value.values():
            _reject_float(item)
    elif isinstance(value, list):
        for item in value:
            _reject_float(item)
