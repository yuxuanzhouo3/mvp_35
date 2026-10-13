from decimal import Decimal

from app.modules.kpi_view import dashboard_view
from app.services.metrics import snapshot
from app.services.profit import calculate
from config.settings import Settings
from db.store import DocumentStore
from test.support import show_rate

PRODUCT = {
    "cost_cny": "72",
    "target_price_usd": "40",
    "international_freight_usd": "2",
    "fx_usd_cny": "7.2",
    "target_market": "US",
    "tax_regime": "cn_us",
    "origin_country": "CN",
}


def test_profit_tax_and_risk_use_the_rules_engine():
    metrics = calculate(PRODUCT)
    price = Decimal(metrics["target_price_usd"])
    landed = Decimal(metrics["landed_cost_usd"])
    fee = Decimal(metrics["channel_fee_usd"])
    tax = Decimal(metrics["tax_usd"])
    profit = Decimal(metrics["net_profit_usd"])
    assert landed == Decimal("12.00")
    assert fee == Decimal("7.16")
    assert tax == Decimal("0.90")
    assert profit == price - landed - fee - tax
    assert metrics["net_margin"] == "0.4985"
    assert Decimal(metrics["net_margin"]) == profit / price
    assert metrics["risk_level"] == "低"
    assert metrics["explanation_model"] == "rules"
    assert metrics["rules_version"] == "pg-rules-1.0"


def test_high_freight_is_high_risk():
    metrics = calculate(
        {
            "cost_cny": "72",
            "target_price_usd": "10",
            "international_freight_usd": "4",
            "fx_usd_cny": "7.2",
            "target_market": "US",
            "tax_regime": "cn_us",
            "origin_country": "CN",
        }
    )
    assert metrics["risk_level"] == "高"
    assert Decimal(metrics["net_margin"]) < Decimal("0.05")


def test_eight_rate_formulas_and_blank_denominator(tmp_path):
    assert show_rate(95, 100) == "0.9500"
    assert show_rate(40, 100) == "0.4000"
    assert show_rate(8, 100) == "0.0800"
    assert show_rate(60, 100) == "0.6000"
    assert show_rate(25, 100) == "0.2500"
    assert show_rate(10, 100) == "0.1000"
    assert show_rate(1, 2) == "0.5000"
    view = dashboard_view(snapshot(DocumentStore(tmp_path / "store.json"), "tenant_missing", Settings(), 30))
    for key in ("net_margin", "act_r", "tr", "open_r", "ar", "qr", "act_r_cold", "rec_r"):
        row = view["headline"].get(key) or view["lifecycle"][key]
        assert row["value"] is None
        assert row["display"] == "—"
