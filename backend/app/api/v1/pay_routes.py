from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.api.deps import bind, respond
from app.modules.payment import apply_webhook, cancel_subscription, checkout, open_channel, query_payment, reconcile_payments, refund
from app.services.common import PLANS
from config.flags import require_flag

router = APIRouter(prefix="/api/v1")


class CheckoutIn(BaseModel):
    plan_id: str | None = None
    idempotency_key: str
    kind: str = "subscription"
    amount_fen: int | None = None
    provider: str | None = None


class WebhookIn(BaseModel):
    event_id: str
    payment_id: str
    status: str
    signature: str


class RefundIn(BaseModel):
    payment_id: str
    amount_fen: int
    idempotency_key: str


class CancelIn(BaseModel):
    subscription_id: str | None = None


class RaasIn(BaseModel):
    amount_fen: int | None = None
    idempotency_key: str | None = None


@router.post("/payments/checkout")
def payments_checkout(request: Request, body: CheckoutIn, authorization: str | None = Header(default=None)):
    settings, store, prof = bind(request, authorization, write=True, permission="billing.write")
    payment = checkout(
        store,
        prof,
        body.plan_id,
        body.idempotency_key,
        kind=body.kind,
        amount_fen=body.amount_fen,
    )
    if body.provider:
        payment = {**payment, **open_channel(store, settings, payment, body.provider)}
    return respond(request, payment)


@router.post("/payments/webhook")
def payments_webhook(request: Request, body: WebhookIn):
    settings = request.app.state.settings
    payment = apply_webhook(
        request.app.state.store,
        settings,
        event_id=body.event_id,
        payment_id=body.payment_id,
        status=body.status,
        signature=body.signature,
    )
    return respond(request, payment)


@router.get("/payments")
def list_payments(request: Request, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization)
    return respond(request, store.query("payments", tenant_id=prof["tenant"]["id"], limit=50))


@router.get("/payments/reconcile")
def payments_reconcile(request: Request, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization)
    return respond(request, reconcile_payments(store, prof["tenant"]["id"]))


@router.post("/payments/{payment_id}/query")
def payments_query(payment_id: str, request: Request, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization, write=True, permission="billing.write")
    return respond(request, query_payment(store, prof, payment_id))


@router.get("/subscriptions")
def list_subscriptions(request: Request, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization)
    return respond(request, store.query("subscriptions", tenant_id=prof["tenant"]["id"], limit=20))


@router.post("/subscriptions/cancel")
def subscriptions_cancel(request: Request, body: CancelIn, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization, write=True, permission="billing.write")
    return respond(request, cancel_subscription(store, prof, body.subscription_id))


@router.post("/refunds")
def create_refund(request: Request, body: RefundIn, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization, write=True, permission="billing.write")
    return respond(request, refund(store, prof, payment_id=body.payment_id, amount_fen=body.amount_fen, idempotency_key=body.idempotency_key))


@router.get("/invoices")
def list_invoices(request: Request, authorization: str | None = Header(default=None)):
    _settings, store, prof = bind(request, authorization)
    return respond(request, store.query("invoices", tenant_id=prof["tenant"]["id"], limit=50))


@router.get("/billing/summary")
def billing_summary(request: Request, authorization: str | None = Header(default=None)):
    """One read for the payment screen: plans, subscription, payments, invoices."""
    _settings, store, prof = bind(request, authorization, permission="billing.write")
    tenant_id = prof["tenant"]["id"]
    return respond(
        request,
        {
            "plans": PLANS,
            "subscription": store.query("subscriptions", tenant_id=tenant_id, limit=5),
            "payments": store.query("payments", tenant_id=tenant_id, limit=20),
            "invoices": store.query("invoices", tenant_id=tenant_id, limit=20),
        },
    )


@router.post("/payments/raas")
def payments_raas(request: Request, body: RaasIn, authorization: str | None = Header(default=None)):
    require_flag("payment.raas")
    bind(request, authorization, write=True, permission="billing.write")
    return respond(request, {"posted": False, "amount_fen": body.amount_fen})
