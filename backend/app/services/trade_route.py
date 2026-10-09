"""Workspace trade direction shared by selection and acquisition."""

from app.core.errors import AppError

ROUTES = {
    "domestic": {
        "origin_country": "CN",
        "target_market": "CN",
        "route": "CN-CN",
        "tax_regime": "domestic",
        "market_pack": "domestic",
    },
    "cn_us": {
        "origin_country": "CN",
        "target_market": "US",
        "route": "CN-US",
        "tax_regime": "cn_us",
        "market_pack": "cn_us",
    },
    "cn_hk": {
        "origin_country": "CN",
        "target_market": "HK",
        "route": "CN-HK",
        "tax_regime": "cn_hk",
        "market_pack": "cn_hk",
    },
    "cn_au": {
        "origin_country": "CN",
        "target_market": "AU",
        "route": "CN-AU",
        "tax_regime": "cn_au",
        "market_pack": "cn_au",
    },
    "us_cn": {
        "origin_country": "US",
        "target_market": "CN",
        "route": "US-CN",
        "tax_regime": "domestic",
        "market_pack": "us_cn",
    },
}

DEFAULT_ROUTE = "cn_us"


def resolve_route(route_id: str | None) -> dict | None:
    if not route_id:
        return None
    spec = ROUTES.get(route_id)
    if not spec:
        raise AppError("UNKNOWN_ROUTE", "不支持的路线", details={"route": route_id})
    return {"id": route_id, **spec}


def market_fields(route_id: str | None) -> dict:
    spec = resolve_route(route_id)
    if not spec:
        return {}
    return {
        "origin_country": spec["origin_country"],
        "target_market": spec["target_market"],
        "route": spec["route"],
        "tax_regime": spec["tax_regime"],
    }
