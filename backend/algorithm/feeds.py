"""Live inputs for the repricer.

The price rule itself stays local: match the competitor median, and do not go
below the cost-plus floor. The numbers that feed it come from outside when a
feed is configured.

FX is the European Central Bank rate published by Frankfurter. Shelf prices, when
`PRICER_API_URL` is set, come from a global-goods pricer that speaks the DxPhi
shape: `product`, `country`, and `X-Api-Key`, with `sellers[].price` or
`market_price.median`. A missing key or a failed call keeps the local shelf book
and the product's own exchange rate.
"""

from decimal import Decimal

import httpx

from app.services.profit import money

STRATEGY = "competitor-median-with-cost-plus-floor"


def _get(url: str, *, params: dict | None = None, headers: dict | None = None) -> dict | None:
    if not url:
        return None
    try:
        response = httpx.get(url, params=params, headers=headers, timeout=4, follow_redirects=True)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def fetch_usd_cny(url: str) -> str | None:
    body = _get(url, params={"from": "USD", "to": "CNY"})
    if not body:
        return None
    rate = (body.get("rates") or {}).get("CNY")
    if rate is None:
        return None
    try:
        parsed = Decimal(str(rate))
    except Exception:
        return None
    if parsed <= 0:
        return None
    return money(parsed)


def fetch_global_offers(url: str, key: str, *, name: str, country: str) -> list[dict]:
    headers = {"X-Api-Key": key} if key else None
    body = _get(url, params={"product": name, "country": country}, headers=headers)
    if not body:
        return []
    currency = str(body.get("currency") or "USD").upper()
    if currency != "USD":
        return []
    prices: list[tuple[str, str]] = []
    for index, seller in enumerate(body.get("sellers") or []):
        if not isinstance(seller, dict) or seller.get("price") is None:
            continue
        prices.append((str(seller.get("domain") or seller.get("source") or "global-pricer"), str(seller["price"])))
    market = body.get("market_price") or {}
    if not prices and isinstance(market, dict) and market.get("median") is not None:
        prices.append(("market", str(market["median"])))
    rows = []
    for index, (source, price) in enumerate(prices):
        try:
            parsed = Decimal(str(price))
        except Exception:
            continue
        if parsed <= 0:
            continue
        rows.append(
            {
                "id": f"live-{index}",
                "source": source,
                "market": country,
                "currency": "USD",
                "sku": "",
                "name": name,
                "category": "",
                "shelf_price": money(parsed),
            }
        )
    return rows


def prepare_market(product: dict, settings) -> tuple[dict, list[dict] | None, dict]:
    """Return the product, optional live overseas quotes, and feed metadata."""
    priced = dict(product)
    fx_url = getattr(settings, "fx_api_url", "") or ""
    pricer_url = getattr(settings, "pricer_api_url", "") or ""
    rate = fetch_usd_cny(fx_url)
    if rate:
        priced["fx_usd_cny"] = rate
    offers = fetch_global_offers(
        pricer_url,
        getattr(settings, "pricer_api_key", "") or "",
        name=str(priced.get("name") or ""),
        country=str(priced.get("target_market") or "US"),
    )
    feed = {
        "strategy": STRATEGY,
        "fx": {
            "provider": "frankfurter" if rate else "product",
            "rate": rate or str(priced.get("fx_usd_cny") or ""),
            "used": bool(rate),
        },
        "offers": {
            "provider": "global-pricer" if offers else "local-book",
            "count": len(offers),
        },
    }
    return priced, (offers or None), feed
