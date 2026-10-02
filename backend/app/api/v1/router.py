import json

from fastapi import APIRouter, BackgroundTasks, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import bind
from app.core.errors import AppError
from app.core.timeutil import iso
from app.modules.acquisition import record_win, touch_delivery
from app.modules.auth import revoke_bearer
from app.modules.events import emit
from app.modules.selection import mark_acquired, present_report
from app.services.common import (
    CHANNELS,
    PLANS,
    apply_market_change,
    base_doc,
    envelope,
    mock_leads,
    new_id,
    post_signed_ledger,
    product_from_body,
    quota_reserve,
    require_doc,
    search_catalog,
    sign_ledger,
)
from app.services.identity import bootstrap, parse_principal, profile
from app.services.metrics import snapshot
from app.workers.execute import _audience, enqueue, execute_job


class BootstrapIn(BaseModel):
    display_name: str | None = None


class ProductIn(BaseModel):
    name: str
    sku: str
    category: str | None = None
    cost_cny: str = "0"
    packaging_cny: str = "0"
    domestic_freight_cny: str = "0"
    international_freight_usd: str = "0"
    target_price_usd: str
    hs_code_hint: str | None = None
    origin_country: str | None = None
    target_market: str | None = None
    route: str | None = None
    incoterm: str | None = None
    tax_regime: str | None = None
    cost_currency: str | None = None
    price_currency: str | None = None
    fx_usd_cny: str | None = None


class ProductPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    cost_cny: str | None = None
    packaging_cny: str | None = None
    domestic_freight_cny: str | None = None
    international_freight_usd: str | None = None
    target_price_usd: str | None = None
    hs_code_hint: str | None = None
    origin_country: str | None = None
    target_market: str | None = None
    incoterm: str | None = None
    tax_regime: str | None = None
    cost_currency: str | None = None
    price_currency: str | None = None
    fx_usd_cny: str | None = None


class CsvIn(BaseModel):
    csv: str


class AdoptIn(BaseModel):
    catalog_id: str


class LeadSearchIn(BaseModel):
    channel: str
    platform: str | None = None
    query: str = ""
    seed_analysis_id: str | None = None


class LeadPatch(BaseModel):
    status: str | None = None


class SignalIn(BaseModel):
    type: str


class CampaignIn(BaseModel):
    name: str
    lead_ids: list[str] = Field(default_factory=list)
    purpose: str = "acquisition"
    seed_analysis_id: str | None = None
    market_pack: str | None = "cn_us"


class OrderIn(BaseModel):
    plan_id: str
    provider: str | None = None


class LedgerIn(BaseModel):
    amount_fen: int
    idempotency_key: str
    signature: str
    channel_account_id: str | None = None
    note: str | None = None


class SignIn(BaseModel):
    idempotency_key: str
    amount_fen: int
    subject: str


class ChatIn(BaseModel):
    title: str | None = None
    context_id: str | None = None


class MessageIn(BaseModel):
    content: str


class SuppressionIn(BaseModel):
    email: str


def _channel_order(settings, store, prof, plan: dict, provider: str) -> dict:
    from app.modules.payment import channel_ready, checkout, open_channel

    label = "微信" if provider == "wechat" else "支付宝"
    if not channel_ready(settings, provider):
        return store.insert(
            "payment_orders",
            base_doc(
                prof["tenant"]["id"],
                prof["user"]["id"],
                id=new_id("ord"),
                plan_id=plan["id"],
                amount_fen=plan["amount_fen"],
                currency="CNY",
                provider="wechat_pay" if provider == "wechat" else "alipay",
                status="pending",
                code_url=None,
                pay_url=None,
                payment_id=None,
                message=f"{label}支付未开通，订单保持待支付，不会发放权益",
            ),
        )
    payment = checkout(store, prof, plan["id"], new_id("idem"))
    charge = open_channel(store, settings, payment, provider)
    return store.insert(
        "payment_orders",
        base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("ord"),
            plan_id=plan["id"],
            amount_fen=plan["amount_fen"],
            currency="CNY",
            provider="wechat_pay" if provider == "wechat" else "alipay",
            status="pending",
            code_url=charge["code_url"],
            pay_url=charge["pay_url"],
            payment_id=payment["id"],
            message=charge["message"],
        ),
    )


def create_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def ctx(request: Request, authorization: str | None, *, write: bool = False):
        return bind(request, authorization, write=write)

    def respond(request: Request, data):
        return envelope(data, request.state.request_id)

    def schedule(background: BackgroundTasks, store, settings, job_id: str):
        background.add_task(execute_job, store, settings, job_id)

    def start_job(store, settings, prof, job_type, payload, module: str | None, idempotency_key: str | None):
        if idempotency_key:
            existing = store.find_global("jobs", tenant_id=prof["tenant"]["id"], idempotency_key=idempotency_key)
            if existing:
                return existing
        job_id = new_id("job")
        if module:
            quota_reserve(store, prof["tenant"]["id"], module, job_id)
        return enqueue(
            store,
            prof["tenant"]["id"],
            prof["user"]["id"],
            job_type,
            payload,
            job_id=job_id,
            idempotency_key=idempotency_key,
        )

    @router.get("/health/live")
    def live():
        return {"data": {"status": "live"}}

    @router.get("/health/ready")
    def ready(request: Request):
        request.app.state.store.transaction(lambda data: data)
        return {"data": {"status": "ready", "auth_mode": request.app.state.settings.auth_mode}}

    @router.post("/auth/bootstrap")
    def auth_bootstrap(request: Request, body: BootstrapIn, authorization: str | None = Header(default=None)):
        settings, store, _prof = ctx(request, authorization)
        principal = parse_principal(authorization, settings)
        user = store.find_global("users", cloudbase_user_id=principal)
        if user and body.display_name:
            store.touch("users", user["id"], {"display_name": body.display_name})
            user = store.get("users", user["id"])
            return respond(request, profile(store, user))
        if user:
            return respond(request, profile(store, user))
        return respond(request, bootstrap(store, principal, body.display_name))

    @router.get("/me")
    def me(request: Request, authorization: str | None = Header(default=None)):
        _settings, _store, prof = ctx(request, authorization)
        return respond(request, prof)

    @router.post("/auth/logout")
    def logout(request: Request, authorization: str | None = Header(default=None)):
        settings, store, prof = ctx(request, authorization)
        revoke_bearer(store, authorization, settings)
        store.insert(
            "audit_logs",
            base_doc(prof["tenant"]["id"], prof["user"]["id"], id=new_id("audit"), action="logout", resource="session"),
        )
        return respond(request, {"logged_out": True})

    @router.get("/tenants/current")
    def current_tenant(request: Request, authorization: str | None = Header(default=None)):
        _settings, _store, prof = ctx(request, authorization)
        return respond(request, prof["tenant"] | {"role": prof["role"]})

    @router.get("/tenants/current/usage")
    def current_usage(request: Request, authorization: str | None = Header(default=None)):
        _settings, _store, prof = ctx(request, authorization)
        return respond(request, prof["quota"])

    @router.get("/channels")
    def channels(request: Request, authorization: str | None = Header(default=None)):
        ctx(request, authorization)
        return respond(request, {"channels": CHANNELS, "providers": "mock"})

    @router.get("/catalog/search")
    def catalog_search(request: Request, q: str = "", authorization: str | None = Header(default=None)):
        ctx(request, authorization)
        return respond(request, {"items": search_catalog(q)})

    @router.post("/catalog/adopt")
    def catalog_adopt(request: Request, body: AdoptIn, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        item = next((row for row in search_catalog("") if row["id"] == body.catalog_id), None)
        if not item:
            raise AppError("CATALOG_NOT_FOUND", "货源目录中没有这个商品", 404)
        fields = product_from_body(item, source="catalog")
        existing = store.find_global("products", tenant_id=prof["tenant"]["id"], normalized_sku=fields["normalized_sku"])
        if existing:
            return respond(request, existing)
        doc = base_doc(prof["tenant"]["id"], prof["user"]["id"], id=new_id("prd"), **fields)
        store.insert("products", doc)
        store.insert(
            "product_sources",
            base_doc(
                prof["tenant"]["id"],
                prof["user"]["id"],
                id=new_id("src"),
                product_id=doc["id"],
                provider="mock_catalog",
                external_id=item["id"],
            ),
        )
        return respond(request, doc)

    @router.post("/products")
    def create_product(request: Request, body: ProductIn, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        fields = product_from_body(body.model_dump(), source="manual")
        existing = store.find_global("products", tenant_id=prof["tenant"]["id"], normalized_sku=fields["normalized_sku"])
        if existing:
            raise AppError("DUPLICATE_SKU", "这个 SKU 已经在商品库里", 409)
        doc = base_doc(prof["tenant"]["id"], prof["user"]["id"], id=new_id("prd"), **fields)
        return respond(request, store.insert("products", doc))

    @router.get("/products")
    def list_products(
        request: Request,
        cursor: str | None = None,
        q: str | None = None,
        authorization: str | None = Header(default=None),
    ):
        _settings, store, prof = ctx(request, authorization)
        return respond(
            request,
            store.query("products", tenant_id=prof["tenant"]["id"], cursor=cursor, limit=50, q=q),
        )

    @router.get("/products/{product_id}")
    def get_product(product_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        return respond(request, require_doc(store, "products", product_id, prof["tenant"]["id"], "PRODUCT_NOT_FOUND", "商品不存在"))

    @router.patch("/products/{product_id}")
    def patch_product(product_id: str, request: Request, body: ProductPatch, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        product = require_doc(store, "products", product_id, prof["tenant"]["id"], "PRODUCT_NOT_FOUND", "商品不存在")
        apply_market_change(product, body.model_dump(exclude_none=True))
        store.put("products", product)
        return respond(request, store.get("products", product_id, prof["tenant"]["id"]))

    @router.delete("/products/{product_id}")
    def delete_product(product_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        require_doc(store, "products", product_id, prof["tenant"]["id"], "PRODUCT_NOT_FOUND", "商品不存在")
        store.touch("products", product_id, {"deleted_at": iso()})
        return respond(request, {"deleted": True})

    @router.post("/products/imports", status_code=202)
    def import_products(
        request: Request,
        body: CsvIn,
        background: BackgroundTasks,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        settings, store, prof = ctx(request, authorization, write=True)
        job = start_job(store, settings, prof, "product_import", {"csv": body.csv}, None, idempotency_key)
        if job["status"] == "queued":
            schedule(background, store, settings, job["id"])
        return respond(request, {"job_id": job["id"], "status": job["status"]})

    @router.post("/products/{product_id}/analyses", status_code=202)
    def create_analysis(
        product_id: str,
        request: Request,
        background: BackgroundTasks,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        settings, store, prof = ctx(request, authorization, write=True)
        require_doc(store, "products", product_id, prof["tenant"]["id"], "PRODUCT_NOT_FOUND", "商品不存在")
        job = start_job(
            store,
            settings,
            prof,
            "product_analysis",
            {"product_id": product_id},
            "analysis",
            idempotency_key,
        )
        if job["status"] == "queued":
            schedule(background, store, settings, job["id"])
        return respond(request, {"job_id": job["id"], "status": job["status"], "resource_id": (job.get("result") or {}).get("analysis_id")})

    @router.get("/analyses/{analysis_id}")
    def get_analysis(analysis_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        report = require_doc(store, "analysis_reports", analysis_id, prof["tenant"]["id"], "ANALYSIS_NOT_FOUND", "报告不存在")
        return respond(request, present_report(store, prof["tenant"]["id"], report))

    @router.get("/analyses/{analysis_id}/export")
    def export_analysis(analysis_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        report = require_doc(store, "analysis_reports", analysis_id, prof["tenant"]["id"], "ANALYSIS_NOT_FOUND", "报告不存在")
        return respond(
            request,
            {
                "filename": f"{analysis_id}.json",
                "mime": "application/json",
                "body": {
                    "rules_version": report["rules_version"],
                    "metrics": report["metrics"],
                    "explanation_model": report["explanation_model"],
                },
            },
        )

    @router.post("/analyses/{analysis_id}/acquire")
    def acquire(analysis_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        return respond(request, mark_acquired(store, prof["tenant"]["id"], prof["user"]["id"], analysis_id))

    @router.post("/lead-searches", status_code=202)
    def lead_search(
        request: Request,
        body: LeadSearchIn,
        background: BackgroundTasks,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        settings, store, prof = ctx(request, authorization, write=True)
        if body.channel not in CHANNELS:
            raise AppError("UNKNOWN_CHANNEL", "未知获客通道")
        mock_leads(body.channel, body.platform, body.query, body.seed_analysis_id)
        job = start_job(
            store,
            settings,
            prof,
            "lead_discovery",
            body.model_dump(),
            "discovery",
            idempotency_key,
        )
        if job["status"] == "queued":
            schedule(background, store, settings, job["id"])
        return respond(request, {"job_id": job["id"], "status": job["status"]})

    @router.get("/leads")
    def list_leads(
        request: Request,
        channel: str | None = None,
        seed_analysis_id: str | None = None,
        authorization: str | None = Header(default=None),
    ):
        _settings, store, prof = ctx(request, authorization)
        filters = {}
        if channel:
            filters["source_channel"] = channel
        if seed_analysis_id:
            filters["seed_analysis_id"] = seed_analysis_id
        return respond(request, store.query("leads", tenant_id=prof["tenant"]["id"], filters=filters, limit=100))

    @router.get("/leads/{lead_id}")
    def get_lead(lead_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        return respond(request, require_doc(store, "leads", lead_id, prof["tenant"]["id"], "LEAD_NOT_FOUND", "线索不存在"))

    @router.patch("/leads/{lead_id}")
    def patch_lead(lead_id: str, request: Request, body: LeadPatch, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        lead = require_doc(store, "leads", lead_id, prof["tenant"]["id"], "LEAD_NOT_FOUND", "线索不存在")
        if body.status:
            _apply_signal(store, prof["tenant"]["id"], lead, {"won": "won", "replied": "reply", "lost": "lost", "silent": "silent"}.get(body.status, body.status))
        return respond(request, store.get("leads", lead_id, prof["tenant"]["id"]))

    @router.post("/leads/{lead_id}/signals")
    def lead_signal(lead_id: str, request: Request, body: SignalIn, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        lead = require_doc(store, "leads", lead_id, prof["tenant"]["id"], "LEAD_NOT_FOUND", "线索不存在")
        _apply_signal(store, prof["tenant"]["id"], lead, body.type)
        return respond(request, store.get("leads", lead_id, prof["tenant"]["id"]))

    @router.post("/campaigns")
    def create_campaign(request: Request, body: CampaignIn, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        if body.purpose not in {"acquisition", "activation", "recall"}:
            raise AppError("INVALID_PURPOSE", "活动目的无效")
        for lead_id in body.lead_ids:
            require_doc(store, "leads", lead_id, prof["tenant"]["id"], "LEAD_NOT_FOUND", "线索不存在")
        doc = base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("cmp"),
            name=body.name,
            lead_ids=body.lead_ids,
            purpose=body.purpose,
            seed_analysis_id=body.seed_analysis_id,
            market_pack=body.market_pack,
            status="draft",
            draft=None,
            audience_snapshot=None,
            approved_at=None,
        )
        return respond(request, store.insert("campaigns", doc))

    @router.get("/campaigns")
    def list_campaigns(request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        return respond(request, store.query("campaigns", tenant_id=prof["tenant"]["id"], limit=50))

    @router.get("/campaigns/{campaign_id}")
    def get_campaign(campaign_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        campaign = require_doc(store, "campaigns", campaign_id, prof["tenant"]["id"], "CAMPAIGN_NOT_FOUND", "活动不存在")
        messages = store.query(
            "outreach_messages",
            tenant_id=prof["tenant"]["id"],
            filters={"campaign_id": campaign_id},
            limit=200,
        )
        return respond(request, {**campaign, "messages": messages["items"]})

    @router.post("/campaigns/{campaign_id}/drafts")
    def draft_campaign(campaign_id: str, request: Request, authorization: str | None = Header(default=None)):
        settings, store, prof = ctx(request, authorization, write=True)
        campaign = require_doc(store, "campaigns", campaign_id, prof["tenant"]["id"], "CAMPAIGN_NOT_FOUND", "活动不存在")
        if campaign["status"] not in {"draft", "pending_approval"}:
            raise AppError("CAMPAIGN_LOCKED", "活动已批准或已发送，不能重写草稿", 409)
        pack = campaign.get("market_pack") or "cn_us"
        text = (
            f"【待批准草稿】市场包 {pack}。"
            f"您好，我们在 {pack} 路线上有一批可复核利润的商品，方便安排 15 分钟沟通吗？"
            f"文案由规则模板生成，混元{'已开启' if settings.hunyuan_enabled else '未开启'}，不会改动金额和评分。"
        )
        store.touch("campaigns", campaign_id, {"draft": text, "status": "pending_approval", "explanation_model": "rules"})
        return respond(request, store.get("campaigns", campaign_id, prof["tenant"]["id"]))

    @router.post("/campaigns/{campaign_id}/approve")
    def approve_campaign(campaign_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        campaign = require_doc(store, "campaigns", campaign_id, prof["tenant"]["id"], "CAMPAIGN_NOT_FOUND", "活动不存在")
        if campaign["status"] != "pending_approval" or not campaign.get("draft"):
            raise AppError("CAMPAIGN_NOT_READY", "请先生成草稿再批准", 409)
        snapshot_audience = _audience(store, prof["tenant"]["id"], campaign.get("lead_ids") or [])
        store.touch(
            "campaigns",
            campaign_id,
            {"status": "approved", "approved_at": iso(), "audience_snapshot": snapshot_audience},
        )
        return respond(request, store.get("campaigns", campaign_id, prof["tenant"]["id"]))

    @router.post("/campaigns/{campaign_id}/send", status_code=202)
    def send_campaign(
        campaign_id: str,
        request: Request,
        background: BackgroundTasks,
        authorization: str | None = Header(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        settings, store, prof = ctx(request, authorization, write=True)
        campaign = require_doc(store, "campaigns", campaign_id, prof["tenant"]["id"], "CAMPAIGN_NOT_FOUND", "活动不存在")
        if campaign["status"] == "paused":
            raise AppError("CAMPAIGN_PAUSED", "活动已暂停", 409)
        if campaign["status"] != "approved":
            raise AppError("CAMPAIGN_NOT_APPROVED", "未批准不能发送", 409)
        store.touch("campaigns", campaign_id, {"status": "sending"})
        job = start_job(
            store,
            settings,
            prof,
            "campaign_send",
            {"campaign_id": campaign_id},
            "send",
            idempotency_key,
        )
        if job["status"] == "queued":
            schedule(background, store, settings, job["id"])
        return respond(request, {"job_id": job["id"], "status": job["status"], "resource_id": campaign_id})

    @router.post("/campaigns/{campaign_id}/pause")
    def pause_campaign(campaign_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        campaign = require_doc(store, "campaigns", campaign_id, prof["tenant"]["id"], "CAMPAIGN_NOT_FOUND", "活动不存在")
        if campaign["status"] == "sent":
            raise AppError("CAMPAIGN_SENT", "已发送的活动不能暂停", 409)
        store.touch("campaigns", campaign_id, {"status": "paused"})
        return respond(request, store.get("campaigns", campaign_id, prof["tenant"]["id"]))

    @router.post("/lifecycle/scan", status_code=202)
    def lifecycle_scan(
        request: Request,
        background: BackgroundTasks,
        authorization: str | None = Header(default=None),
    ):
        settings, store, prof = ctx(request, authorization, write=True)
        job = start_job(store, settings, prof, "lifecycle_scan", {}, None, None)
        schedule(background, store, settings, job["id"])
        return respond(request, {"job_id": job["id"], "status": job["status"]})

    @router.get("/activation/jobs")
    def activation_jobs(request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        return respond(request, store.query("activation_jobs", tenant_id=prof["tenant"]["id"], limit=100))

    @router.get("/recall/jobs")
    def recall_jobs(request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        return respond(request, store.query("recall_jobs", tenant_id=prof["tenant"]["id"], limit=100))

    @router.post("/activation/jobs/{job_id}/approve")
    def approve_activation(job_id: str, request: Request, authorization: str | None = Header(default=None)):
        return respond(request, _approve_lifecycle(request, authorization, "activation_jobs", job_id))

    @router.post("/recall/jobs/{job_id}/approve")
    def approve_recall(job_id: str, request: Request, authorization: str | None = Header(default=None)):
        return respond(request, _approve_lifecycle(request, authorization, "recall_jobs", job_id))

    @router.post("/activation/jobs/{job_id}/send", status_code=202)
    def send_activation(
        job_id: str,
        request: Request,
        background: BackgroundTasks,
        authorization: str | None = Header(default=None),
    ):
        return _send_lifecycle(request, background, authorization, "activation", job_id)

    @router.post("/recall/jobs/{job_id}/send", status_code=202)
    def send_recall(
        job_id: str,
        request: Request,
        background: BackgroundTasks,
        authorization: str | None = Header(default=None),
    ):
        return _send_lifecycle(request, background, authorization, "recall", job_id)

    def _approve_lifecycle(request: Request, authorization: str | None, collection: str, job_id: str):
        _settings, store, prof = ctx(request, authorization, write=True)
        row = require_doc(store, collection, job_id, prof["tenant"]["id"], "LIFECYCLE_NOT_FOUND", "任务不存在")
        if row["status"] != "queued":
            raise AppError("LIFECYCLE_NOT_READY", "只有待批准任务可以通过", 409)
        store.touch(collection, job_id, {"status": "approved", "approved_at": iso()})
        return store.get(collection, job_id, prof["tenant"]["id"])

    def _send_lifecycle(request: Request, background: BackgroundTasks, authorization: str | None, kind: str, lifecycle_id: str):
        settings, store, prof = ctx(request, authorization, write=True)
        collection = "activation_jobs" if kind == "activation" else "recall_jobs"
        row = require_doc(store, collection, lifecycle_id, prof["tenant"]["id"], "LIFECYCLE_NOT_FOUND", "任务不存在")
        if row["status"] != "approved":
            raise AppError("LIFECYCLE_NOT_APPROVED", "未批准不能发送", 409)
        job = start_job(
            store,
            settings,
            prof,
            "lifecycle_send",
            {"kind": kind, "lifecycle_id": lifecycle_id},
            "send",
            None,
        )
        schedule(background, store, settings, job["id"])
        return respond(request, {"job_id": job["id"], "status": job["status"], "resource_id": lifecycle_id})

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        return respond(request, require_doc(store, "jobs", job_id, prof["tenant"]["id"], "JOB_NOT_FOUND", "任务不存在"))

    @router.get("/jobs/{job_id}/events")
    def job_events(job_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        job = require_doc(store, "jobs", job_id, prof["tenant"]["id"], "JOB_NOT_FOUND", "任务不存在")

        def stream():
            payload = json.dumps({"status": job["status"], "progress": job["progress"], "steps": job.get("steps") or []})
            yield f"event: start\ndata: {payload}\n\n"
            yield f"event: done\ndata: {payload}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    @router.post("/internal/jobs/{job_id}/execute")
    def internal_execute(job_id: str, request: Request, x_worker_token: str | None = Header(default=None)):
        settings = request.app.state.settings
        if x_worker_token != settings.worker_token:
            raise AppError("FORBIDDEN", "worker 凭证无效", 403)
        job = execute_job(request.app.state.store, settings, job_id)
        if not job:
            raise AppError("JOB_NOT_FOUND", "任务不存在", 404)
        return respond(request, {"id": job["id"], "status": job["status"]})

    @router.get("/metrics")
    def metrics(request: Request, window_days: int = 30, authorization: str | None = Header(default=None)):
        settings, store, prof = ctx(request, authorization)
        return respond(request, snapshot(store, prof["tenant"]["id"], settings, window_days))

    @router.get("/billing/plans")
    def plans(request: Request, authorization: str | None = Header(default=None)):
        ctx(request, authorization)
        return respond(request, {"items": PLANS})

    @router.get("/billing/subscription")
    def subscription(request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        row = store.find_global("subscriptions", tenant_id=prof["tenant"]["id"])
        return respond(request, row or {"plan_id": "free", "status": "active", "source": "bootstrap"})

    @router.get("/billing/entitlements")
    def entitlements(request: Request, authorization: str | None = Header(default=None)):
        _settings, _store, prof = ctx(request, authorization)
        return respond(request, prof["entitlement"])

    @router.get("/billing/usage")
    def billing_usage(request: Request, authorization: str | None = Header(default=None)):
        _settings, _store, prof = ctx(request, authorization)
        return respond(request, prof["quota"])

    @router.post("/billing/orders")
    def create_order(request: Request, body: OrderIn, authorization: str | None = Header(default=None)):
        settings, store, prof = ctx(request, authorization, write=True)
        plan = next((item for item in PLANS if item["id"] == body.plan_id), None)
        if not plan or plan["amount_fen"] <= 0:
            raise AppError("PLAN_NOT_PURCHASABLE", "这个套餐不能下单")
        if body.provider in {"wechat", "alipay"}:
            return respond(request, _channel_order(settings, store, prof, plan, body.provider))
        if settings.wechat_pay_mode != "live":
            code_url = None
            pay_message = "微信支付未开通，订单保持待支付，不会发放权益"
        else:
            code_url = None
            pay_message = "微信支付配置不完整"
        doc = base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("ord"),
            plan_id=plan["id"],
            amount_fen=plan["amount_fen"],
            currency="CNY",
            provider="wechat_pay",
            status="pending",
            code_url=code_url,
            message=pay_message,
        )
        return respond(request, store.insert("payment_orders", doc))

    @router.get("/billing/orders/{order_id}")
    def get_order(order_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        return respond(request, require_doc(store, "payment_orders", order_id, prof["tenant"]["id"], "ORDER_NOT_FOUND", "订单不存在"))

    @router.post("/billing/orders/{order_id}/close")
    def close_order(order_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        order = require_doc(store, "payment_orders", order_id, prof["tenant"]["id"], "ORDER_NOT_FOUND", "订单不存在")
        if order["status"] == "pending":
            store.touch("payment_orders", order_id, {"status": "closed"})
        return respond(request, store.get("payment_orders", order_id, prof["tenant"]["id"]))

    @router.post("/billing/orders/{order_id}/query")
    def query_order(order_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        order = require_doc(store, "payment_orders", order_id, prof["tenant"]["id"], "ORDER_NOT_FOUND", "订单不存在")
        payment = store.get("payments", order["payment_id"], prof["tenant"]["id"]) if order.get("payment_id") else None
        granted = bool(payment and payment["status"] == "succeeded")
        return respond(
            request,
            {
                "status": "paid" if granted else order["status"],
                "granted": granted,
                "amount_fen": order["amount_fen"],
            },
        )

    @router.post("/billing/agency/commissions")
    def agency_commission(request: Request, body: LedgerIn, authorization: str | None = Header(default=None)):
        return _ledger(request, authorization, body, "commission_ledger", "agency_commission")

    @router.post("/billing/raas/commissions")
    def raas_commission(request: Request, body: LedgerIn, authorization: str | None = Header(default=None)):
        return _ledger(request, authorization, body, "raas_ledger", "raas_fee")

    def _ledger(request: Request, authorization: str | None, body: LedgerIn, collection: str, subject: str):
        settings, store, prof = ctx(request, authorization, write=True)
        doc = post_signed_ledger(
            store,
            settings,
            collection=collection,
            tenant_id=prof["tenant"]["id"],
            created_by=prof["user"]["id"],
            amount_fen=body.amount_fen,
            subject=subject,
            idempotency_key=body.idempotency_key,
            signature=body.signature,
            meta={"channel_account_id": body.channel_account_id, "note": body.note},
        )
        return respond(request, doc)

    @router.get("/billing/ledgers")
    def ledgers(request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        return respond(
            request,
            {
                "agency": store.query("commission_ledger", tenant_id=prof["tenant"]["id"], limit=50)["items"],
                "raas": store.query("raas_ledger", tenant_id=prof["tenant"]["id"], limit=50)["items"],
            },
        )

    @router.post("/dev/ledger-signature")
    def dev_sign(request: Request, body: SignIn, authorization: str | None = Header(default=None)):
        settings, _store, _prof = ctx(request, authorization, write=True)
        if not settings.demo_signing_helper:
            raise AppError("NOT_FOUND", "签名辅助未开启", 404)
        return respond(
            request,
            {"signature": sign_ledger(settings.ledger_hmac_secret, body.idempotency_key, body.amount_fen, body.subject)},
        )

    @router.post("/suppressions")
    def suppress(request: Request, body: SuppressionIn, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        doc = base_doc(prof["tenant"]["id"], prof["user"]["id"], id=new_id("sup"), email=body.email.strip().lower())
        return respond(request, store.insert("suppressions", doc))

    @router.post("/webhooks/alipay")
    async def alipay_webhook(request: Request):
        from urllib.parse import parse_qsl

        from app.modules.alipay_pay import accept_notification

        raw = (await request.body()).decode()
        params = {key: value for key, value in parse_qsl(raw, keep_blank_values=False)}
        return respond(request, accept_notification(request.app.state.store, request.app.state.settings, params))

    @router.post("/webhooks/wechat-pay")
    async def wechat_webhook(request: Request):
        from app.modules.wechat_pay import accept_wechat_notification

        raw = (await request.body()).decode()
        return respond(
            request,
            accept_wechat_notification(
                request.app.state.store,
                request.app.state.settings,
                body=raw,
                timestamp=request.headers.get("wechatpay-timestamp"),
                nonce=request.headers.get("wechatpay-nonce"),
                signature=request.headers.get("wechatpay-signature"),
                serial=request.headers.get("wechatpay-serial"),
            ),
        )

    @router.post("/webhooks/ses")
    def ses_webhook(request: Request, x_worker_token: str | None = Header(default=None)):
        settings = request.app.state.settings
        if settings.ses_mode != "live" and x_worker_token != settings.worker_token:
            raise AppError("FORBIDDEN", "SES 回调未验签", 401)
        if settings.ses_mode == "live":
            raise AppError("SES_NOT_READY", "正式 SES 验签尚未接通", 401)
        return respond(request, {"accepted": True, "mode": "mock"})

    @router.post("/chat/conversations")
    def create_conversation(request: Request, body: ChatIn, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        doc = base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("chat"),
            title=body.title or "业务助手",
            context_id=body.context_id,
        )
        return respond(request, store.insert("ai_conversations", doc))

    @router.get("/chat/conversations")
    def list_conversations(request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        return respond(request, store.query("ai_conversations", tenant_id=prof["tenant"]["id"], limit=20))

    @router.get("/chat/conversations/{conversation_id}")
    def get_conversation(conversation_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        return respond(
            request,
            require_doc(store, "ai_conversations", conversation_id, prof["tenant"]["id"], "CHAT_NOT_FOUND", "会话不存在"),
        )

    @router.delete("/chat/conversations/{conversation_id}")
    def delete_conversation(conversation_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization, write=True)
        require_doc(store, "ai_conversations", conversation_id, prof["tenant"]["id"], "CHAT_NOT_FOUND", "会话不存在")
        store.touch("ai_conversations", conversation_id, {"deleted_at": iso()})
        return respond(request, {"deleted": True})

    @router.get("/chat/conversations/{conversation_id}/messages")
    def list_messages(conversation_id: str, request: Request, authorization: str | None = Header(default=None)):
        _settings, store, prof = ctx(request, authorization)
        require_doc(store, "ai_conversations", conversation_id, prof["tenant"]["id"], "CHAT_NOT_FOUND", "会话不存在")
        return respond(
            request,
            store.query("ai_messages", tenant_id=prof["tenant"]["id"], filters={"conversation_id": conversation_id}, limit=100),
        )

    @router.post("/chat/conversations/{conversation_id}/messages")
    def post_message(conversation_id: str, request: Request, body: MessageIn, authorization: str | None = Header(default=None)):
        settings, store, prof = ctx(request, authorization, write=True)
        require_doc(store, "ai_conversations", conversation_id, prof["tenant"]["id"], "CHAT_NOT_FOUND", "会话不存在")
        user_message = base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("msg"),
            conversation_id=conversation_id,
            role="user",
            content=body.content[:4000],
        )
        store.insert("ai_messages", user_message)
        reply = _copilot_reply(store, prof["tenant"]["id"], settings)
        assistant = base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("msg"),
            conversation_id=conversation_id,
            role="assistant",
            content=reply,
            model="rules" if not settings.hunyuan_enabled else "hunyuan",
        )
        store.insert("ai_messages", assistant)
        return respond(request, {"user": user_message, "assistant": assistant})

    @router.get("/chat/runs/{conversation_id}/events")
    def chat_events(conversation_id: str, request: Request, authorization: str | None = Header(default=None)):
        settings, store, prof = ctx(request, authorization)
        require_doc(store, "ai_conversations", conversation_id, prof["tenant"]["id"], "CHAT_NOT_FOUND", "会话不存在")
        reply = _copilot_reply(store, prof["tenant"]["id"], settings)

        def stream():
            yield "event: start\ndata: {}\n\n"
            yield f"event: delta\ndata: {json.dumps({'text': reply}, ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return router


def _copilot_reply(store, tenant_id: str, settings) -> str:
    reports = store.query("analysis_reports", tenant_id=tenant_id, limit=1)["items"]
    if not reports:
        return "还没有完成的选品报告。可以先导入商品并开始分析。混元当前关闭，金额只会由规则引擎计算。"
    report = reports[0]
    metrics = report["metrics"]
    return (
        f"最近一份报告利润率 {metrics['net_margin']}，净利润 {metrics['net_profit_usd']} USD，"
        f"风险 {metrics['risk_level']}。规则版本 {metrics['rules_version']}。"
        f"混元{'开启' if settings.hunyuan_enabled else '关闭'}，我不会改这些数字。"
        "若要获客，请在报告页使用「一键获客」，发送前仍需人工批准。"
    )


def _apply_signal(store, tenant_id: str, lead: dict, kind: str) -> None:
    now = iso()
    messages = store.query("outreach_messages", tenant_id=tenant_id, filters={"lead_id": lead["id"]}, limit=20)["items"]
    latest = next((item for item in messages if item.get("status") == "delivered"), None)
    patch: dict = {}
    message_patch: dict = {}
    opened = lead.get("opened_at") or (latest or {}).get("opened_at") or now
    if kind == "open":
        patch["opened_at"] = opened
        message_patch["opened_at"] = opened
    elif kind in {"reply", "replied"}:
        patch.update({"replied_at": now, "status": "replied", "opened_at": opened})
        message_patch.update({"opened_at": opened, "replied_at": now})
    elif kind == "won":
        patch.update({"won_at": now, "status": "won", "replied_at": lead.get("replied_at") or now, "opened_at": opened})
        message_patch.update({"opened_at": opened, "replied_at": now})
    elif kind == "lost":
        patch["status"] = "lost"
    elif kind == "silent":
        patch["status"] = "silent"
    else:
        raise AppError("INVALID_SIGNAL", "无法识别的线索动作")
    if patch:
        store.touch("leads", lead["id"], patch)
    if message_patch:
        touch_delivery(store, tenant_id, lead["id"], message_patch)
    if latest and message_patch:
        store.touch("outreach_messages", latest["id"], message_patch)
    if kind == "open":
        emit(store, tenant_id, "campaign.opened", {"lead_id": lead["id"]}, lead.get("created_by") or "system")
    elif kind in {"reply", "replied"}:
        emit(store, tenant_id, "campaign.replied", {"lead_id": lead["id"]}, lead.get("created_by") or "system")
    elif kind == "won":
        record_win(store, tenant_id, lead.get("created_by") or "system", lead)
    if kind in {"reply", "replied", "won"}:
        recalls = store.query("recall_jobs", tenant_id=tenant_id, filters={"lead_id": lead["id"]}, limit=20)["items"]
        for row in recalls:
            if row.get("delivered_at") and not row.get("warmed_at"):
                store.touch("recall_jobs", row["id"], {"warmed_at": now})
                store.touch("leads", lead["id"], {"warmed_at": now})
