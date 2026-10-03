"""Domestic and overseas price compare.

Listed price R is checked against CN shelf quotes and the target-market shelf quotes.
The 15% floor uses the same profit identity as the selection report:

    N/R >= 0.15
    N = R - C - F - T
    F = R * (platform_fee_rate + payment_fee_rate)
    T = (purchase + international) * duty_rate + R * vat_rate
"""

import csv
import io
from decimal import Decimal

from app.core.errors import AppError
from app.services.common import product_from_body
from app.services.profit import (
    PAYMENT_FEE,
    PLATFORM_FEE,
    RULES_VERSION,
    TAX,
    calculate,
    money,
    parse_decimal,
)

from algorithm.feeds import prepare_market
from algorithm.sources import DOMESTIC_QUOTES, DOMESTIC_SOURCE, OVERSEAS_QUOTES, OVERSEAS_SOURCE, match_quotes

PRODUCT_PRICER = "product-pricer"
TARGET_MARGIN = Decimal("0.15")
BAND = Decimal("0.05")


def assert_product_pricer(algorithm: str | None) -> None:
    if algorithm and algorithm != PRODUCT_PRICER:
        raise AppError(
            "UNKNOWN_ALGORITHM",
            "CSV 导入只接受定价算法 product-pricer",
            details={"algorithm": algorithm, "expected": PRODUCT_PRICER},
        )


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _floor_price(product: dict) -> Decimal:
    market = product.get("target_market") or "US"
    regime = product.get("tax_regime") or "cn_us"
    if regime not in TAX:
        raise AppError("UNKNOWN_TAX_REGIME", "不支持的税务口径", details={"tax_regime": regime})
    fx = parse_decimal(product.get("fx_usd_cny") or "7.20", "fx_usd_cny")
    purchase = parse_decimal(product.get("cost_cny") or "0", "cost_cny") / fx
    packaging = parse_decimal(product.get("packaging_cny") or "0", "packaging_cny") / fx
    domestic = parse_decimal(product.get("domestic_freight_cny") or "0", "domestic_freight_cny") / fx
    international = parse_decimal(product.get("international_freight_usd") or "0", "international_freight_usd")
    landed = purchase + packaging + domestic + international
    fee_rate = PLATFORM_FEE.get(market, Decimal("0.15")) + PAYMENT_FEE
    duty_rate = TAX[regime]["duty_rate"]
    vat_rate = TAX[regime]["vat_rate"]
    fixed_tax = (purchase + international) * duty_rate
    denominator = Decimal("1") - fee_rate - vat_rate - TARGET_MARGIN
    if denominator <= 0:
        raise AppError("INVALID_AMOUNT", "当前费率下无法算出 15% 利润线")
    return (landed + fixed_tax) / denominator


def _side(samples: list[dict], *, fx: Decimal, to_usd: bool) -> dict:
    prices = [parse_decimal(row["shelf_price"], "shelf_price") for row in samples]
    if not prices:
        return {"median": None, "usd": None, "count": 0, "samples": []}
    median = _median(prices)
    usd = median / fx if to_usd else median
    return {
        "median": money(median),
        "usd": money(usd),
        "count": len(samples),
        "samples": samples[:8],
    }


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


def _position(listed: Decimal, overseas_median: Decimal | None) -> str:
    if overseas_median is None:
        return "no_overseas_comp"
    if listed < overseas_median * (Decimal("1") - BAND):
        return "below_market"
    if listed > overseas_median * (Decimal("1") + BAND):
        return "above_market"
    return "in_band"


def compare_product(
    product: dict,
    rules_version: str = RULES_VERSION,
    *,
    overseas_quotes: list[dict] | None = None,
    feed: dict | None = None,
) -> dict:
    metrics = calculate(product, rules_version)
    fx = parse_decimal(metrics["fx_usd_cny"], "fx_usd_cny")
    listed = parse_decimal(metrics["target_price_usd"], "target_price_usd")
    market = metrics["target_market"]
    domestic_samples = match_quotes(DOMESTIC_QUOTES, product, market="CN")
    overseas_samples = overseas_quotes if overseas_quotes is not None else match_quotes(OVERSEAS_QUOTES, product, market=market)
    domestic = _side(domestic_samples, fx=fx, to_usd=True)
    overseas = _side(overseas_samples, fx=fx, to_usd=False)
    floor = _floor_price(product)
    overseas_median = parse_decimal(overseas["usd"], "overseas") if overseas["usd"] else None
    if overseas_median is None:
        recommended = listed if listed >= floor else floor
        advice = "没有匹配的海外报价。建议售价不低于 15% 利润线。"
    elif overseas_median >= floor:
        recommended = overseas_median
        advice = "建议对齐目标市场中位价，该价格仍在 15% 利润线之上。"
    else:
        recommended = floor
        advice = "目标市场中位价低于 15% 利润线，建议售价抬到利润线。"
    if listed < floor:
        advice = f"当前售价低于 15% 利润线。{advice}"
    domestic_usd = parse_decimal(domestic["usd"], "domestic") if domestic["usd"] else None
    return {
        "algorithm": PRODUCT_PRICER,
        "rules_version": metrics["rules_version"],
        "sku": product.get("sku") or product.get("normalized_sku") or "",
        "name": product.get("name") or "",
        "listed_price_usd": money(listed),
        "floor_price_usd": money(floor),
        "recommended_price_usd": money(recommended),
        "position": _position(listed, overseas_median),
        "spread_vs_domestic_usd": None if domestic_usd is None else money(listed - domestic_usd),
        "spread_vs_overseas_usd": None if overseas_median is None else money(listed - overseas_median),
        "domestic": {"market": "CN", "currency": "CNY", "source": DOMESTIC_SOURCE, **domestic},
        "overseas": {"market": market, "currency": "USD", "source": OVERSEAS_SOURCE, **overseas},
        "report": _report(metrics),
        "advice": advice,
        "market_feed": feed
        or {
            "strategy": "competitor-median-with-cost-plus-floor",
            "fx": {"provider": "product", "rate": metrics["fx_usd_cny"], "used": False},
            "offers": {"provider": "local-book", "count": 0},
        },
    }


def compare_csv(csv_text: str, rules_version: str = RULES_VERSION, settings=None) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text or ""))
    items = []
    errors = []
    for index, row in enumerate(reader, start=2):
        try:
            fields = product_from_body(row, source="csv")
            fields, overseas, feed = prepare_market(fields, settings) if settings is not None else (fields, None, None)
            items.append(compare_product(fields, rules_version, overseas_quotes=overseas, feed=feed))
        except AppError as exc:
            errors.append({"line": index, "message": exc.message})
    return {
        "algorithm": PRODUCT_PRICER,
        "rules_version": rules_version,
        "sources": {"domestic": DOMESTIC_SOURCE, "overseas": OVERSEAS_SOURCE},
        "items": items,
        "errors": errors[:20],
    }
