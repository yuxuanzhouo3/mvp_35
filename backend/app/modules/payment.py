import hashlib
import hmac
from datetime import timedelta

from config.settings import Settings
from db.store import DocumentStore

from app.core.errors import AppError
from app.core.timeutil import iso, utcnow
from app.modules.events import emit
from app.modules.state import transition
from app.services.common import PLANS, base_doc, new_id


def sign_payment_event(secret: str, event_id: str, payment_id: str, status: str) -> str:
    payload = f"{event_id}:{payment_id}:{status}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _plan(plan_id: str) -> dict:
    plan = next((item for item in PLANS if item["id"] == plan_id), None)
    if not plan or plan["amount_fen"] <= 0:
        raise AppError("PLAN_NOT_PURCHASABLE", "这个套餐不能下单")
    return plan


def checkout(
    store: DocumentStore,
    prof: dict,
    plan_id: str | None,
    idempotency_key: str,
    *,
    kind: str = "subscription",
    amount_fen: int | None = None,
) -> dict:
    if kind not in {"subscription", "usage"}:
        raise AppError("INVALID_PAYMENT_KIND", "支付类型无效")
    if not idempotency_key:
        raise AppError("IDEMPOTENCY_REQUIRED", "需要 idempotency_key")
    if kind == "usage":
        if not isinstance(amount_fen, int) or isinstance(amount_fen, bool) or amount_fen <= 0:
            raise AppError("INVALID_AMOUNT", "按次支付金额必须是正整数分")
        amount = amount_fen
        stored_plan = None
    else:
        plan = _plan(plan_id or "")
        amount = plan["amount_fen"]
        stored_plan = plan["id"]
    existing = store.find_global("payments", tenant_id=prof["tenant"]["id"], idempotency_key=idempotency_key)
    if existing:
        if int(existing["amount"]) != amount or existing.get("kind", "subscription") != kind:
            raise AppError("IDEMPOTENCY_CONFLICT", "同一幂等键的金额或类型不一致", 409)
        return existing
    status = transition("Payment", "created", "pending")
    doc = base_doc(
        prof["tenant"]["id"],
        prof["user"]["id"],
        id=new_id("pay"),
        user_id=prof["user"]["id"],
        provider="mock",
        amount=amount,
        currency="CNY",
        status=status,
        external_id=None,
        idempotency_key=idempotency_key,
        plan_id=stored_plan,
        kind=kind,
        shard_key=None,
        region=None,
    )
    return store.insert("payments", doc)


def apply_webhook(
    store: DocumentStore,
    settings: Settings,
    *,
    event_id: str,
    payment_id: str,
    status: str,
    signature: str,
) -> dict:
    expected = sign_payment_event(settings.ledger_hmac_secret, event_id, payment_id, status)
    if not hmac.compare_digest(expected, signature or ""):
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    seen = store.find_global("payment_events", external_id=event_id)
    if seen:
        payment = store.get("payments", seen["payment_id"])
        if not payment:
            raise AppError("PAYMENT_NOT_FOUND", "支付单不存在", 404)
        return payment
    payment = store.get("payments", payment_id)
    if not payment:
        raise AppError("PAYMENT_NOT_FOUND", "支付单不存在", 404)
    if status not in {"succeeded", "failed"}:
        raise AppError("INVALID_PAYMENT_STATUS", "无法识别的支付结果")
    nxt = transition("Payment", payment["status"], status)
    store.touch("payments", payment_id, {"status": nxt, "external_id": event_id})
    store.insert(
        "payment_events",
        base_doc(
            payment["tenant_id"],
            "webhook",
            id=new_id("pev"),
            payment_id=payment_id,
            external_id=event_id,
            status=nxt,
        ),
    )
    if nxt == "succeeded":
        _grant(store, payment)
        emit(
            store,
            payment["tenant_id"],
            "payment.succeeded",
            {"payment_id": payment_id, "amount": payment["amount"]},
            payment["created_by"],
        )
    return store.get("payments", payment_id)


def _issue_invoice(store: DocumentStore, payment: dict) -> None:
    if store.find_global("invoices", tenant_id=payment["tenant_id"], payment_id=payment["id"]):
        return
    store.insert(
        "invoices",
        base_doc(
            payment["tenant_id"],
            payment["created_by"],
            id=new_id("inv"),
            payment_id=payment["id"],
            amount=payment["amount"],
            currency=payment["currency"],
            status="issued",
        ),
    )


def _grant(store: DocumentStore, payment: dict) -> None:
    if payment.get("kind") == "usage":
        _issue_invoice(store, payment)
        return
    plan = _plan(payment["plan_id"])
    days = 365 if plan["period"] == "year" else 30
    start = iso()
    end = iso(utcnow() + timedelta(days=days))
    if not store.find_global("subscriptions", tenant_id=payment["tenant_id"], payment_id=payment["id"]):
        store.insert(
            "subscriptions",
            base_doc(
                payment["tenant_id"],
                payment["created_by"],
                id=new_id("sub"),
                plan=plan["id"],
                plan_id=plan["id"],
                status="active",
                period_start=start,
                period_end=end,
                payment_id=payment["id"],
            ),
        )
        store.touch("tenants", payment["tenant_id"], {"plan_id": plan["id"]})
    _issue_invoice(store, payment)


def refund(store: DocumentStore, prof: dict, *, payment_id: str, amount_fen: int, idempotency_key: str) -> dict:
    if not isinstance(amount_fen, int) or isinstance(amount_fen, bool) or amount_fen <= 0:
        raise AppError("INVALID_AMOUNT", "退款金额必须是正整数分")
    if not idempotency_key:
        raise AppError("IDEMPOTENCY_REQUIRED", "需要 idempotency_key")
    existing = store.find_global("refunds", tenant_id=prof["tenant"]["id"], idempotency_key=idempotency_key)
    if existing:
        return existing
    payment = store.get("payments", payment_id, prof["tenant"]["id"])
    if not payment:
        raise AppError("PAYMENT_NOT_FOUND", "支付单不存在", 404)
    if payment["status"] not in {"succeeded", "refunded"}:
        raise AppError("PAYMENT_NOT_REFUNDABLE", "只有已入账的支付可以退款", 409)
    prior = store.query("refunds", tenant_id=prof["tenant"]["id"], filters={"payment_id": payment_id}, limit=50)["items"]
    refunded = sum(int(item["amount"]) for item in prior)
    if refunded + amount_fen > int(payment["amount"]):
        raise AppError("REFUND_EXCEEDS", "退款超过原支付金额", 409)
    doc = base_doc(
        prof["tenant"]["id"],
        prof["user"]["id"],
        id=new_id("rfd"),
        payment_id=payment_id,
        amount=amount_fen,
        currency=payment["currency"],
        status="refunded",
        idempotency_key=idempotency_key,
    )
    store.insert("refunds", doc)
    if refunded + amount_fen == int(payment["amount"]) and payment["status"] != "refunded":
        nxt = transition("Payment", payment["status"], "refunded")
        store.touch("payments", payment_id, {"status": nxt})
    return doc


def query_payment(store: DocumentStore, prof: dict, payment_id: str) -> dict:
    payment = store.get("payments", payment_id, prof["tenant"]["id"])
    if not payment:
        raise AppError("PAYMENT_NOT_FOUND", "支付单不存在", 404)
    granted = payment["status"] == "succeeded"
    if granted:
        _grant(store, payment)
        payment = store.get("payments", payment_id, prof["tenant"]["id"])
    return {
        "id": payment["id"],
        "status": payment["status"],
        "granted": granted,
        "amount": payment["amount"],
        "kind": payment.get("kind", "subscription"),
    }


def reconcile_payments(store: DocumentStore, tenant_id: str) -> dict:
    payments = store.query("payments", tenant_id=tenant_id, limit=200)["items"]
    invoices = store.query("invoices", tenant_id=tenant_id, limit=200)["items"]
    events = store.query("payment_events", tenant_id=tenant_id, limit=200)["items"]
    refunds = store.query("refunds", tenant_id=tenant_id, limit=200)["items"]
    booked = [row for row in payments if row.get("status") in {"succeeded", "refunded"}]
    signed = {row["payment_id"] for row in events if row.get("status") == "succeeded"}
    issued = {row["payment_id"]: int(row["amount"]) for row in invoices if row.get("status") == "issued"}
    unmatched = []
    payments_fen = 0
    for row in booked:
        amount = int(row["amount"])
        payments_fen += amount
        if row["id"] not in signed or issued.get(row["id"]) != amount:
            unmatched.append(row["id"])
    invoices_fen = sum(issued.values())
    refunds_fen = sum(int(row["amount"]) for row in refunds)
    return {
        "balanced": not unmatched and payments_fen == invoices_fen,
        "payments_fen": payments_fen,
        "invoices_fen": invoices_fen,
        "refunds_fen": refunds_fen,
        "unmatched_payment_ids": unmatched,
    }


def cancel_subscription(store: DocumentStore, prof: dict, subscription_id: str | None) -> dict:
    tenant_id = prof["tenant"]["id"]
    if subscription_id:
        row = store.get("subscriptions", subscription_id, tenant_id)
    else:
        row = store.find_global("subscriptions", tenant_id=tenant_id, status="active")
    if not row:
        raise AppError("SUBSCRIPTION_NOT_FOUND", "订阅不存在", 404)
    if row["status"] == "canceled":
        return row
    if row["status"] != "active":
        raise AppError("INVALID_STATE", "当前订阅不能取消", 409)
    store.touch("subscriptions", row["id"], {"status": "canceled"})
    return store.get("subscriptions", row["id"], tenant_id)
