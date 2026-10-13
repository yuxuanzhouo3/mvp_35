from decimal import Decimal, ROUND_HALF_UP

from app.core.errors import AppError

MONEY = Decimal("0.01")
RATE = Decimal("0.0001")
RULES_VERSION = "pg-rules-1.0"

TAX = {
    "cn_us": {"duty_rate": Decimal("0.075"), "vat_rate": Decimal("0")},
    "cn_hk": {"duty_rate": Decimal("0"), "vat_rate": Decimal("0")},
    "cn_au": {"duty_rate": Decimal("0.05"), "vat_rate": Decimal("0.10")},
    "domestic": {"duty_rate": Decimal("0"), "vat_rate": Decimal("0.13")},
}
PLATFORM_FEE = {
    "US": Decimal("0.15"),
    "HK": Decimal("0.08"),
    "AU": Decimal("0.12"),
    "CN": Decimal("0.05"),
}
PAYMENT_FEE = Decimal("0.029")
TRANSIT_DAYS = {
    "US": (12, 20),
    "HK": (2, 4),
    "AU": (14, 22),
    "CN": (2, 5),
}
MARKET_DEFAULTS = {
    "origin_country": "CN",
    "target_market": "US",
    "route": "CN-US",
    "incoterm": "DDP",
    "tax_regime": "cn_us",
    "cost_currency": "CNY",
    "price_currency": "USD",
    "fx_usd_cny": "7.20",
}


def money(value: Decimal) -> str:
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def rate(value: Decimal) -> str:
    return str(value.quantize(RATE, rounding=ROUND_HALF_UP))


def parse_decimal(value: str, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise AppError("INVALID_AMOUNT", f"{field} 不是有效金额", details={"field": field}) from exc
    if parsed < 0:
        raise AppError("INVALID_AMOUNT", f"{field} 不能为负", details={"field": field})
    return parsed


def explain(metrics: dict) -> str:
    margin = Decimal(metrics["net_margin"])
    advice = "利润率达到 15% 推荐线，可以进入获客。" if margin >= Decimal("0.15") else "利润率低于 15% 推荐线，建议先复核成本或售价后再获客。"
    return (
        f"规则版本 {metrics['rules_version']}。"
        f"售价 R={metrics['target_price_usd']} USD，"
        f"成本 C={metrics['landed_cost_usd']} USD"
        f"（采购 {metrics['purchase_usd']}+包装 {metrics['packaging_usd']}+国内段 {metrics['domestic_usd']}+国际段 {metrics['international_usd']}），"
        f"渠道费 F={metrics['channel_fee_usd']} USD，税费 T={metrics['tax_usd']} USD，"
        f"净利润 N={metrics['net_profit_usd']} USD，利润率 {metrics['net_margin']}。"
        f"金额只由规则引擎计算。{advice}"
    )


def calculate(product: dict, rules_version: str = RULES_VERSION) -> dict:
    market = product.get("target_market") or "US"
    regime = product.get("tax_regime") or "cn_us"
    if regime not in TAX:
        raise AppError("UNKNOWN_TAX_REGIME", "不支持的税务口径", details={"tax_regime": regime})
    fx = parse_decimal(product.get("fx_usd_cny") or "7.20", "fx_usd_cny")
    if fx <= 0:
        raise AppError("INVALID_AMOUNT", "汇率必须大于 0", details={"field": "fx_usd_cny"})
    price = parse_decimal(product.get("target_price_usd") or "0", "target_price_usd")
    if price <= 0:
        raise AppError("INVALID_AMOUNT", "售价必须大于 0", details={"field": "target_price_usd"})

    purchase = parse_decimal(product.get("cost_cny") or "0", "cost_cny") / fx
    packaging = parse_decimal(product.get("packaging_cny") or "0", "packaging_cny") / fx
    domestic = parse_decimal(product.get("domestic_freight_cny") or "0", "domestic_freight_cny") / fx
    international = parse_decimal(product.get("international_freight_usd") or "0", "international_freight_usd")
    landed = purchase + packaging + domestic + international
    platform = PLATFORM_FEE.get(market, Decimal("0.15"))
    fee = price * (platform + PAYMENT_FEE)
    duty_rate = TAX[regime]["duty_rate"]
    vat_rate = TAX[regime]["vat_rate"]
    tax = (purchase + international) * duty_rate + price * vat_rate
    profit = price - landed - fee - tax
    margin = profit / price
    low, high = TRANSIT_DAYS.get(market, (7, 21))
    if margin < Decimal("0.05") or international / price > Decimal("0.35"):
        risk = "高"
    elif margin < Decimal("0.15"):
        risk = "中"
    else:
        risk = "低"
    opportunity = max(0, min(100, int((margin * Decimal(160)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))))
    if risk == "高":
        opportunity = max(0, opportunity - 15)

    metrics = {
        "target_price_usd": money(price),
        "purchase_usd": money(purchase),
        "packaging_usd": money(packaging),
        "domestic_usd": money(domestic),
        "international_usd": money(international),
        "landed_cost_usd": money(landed),
        "channel_fee_usd": money(fee),
        "tax_usd": money(tax),
        "net_profit_usd": money(profit),
        "net_margin": rate(margin),
        "fx_usd_cny": money(fx),
        "platform_fee_rate": rate(platform),
        "payment_fee_rate": rate(PAYMENT_FEE),
        "duty_rate": rate(duty_rate),
        "vat_rate": rate(vat_rate),
        "rules_version": rules_version,
        "origin_country": product.get("origin_country") or "CN",
        "target_market": market,
        "route": product.get("route") or f"{product.get('origin_country') or 'CN'}-{market}",
        "incoterm": product.get("incoterm") or "DDP",
        "tax_regime": regime,
        "transit_days_min": low,
        "transit_days_max": high,
        "risk_level": risk,
        "opportunity_score": opportunity,
        "context_version": int(product.get("context_version") or 1),
    }
    metrics["explanation"] = explain(metrics)
    metrics["explanation_model"] = "rules"
    return metrics
