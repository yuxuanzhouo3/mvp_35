from app.core.errors import AppError
from app.core.timeutil import iso
from app.modules.events import emit
from app.services.common import require_doc


def present_report(store, tenant_id: str, report: dict) -> dict:
    product = store.get("products", report["product_id"], tenant_id)
    metrics = report.get("metrics") or {}
    snapshot = report.get("market_snapshot") or {}
    view = dict(report)
    view["stale"] = bool(product and product.get("context_version") != report.get("context_version"))
    view["seed_analysis_id"] = report["id"] if report.get("acquired_at") else None
    view["numbers_locked"] = True
    view["market"] = snapshot.get("target_market") or metrics.get("target_market")
    view["route"] = snapshot.get("route") or metrics.get("route")
    view["profit_margin"] = report.get("net_margin") or metrics.get("net_margin")
    view["tax"] = metrics.get("tax_usd")
    view["time_cost"] = {
        "transit_days_min": metrics.get("transit_days_min"),
        "transit_days_max": metrics.get("transit_days_max"),
    }
    view["risk"] = metrics.get("risk_level")
    view["score"] = metrics.get("opportunity_score")
    view["rules_version"] = report.get("rules_version") or metrics.get("rules_version")
    view["seed_ready"] = bool(report.get("acquired_at"))
    if report.get("acquired_at"):
        view["status"] = "acquired"
    return view


def mark_acquired(store, tenant_id: str, user_id: str, analysis_id: str) -> dict:
    report = require_doc(store, "analysis_reports", analysis_id, tenant_id, "ANALYSIS_NOT_FOUND", "报告不存在")
    product = store.get("products", report["product_id"], tenant_id)
    if product and product.get("context_version") != report.get("context_version"):
        raise AppError("ANALYSIS_STALE", "市场或成本已变更，请重新分析后再获客", 409)
    if not report.get("acquired_at"):
        now = iso()
        store.touch(
            "analysis_reports",
            analysis_id,
            {"acquired_at": now, "seed_analysis_id": analysis_id, "status": "acquired"},
        )
        if store.get("selection_reports", analysis_id, tenant_id):
            store.touch(
                "selection_reports",
                analysis_id,
                {"seed_ready": True, "status": "acquired", "seed_analysis_id": analysis_id},
            )
        emit(
            store,
            tenant_id,
            "acquisition.started",
            {"seed_analysis_id": analysis_id, "report_id": analysis_id},
            user_id,
        )
    return {"seed_analysis_id": analysis_id, "href": f"/workspace/acquire?seed_analysis_id={analysis_id}"}
