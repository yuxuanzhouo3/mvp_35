import csv
import io
from datetime import timedelta

from config.settings import Settings
from db.store import DocumentStore

from algorithm.feeds import prepare_market
from algorithm.lead_feeds import discover
from algorithm.product_pricer import PRODUCT_PRICER, compare_product
from algorithm.sources import DOMESTIC_SOURCE, OVERSEAS_SOURCE
from app.core.errors import AppError
from app.core.timeutil import iso, parse_iso, utcnow
from app.modules.events import emit
from app.services.common import (
    apply_market_change,
    base_doc,
    new_id,
    normalize_sku,
    product_from_body,
    quota_finish,
    quota_reserve,
)
from app.services.trade_route import market_fields
from app.services.profit import calculate


def enqueue(
    store: DocumentStore,
    tenant_id: str,
    created_by: str,
    job_type: str,
    payload: dict,
    job_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    job = base_doc(
        tenant_id,
        created_by,
        id=job_id or new_id("job"),
        idempotency_key=idempotency_key,
        job_type=job_type,
        status="queued",
        progress=0,
        steps=[],
        payload=payload,
        result=None,
        error=None,
        requested_at=iso(),
        started_at=None,
        finished_at=None,
    )
    return store.insert("jobs", job)


def execute_job(store: DocumentStore, settings: Settings, job_id: str) -> dict | None:
    claimed = _claim(store, job_id)
    if not claimed:
        return store.get("jobs", job_id)
    try:
        result = _run(store, settings, claimed)
    except Exception as exc:
        message = exc.message if isinstance(exc, AppError) else "任务执行失败"
        _fail(store, claimed, message)
        task_id = (claimed.get("payload") or {}).get("task_id")
        if task_id:
            store.touch("acquisition_tasks", task_id, {"status": "failed", "finished_at": iso()})
        if claimed["job_type"] in {"product_analysis", "lead_discovery", "campaign_send", "lifecycle_send"}:
            module = {
                "product_analysis": "analysis",
                "lead_discovery": "discovery",
                "campaign_send": "send",
                "lifecycle_send": "send",
            }[claimed["job_type"]]
            quota_finish(store, claimed["tenant_id"], module, claimed["id"], False)
        return store.get("jobs", job_id)
    _succeed(store, claimed, result)
    return store.get("jobs", job_id)


def _claim(store: DocumentStore, job_id: str) -> dict | None:
    def op(data: dict) -> dict | None:
        job = data["collections"].get("jobs", {}).get(job_id)
        if not job or job.get("status") != "queued":
            return None
        job["status"] = "running"
        job["started_at"] = iso()
        job["progress"] = 10
        job["updated_at"] = job["started_at"]
        return dict(job)

    return store.transaction(op)


def _succeed(store: DocumentStore, job: dict, result: dict) -> None:
    store.touch(
        "jobs",
        job["id"],
        {
            "status": "succeeded",
            "progress": 100,
            "result": result,
            "finished_at": iso(),
            "steps": result.get("steps") or job.get("steps") or [],
        },
    )


def _fail(store: DocumentStore, job: dict, message: str) -> None:
    store.touch(
        "jobs",
        job["id"],
        {"status": "failed", "progress": 100, "error": {"message": message}, "finished_at": iso()},
    )


def _run(store: DocumentStore, settings: Settings, job: dict) -> dict:
    kind = job["job_type"]
    if kind == "product_import":
        return _import(store, settings, job)
    if kind == "product_analysis":
        return _analysis(store, settings, job)
    if kind == "lead_discovery":
        return _discovery(store, settings, job)
    if kind == "campaign_send":
        return _send_campaign(store, job)
    if kind == "lifecycle_scan":
        return _scan(store, settings, job)
    if kind == "lifecycle_send":
        return _send_lifecycle(store, job)
    raise AppError("UNKNOWN_JOB", "未知任务类型")


def _import(store: DocumentStore, settings: Settings, job: dict) -> dict:
    reader = csv.DictReader(io.StringIO(job["payload"].get("csv") or ""))
    algorithm = (job.get("payload") or {}).get("algorithm")
    imported, failed, ids, errors, quotes = 0, 0, [], [], []
    for index, row in enumerate(reader, start=2):
        try:
            overlay = {key: job["payload"][key] for key in ("origin_country", "target_market", "route", "tax_regime") if job["payload"].get(key)}
            fields = product_from_body({**row, **overlay}, source="csv")
            existing = store.find_global(
                "products", tenant_id=job["tenant_id"], normalized_sku=fields["normalized_sku"]
            )
            if existing and not existing.get("deleted_at"):
                raise AppError("DUPLICATE_SKU", f"SKU {fields['normalized_sku']} 已存在")
            if algorithm == PRODUCT_PRICER:
                fields, overseas, feed = prepare_market(fields, settings)
                quote = compare_product(fields, settings.rules_version, overseas_quotes=overseas, feed=feed)
            else:
                quote = None
            doc = base_doc(job["tenant_id"], job["created_by"], id=new_id("prd"), **fields)
            store.insert("products", doc)
            ids.append(doc["id"])
            if quote is not None:
                quotes.append({"product_id": doc["id"], **quote})
            imported += 1
        except AppError as exc:
            failed += 1
            errors.append({"line": index, "message": exc.message})
    total = imported + failed
    emit(store, job["tenant_id"], "product.imported", {"imported": imported, "failed": failed}, job["created_by"])
    steps = [{"key": "parse", "status": "succeeded"}, {"key": "upsert", "status": "succeeded"}]
    result = {
        "imported": imported,
        "failed": failed,
        "total": total,
        "success_rate": None if total == 0 else round(imported / total, 4),
        "product_ids": ids,
        "errors": errors[:20],
        "steps": steps,
    }
    if algorithm == PRODUCT_PRICER:
        steps.append({"key": "price_compare", "status": "succeeded"})
        result["algorithm"] = PRODUCT_PRICER
        result["sources"] = {"domestic": DOMESTIC_SOURCE, "overseas": OVERSEAS_SOURCE}
        result["quotes"] = quotes
    return result


def _analysis(store: DocumentStore, settings: Settings, job: dict) -> dict:
    product = store.get("products", job["payload"]["product_id"], job["tenant_id"])
    if not product:
        raise AppError("PRODUCT_NOT_FOUND", "商品不存在")
    route_id = (job.get("payload") or {}).get("route")
    if route_id:
        apply_market_change(product, market_fields(route_id))
        store.put("products", product)
    metrics = calculate(product, settings.rules_version)
    if settings.hunyuan_enabled:
        metrics["explanation_model"] = "rules"
    report = base_doc(
        job["tenant_id"],
        job["created_by"],
        id=new_id("an"),
        product_id=product["id"],
        status="completed",
        metrics=metrics,
        rules_version=metrics["rules_version"],
        context_version=metrics["context_version"],
        market_snapshot={
            "origin_country": metrics["origin_country"],
            "target_market": metrics["target_market"],
            "route": metrics["route"],
            "incoterm": metrics["incoterm"],
            "tax_regime": metrics["tax_regime"],
            "fx_usd_cny": metrics["fx_usd_cny"],
        },
        net_margin=metrics["net_margin"],
        net_profit_usd=metrics["net_profit_usd"],
        fx_usd_cny=metrics["fx_usd_cny"],
        explanation=metrics["explanation"],
        explanation_model="rules",
        acquired_at=None,
        seed_analysis_id=None,
        requested_at=job["requested_at"],
        finished_at=iso(),
    )
    store.insert("analysis_reports", report)
    store.insert(
        "selection_reports",
        base_doc(
            job["tenant_id"],
            job["created_by"],
            id=report["id"],
            product_id=product["id"],
            route=metrics["route"],
            market=metrics["target_market"],
            profit_margin=metrics["net_margin"],
            tax=metrics["tax_usd"],
            time_cost={"transit_days_min": metrics["transit_days_min"], "transit_days_max": metrics["transit_days_max"]},
            risk=metrics["risk_level"],
            score=metrics["opportunity_score"],
            status="completed",
            rules_version=metrics["rules_version"],
            seed_ready=False,
            net_margin=metrics["net_margin"],
            net_profit_usd=metrics["net_profit_usd"],
            fx_usd_cny=metrics["fx_usd_cny"],
            metrics=metrics,
            market_snapshot=report["market_snapshot"],
            context_version=metrics["context_version"],
            shard_key=None,
            region=None,
            ai_model_version=None,
        ),
    )
    emit(store, job["tenant_id"], "selection.completed", {"report_id": report["id"]}, job["created_by"])
    emit(store, job["tenant_id"], "report.generated", {"report_id": report["id"]}, job["created_by"])
    quota_finish(store, job["tenant_id"], "analysis", job["id"], True)
    return {
        "analysis_id": report["id"],
        "steps": [
            {"key": "rules", "status": "succeeded"},
            {"key": "explain", "status": "succeeded", "model": "rules"},
        ],
    }


def _discovery(store: DocumentStore, settings: Settings, job: dict) -> dict:
    payload = job["payload"]
    rows, provider = discover(store, settings, payload, job["tenant_id"])
    inserted, updated, ids = 0, 0, []
    for row in rows:
        dedupe_key = f"{row['source_channel']}:{row['company'].strip().lower()}:{row['market']}"
        existing = None
        if row.get("external_id"):
            existing = store.find_global(
                "leads",
                tenant_id=job["tenant_id"],
                platform=row["platform"],
                external_id=row["external_id"],
            )
        if not existing:
            existing = store.find_global("leads", tenant_id=job["tenant_id"], dedupe_key=dedupe_key)
        if existing and not existing.get("deleted_at"):
            store.touch(
                "leads",
                existing["id"],
                {
                    "quality_score": row["quality_score"],
                    "email": row["email"],
                    "platform": row["platform"],
                    "external_id": row.get("external_id") or existing.get("external_id") or "",
                },
            )
            updated += 1
            ids.append(existing["id"])
            continue
        lead = base_doc(
            job["tenant_id"],
            job["created_by"],
            id=new_id("lead"),
            dedupe_key=dedupe_key,
            company=row["company"],
            contact_name=row["contact_name"],
            email=row["email"],
            market=row["market"],
            quality_score=row["quality_score"],
            qualified=row["quality_score"] >= settings.quality_threshold,
            source_channel=row["source_channel"],
            platform=row["platform"],
            seed_analysis_id=payload.get("seed_analysis_id"),
            status="new",
            exclude_from_ar=row["exclude_from_ar"],
            note=row["note"],
            external_id=row.get("external_id") or "",
            opened_at=None,
            replied_at=None,
            won_at=None,
            warmed_at=None,
        )
        store.insert("leads", lead)
        inserted += 1
        ids.append(lead["id"])
    if payload.get("task_id"):
        store.touch(
            "acquisition_tasks",
            payload["task_id"],
            {"status": "completed", "finished_at": iso()},
        )
    emit(
        store,
        job["tenant_id"],
        "lead.discovered",
        {"lead_ids": ids, "inserted": inserted},
        job["created_by"],
    )
    quota_finish(store, job["tenant_id"], "discovery", job["id"], True)
    return {
        "inserted": inserted,
        "updated": updated,
        "lead_ids": ids,
        "provider": provider,
        "finished_at": iso(),
        "steps": [{"key": "normalize", "status": "succeeded"}, {"key": "score", "status": "succeeded"}],
    }


def _audience(store: DocumentStore, tenant_id: str, lead_ids: list[str]) -> dict:
    suppressed = {
        item["email"]
        for item in store.query("suppressions", tenant_id=tenant_id, limit=500)["items"]
        if item.get("email")
    }
    prior_bounce = {
        item["lead_id"]
        for item in store.query("outreach_messages", tenant_id=tenant_id, limit=500)["items"]
        if item.get("status") == "bounced"
    }
    kept, excluded = [], {"suppressed": [], "no_email": [], "prior_bounce": []}
    for lead_id in lead_ids:
        lead = store.get("leads", lead_id, tenant_id)
        if not lead:
            continue
        email = lead.get("email") or ""
        if not email:
            excluded["no_email"].append(lead_id)
        elif email in suppressed:
            excluded["suppressed"].append(lead_id)
        elif lead_id in prior_bounce:
            excluded["prior_bounce"].append(lead_id)
        else:
            kept.append(lead_id)
    return {"lead_ids": kept, "excluded": excluded}


def _send_campaign(store: DocumentStore, job: dict) -> dict:
    campaign = store.get("campaigns", job["payload"]["campaign_id"], job["tenant_id"])
    if not campaign:
        raise AppError("CAMPAIGN_NOT_FOUND", "活动不存在")
    if campaign.get("status") not in {"approved", "sending"}:
        raise AppError("CAMPAIGN_NOT_APPROVED", "发送前需要人工批准")
    sent = _deliver(
        store,
        job,
        campaign["audience_snapshot"]["lead_ids"],
        purpose=campaign.get("purpose") or "acquisition",
        campaign_id=campaign["id"],
        lifecycle_job_id=None,
        copy=campaign.get("draft") or "",
    )
    store.touch("campaigns", campaign["id"], {"status": "sent", "sent_at": iso()})
    emit(store, job["tenant_id"], "campaign.delivered", {"campaign_id": campaign["id"], "sent": sent}, job["created_by"])
    quota_finish(store, job["tenant_id"], "send", job["id"], True)
    return {"sent": sent, "steps": [{"key": "ses_mock", "status": "succeeded"}]}


def _deliver(store, job, lead_ids, *, purpose, campaign_id, lifecycle_job_id, copy: str) -> int:
    count = 0
    for lead_id in lead_ids:
        lead = store.get("leads", lead_id, job["tenant_id"])
        if not lead or not lead.get("email"):
            continue
        email = lead["email"]
        if email.startswith("bounce."):
            status, delivered_at = "bounced", None
        elif email.startswith("complaint."):
            status, delivered_at = "complained", None
        else:
            status, delivered_at = "delivered", iso()
        message = base_doc(
            job["tenant_id"],
            job["created_by"],
            id=new_id("msg"),
            lead_id=lead_id,
            campaign_id=campaign_id,
            lifecycle_job_id=lifecycle_job_id,
            purpose=purpose,
            source_channel=lead.get("source_channel"),
            exclude_from_ar=bool(lead.get("exclude_from_ar")),
            email=email,
            body=copy,
            status=status,
            ses_message_id=f"ses_mock_{new_id('m')}",
            delivered_at=delivered_at,
            opened_at=None,
        )
        store.insert("outreach_messages", message)
        store.insert(
            "deliveries",
            base_doc(
                job["tenant_id"],
                job["created_by"],
                id=new_id("dlv"),
                campaign_id=campaign_id,
                lead_id=lead_id,
                channel=lead.get("source_channel") or "email",
                status=status,
                delivered_at=delivered_at,
                opened_at=None,
                replied_at=None,
            ),
        )
        if status == "delivered":
            store.touch("leads", lead_id, {"status": "contacted" if lead.get("status") == "new" else lead.get("status")})
        count += 1
    return count


def _scan(store: DocumentStore, settings: Settings, job: dict) -> dict:
    leads = store.query("leads", tenant_id=job["tenant_id"], limit=500)["items"]
    messages = store.query("outreach_messages", tenant_id=job["tenant_id"], limit=500)["items"]
    campaigns = store.query("campaigns", tenant_id=job["tenant_id"], limit=200)["items"]
    busy = set()
    for campaign in campaigns:
        if campaign.get("status") in {"draft", "pending_approval", "approved", "sending"}:
            busy.update(campaign.get("audience_snapshot", {}).get("lead_ids") or campaign.get("lead_ids") or [])
    delivered_leads = {item["lead_id"] for item in messages if item.get("status") == "delivered"}
    activation_open = {
        item["lead_id"]
        for item in store.query("activation_jobs", tenant_id=job["tenant_id"], limit=500)["items"]
        if item.get("status") in {"queued", "approved", "sent"}
    }
    recall_open = {
        item["lead_id"]
        for item in store.query("recall_jobs", tenant_id=job["tenant_id"], limit=500)["items"]
        if item.get("status") in {"queued", "approved", "sent"}
    }
    activated, recalled = [], []
    for lead in leads:
        if lead["id"] in busy:
            continue
        if (
            lead.get("status") == "new"
            and lead["id"] not in delivered_leads
            and lead.get("quality_score", 0) >= settings.quality_threshold
            and lead["id"] not in activation_open
            and lead.get("email")
        ):
            doc = base_doc(
                job["tenant_id"],
                job["created_by"],
                id=new_id("act"),
                lead_id=lead["id"],
                status="queued",
                reason="qualified_never_contacted",
                enqueued_at=iso(),
                draft=_copy(lead, "activation"),
                delivered_at=None,
            )
            store.insert("activation_jobs", doc)
            activated.append(doc["id"])
        if (
            lead.get("opened_at")
            and not lead.get("replied_at")
            and not lead.get("won_at")
            and lead["id"] not in recall_open
            and lead.get("email")
        ):
            doc = base_doc(
                job["tenant_id"],
                job["created_by"],
                id=new_id("rec"),
                lead_id=lead["id"],
                status="queued",
                reason="opened_without_reply",
                enqueued_at=iso(),
                triggered_at=iso(),
                draft=_copy(lead, "recall"),
                delivered_at=None,
                warmed_at=None,
            )
            store.insert("recall_jobs", doc)
            recalled.append(doc["id"])
    return {
        "activation_job_ids": activated,
        "recall_job_ids": recalled,
        "steps": [{"key": "rules", "status": "succeeded"}],
    }


def _copy(lead: dict, purpose: str) -> str:
    action = "冷客启动" if purpose == "activation" else "流失召回"
    return (
        f"{lead['contact_name']}，你好。这是一封待人工批准的{action}草稿，"
        f"对象是 {lead['company']}（{lead['market']}）。规则入队，文案未改动线索评分。"
    )


def _send_lifecycle(store: DocumentStore, job: dict) -> dict:
    payload = job["payload"]
    collection = "activation_jobs" if payload["kind"] == "activation" else "recall_jobs"
    row = store.get(collection, payload["lifecycle_id"], job["tenant_id"])
    if not row:
        raise AppError("LIFECYCLE_NOT_FOUND", "生命周期任务不存在")
    if row.get("status") != "approved":
        raise AppError("LIFECYCLE_NOT_APPROVED", "发送前需要人工批准")
    sent = _deliver(
        store,
        job,
        [row["lead_id"]],
        purpose=payload["kind"],
        campaign_id=None,
        lifecycle_job_id=row["id"],
        copy=row.get("draft") or "",
    )
    messages = store.query("outreach_messages", tenant_id=job["tenant_id"], filters={"lifecycle_job_id": row["id"]}, limit=20)
    delivered_at = None
    for item in messages["items"]:
        if item.get("delivered_at"):
            delivered_at = item["delivered_at"]
    store.touch(collection, row["id"], {"status": "sent", "delivered_at": delivered_at})
    quota_finish(store, job["tenant_id"], "send", job["id"], True)
    return {"sent": sent, "delivered_at": delivered_at, "steps": [{"key": "ses_mock", "status": "succeeded"}]}


def reclaim_stale(store: DocumentStore, minutes: int = 15) -> int:
    cutoff = utcnow() - timedelta(minutes=minutes)
    jobs = store.query("jobs", limit=200, filters={"status": "running"})["items"]
    count = 0
    for job in jobs:
        started = job.get("started_at")
        if started and parse_iso(started) < cutoff:
            store.touch("jobs", job["id"], {"status": "queued"})
            count += 1
    return count
