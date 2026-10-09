import json
from decimal import Decimal
from pathlib import Path


def load_s4() -> dict:
    path = Path(__file__).resolve().parents[2] / "config" / "s4-v1.0.0.json"
    return json.loads(path.read_text())


def rollback_signal(
    *,
    error_rate: float | None = None,
    p95_ratio: float | None = None,
    payment_failure_rate: float | None = None,
    delivery_rate: float | None = None,
    bounce_rate: float | None = None,
    complaint_rate: float | None = None,
) -> str | None:
    limits = load_s4()["rollback"]
    if error_rate is not None and error_rate > limits["error_rate"]:
        return "s2_error_rate"
    if p95_ratio is not None and p95_ratio > limits["p95_ratio"]:
        return "s2_latency"
    if payment_failure_rate is not None and payment_failure_rate > limits["payment_failure_rate"]:
        return "payment"
    if delivery_rate is not None and delivery_rate < limits["delivery_rate"]:
        return "delivery"
    if bounce_rate is not None and bounce_rate > limits["bounce_rate"]:
        return "bounce"
    if complaint_rate is not None and complaint_rate > limits["complaint_rate"]:
        return "complaint"
    return None


def margin_drift_points(rules_margin: Decimal, model_margin: Decimal) -> Decimal:
    return abs(rules_margin - model_margin) * Decimal(100)


def needs_rule_fallback(rules_margin: Decimal, model_margin: Decimal) -> bool:
    return margin_drift_points(rules_margin, model_margin) > Decimal(5)
