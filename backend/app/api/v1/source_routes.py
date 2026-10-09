from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from algorithm.feeds import prepare_market
from algorithm.product_pricer import PRODUCT_PRICER, compare_csv, compare_product
from algorithm.selection_assist import rank_query
from algorithm.sources import CATALOG_SOURCE, DOMESTIC_QUOTES, DOMESTIC_SOURCE, OVERSEAS_QUOTES, OVERSEAS_SOURCE, query_quotes
from app.api.deps import bind, respond
from app.services.common import product_from_body, search_catalog
from app.services.trade_route import market_fields, resolve_route

router = APIRouter(prefix="/api/v1")


class PricerIn(BaseModel):
    csv: str | None = None
    name: str | None = None
    sku: str | None = None
    category: str | None = None
    cost_cny: str | None = None
    packaging_cny: str | None = None
    domestic_freight_cny: str | None = None
    international_freight_usd: str | None = None
    target_price_usd: str | None = None
    origin_country: str | None = None
    target_market: str | None = None
    route: str | None = None
    incoterm: str | None = None
    tax_regime: str | None = None
    cost_currency: str | None = None
    price_currency: str | None = None
    fx_usd_cny: str | None = None
    route_id: str | None = None


class SelectionIn(BaseModel):
    q: str = ""
    target_market: str | None = None


@router.get("/sources/pricer/domestic")
def domestic_prices(
    request: Request,
    q: str = "",
    sku: str = "",
    authorization: str | None = Header(default=None),
):
    bind(request, authorization)
    return respond(
        request,
        {"source": DOMESTIC_SOURCE, "market": "CN", "currency": "CNY", "items": query_quotes(DOMESTIC_QUOTES, q=q, sku=sku, market="CN")},
    )


@router.get("/sources/pricer/overseas")
def overseas_prices(
    request: Request,
    q: str = "",
    sku: str = "",
    market: str = "US",
    authorization: str | None = Header(default=None),
):
    bind(request, authorization)
    return respond(
        request,
        {
            "source": OVERSEAS_SOURCE,
            "market": market,
            "currency": "USD",
            "items": query_quotes(OVERSEAS_QUOTES, q=q, sku=sku, market=market),
        },
    )


@router.get("/sources/catalog")
def catalog_source(request: Request, q: str = "", authorization: str | None = Header(default=None)):
    bind(request, authorization)
    return respond(request, {"source": CATALOG_SOURCE, "items": search_catalog(q)})


@router.post("/algorithms/product-pricer")
def run_product_pricer(request: Request, body: PricerIn, authorization: str | None = Header(default=None)):
    settings, _store, _prof = bind(request, authorization)
    if body.csv is not None:
        spec = resolve_route(body.route_id)
        return respond(request, compare_csv(body.csv, settings.rules_version, settings, market_fields(body.route_id) if spec else None))
    fields = product_from_body(body.model_dump(exclude_none=True), source="pricer")
    fields, overseas, feed = prepare_market(fields, settings)
    result = compare_product(fields, settings.rules_version, overseas_quotes=overseas, feed=feed)
    result["sources"] = {"domestic": DOMESTIC_SOURCE, "overseas": OVERSEAS_SOURCE}
    result["algorithm"] = PRODUCT_PRICER
    return respond(request, result)


@router.post("/algorithms/selection-assist")
def run_selection_assist(request: Request, body: SelectionIn, authorization: str | None = Header(default=None)):
    settings, _store, _prof = bind(request, authorization)
    return respond(request, rank_query(body.q, settings.rules_version, body.target_market, settings))
