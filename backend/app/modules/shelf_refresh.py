"""How often 1688 shelf prices may be fetched again.

Free accounts reuse the last live prices for one hour. A paid growth or scale
subscription refreshes every 15 minutes and may spend 10 extra pulls that ignore
that wait. The plan prices themselves stay on PLANS.
"""

from app.core.errors import AppError
from app.core.timeutil import iso

FREE_INTERVAL = 3600
PREMIUM_INTERVAL = 900
MANUAL_REFRESHES = 10
PREMIUM_PLANS = {"growth", "scale"}


def policy(store, tenant_id: str) -> dict:
    premium = _premium(store, tenant_id)
    left = 0
    if premium:
        tenant = store.get("tenants", tenant_id) or {}
        if "shelf_refresh_left" not in tenant:
            store.touch("tenants", tenant_id, {"shelf_refresh_left": MANUAL_REFRESHES})
            left = MANUAL_REFRESHES
        else:
            left = int(tenant.get("shelf_refresh_left") or 0)
    return {
        "premium": premium,
        "interval_seconds": PREMIUM_INTERVAL if premium else FREE_INTERVAL,
        "manual_left": left,
    }


def grant(store, tenant_id: str) -> None:
    store.touch("tenants", tenant_id, {"shelf_refresh_left": MANUAL_REFRESHES})


def spend(store, tenant_id: str) -> int:
    tenant = store.get("tenants", tenant_id) or {}
    left = int(tenant.get("shelf_refresh_left") or 0)
    if left <= 0:
        raise AppError("SHELF_REFRESH_USED", "10 次随时刷新已经用完", 403)
    nxt = left - 1
    store.touch("tenants", tenant_id, {"shelf_refresh_left": nxt})
    return nxt


def _premium(store, tenant_id: str) -> bool:
    found = store.query("subscriptions", tenant_id=tenant_id, limit=20)
    now = iso()
    for row in found.get("items") or []:
        plan = row.get("plan_id") or row.get("plan")
        if row.get("status") != "active" or plan not in PREMIUM_PLANS:
            continue
        end = row.get("period_end") or ""
        if end and end < now:
            continue
        return True
    return False
