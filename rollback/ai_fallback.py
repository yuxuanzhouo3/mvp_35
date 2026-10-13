"""Drop model prose when it drifts from the rules engine. Amounts always come from rules."""

import sys
from decimal import Decimal
from pathlib import Path

from rollback.store import collections, transaction

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.profit import calculate  # noqa: E402

DRIFT_LIMIT = Decimal("0.05")


def _product_for(data: dict, report: dict) -> dict | None:
    product_id = report.get("product_id")
    products = collections(data).get("products") or {}
    if product_id and product_id in products:
        return products[product_id]
    snapshot = report.get("inputs")
    if isinstance(snapshot, dict):
        return snapshot
    return None


def _needs_rules(report: dict, metrics: dict) -> bool:
    if report.get("explanation_model") not in {None, "rules"}:
        return True
    model_margin = report.get("model_margin")
    if model_margin is None:
        return False
    return abs(Decimal(str(model_margin)) - Decimal(metrics["net_margin"])) > DRIFT_LIMIT


def degrade_store(path) -> dict:
    changed = []

    def op(data: dict) -> dict:
        reports = collections(data).get("analysis_reports") or collections(data).get("selection_reports") or {}
        for doc in reports.values():
            product = _product_for(data, doc)
            if not product:
                continue
            metrics = calculate(product)
            if not _needs_rules(doc, metrics):
                doc["explanation_model"] = "rules"
                continue
            doc["metrics"] = metrics
            doc["net_margin"] = metrics["net_margin"]
            doc["net_profit_usd"] = metrics["net_profit_usd"]
            doc["explanation"] = metrics["explanation"]
            doc["explanation_model"] = "rules"
            doc["rules_version"] = metrics["rules_version"]
            doc.pop("model_margin", None)
            changed.append(doc["id"])
        meta = data.setdefault("meta", {})
        meta["ai_route"] = "rules"
        meta["prompt_version"] = "rules-v1"
        return {"degraded": changed}

    return transaction(path, op)
