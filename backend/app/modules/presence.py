"""Daily and monthly login, recall links, and continuous-login rewards."""

import secrets
from datetime import date, datetime, timedelta, timezone

from db.store import DocumentStore

from app.core.errors import AppError
from app.core.timeutil import iso, parse_iso
from app.modules.referrals import schedule_cash
from app.services.common import base_doc, new_id

CN = timezone(timedelta(hours=8))
STREAK_CASH_FEN = 3000
DRAW_WEIGHTS = ((0, 50), (100, 30), (500, 15), (1000, 5))


def today_cn(moment: datetime | None = None) -> str:
    current = moment or datetime.now(CN)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(CN).date().isoformat()


def _shift(day: str, delta: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=delta)).isoformat()


def _streak(days: list[str], today: str) -> int:
    have = set(days)
    if today not in have:
        return 0
    count = 0
    cursor = today
    while cursor in have:
        count += 1
        cursor = _shift(cursor, -1)
    return count


def _month_count(days: list[str], today: str) -> int:
    prefix = today[:7]
    return len({day for day in days if day.startswith(prefix)})


def _absent_days(user: dict, today: str) -> int:
    raw = user.get("last_login_at") or user.get("created_at")
    if not raw:
        return 0
    try:
        moment = parse_iso(str(raw))
    except ValueError:
        return 0
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    last = moment.astimezone(CN).date()
    return (date.fromisoformat(today) - last).days


def _bucket(absent: int) -> int | None:
    if absent >= 30:
        return 30
    if absent >= 14:
        return 14
    if absent >= 7:
        return 7
    return None


def _mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    name, domain = email.split("@", 1)
    return f"{name[:2]}***@{domain}"


def _draw_amount() -> int:
    roll = secrets.randbelow(100)
    cursor = 0
    for amount, weight in DRAW_WEIGHTS:
        cursor += weight
        if roll < cursor:
            return amount
    return 0


def note_login(store: DocumentStore, user: dict, recall_token: str | None = None) -> dict:
    fresh = store.get("users", user["id"]) or user
    today = today_cn()
    days = [day for day in list(fresh.get("login_dates") or []) if isinstance(day, str)]
    if today not in days:
        days.append(today)
    days = days[-400:]
    streak = _streak(days, today)
    grants = {str(key): value for key, value in dict(fresh.get("streak_grants") or {}).items()}
    if streak < 30:
        grants.pop("30", None)
    if streak < 14:
        grants.pop("14", None)
    if streak < 7:
        grants.pop("7", None)
    draws = int(fresh.get("draw_chances") or 0)
    if streak >= 7 and "7" not in grants:
        draws += 1
        grants["7"] = today
    if streak >= 14 and "14" not in grants:
        draws += 2
        grants["14"] = today
    if streak >= 30 and "30" not in grants:
        grants["30"] = today
        schedule_cash(store, fresh, kind="streak", amount_fen=STREAK_CASH_FEN)
    updated = store.touch(
        "users",
        fresh["id"],
        {
            "last_login_at": iso(),
            "login_dates": days,
            "login_streak": streak,
            "draw_chances": draws,
            "streak_grants": grants,
        },
    )
    if recall_token:
        _redeem_recall(store, updated or fresh, recall_token.strip())
    return store.get("users", fresh["id"]) or fresh


def _redeem_recall(store: DocumentStore, user: dict, token: str) -> None:
    link = store.find_global("recall_links", token=token)
    if not link or link.get("used_at") or link.get("user_id") != user["id"]:
        return
    store.touch("recall_links", link["id"], {"used_at": iso()})
    fresh = store.get("users", user["id"]) or user
    coupons = list(fresh.get("coupons") or [])
    if any(item.get("id") == link["id"] for item in coupons):
        return
    coupons.append(
        {
            "id": link["id"],
            "label": "召回登录优惠",
            "rate": "0.10",
            "status": "open",
            "granted_at": iso(),
        }
    )
    store.touch("users", user["id"], {"coupons": coupons})


def draw_cash(store: DocumentStore, user: dict) -> dict:
    fresh = store.get("users", user["id"]) or user
    chances = int(fresh.get("draw_chances") or 0)
    if chances <= 0:
        raise AppError("NO_DRAW", "没有可使用的抽奖次数")
    amount = _draw_amount()
    store.touch("users", fresh["id"], {"draw_chances": chances - 1})
    payout = None
    if amount > 0:
        payout = schedule_cash(store, fresh, kind="draw", amount_fen=amount)
    return {"amount_fen": amount, "draw_chances": chances - 1, "payout": payout}


def recall_audience(store: DocumentStore) -> dict:
    today = today_cn()
    users = store.query("users", limit=500)["items"]
    daily = 0
    monthly = 0
    buckets: dict[str, list[dict]] = {"7": [], "14": [], "30": []}
    for user in users:
        days = [day for day in list(user.get("login_dates") or []) if isinstance(day, str)]
        if today in days:
            daily += 1
        if _month_count(days, today):
            monthly += 1
        absent = _absent_days(user, today)
        bucket = _bucket(absent)
        if bucket is None:
            continue
        buckets[str(bucket)].append(
            {
                "id": user["id"],
                "name": user.get("display_name") or user.get("username") or "",
                "email_masked": _mask_email(user.get("email")),
                "absent_days": absent,
                "login_streak": int(user.get("login_streak") or 0),
                "month_logins": _month_count(days, today),
                "last_login_at": user.get("last_login_at"),
            }
        )
    for rows in buckets.values():
        rows.sort(key=lambda item: item["absent_days"], reverse=True)
    return {"today": today, "daily_logins": daily, "monthly_logins": monthly, "buckets": buckets}


def issue_recall_links(store: DocumentStore, days: int) -> list[dict]:
    if days not in {7, 14, 30}:
        raise AppError("INVALID_RECALL", "召回只按 7、14 或 30 天未登录")
    created = []
    for person in recall_audience(store)["buckets"][str(days)]:
        existing = store.find_global("recall_links", user_id=person["id"], bucket=days)
        if existing and not existing.get("used_at"):
            created.append(_public_link(existing, person))
            continue
        user = store.get("users", person["id"])
        if not user:
            continue
        token = secrets.token_urlsafe(18)
        doc = store.insert(
            "recall_links",
            base_doc(
                user["tenant_id"],
                user["id"],
                id=new_id("rcl"),
                user_id=user["id"],
                bucket=days,
                token=token,
                share_path=f"/login?recall={token}",
            ),
        )
        created.append(_public_link(doc, person))
    return created


def _public_link(row: dict, person: dict) -> dict:
    return {
        "id": row["id"],
        "user_id": row.get("user_id"),
        "name": person.get("name") or "",
        "email_masked": person.get("email_masked"),
        "bucket": row.get("bucket"),
        "share_path": row.get("share_path"),
        "used_at": row.get("used_at"),
    }
