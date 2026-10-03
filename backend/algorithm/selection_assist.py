"""Good-selection ranking for the domestic catalog.

Each row is scored with the rules engine. A row is picked when net margin is at
least 15% and risk is not high. Profit, tax, transit time, and risk travel with
the rank so the report dimensions stay on the same snapshot.
"""

from decimal import Decimal

from app.core.errors import AppError
from app.services.common import search_catalog
from app.services.profit import RULES_VERSION, calculate

from algorithm.sources import CATALOG_SOURCE

SELECTION_ASSIST = "selection-assist"
TARGET_MARGIN = Decimal("0.15")


def _report(metrics: dict) -> dict:
    return {
        "profit": {"net_profit_usd": metrics["net_profit_usd"], "net_margin": metrics["net_margin"]},
        "tax": {
            "tax_usd": metrics["tax_usd"],
            "duty_rate": metrics["duty_rate"],
            "vat_rate": metrics["vat_rate"],
            "tax_regime": metrics["tax_regime"],
        },
        "time": {"transit_days_min": metrics["transit_days_min"], "transit_days_max": metrics["transit_days_max"]},
        "risk": {"risk_level": metrics["risk_level"], "opportunity_score": metrics["opportunity_score"]},
    }


def rank_items(items: list[dict], rules_version: str = RULES_VERSION) -> dict:
    ranked = []
    for item in items:
        metrics = calculate(item, rules_version)
        margin = Decimal(metrics["net_margin"])
        pick = margin >= TARGET_MARGIN and metrics["risk_level"] != "高"
        if pick:
            reason = f"利润率 {metrics['net_margin']} 达到 15% 推荐线，风险{metrics['risk_level']}，机会分 {metrics['opportunity_score']}。"
        else:
            reason = f"利润率 {metrics['net_margin']} 或风险{metrics['risk_level']}未过线，暂不优先。"
        ranked.append(
            {
                **item,
                "selection": {
                    "pick": pick,
                    "score": metrics["opportunity_score"],
                    "net_margin": metrics["net_margin"],
                    "net_profit_usd": metrics["net_profit_usd"],
                    "risk_level": metrics["risk_level"],
                    "reason": reason,
                    "report": _report(metrics),
                },
            }
        )
    ranked.sort(
        key=lambda row: (
            1 if row["selection"]["pick"] else 0,
            row["selection"]["score"],
            Decimal(row["selection"]["net_margin"]),
            row.get("sku") or "",
        ),
        reverse=True,
    )
    return {
        "algorithm": SELECTION_ASSIST,
        "rules_version": rules_version,
        "sources": {"catalog": CATALOG_SOURCE},
        "picked": sum(1 for row in ranked if row["selection"]["pick"]),
        "items": ranked,
    }


def rank_query(query: str, rules_version: str = RULES_VERSION, target_market: str | None = None) -> dict:
    items = search_catalog(query)
    if target_market:
        regime = {"US": "cn_us", "HK": "cn_hk", "AU": "cn_au", "CN": "domestic"}.get(target_market, "cn_us")
        items = [
            {**item, "target_market": target_market, "tax_regime": regime, "route": f"CN-{target_market}"}
            for item in items
        ]
    return rank_items(items, rules_version)


def catalog_payload(query: str, algorithm: str | None = None, rules_version: str = RULES_VERSION) -> dict:
    if algorithm and algorithm != SELECTION_ASSIST:
        raise AppError(
            "UNKNOWN_ALGORITHM",
            "帮我选品只接受选品算法 selection-assist",
            details={"algorithm": algorithm, "expected": SELECTION_ASSIST},
        )
    if algorithm == SELECTION_ASSIST:
        return rank_query(query, rules_version)
    return {"items": search_catalog(query)}
