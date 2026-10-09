"""China supply and US shelf lookups for selection-assist.

Each platform uses its official open API. A missing key skips that platform.
A timeout or a bad response skips it too, and the rest of the search continues.
Domestic rows carry the supply price in CNY. US rows carry the shelf price in
USD. The sell price used for ranking is the US median when any US offer came
back, otherwise the existing 15% cost-plus floor.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal

import httpx

from algorithm.feeds import fetch_usd_cny
from algorithm.product_pricer import _floor_price
from app.services.profit import money

_SHELF: dict[str, dict] = {}
_GOODS_CACHE: dict[str, dict] = {}
_ALIBABA_SESSION = {"access_token": "", "refresh_token": "", "access_until": 0.0, "refresh_until": 0.0}
_ALIBABA_DENY: dict[str, float] = {}
TIMEOUT = 4


def clear_goods_cache() -> None:
    _GOODS_CACHE.clear()


def goods_age(query: str, target_market: str = "US") -> float | None:
    hit = _GOODS_CACHE.get(f"{target_market}:{query.strip().lower()}")
    if not hit:
        return None
    return time.time() - hit["at"]


def cached_collect(query: str, settings, target_market: str = "US", *, interval: int = 3600, force: bool = False):
    needle = query.strip().lower()
    key = f"{target_market}:{needle}"
    now = time.time()
    hit = _GOODS_CACHE.get(key)
    if hit and needle and not force and now - hit["at"] < interval:
        return hit["items"], hit["statuses"], {"fresh": False, "at": hit["at"]}
    items, statuses = collect_goods(query, settings, target_market)
    if items:
        _GOODS_CACHE[key] = {"at": now, "items": items, "statuses": statuses}
        return items, statuses, {"fresh": True, "at": now}
    return items, statuses, {"fresh": True, "at": None}


def lookup_shelf(catalog_id: str) -> dict | None:
    return _SHELF.get(catalog_id)


def remember_shelf(items: list[dict]) -> None:
    for item in items:
        if item.get("id"):
            _SHELF[item["id"]] = item


def collect_goods(query: str, settings, target_market: str = "US") -> tuple[list[dict], list[dict]]:
    needle = query.strip()
    fx = fetch_usd_cny(getattr(settings, "fx_api_url", "") or "") or "7.20"
    if not needle or target_market == "CN":
        return [], _planned(settings, called=False)
    jobs = (
        _alibaba,
        _taobao,
        _tmall,
        _pinduoduo,
        _jd,
        _amazon,
        _walmart,
        _ebay,
    )
    domestic: list[dict] = []
    us_prices: list[Decimal] = []
    statuses: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(job, needle, settings) for job in jobs]
        for future in as_completed(futures):
            rows, status = future.result()
            statuses.append(_attach_offers(rows, status))
            if status["region"] == "CN":
                domestic.extend(rows)
            else:
                us_prices.extend(row["usd"] for row in rows if row.get("usd"))
    statuses.sort(key=lambda row: row["id"])
    if not domestic:
        return [], statuses
    median = _median(us_prices)
    items = []
    for row in domestic:
        item = {
            **row,
            "packaging_cny": "4.00",
            "domestic_freight_cny": "6.00",
            "international_freight_usd": "3.20",
            "origin_country": "CN",
            "target_market": "US" if target_market != "CN" else "CN",
            "route": f"CN-{target_market if target_market != 'CN' else 'US'}",
            "incoterm": "DDP",
            "tax_regime": {"US": "cn_us", "HK": "cn_hk", "AU": "cn_au"}.get(target_market, "cn_us"),
            "fx_usd_cny": fx,
            "category": row.get("category") or "未分类",
        }
        if median is not None:
            item["target_price_usd"] = money(median)
            item["price_basis"] = "us_shelf"
        else:
            item["target_price_usd"] = money(_floor_price(item))
            item["price_basis"] = "floor_reference"
        items.append(item)
    return items, statuses


def _planned(settings, *, called: bool) -> list[dict]:
    del settings, called
    return [
        {"id": platform, "name": name, "region": region, "status": "skipped", "count": 0}
        for platform, name, region in _PLATFORMS
    ]


_PLATFORMS = (
    ("1688", "1688", "CN"),
    ("taobao", "淘宝", "CN"),
    ("tmall", "天猫", "CN"),
    ("pinduoduo", "拼多多", "CN"),
    ("jd", "京东", "CN"),
    ("amazon", "亚马逊", "US"),
    ("walmart", "沃尔玛", "US"),
    ("ebay", "eBay", "US"),
)


def _median(prices: list[Decimal]) -> Decimal | None:
    if not prices:
        return None
    ordered = sorted(prices)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _amount(value) -> Decimal | None:
    if value is None or value == "":
        return None
    text = str(value).replace(",", "").replace("¥", "").replace("$", "").strip()
    try:
        parsed = Decimal(text)
    except Exception:
        return None
    if parsed <= 0:
        return None
    return parsed


def _attach_offers(rows: list, status: dict) -> dict:
    offers = []
    for row in rows[:3]:
        if status.get("region") == "CN" and row.get("cost_cny"):
            offers.append({"name": str(row.get("name") or ""), "price": str(row["cost_cny"]), "currency": "CNY"})
        elif row.get("usd") is not None:
            offers.append({"name": str(row.get("name") or ""), "price": money(row["usd"]), "currency": "USD"})
    return {**status, "offers": offers}


def _status(platform: str, name: str, region: str, status: str, count: int) -> dict:
    return {"id": platform, "name": name, "region": region, "status": status, "count": count}


def _skip(platform: str, name: str, region: str) -> tuple[list, dict]:
    return [], _status(platform, name, region, "skipped", 0)


def _fail(platform: str, name: str, region: str) -> tuple[list, dict]:
    return [], _status(platform, name, region, "failed", 0)


def _post(url: str, *, data: dict | None = None, content: bytes | None = None, headers: dict | None = None) -> dict | None:
    try:
        response = httpx.post(url, data=data, content=content, headers=headers, timeout=TIMEOUT, follow_redirects=True)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _get(url: str, *, params: dict | None = None, headers: dict | None = None) -> dict | None:
    try:
        response = httpx.get(url, params=params, headers=headers, timeout=TIMEOUT, follow_redirects=True)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _md5_sign(secret: str, params: dict) -> str:
    raw = secret + "".join(f"{key}{params[key]}" for key in sorted(params)) + secret
    return hashlib.md5(raw.encode()).hexdigest().upper()


def _domestic(platform: str, external_id: str, name: str, cost: Decimal, supplier: str, url: str, category: str = "") -> dict:
    return {
        "id": f"{platform}:{external_id}",
        "name": name.strip(),
        "sku": external_id,
        "category": category or "未分类",
        "cost_cny": money(cost),
        "supplier": supplier or platform,
        "platform": platform,
        "external_id": external_id,
        "source_url": url,
    }


def clear_alibaba_session() -> None:
    _ALIBABA_SESSION.update(access_token="", refresh_token="", access_until=0.0, refresh_until=0.0)
    _ALIBABA_DENY.clear()


def _alibaba_deadline(text: str) -> float:
    raw = (text or "").strip()
    if not raw:
        return 0.0
    try:
        if len(raw) >= 19 and raw[:14].isdigit():
            stamp = datetime.strptime(raw[:14] + raw[17:], "%Y%m%d%H%M%S%z")
        else:
            stamp = datetime.fromisoformat(raw)
    except ValueError:
        return 0.0
    return stamp.timestamp()


def _alibaba_token(settings, *, force: bool = False) -> tuple[str, bool]:
    now = time.time()
    app_key = getattr(settings, "alibaba_app_key", "") or ""
    secret = getattr(settings, "alibaba_app_secret", "") or ""
    refresh = _ALIBABA_SESSION["refresh_token"] or getattr(settings, "alibaba_refresh_token", "") or ""
    deadline = _ALIBABA_SESSION["refresh_until"] or _alibaba_deadline(getattr(settings, "alibaba_refresh_token_timeout", "") or "")
    if deadline and now >= deadline:
        return "", True
    if _ALIBABA_SESSION["access_token"] and not force and now + 120 < _ALIBABA_SESSION["access_until"]:
        return _ALIBABA_SESSION["access_token"], False
    env_access = getattr(settings, "alibaba_access_token", "") or ""
    if env_access and not force and not _ALIBABA_SESSION["access_token"]:
        _ALIBABA_SESSION["access_token"] = env_access
        _ALIBABA_SESSION["access_until"] = now + 9 * 3600
        return env_access, False
    if not (app_key and secret and refresh):
        return "", True
    url = f"https://gw.open.1688.com/openapi/http/1/system.oauth2/getToken/{app_key}"
    body, _code = _alibaba_http(url, {
        "grant_type": "refresh_token",
        "client_id": app_key,
        "client_secret": secret,
        "refresh_token": refresh,
    })
    access = str((body or {}).get("access_token") or "")
    if not access:
        return "", True
    _ALIBABA_SESSION["access_token"] = access
    _ALIBABA_SESSION["refresh_token"] = str(body.get("refresh_token") or refresh)
    try:
        expires = int(body.get("expires_in") or 35000)
    except (TypeError, ValueError):
        expires = 35000
    _ALIBABA_SESSION["access_until"] = now + max(expires, 60)
    refreshed_deadline = _alibaba_deadline(str(body.get("refresh_token_timeout") or ""))
    if refreshed_deadline:
        _ALIBABA_SESSION["refresh_until"] = refreshed_deadline
    return access, False


def _alibaba_http(url: str, data: dict) -> tuple[dict | None, int]:
    try:
        response = httpx.post(url, data=data, timeout=8, follow_redirects=True)
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return None, 0
    return (body if isinstance(body, dict) else None), response.status_code


def _alibaba_rejected(body: dict | None, code: int) -> bool:
    if code in (401, 403):
        return True
    if not isinstance(body, dict):
        return False
    blob = " ".join(
        str(body.get(key) or "")
        for key in ("error", "error_code", "error_message", "exception", "error_description")
    ).lower()
    return any(part in blob for part in ("401", "authorized", "invalid_token", "access_token", "access token"))


def _alibaba(query: str, settings) -> tuple[list, dict]:
    app_key = getattr(settings, "alibaba_app_key", "") or ""
    secret = getattr(settings, "alibaba_app_secret", "") or ""
    has_grant = bool(
        (getattr(settings, "alibaba_access_token", "") or "")
        or (getattr(settings, "alibaba_refresh_token", "") or "")
        or _ALIBABA_SESSION["access_token"]
        or _ALIBABA_SESSION["refresh_token"]
    )
    if not (app_key and secret and has_grant):
        return _skip("1688", "1688", "CN")
    token, reauth = _alibaba_token(settings)
    if reauth or not token:
        return [], _status("1688", "1688", "CN", "reauth" if reauth else "skipped", 0)
    body = _alibaba_search(app_key, secret, token, query, settings)
    if body == "reauth":
        return [], _status("1688", "1688", "CN", "reauth", 0)
    products = _alibaba_rows(body if isinstance(body, dict) else None)
    if not isinstance(body, dict) or body.get("error_code") or body.get("error"):
        return _fail("1688", "1688", "CN")
    rows = []
    for product in products:
        name = str(product.get("subject") or product.get("title") or "")
        external = str(product.get("offerId") or product.get("productID") or "")
        price_info = product.get("priceInfo") if isinstance(product.get("priceInfo"), dict) else {}
        cost = _amount((product.get("price") or {}).get("price") if isinstance(product.get("price"), dict) else product.get("price"))
        if cost is None:
            cost = _amount(price_info.get("price") or price_info.get("consignPrice"))
        if not name or not external or cost is None:
            continue
        rows.append(
            _domestic(
                "1688",
                external,
                name,
                cost,
                str(product.get("companyName") or product.get("supplier") or "1688"),
                str(product.get("productUrl") or product.get("detailUrl") or ""),
            )
        )
    return rows[:8], _status("1688", "1688", "CN", "ok", len(rows[:8]))


def _alibaba_sign(path: str, secret: str, params: dict) -> dict:
    signed = path + "".join(f"{key}{params[key]}" for key in sorted(params))
    stamped = dict(params)
    stamped["_aop_signature"] = hmac.new(secret.encode(), signed.encode(), hashlib.sha1).hexdigest().upper()
    return stamped


def _alibaba_acl(body: dict | None) -> bool:
    if not isinstance(body, dict):
        return False
    blob = f"{body.get('error_code') or ''} {body.get('error_message') or ''}"
    return "APIACLDecline" in blob or "not allowed" in blob.lower()


def _alibaba_search(app_key: str, secret: str, token: str, query: str, settings):
    now = time.time()
    endpoints = (
        (
            "crossborder",
            f"param2/1/com.alibaba.fenxiao.crossborder/product.search.keywordQuery/{app_key}",
            {"offerQueryParam": json.dumps({"keyword": query, "beginPage": 1, "pageSize": 8, "country": "en"}, separators=(",", ":"))},
        ),
        (
            "keyword",
            f"param2/1/com.alibaba.product/product.keyword.search/{app_key}",
            {"keyword": query},
        ),
    )
    last = None
    tried = False
    for name, path, extra in endpoints:
        if _ALIBABA_DENY.get(name, 0) > now:
            continue
        tried = True
        current = token
        params = _alibaba_sign(path, secret, {"access_token": current, **extra})
        body, code = _alibaba_http(f"https://gw.open.1688.com/openapi/{path}", params)
        if _alibaba_rejected(body, code):
            current, reauth = _alibaba_token(settings, force=True)
            if reauth or not current:
                return "reauth"
            params = _alibaba_sign(path, secret, {"access_token": current, **extra})
            body, code = _alibaba_http(f"https://gw.open.1688.com/openapi/{path}", params)
        last = body
        if _alibaba_acl(body):
            _ALIBABA_DENY[name] = now + 15 * 60
            continue
        return body
    return last if tried else {"error_code": "gw.APIACLDecline"}


def _alibaba_rows(body: dict | None) -> list:
    if not isinstance(body, dict):
        return []
    for key in ("products", "result", "data"):
        value = body.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            nested = value.get("products") or value.get("result") or value.get("toReturn") or value.get("data")
            if isinstance(nested, list):
                return [row for row in nested if isinstance(row, dict)]
            if isinstance(nested, dict):
                deeper = nested.get("data") or nested.get("products") or nested.get("toReturn")
                if isinstance(deeper, list):
                    return [row for row in deeper if isinstance(row, dict)]
    return []


def _taobao_call(query: str, settings, *, tmall: bool) -> tuple[list, dict]:
    platform = "tmall" if tmall else "taobao"
    name = "天猫" if tmall else "淘宝"
    app_key = getattr(settings, "taobao_app_key", "") or ""
    secret = getattr(settings, "taobao_app_secret", "") or ""
    adzone = getattr(settings, "taobao_adzone_id", "") or ""
    if not (app_key and secret and adzone):
        return _skip(platform, name, "CN")
    params = {
        "method": "taobao.tbk.dg.material.optional",
        "app_key": app_key,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        "q": query,
        "adzone_id": adzone,
        "page_size": "8",
        "platform": "2",
    }
    if tmall:
        params["is_tmall"] = "true"
    params["sign"] = _md5_sign(secret, params)
    body = _post("https://eco.taobao.com/router/rest", data=params)
    if body is None or body.get("error_response"):
        return _fail(platform, name, "CN")
    result = ((body.get("tbk_dg_material_optional_response") or {}).get("result_list") or {}).get("map_data") or []
    rows = []
    for product in result:
        if not isinstance(product, dict):
            continue
        title = str(product.get("title") or "")
        external = str(product.get("item_id") or product.get("num_iid") or "")
        cost = _amount(product.get("zk_final_price"))
        if not title or not external or cost is None:
            continue
        rows.append(
            _domestic(
                platform,
                external,
                title,
                cost,
                str(product.get("shop_title") or product.get("nick") or name),
                str(product.get("item_url") or product.get("url") or ""),
                str(product.get("category_name") or ""),
            )
        )
    return rows[:8], _status(platform, name, "CN", "ok", len(rows[:8]))


def _taobao(query: str, settings) -> tuple[list, dict]:
    return _taobao_call(query, settings, tmall=False)


def _tmall(query: str, settings) -> tuple[list, dict]:
    return _taobao_call(query, settings, tmall=True)


def _pinduoduo(query: str, settings) -> tuple[list, dict]:
    client_id = getattr(settings, "pdd_client_id", "") or ""
    secret = getattr(settings, "pdd_client_secret", "") or ""
    pid = getattr(settings, "pdd_pid", "") or ""
    if not (client_id and secret and pid):
        return _skip("pinduoduo", "拼多多", "CN")
    params = {
        "type": "pdd.ddk.goods.search",
        "client_id": client_id,
        "timestamp": str(int(datetime.now().timestamp())),
        "data_type": "JSON",
        "keyword": query,
        "pid": pid,
        "page_size": "8",
    }
    params["sign"] = _md5_sign(secret, params)
    body = _post("https://gw-api.pinduoduo.com/api/router", data=params)
    if body is None or body.get("error_response"):
        return _fail("pinduoduo", "拼多多", "CN")
    goods = ((body.get("goods_search_response") or {}).get("goods_list")) or []
    rows = []
    for product in goods:
        if not isinstance(product, dict):
            continue
        title = str(product.get("goods_name") or "")
        external = str(product.get("goods_id") or product.get("goods_sign") or "")
        fen = _amount(product.get("min_group_price"))
        if not title or not external or fen is None:
            continue
        rows.append(_domestic("pinduoduo", external, title, fen / Decimal("100"), str(product.get("mall_name") or "拼多多"), ""))
    return rows[:8], _status("pinduoduo", "拼多多", "CN", "ok", len(rows[:8]))


def _jd(query: str, settings) -> tuple[list, dict]:
    app_key = getattr(settings, "jd_app_key", "") or ""
    secret = getattr(settings, "jd_app_secret", "") or ""
    if not (app_key and secret):
        return _skip("jd", "京东", "CN")
    params = {
        "method": "jd.union.open.goods.query",
        "app_key": app_key,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "1.0",
        "sign_method": "md5",
        "360buy_param_json": json.dumps({"goodsReqDTO": {"keyword": query, "pageIndex": 1, "pageSize": 8}}, separators=(",", ":")),
    }
    params["sign"] = _md5_sign(secret, params)
    body = _post("https://api.jd.com/routerjson", data=params)
    if body is None or body.get("error_response"):
        return _fail("jd", "京东", "CN")
    outer = body.get("jd_union_open_goods_query_responce") or body.get("jd_union_open_goods_query_response") or {}
    raw = outer.get("queryResult")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = {}
    goods = (raw or {}).get("data") if isinstance(raw, dict) else []
    rows = []
    for product in goods or []:
        if not isinstance(product, dict):
            continue
        title = str(product.get("skuName") or "")
        external = str(product.get("skuId") or "")
        price = _amount((product.get("priceInfo") or {}).get("price"))
        if not title or not external or price is None:
            continue
        shop = (product.get("shopInfo") or {}).get("shopName") or "京东"
        rows.append(_domestic("jd", external, title, price, str(shop), str(product.get("materialUrl") or "")))
    return rows[:8], _status("jd", "京东", "CN", "ok", len(rows[:8]))


def _us(platform: str, external_id: str, name: str, usd: Decimal, supplier: str, url: str) -> dict:
    return {"id": f"{platform}:{external_id}", "name": name, "usd": usd, "supplier": supplier, "source_url": url}


def _amazon(query: str, settings) -> tuple[list, dict]:
    access = getattr(settings, "amazon_access_key", "") or ""
    secret = getattr(settings, "amazon_secret_key", "") or ""
    partner = getattr(settings, "amazon_partner_tag", "") or ""
    if not (access and secret and partner):
        return _skip("amazon", "亚马逊", "US")
    payload = json.dumps(
        {
            "Keywords": query,
            "Resources": ["ItemInfo.Title", "Offers.Listings.Price"],
            "PartnerTag": partner,
            "PartnerType": "Associates",
            "Marketplace": "www.amazon.com",
            "ItemCount": 8,
        },
        separators=(",", ":"),
    )
    headers = _paapi_headers(access, secret, payload)
    body = _post("https://webservices.amazon.com/paapi5/searchitems", content=payload.encode(), headers=headers)
    items = ((body or {}).get("SearchResult") or {}).get("Items") or []
    if body is None:
        return _fail("amazon", "亚马逊", "US")
    rows = []
    for product in items:
        if not isinstance(product, dict):
            continue
        title = str(((product.get("ItemInfo") or {}).get("Title") or {}).get("DisplayValue") or "")
        listings = ((product.get("Offers") or {}).get("Listings")) or []
        price = _amount(((listings[0].get("Price") or {}).get("Amount")) if listings and isinstance(listings[0], dict) else None)
        asin = str(product.get("ASIN") or "")
        if not title or not asin or price is None:
            continue
        rows.append(_us("amazon", asin, title, price, "amazon.com", str(product.get("DetailPageURL") or "")))
    return rows[:8], _status("amazon", "亚马逊", "US", "ok", len(rows[:8]))


def _paapi_headers(access: str, secret: str, payload: str) -> dict:
    host = "webservices.amazon.com"
    target = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
    now = datetime.now(timezone.utc)
    amzdate = now.strftime("%Y%m%dT%H%M%SZ")
    day = amzdate[:8]
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    canonical_headers = (
        "content-encoding:amz-1.0\n"
        "content-type:application/json; charset=utf-8\n"
        f"host:{host}\n"
        f"x-amz-date:{amzdate}\n"
        f"x-amz-target:{target}\n"
    )
    signed = "content-encoding;content-type;host;x-amz-date;x-amz-target"
    canonical = f"POST\n/paapi5/searchitems\n\n{canonical_headers}\n{signed}\n{payload_hash}"
    scope = f"{day}/us-east-1/ProductAdvertisingAPI/aws4_request"
    string_to_sign = "AWS4-HMAC-SHA256\n" + amzdate + "\n" + scope + "\n" + hashlib.sha256(canonical.encode()).hexdigest()
    key = hmac.new(("AWS4" + secret).encode(), day.encode(), hashlib.sha256).digest()
    key = hmac.new(key, b"us-east-1", hashlib.sha256).digest()
    key = hmac.new(key, b"ProductAdvertisingAPI", hashlib.sha256).digest()
    key = hmac.new(key, b"aws4_request", hashlib.sha256).digest()
    signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    return {
        "Host": host,
        "Content-Type": "application/json; charset=utf-8",
        "Content-Encoding": "amz-1.0",
        "X-Amz-Date": amzdate,
        "X-Amz-Target": target,
        "Authorization": f"AWS4-HMAC-SHA256 Credential={access}/{scope}, SignedHeaders={signed}, Signature={signature}",
    }


def _walmart(query: str, settings) -> tuple[list, dict]:
    publisher = getattr(settings, "walmart_publisher_id", "") or ""
    consumer = getattr(settings, "walmart_consumer_id", "") or ""
    if not (publisher and consumer):
        return _skip("walmart", "沃尔玛", "US")
    body = _get(
        "https://developer.api.walmart.com/api-proxy/service/affil/product/v2/search",
        params={"query": query, "publisherId": publisher},
        headers={"WM_CONSUMER.ID": consumer, "WM_QOS.CORRELATION_ID": uuid.uuid4().hex},
    )
    if body is None:
        return _fail("walmart", "沃尔玛", "US")
    rows = []
    for product in body.get("items") or []:
        if not isinstance(product, dict):
            continue
        title = str(product.get("name") or "")
        external = str(product.get("itemId") or "")
        price = _amount(product.get("salePrice"))
        if not title or not external or price is None:
            continue
        rows.append(_us("walmart", external, title, price, "walmart.com", str(product.get("productUrl") or "")))
    return rows[:8], _status("walmart", "沃尔玛", "US", "ok", len(rows[:8]))


def _ebay(query: str, settings) -> tuple[list, dict]:
    client_id = getattr(settings, "ebay_client_id", "") or ""
    secret = getattr(settings, "ebay_client_secret", "") or ""
    if not (client_id and secret):
        return _skip("ebay", "eBay", "US")
    token = _ebay_token(client_id, secret)
    if not token:
        return _fail("ebay", "eBay", "US")
    body = _get(
        "https://api.ebay.com/buy/browse/v1/item_summary/search",
        params={"q": query, "limit": "8"},
        headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
    )
    if body is None:
        return _fail("ebay", "eBay", "US")
    rows = []
    for product in body.get("itemSummaries") or []:
        if not isinstance(product, dict):
            continue
        price = product.get("price") or {}
        if str(price.get("currency") or "USD").upper() != "USD":
            continue
        amount = _amount(price.get("value"))
        title = str(product.get("title") or "")
        external = str(product.get("itemId") or "")
        if not title or not external or amount is None:
            continue
        seller = (product.get("seller") or {}).get("username") or "eBay"
        rows.append(_us("ebay", external, title, amount, str(seller), str(product.get("itemWebUrl") or "")))
    return rows[:8], _status("ebay", "eBay", "US", "ok", len(rows[:8]))


def _ebay_token(client_id: str, secret: str) -> str:
    try:
        response = httpx.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
            auth=(client_id, secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        token = response.json().get("access_token")
    except (httpx.HTTPError, ValueError):
        return ""
    return str(token or "")
