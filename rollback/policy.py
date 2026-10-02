"""Triggers from project.md §8.7. Any hit selects the full return to the CloudBase baseline."""

from rollback.baseline import BASELINE_VERSION


def decide(signals: dict) -> str:
    if signals.get("schema_failed") or signals.get("ledger_mismatch") or signals.get("kpi_gap"):
        return "storage"
    if signals.get("payment_failure_rate", 0) > 0.005:
        return "payment"
    if signals.get("margin_drift", 0) > 0.05 or signals.get("ai_compliance"):
        return "ai"
    if signals.get("event_backlog") or signals.get("duplicate_post"):
        return "event"
    error_rate = signals.get("error_rate", 0)
    p95_ratio = signals.get("p95_ratio", 1)
    delivery = signals.get("delivery_rate", 1)
    if (
        error_rate > 0.01
        or p95_ratio > 2
        or delivery < 0.95
        or signals.get("bounce_rate", 0) > 0.015
        or signals.get("complaint_rate", 0) > 0.001
    ):
        return "service"
    if signals.get("cost_over_budget") or signals.get("cpu", 0) > 0.8:
        return "scale"
    return "none"


def plan_for(action: str) -> dict:
    if action == "none":
        return {"action": "none", "target": None, "steps": []}
    return {
        "action": action,
        "target": BASELINE_VERSION,
        "steps": ["config", "traffic", "migrate_down", "pitr_if_needed", "replay", "ai_rules", "verify"],
    }
