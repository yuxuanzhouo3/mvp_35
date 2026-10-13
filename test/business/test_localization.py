from app.services.profit import calculate

BASE = {
    "cost_cny": "72",
    "target_price_usd": "40",
    "international_freight_usd": "2",
    "fx_usd_cny": "7.2",
    "origin_country": "CN",
}


def test_cn_us_hk_au_and_inland_taxes_differ():
    us = calculate({**BASE, "target_market": "US", "tax_regime": "cn_us"})
    hk = calculate({**BASE, "target_market": "HK", "tax_regime": "cn_hk"})
    au = calculate({**BASE, "target_market": "AU", "tax_regime": "cn_au"})
    inland = calculate({**BASE, "target_market": "CN", "tax_regime": "domestic"})
    assert us["tax_usd"] == "0.90"
    assert hk["tax_usd"] == "0.00"
    assert au["tax_usd"] == "4.60"
    assert inland["tax_usd"] == "5.20"
    assert len({us["net_margin"], hk["net_margin"], au["net_margin"], inland["net_margin"]}) == 4
    assert us["route"] == "CN-US"
    assert hk["route"] == "CN-HK"
    assert au["route"] == "CN-AU"
    assert inland["route"] == "CN-CN"
