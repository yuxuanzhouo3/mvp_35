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
import re
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
TIMEOUT = 3
EBAY_TIMEOUT = 10
_EBAY_TOKEN: dict[str, object] = {"key": "", "token": "", "until": 0.0}
_CJK = re.compile(r"[\u4e00-\u9fff]")
_PRICE_CN = re.compile(
    r"(?:不超过|低于|不到|以内|以下|内)?\s*(\d+(?:\.\d+)?)\s*(?:美元|美金|刀|usd|\$)\s*(?:以内|以下|内)?",
    re.I,
)
_PRICE_EN = re.compile(r"(?:under|below|<=|max(?:imum)?)\s*\$?\s*(\d+(?:\.\d+)?)", re.I)
_USED = re.compile(r"二手|闲置|翻新|used|pre-?owned|refurbished", re.I)
_STOP = {
    "usd",
    "us",
    "usa",
    "under",
    "below",
    "with",
    "the",
    "and",
    "for",
    "or",
    "within",
    "less",
    "than",
    "station",
    "market",
    "site",
}


def clear_goods_cache() -> None:
    _GOODS_CACHE.clear()
    _EBAY_TOKEN.update(key="", token="", until=0.0)


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
    if not needle or target_market == "CN":
        return [], _planned(settings, called=False)
    jobs = (
        _alibaba,
        _pinduoduo,
        _ebay,
        _aliexpress,
        _tiktok,
        _temu,
    )
    domestic: list[dict] = []
    us_rows: list[dict] = []
    us_prices: list[Decimal] = []
    statuses: list[dict] = []
    fx_url = getattr(settings, "fx_api_url", "") or ""
    with ThreadPoolExecutor(max_workers=len(jobs) + 1) as pool:
        fx_future = pool.submit(fetch_usd_cny, fx_url)
        futures = [pool.submit(job, needle, settings) for job in jobs]
        for future in as_completed(futures):
            rows, status = future.result()
            statuses.append(_attach_offers(rows, status))
            if status["region"] == "CN":
                domestic.extend(rows)
            else:
                us_rows.extend(rows)
                us_prices.extend(row["usd"] for row in rows if row.get("usd"))
        fx = fx_future.result() or "7.20"
    statuses.sort(key=lambda row: row["id"])
    if not domestic:
        return _us_shelf_items(us_rows, fx, target_market), statuses
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
    ("pinduoduo", "拼多多", "CN"),
    ("ebay", "eBay", "US"),
    ("aliexpress", "速卖通", "US"),
    ("tiktok", "TikTok Shop", "US"),
    ("temu", "Temu", "US"),
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
    for row in rows[:30]:
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


def _us_shelf_items(rows: list[dict], fx: str, target_market: str) -> list[dict]:
    rate = Decimal(fx)
    market = target_market if target_market != "CN" else "US"
    items = []
    for row in rows[:30]:
        usd = row.get("usd")
        if not isinstance(usd, Decimal):
            continue
        external = str(row["id"]).split(":", 1)[-1]
        platform = str(row["id"]).split(":", 1)[0]
        items.append(
            {
                "id": row["id"],
                "name": row["name"],
                "sku": external,
                "category": "未分类",
                "cost_cny": money(usd * rate),
                "target_price_usd": money(usd),
                "price_basis": "us_shelf",
                "supplier": row.get("supplier") or platform,
                "platform": platform,
                "external_id": external,
                "source_url": row.get("source_url") or "",
                "packaging_cny": "0.00",
                "domestic_freight_cny": "0.00",
                "international_freight_usd": "0.00",
                "origin_country": "US",
                "target_market": market,
                "route": f"CN-{market}",
                "incoterm": "DDP",
                "tax_regime": {"US": "cn_us", "HK": "cn_hk", "AU": "cn_au"}.get(market, "cn_us"),
                "fx_usd_cny": fx,
            }
        )
    return items


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


def ebay_search_plan(query: str) -> dict:
    """Turn a Chinese/English need into Browse API q + filter.

    eBay keyword search returns 0 hits for long Chinese prompts like
    「美国站 100 美元以内的二手 iPhone」. Pull Latin product tokens, map common
    CN product words, and push budget / used into the official filter param.
    """
    text = " ".join((query or "").split())
    max_price = None
    for pattern in (_PRICE_CN, _PRICE_EN):
        match = pattern.search(text)
        if match:
            try:
                max_price = float(match.group(1))
            except ValueError:
                max_price = None
            if max_price and max_price > 0:
                break
            max_price = None
    used = bool(_USED.search(text))
    latin = [token for token in re.findall(r"[A-Za-z][A-Za-z0-9+\-]{1,}", text) if token.lower() not in _STOP]
    words = list(dict.fromkeys(latin))
    if re.search(r"iphone|苹果\s*手机|苹果手机", text, re.I) and not any(w.lower() == "iphone" for w in words):
        words.insert(0, "iphone")
    if re.search(r"\bipad\b|平板", text, re.I) and not any(w.lower() == "ipad" for w in words):
        words.insert(0, "ipad")
    if re.search(r"耳机|airpods", text, re.I) and not any(w.lower() in {"airpods", "earbuds", "headphones"} for w in words):
        words.insert(0, "headphones")
    if used and not any(w.lower() == "used" for w in words):
        # Prefer the filter for condition; keep q short for recall.
        pass
    q = " ".join(words[:8]).strip()
    if not q or _CJK.search(q):
        stripped = _CJK.sub(" ", text)
        stripped = re.sub(r"[^\w\s+\-]", " ", stripped)
        q = " ".join(token for token in stripped.split() if token.lower() not in _STOP)[:80].strip()
    if not q:
        q = "iphone" if re.search(r"手机|iphone|苹果", text, re.I) else text[:60]
    filters: list[str] = []
    if max_price:
        ceiling = max(1, int(max_price))
        # Browse API ignores price bounds unless priceCurrency is set.
        filters.append(f"price:[1..{ceiling}]")
        filters.append("priceCurrency:USD")
    if used:
        filters.append("conditions:{USED}")
    return {"q": q, "filter": ",".join(filters), "max_price": max_price, "used": used}


def _ebay_browse(token: str, *, q: str, limit: int = 30, filter_expr: str = "") -> dict | None:
    params: dict[str, str] = {"q": q, "limit": str(limit)}
    if filter_expr:
        params["filter"] = filter_expr
    try:
        response = httpx.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            params=params,
            headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
            timeout=EBAY_TIMEOUT,
            follow_redirects=True,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _ebay_rows(body: dict | None) -> list:
    rows = []
    for product in (body or {}).get("itemSummaries") or []:
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
    return rows[:30]


def _ebay(query: str, settings) -> tuple[list, dict]:
    client_id = getattr(settings, "ebay_client_id", "") or ""
    secret = getattr(settings, "ebay_client_secret", "") or ""
    if not (client_id and secret):
        return _skip("ebay", "eBay", "US")
    token = _ebay_token(client_id, secret)
    if not token:
        return _fail("ebay", "eBay", "US")
    plan = ebay_search_plan(query)
    body = _ebay_browse(token, q=plan["q"], filter_expr=plan["filter"])
    if body is None:
        return _fail("ebay", "eBay", "US")
    rows = _ebay_rows(body)
    # Drop filters then broaden q if the refined search was too tight.
    if not rows and plan["filter"]:
        body = _ebay_browse(token, q=plan["q"])
        if body is not None:
            rows = _ebay_rows(body)
    if not rows and plan["q"].lower() != "iphone" and re.search(r"iphone|苹果|手机", query or "", re.I):
        body = _ebay_browse(token, q="iphone", filter_expr=plan["filter"])
        if body is None:
            body = _ebay_browse(token, q="iphone")
        if body is not None:
            rows = _ebay_rows(body)
    return rows[:30], _status("ebay", "eBay", "US", "ok", len(rows[:30]))


def _aliexpress(query: str, settings) -> tuple[list, dict]:
    app_key = getattr(settings, "aliexpress_app_key", "") or ""
    secret = getattr(settings, "aliexpress_app_secret", "") or ""
    tracking = getattr(settings, "aliexpress_tracking_id", "") or ""
    if not (app_key and secret and tracking):
        return _skip("aliexpress", "速卖通", "US")
    params = {
        "method": "aliexpress.affiliate.product.query",
        "app_key": app_key,
        "timestamp": str(int(time.time() * 1000)),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        "keywords": query,
        "page_no": "1",
        "page_size": "30",
        "target_currency": "USD",
        "target_language": "EN",
        "ship_to_country": "US",
        "tracking_id": tracking,
    }
    params["sign"] = _md5_sign(secret, params)
    body = _post("https://api-sg.aliexpress.com/sync", data=params)
    products = _aliexpress_products(body)
    if products is None:
        return _fail("aliexpress", "速卖通", "US")
    rows = []
    for product in products:
        if not isinstance(product, dict):
            continue
        title = str(product.get("product_title") or "")
        external = str(product.get("product_id") or "")
        price = _amount(product.get("target_sale_price") or product.get("sale_price"))
        if not title or not external or price is None:
            continue
        rows.append(
            _us(
                "aliexpress",
                external,
                title,
                price,
                str(product.get("shop_name") or "AliExpress"),
                str(product.get("promotion_link") or product.get("product_detail_url") or ""),
            )
        )
    return rows[:30], _status("aliexpress", "速卖通", "US", "ok", len(rows[:30]))


def _tiktok_sign(path: str, secret: str, params: dict, body: str) -> str:
    pieces = "".join(f"{key}{params[key]}" for key in sorted(params) if key not in {"sign", "access_token"})
    raw = f"{secret}{path}{pieces}{body}{secret}"
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()


def _tiktok_price(product: dict) -> Decimal | None:
    for key in ("sale_price", "original_price", "price"):
        value = product.get(key)
        if isinstance(value, dict):
            amount = _amount(value.get("amount") or value.get("sale_price") or value.get("value"))
            currency = str(value.get("currency") or "USD").upper()
            if amount is not None and currency == "USD":
                return amount
        else:
            amount = _amount(value)
            if amount is not None:
                return amount
    for sku in product.get("skus") or []:
        if isinstance(sku, dict):
            found = _tiktok_price(sku)
            if found is not None:
                return found
    return None


def _tiktok(query: str, settings) -> tuple[list, dict]:
    app_key = getattr(settings, "tiktok_shop_app_key", "") or ""
    secret = getattr(settings, "tiktok_shop_app_secret", "") or ""
    token = getattr(settings, "tiktok_shop_access_token", "") or ""
    cipher = getattr(settings, "tiktok_shop_shop_cipher", "") or ""
    if not (app_key and secret and token and cipher):
        return _skip("tiktok", "TikTok Shop", "US")
    plan = ebay_search_plan(query)
    keywords = [part for part in plan["q"].split() if part][:3] or [query.strip()[:40]]
    path = "/affiliate_seller/202405/open_collaborations/products/search"
    payload = json.dumps({"title_keywords": keywords}, separators=(",", ":"))
    params = {
        "app_key": app_key,
        "timestamp": str(int(time.time())),
        "shop_cipher": cipher,
        "page_size": "20",
    }
    params["sign"] = _tiktok_sign(path, secret, params, payload)
    try:
        response = httpx.post(
            f"https://open-api.tiktokglobalshop.com{path}",
            params=params,
            content=payload,
            headers={
                "Content-Type": "application/json",
                "x-tts-access-token": token,
            },
            timeout=8,
        )
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return _fail("tiktok", "TikTok Shop", "US")
    if not isinstance(body, dict) or body.get("code") not in (0, "0", None):
        # Some success envelopes omit code and nest under data.
        if not isinstance(body, dict) or (body.get("code") not in (0, "0") and "data" not in body):
            return _fail("tiktok", "TikTok Shop", "US")
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    products = data.get("products") or data.get("product_list") or []
    if not isinstance(products, list):
        return _fail("tiktok", "TikTok Shop", "US")
    rows = []
    for product in products:
        if not isinstance(product, dict):
            continue
        title = str(product.get("title") or product.get("product_name") or product.get("name") or "")
        external = str(product.get("id") or product.get("product_id") or "")
        amount = _tiktok_price(product)
        if not title or not external or amount is None:
            continue
        link = str(product.get("product_url") or product.get("detail_url") or "")
        rows.append(_us("tiktok", external, title, amount, "TikTok Shop", link))
    return rows[:20], _status("tiktok", "TikTok Shop", "US", "ok", len(rows[:20]))


def _temu_price(product: dict) -> Decimal | None:
    for key in ("retailPrice", "listPrice", "price", "salePrice", "marketPrice"):
        value = product.get(key)
        if isinstance(value, dict):
            amount = _amount(value.get("amount") or value.get("price") or value.get("value"))
            currency = str(value.get("currency") or "USD").upper()
            if amount is not None and currency in {"USD", ""}:
                return amount
        else:
            amount = _amount(value)
            if amount is not None:
                return amount
    for sku in product.get("skuInfoList") or product.get("skuList") or []:
        if isinstance(sku, dict):
            found = _temu_price(sku)
            if found is not None:
                return found
    return None


def _temu_goods(body: dict | None):
    if not isinstance(body, dict):
        return None
    if body.get("success") is False:
        return None
    err = body.get("errorCode")
    if err not in (None, 0, "0", 1000000, "1000000") and body.get("success") is not True:
        return None
    result = body.get("result")
    if isinstance(result, list):
        return result
    if not isinstance(result, dict):
        return []
    for key in ("goodsList", "pageItems", "list", "goodsInfoList"):
        rows = result.get(key)
        if isinstance(rows, list):
            return rows
        if isinstance(rows, dict):
            nested = rows.get("goodsList") or rows.get("list") or []
            if isinstance(nested, list):
                return nested
    return []


def _temu(query: str, settings) -> tuple[list, dict]:
    """US Temu Partner goods list (seller mall) via bg.local.goods.list.query."""
    app_key = getattr(settings, "temu_app_key", "") or ""
    secret = getattr(settings, "temu_app_secret", "") or ""
    token = getattr(settings, "temu_access_token", "") or ""
    if not (app_key and secret and token):
        return _skip("temu", "Temu", "US")
    host = (getattr(settings, "temu_open_host", "") or "https://openapi-b-us.temu.com").rstrip("/")
    plan = ebay_search_plan(query)
    needle = (plan.get("q") or query).strip()[:80] or query.strip()[:80]
    params = {
        "type": "bg.local.goods.list.query",
        "app_key": app_key,
        "access_token": token,
        "timestamp": str(int(time.time())),
        "data_type": "JSON",
        "pageNo": "1",
        "pageSize": "20",
        "goodsSearchType": "1",
        "goodsStatusFilterType": "1",
        "searchText": needle,
    }
    params["sign"] = _md5_sign(secret, params)
    try:
        response = httpx.post(
            f"{host}/openapi/router",
            content=json.dumps(params, separators=(",", ":")),
            headers={"Content-Type": "application/json"},
            timeout=8,
        )
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return _fail("temu", "Temu", "US")
    products = _temu_goods(body if isinstance(body, dict) else None)
    if products is None:
        return _fail("temu", "Temu", "US")
    rows = []
    for product in products:
        if not isinstance(product, dict):
            continue
        title = str(product.get("goodsName") or product.get("title") or product.get("name") or "")
        external = str(product.get("goodsId") or product.get("id") or "")
        amount = _temu_price(product)
        if not title or not external or amount is None:
            continue
        link = str(product.get("goodsUrl") or product.get("thumbUrl") or "")
        if not link and external:
            link = f"https://www.temu.com/goods.html?goods_id={external}"
        rows.append(_us("temu", external, title, amount, "Temu", link))
    return rows[:20], _status("temu", "Temu", "US", "ok", len(rows[:20]))


def _aliexpress_products(body: dict | None):
    if not isinstance(body, dict) or body.get("error_response"):
        return None
    resp = body.get("aliexpress_affiliate_product_query_response") or {}
    result = ((resp.get("resp_result") or {}).get("result")) or {}
    products = result.get("products") or {}
    if isinstance(products, dict):
        rows = products.get("product") or []
    elif isinstance(products, list):
        rows = products
    else:
        rows = []
    if isinstance(rows, dict):
        return [rows]
    return rows if isinstance(rows, list) else None


def _ebay_token(client_id: str, secret: str) -> str:
    key = f"{client_id}:{secret[:12]}"
    now = time.time()
    if _EBAY_TOKEN["token"] and _EBAY_TOKEN["key"] == key and now < float(_EBAY_TOKEN["until"] or 0):
        return str(_EBAY_TOKEN["token"])
    try:
        response = httpx.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
            auth=(client_id, secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=EBAY_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
        token = str(body.get("access_token") or "")
        expires = int(body.get("expires_in") or 7200)
    except (httpx.HTTPError, ValueError, TypeError):
        return ""
    if not token:
        return ""
    _EBAY_TOKEN.update(key=key, token=token, until=now + max(60, expires - 60))
    return token
