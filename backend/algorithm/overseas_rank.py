"""How many overseas shelf rows a plan may see.

The current pass keeps the rows with the highest rules-engine net profit in USD.
Replace `profit_usd` when a later source-selection pass is ready; the plan caps stay here.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.errors import AppError
from app.core.timeutil import iso
from app.services.common import plan_tier

SHELF_CAPS = {"free": 5, "growth": 10, "scale": 30}
AI_DAILY = {"free": 0, "growth": 5, "scale": 20}
_RANK = {"free": 0, "growth": 1, "scale": 2}
_SHANGHAI = timezone(timedelta(hours=8))


def shanghai_today() -> str:
    return datetime.now(_SHANGHAI).date().isoformat()


def cap_for(plan: str) -> int:
    return SHELF_CAPS.get(plan, SHELF_CAPS["free"])


def profit_usd(row: dict) -> Decimal:
    raw = ((row.get("selection") or {}).get("net_profit_usd")) or "0"
    try:
        return Decimal(str(raw))
    except Exception:
        return Decimal("0")


def top_by_overseas_profit(items: list[dict], plan: str) -> list[dict]:
    ordered = sorted(items, key=profit_usd, reverse=True)
    return ordered[: cap_for(plan)]


def active_plan(store, tenant_id: str) -> str:
    best = "free"
    found = store.query("subscriptions", tenant_id=tenant_id, limit=20)
    now = iso()
    for row in found.get("items") or []:
        plan = plan_tier(str(row.get("plan_id") or row.get("plan") or ""))
        if row.get("status") != "active" or plan not in SHELF_CAPS:
            continue
        end = row.get("period_end") or ""
        if end and end < now:
            continue
        if _RANK[plan] > _RANK[best]:
            best = plan
    if best != "free":
        return best
    tenant = store.get("tenants", tenant_id) or {}
    plan = plan_tier(str(tenant.get("plan_id") or "free"))
    return plan if plan in SHELF_CAPS else "free"


def allowance(store, tenant_id: str) -> dict:
    plan = active_plan(store, tenant_id)
    daily = AI_DAILY[plan]
    tenant = store.get("tenants", tenant_id) or {}
    used = int(tenant.get("selection_ai_used") or 0) if tenant.get("selection_ai_day") == shanghai_today() else 0
    return {
        "plan": plan,
        "shelf_limit": cap_for(plan),
        "ai_daily": daily,
        "ai_left": max(0, daily - used),
    }


def spend_ai(store, tenant_id: str) -> dict:
    info = allowance(store, tenant_id)
    if info["ai_daily"] <= 0:
        raise AppError(
            "SELECTION_AI_CLOSED",
            "免费套餐每天不能使用 AI 选品。专业版每天 5 次，企业版每天 20 次。",
            403,
        )
    if info["ai_left"] <= 0:
        raise AppError("SELECTION_AI_USED", "今天的 AI 选品次数已用完，明天再试。", 403)
    tenant = store.get("tenants", tenant_id) or {}
    today = shanghai_today()
    used = int(tenant.get("selection_ai_used") or 0) if tenant.get("selection_ai_day") == today else 0
    store.touch("tenants", tenant_id, {"selection_ai_day": today, "selection_ai_used": used + 1})
    info["ai_left"] = info["ai_daily"] - used - 1
    return info
