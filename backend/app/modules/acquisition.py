from app.core.errors import AppError
from app.core.timeutil import iso
from app.modules.events import emit
from app.modules.providers import provider_for
from app.modules.state import transition
from app.services.common import base_doc, new_id, require_doc


def rule_score(quality_score: int, threshold: int, status: str, model_suggestion: int | None = None) -> dict:
    del model_suggestion
    qualified = quality_score >= threshold
    new_status = status
    if status in {"new", "scored"}:
        new_status = "qualified" if qualified else "scored"
    return {
        "quality_score": quality_score,
        "qualified": qualified,
        "status": new_status,
        "scored_by": "rules",
        "model_score": None,
    }


def score_lead(store, settings, prof: dict, lead_id: str) -> dict:
    lead = require_doc(store, "leads", lead_id, prof["tenant"]["id"], "LEAD_NOT_FOUND", "线索不存在")
    scored = rule_score(int(lead.get("quality_score") or 0), settings.quality_threshold, lead.get("status") or "new")
    store.touch(
        "leads",
        lead_id,
        {"qualified": scored["qualified"], "status": scored["status"], "scored_by": "rules", "model_score": None},
    )
    if scored["qualified"]:
        emit(store, prof["tenant"]["id"], "lead.qualified", {"lead_id": lead_id, "score": scored["quality_score"]}, prof["user"]["id"])
    return store.get("leads", lead_id, prof["tenant"]["id"]) | scored


def open_acquisition_task(store, prof: dict, *, channel: str, platform: str | None, query: str, seed_analysis_id: str | None) -> dict:
    provider_for(channel)
    tenant_id = prof["tenant"]["id"]
    if seed_analysis_id:
        require_doc(store, "analysis_reports", seed_analysis_id, tenant_id, "ANALYSIS_NOT_FOUND", "报告不存在")
    task = base_doc(
        tenant_id,
        prof["user"]["id"],
        id=new_id("task"),
        report_id=seed_analysis_id,
        channel=channel,
        status="created",
        started_at=None,
        finished_at=None,
    )
    store.insert("acquisition_tasks", task)
    running = transition("Task", "created", "running")
    store.touch("acquisition_tasks", task["id"], {"status": running, "started_at": iso()})
    return store.get("acquisition_tasks", task["id"], tenant_id)


def enqueue_recall(store, prof: dict, *, lead_id: str, trigger: str) -> dict:
    if trigger not in {"cold_start", "churn", "opened_without_reply"}:
        raise AppError("INVALID_TRIGGER", "无法识别的召回触发")
    tenant_id = prof["tenant"]["id"]
    lead = require_doc(store, "leads", lead_id, tenant_id, "LEAD_NOT_FOUND", "线索不存在")
    if lead.get("status") == "won":
        raise AppError("LEAD_WON", "已成交的线索不进入召回", 409)
    existing = store.find_global("recalls", tenant_id=tenant_id, lead_id=lead_id, trigger=trigger)
    if existing and existing.get("status") in {"triggered", "queued", "delivered"}:
        return existing
    recall = base_doc(
        tenant_id,
        prof["user"]["id"],
        id=new_id("recall"),
        lead_id=lead_id,
        trigger=trigger,
        recall_trigger=trigger,
        status="triggered",
        delivered_at=None,
        recovered_at=None,
    )
    store.insert("recalls", recall)
    queued = transition("Recall", "triggered", "queued")
    store.touch("recalls", recall["id"], {"status": queued})
    collection = "activation_jobs" if trigger == "cold_start" else "recall_jobs"
    purpose = "activation" if trigger == "cold_start" else "recall"
    store.insert(
        collection,
        base_doc(
            tenant_id,
            prof["user"]["id"],
            id=recall["id"],
            lead_id=lead_id,
            status="queued",
            reason=trigger,
            enqueued_at=iso(),
            triggered_at=iso(),
            draft=_copy(lead, purpose),
            delivered_at=None,
            warmed_at=None,
        ),
    )
    emit(store, tenant_id, "recall.triggered", {"recall_id": recall["id"], "lead_id": lead_id, "trigger": trigger}, prof["user"]["id"])
    return store.get("recalls", recall["id"], tenant_id)


def _copy(lead: dict, purpose: str) -> str:
    action = "冷客启动" if purpose == "activation" else "流失召回"
    return (
        f"{lead.get('contact_name') or '你好'}，这是一封待人工批准的{action}草稿，"
        f"对象是 {lead.get('company')}（{lead.get('market')}）。规则入队，文案未改动线索评分。"
    )


def record_win(store, tenant_id: str, user_id: str, lead: dict) -> dict | None:
    existing = store.find_global("deals", tenant_id=tenant_id, lead_id=lead["id"])
    if existing:
        return existing
    doc = base_doc(
        tenant_id,
        user_id,
        id=new_id("deal"),
        lead_id=lead["id"],
        amount="0.00",
        currency="USD",
        status="won",
        won_at=iso(),
    )
    store.insert("deals", doc)
    emit(store, tenant_id, "deal.won", {"deal_id": doc["id"], "lead_id": lead["id"]}, user_id)
    return doc


def touch_delivery(store, tenant_id: str, lead_id: str, patch: dict) -> None:
    rows = store.query("deliveries", tenant_id=tenant_id, filters={"lead_id": lead_id}, limit=20)["items"]
    if rows:
        store.touch("deliveries", rows[0]["id"], patch)
