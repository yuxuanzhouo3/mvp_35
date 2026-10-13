"""Redis key catalog for project.md §3.3.

PostgreSQL remains the source of truth. Redis holds hot copies and counters.
The prefix is the rollback switch: point callers at `pg:v1` or the previous
prefix and let the old keys expire. Do not scan or flush the instance.

| namespace | key | ttl | tenant |
| --- | --- | --- | --- |
| session | sess:{sid} | refresh ttl | tenant_id is in the value; the user index key carries it |
| session index | sess:user:{tenant_id}:{user_id} | refresh ttl | required |
| otp | otp:{purpose}:{target_hash} | 10 min | destination is hashed; no raw email or phone |
| otp attempts | otp:try:{purpose}:{target_hash} | 10 min | same hash |
| sms quota | otp:sms:{yyyymmdd}:{phone_hash} | until Beijing midnight | hashed phone, cap 10 |
| rate tenant | rl:tenant:{tenant_id}:{window} | 60s | required, 120/min |
| rate ip | rl:ip:{ip}:{window} | 60s | none, 240/min |
| rate api | rl:api:{tenant_id}:{route}:{window} | 60s | required, 60/min |
| rate channel | rl:channel:{tenant_id}:{channel}:{window} | 60s | required, 30/min |
| rate send | rl:send:{tenant_id}:{window} | 60s | required, 30/min |
| send hold | rl:hold:{tenant_id} or rl:hold:{tenant_id}:{channel} | 1h | red line pauses sending |
| report | report:{tenant_id}:{report_id} | 10 min | required |
| kpi | kpi:{tenant_id}:{period} | 60s | required |
| job lock | lock:job:{tenant_id}:{job_id} | 15 min | required, token release |
| ai | ai:{tenant_id}:{model}:{prompt_version}:{cache_key} | 24h | version is in the key so a prompt rollback misses |
| shelf | shelf:{market}:{query_hash} | 1h | shared market data, not a tenant row |
"""

KEY_PREFIX = "pg:v1"

SESSION_TTL = 1_209_600
OTP_TTL = 600
OTP_ATTEMPTS = 5
SMS_DAILY_CAP = 10
WINDOW_SECONDS = 60
HOLD_TTL = 3600
REPORT_TTL = 600
KPI_TTL = 60
LOCK_TTL = 900
AI_TTL = 86_400
SHELF_TTL = 3600

# tenant, ip, and send match backend/config/s4-v1.0.0.json.
# api and channel are the other two axes in §3.2; s4 does not number them yet.
LIMITS = {
    "tenant": 120,
    "ip": 240,
    "api": 60,
    "channel": 30,
    "send": 30,
}

OTP_PURPOSES = frozenset({"login", "register", "reset_password"})
CHANNELS = frozenset(
    {
        "ecommerce",
        "social",
        "expo",
        "agency",
        "enrichment",
        "geo_seo",
        "content_dh",
        "cross_border",
        "raas",
        "email",
    }
)

INCR_LUA = """
local n = redis.call("INCR", KEYS[1])
if n == 1 then
  redis.call("EXPIRE", KEYS[1], tonumber(ARGV[1]))
end
return n
""".strip()

RELEASE_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
end
return 0
""".strip()
