import time
from decimal import Decimal

from app.modules.events import emit
from app.modules.scale import needs_rule_fallback
from app.services.common import base_doc, new_id


def _record_call(store, prof: dict, settings, *, model: str, status: str, prompt: str, completion: str, started: float) -> dict:
    latency_ms = int((time.perf_counter() - started) * 1000)
    doc = base_doc(
        prof["tenant"]["id"],
        prof["user"]["id"],
        id=new_id("aic"),
        model=model,
        prompt_version=settings.prompt_version,
        prompt_tokens=max(1, len(prompt) // 4),
        completion_tokens=max(1, len(completion) // 4),
        latency_ms=latency_ms,
        status=status,
        ai_model_version=model,
    )
    store.insert("ai_calls", doc)
    emit(
        store,
        prof["tenant"]["id"],
        "ai.called",
        {"ai_call_id": doc["id"], "model": model, "status": status},
        prof["user"]["id"],
    )
    return doc


def chat(store, settings, prof: dict, content: str, context_id: str | None) -> dict:
    started = time.perf_counter()
    reports = store.query("analysis_reports", tenant_id=prof["tenant"]["id"], limit=1)["items"]
    if context_id:
        chosen = store.get("analysis_reports", context_id, prof["tenant"]["id"])
        if chosen:
            reports = [chosen]
    if not reports:
        text = "还没有完成的选品报告。可以先导入商品并开始分析。金额只会由规则引擎计算。"
    else:
        metrics = reports[0]["metrics"]
        text = (
            f"规则版本 {metrics['rules_version']}。利润率 {metrics['net_margin']}，"
            f"净利润 {metrics['net_profit_usd']} USD，风险 {metrics['risk_level']}。"
            "这些问题里的金额要求已被忽略，模型不能改利润、评分或是否流失。"
        )
    model = "rules"
    status = "succeeded"
    if settings.hunyuan_enabled and not settings.hunyuan_api_key:
        model = "rules"
        status = "degraded"
        text = f"{text} 混元未配置，已降级到规则说明。"
    elif settings.hunyuan_enabled:
        model = "hunyuan"
    call = _record_call(store, prof, settings, model=model, status=status, prompt=content, completion=text, started=started)
    return {"reply": text, "model": model, "status": status, "ai_call_id": call["id"], "numbers_locked": True}


def contract_stub(store, settings, prof: dict, kind: str, text: str) -> dict:
    started = time.perf_counter()
    call = _record_call(
        store,
        prof,
        settings,
        model="rules",
        status="placeholder",
        prompt=text or kind,
        completion="",
        started=started,
    )
    return {"mode": "contract", "kind": kind, "enabled": False, "applied_to_money": False, "ai_call_id": call["id"], "items": []}


def predict_lead(store, settings, prof: dict, lead_id: str) -> dict:
    from app.services.common import require_doc

    lead = require_doc(store, "leads", lead_id, prof["tenant"]["id"], "LEAD_NOT_FOUND", "线索不存在")
    started = time.perf_counter()
    qualified = int(lead.get("quality_score") or 0) >= settings.quality_threshold
    text = "qualified" if qualified else "unqualified"
    call = _record_call(store, prof, settings, model="rules", status="succeeded", prompt=lead_id, completion=text, started=started)
    return {
        "lead_id": lead_id,
        "qualified": qualified,
        "quality_score": lead.get("quality_score"),
        "scored_by": "rules",
        "model_score": None,
        "applied_to_money": False,
        "ai_call_id": call["id"],
    }


def guard_margin(rules_margin: str, model_margin: str | None) -> bool:
    if model_margin is None:
        return False
    return needs_rule_fallback(Decimal(rules_margin), Decimal(model_margin))
