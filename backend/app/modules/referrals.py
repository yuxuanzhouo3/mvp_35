"""Personal invite links. Rewards stay as account discount until the inviter asks for cash."""

import secrets
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from db.store import DocumentStore

from app.core.errors import AppError
from app.core.timeutil import iso, utcnow
from app.services.common import base_doc, new_id

REFERRAL_RATE = Decimal("0.10")


def ensure_invite_code(store: DocumentStore, user: dict) -> str:
    existing = str(user.get("invite_code") or "")
    if existing:
        return existing
    for _ in range(5):
        code = secrets.token_hex(4).upper()
        if store.find_global("users", invite_code=code) is None:
            store.touch("users", user["id"], {"invite_code": code})
            return code
    raise AppError("INVITE_UNAVAILABLE", "暂时无法生成邀请码", 503)


def attach_inviter(store: DocumentStore, user: dict, invite_code: str | None) -> None:
    code = (invite_code or "").strip().upper()
    if not code:
        return
    inviter = store.find_global("users", invite_code=code)
    if not inviter or inviter["id"] == user["id"]:
        raise AppError("INVALID_INVITE", "邀请码无效", 400)
    store.touch(
        "users",
        user["id"],
        {
            "invited_by": inviter["id"],
            "invited_at": user.get("created_at") or iso(),
            "invite_link": f"/register?invite={code}",
        },
    )


def _mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    name, domain = email.split("@", 1)
    return f"{name[:2]}***@{domain}"


def _person(user: dict) -> dict:
    return {
        "id": user["id"],
        "name": user.get("display_name") or user.get("username") or "",
        "email_masked": _mask_email(user.get("email")),
        "created_at": user.get("created_at"),
    }


def _owed(paid_fen: int) -> int:
    return int((Decimal(paid_fen) * REFERRAL_RATE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def add_business_days(start: datetime, days: int) -> datetime:
    current = start
    left = days
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current


def _payouts_for(store: DocumentStore, inviter_id: str, kind: str | None = None) -> list[dict]:
    rows = store.query("referral_payouts", limit=500)["items"]
    return [row for row in rows if row.get("inviter_id") == inviter_id and (kind is None or row.get("kind") == kind)]


def _public_payout(row: dict) -> dict:
    return {
        "id": row["id"],
        "kind": row.get("kind"),
        "amount_fen": int(row.get("amount_fen") or 0),
        "status": row.get("status") or "scheduled",
        "requested_at": row.get("requested_at"),
        "due_at": row.get("due_at"),
        "paid_at": row.get("paid_at"),
    }


def payout_rows(store: DocumentStore) -> list[dict]:
    users = store.query("users", limit=500)["items"]
    payments = store.query("payments", limit=500)["items"]
    by_id = {row["id"]: row for row in users}
    children: dict[str, list[dict]] = {}
    for row in users:
        parent = row.get("invited_by")
        if parent:
            children.setdefault(parent, []).append(row)
    paid: dict[str, int] = {}
    for payment in payments:
        if payment.get("status") != "succeeded":
            continue
        user_id = payment.get("user_id") or ""
        paid[user_id] = paid.get(user_id, 0) + int(payment.get("amount") or 0)
    rows = []
    for invitor_id, used in children.items():
        invitor = by_id.get(invitor_id)
        if not invitor:
            continue
        later = []
        for child in used:
            for grandchild in children.get(child["id"], []):
                person = _person(grandchild)
                person["via_name"] = child.get("display_name") or child.get("username") or ""
                later.append(person)
        paid_fen = sum(paid.get(child["id"], 0) for child in used)
        owed_fen = _owed(paid_fen)
        events = []
        link = f"/register?invite={invitor.get('invite_code') or ''}"
        payments_by_user: dict[str, list[dict]] = {}
        for payment in payments:
            if payment.get("status") != "succeeded":
                continue
            payments_by_user.setdefault(payment.get("user_id") or "", []).append(payment)
        for child in used:
            child_link = child.get("invite_link") or link
            invited_at = child.get("invited_at") or child.get("created_at")
            child_payments = payments_by_user.get(child["id"], [])
            if not child_payments:
                events.append(
                    {
                        "invitee_id": child["id"],
                        "invitee_name": child.get("display_name") or child.get("username") or "",
                        "link": child_link,
                        "invited_at": invited_at,
                        "paid_at": None,
                        "paid_fen": 0,
                        "reward_fen": 0,
                    }
                )
                continue
            for payment in child_payments:
                amount = int(payment.get("amount") or 0)
                events.append(
                    {
                        "invitee_id": child["id"],
                        "invitee_name": child.get("display_name") or child.get("username") or "",
                        "link": child_link,
                        "invited_at": invited_at,
                        "paid_at": payment.get("created_at"),
                        "paid_fen": amount,
                        "reward_fen": _owed(amount),
                    }
                )
        cash_rows = [_public_payout(row) for row in _payouts_for(store, invitor_id)]
        claimed = sum(row["amount_fen"] for row in cash_rows if row["kind"] == "invite")
        rows.append(
            {
                "invitor_id": invitor_id,
                "invitor_name": invitor.get("display_name") or invitor.get("username") or "",
                "email_masked": _mask_email(invitor.get("email")),
                "invite_code": invitor.get("invite_code") or "",
                "used_by": [_person(child) for child in used],
                "invited_later": later,
                "paid_fen": paid_fen,
                "owed_fen": owed_fen,
                "discount_fen": max(owed_fen - claimed, 0),
                "events": events,
                "cash_requests": cash_rows,
            }
        )
    rows.sort(key=lambda item: item["owed_fen"], reverse=True)
    return rows


def my_invite(store: DocumentStore, user: dict) -> dict:
    code = ensure_invite_code(store, user)
    fresh = store.get("users", user["id"]) or user
    row = next((item for item in payout_rows(store) if item["invitor_id"] == fresh["id"]), None)
    return {
        "invite_code": code,
        "share_path": f"/register?invite={code}",
        "rate": str(REFERRAL_RATE),
        "used_by": row["used_by"] if row else [],
        "invited_later": row["invited_later"] if row else [],
        "paid_fen": row["paid_fen"] if row else 0,
        "owed_fen": row["owed_fen"] if row else 0,
        "discount_fen": row["discount_fen"] if row else 0,
        "events": row["events"] if row else [],
        "cash_requests": row["cash_requests"] if row else _public_cash(store, fresh["id"]),
        "draw_chances": int(fresh.get("draw_chances") or 0),
        "login_streak": int(fresh.get("login_streak") or 0),
        "coupons": list(fresh.get("coupons") or []),
    }


def _public_cash(store: DocumentStore, inviter_id: str) -> list[dict]:
    return [_public_payout(row) for row in _payouts_for(store, inviter_id)]


def request_cash(store: DocumentStore, user: dict) -> dict:
    fresh = store.get("users", user["id"]) or user
    mine = next((item for item in payout_rows(store) if item["invitor_id"] == fresh["id"]), None)
    available = int(mine["discount_fen"]) if mine else 0
    if available <= 0:
        raise AppError("NOTHING_TO_CASH", "当前没有可申请兑现的邀请奖励")
    due = add_business_days(utcnow(), 5)
    return store.insert(
        "referral_payouts",
        base_doc(
            fresh["tenant_id"],
            fresh["id"],
            id=new_id("rpay"),
            inviter_id=fresh["id"],
            kind="invite",
            amount_fen=available,
            status="scheduled",
            requested_at=iso(),
            due_at=iso(due),
        ),
    )


def schedule_cash(store: DocumentStore, user: dict, *, kind: str, amount_fen: int) -> dict:
    if amount_fen <= 0:
        raise AppError("NOTHING_TO_CASH", "没有可入账的现金奖励")
    due = add_business_days(utcnow(), 5)
    return store.insert(
        "referral_payouts",
        base_doc(
            user["tenant_id"],
            user["id"],
            id=new_id("rpay"),
            inviter_id=user["id"],
            kind=kind,
            amount_fen=amount_fen,
            status="scheduled",
            requested_at=iso(),
            due_at=iso(due),
        ),
    )


def mark_payout_paid(store: DocumentStore, payout_id: str) -> dict:
    row = store.get("referral_payouts", payout_id)
    if not row:
        raise AppError("PAYOUT_NOT_FOUND", "兑现申请不存在", 404)
    if row.get("status") == "paid":
        return row
    updated = store.touch("referral_payouts", payout_id, {"status": "paid", "paid_at": iso()})
    return updated or row
