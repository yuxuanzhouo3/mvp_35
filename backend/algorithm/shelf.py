"""China supply and US shelf lookups for selection-assist.

Each platform uses its official open API. A missing key skips that platform.
A timeout or a bad response skips it too, and the rest of the search continues.
Domestic rows carry the supply price in CNY. US rows carry the shelf price in
USD. The sell price used for ranking is the US median when any US offer came
back, otherwise the existing 15% cost-plus floor.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
# Hard budget for the whole shelf fan-out. Slow platforms are cut off, not waited out.
SHELF_DEADLINE = 0.85
TIMEOUT = 0.65
EBAY_TIMEOUT = 0.65
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


def _keys_stamp(settings) -> str:
    names = (
        "ebay_client_id",
        "serpapi_api_key",
        "bestbuy_api_key",
        "etsy_api_keystring",
        "amazon_access_key",
        "walmart_publisher_id",
        "taobao_app_key",
        "jd_app_key",
        "alibaba_app_key",
        "vipshop_app_key",
        "suning_app_key",
        "douyin_shop_app_key",
    )
    return "".join("1" if (getattr(settings, name, "") or os.environ.get(name.upper(), "")) else "0" for name in names)


def goods_age(query: str, target_market: str = "US", settings=None) -> float | None:
    stamp = _keys_stamp(settings) if settings is not None else ""
    hit = _GOODS_CACHE.get(f"{target_market}:{query.strip().lower()}:{stamp}") or _GOODS_CACHE.get(
        f"{target_market}:{query.strip().lower()}"
    )
    if not hit:
        return None
    return time.time() - hit["at"]


def cached_collect(query: str, settings, target_market: str = "US", *, interval: int = 3600, force: bool = False):
    needle = query.strip().lower()
    key = f"{target_market}:{needle}:{_keys_stamp(settings)}"
    now = time.time()
    hit = _GOODS_CACHE.get(key)
    if hit and needle and not force and now - hit["at"] < interval:
        return hit["items"], hit["statuses"], {"fresh": False, "at": hit["at"]}
    # Stale cache: answer in <1s, then a later refresh can refill.
    if hit and needle and not force:
        return hit["items"], hit["statuses"], {"fresh": False, "at": hit["at"]}
    items, statuses = collect_goods(query, settings, target_market)
    if items or any(row.get("status") == "ok" for row in statuses):
        _GOODS_CACHE[key] = {"at": now, "items": items, "statuses": statuses}
        return items, statuses, {"fresh": True, "at": now}
    return items, statuses, {"fresh": True, "at": None}


def lookup_shelf(catalog_id: str) -> dict | None:
    return _SHELF.get(catalog_id)


def remember_shelf(items: list[dict]) -> None:
    for item in items:
        if item.get("id"):
            _SHELF[item["id"]] = item


def _env_set(settings, *names: str) -> bool:
    for name in names:
        if (getattr(settings, name, "") or os.environ.get(name.upper(), "") or "").strip():
            return True
    return False


def _live_jobs(settings) -> list[tuple[object, str, str, str]]:
    """Only start workers that have credentials; empty keys stay skipped."""
    jobs: list[tuple[object, str, str, str]] = []
    if _env_set(settings, "ebay_client_id") and _env_set(settings, "ebay_client_secret"):
        jobs.append((_ebay, "ebay", "eBay", "US"))
    if _env_set(settings, "serpapi_api_key"):
        jobs.append((_google_shopping, "google_shopping", "Google 购物", "US"))
    if _env_set(settings, "etsy_api_keystring"):
        jobs.append((_etsy, "etsy", "Etsy", "US"))
    if _env_set(settings, "alibaba_app_key") and _env_set(settings, "alibaba_app_secret"):
        jobs.append((_alibaba, "1688", "1688", "CN"))
    if _env_set(settings, "pdd_client_id") and _env_set(settings, "pdd_client_secret") and _env_set(settings, "pdd_pid"):
        jobs.append((_pinduoduo, "pinduoduo", "拼多多", "CN"))
    if _env_set(settings, "jd_app_key") and _env_set(settings, "jd_app_secret"):
        jobs.append((_jd, "jd", "京东", "CN"))
    if _env_set(settings, "taobao_app_key") and _env_set(settings, "taobao_app_secret") and _env_set(settings, "taobao_adzone_id"):
        jobs.append((_taobao, "taobao", "淘宝", "CN"))
        jobs.append((_tmall, "tmall", "天猫", "CN"))
    if _env_set(settings, "xianyu_app_key") and _env_set(settings, "xianyu_app_secret"):
        jobs.append((_xianyu, "xianyu", "闲鱼", "CN"))
    if _env_set(settings, "vipshop_app_key") and _env_set(settings, "vipshop_app_secret"):
        jobs.append((_vipshop, "vipshop", "唯品会", "CN"))
    if _env_set(settings, "suning_app_key") and _env_set(settings, "suning_app_secret"):
        jobs.append((_suning, "suning", "苏宁", "CN"))
    if _env_set(settings, "douyin_shop_app_key") and _env_set(settings, "douyin_shop_app_secret"):
        jobs.append((_douyin_shop, "douyin_shop", "抖店", "CN"))
    if _env_set(settings, "aliexpress_app_key") and _env_set(settings, "aliexpress_app_secret") and _env_set(
        settings, "aliexpress_tracking_id"
    ):
        jobs.append((_aliexpress, "aliexpress", "速卖通", "US"))
    if _env_set(settings, "amazon_access_key") and _env_set(settings, "amazon_secret_key") and _env_set(
        settings, "amazon_partner_tag"
    ):
        jobs.append((_amazon, "amazon", "亚马逊", "US"))
    if _env_set(settings, "walmart_publisher_id") and _env_set(settings, "walmart_consumer_id"):
        jobs.append((_walmart, "walmart", "沃尔玛", "US"))
    if _env_set(settings, "bestbuy_api_key"):
        jobs.append((_bestbuy, "bestbuy", "Best Buy", "US"))
    if _env_set(settings, "tiktok_shop_app_key") and _env_set(settings, "tiktok_shop_app_secret"):
        jobs.append((_tiktok, "tiktok", "TikTok Shop", "US"))
    if _env_set(settings, "temu_app_key") and _env_set(settings, "temu_app_secret") and _env_set(settings, "temu_access_token"):
        jobs.append((_temu, "temu", "Temu", "US"))
    return jobs


def collect_goods(query: str, settings, target_market: str = "US") -> tuple[list[dict], list[dict]]:
    needle = query.strip()
    if not needle:
        return [], _planned(settings, called=False)
    by_id = {row["id"]: row for row in _planned(settings, called=False)}
    jobs = _live_jobs(settings)
    domestic: list[dict] = []
    us_rows: list[dict] = []
    us_prices: list[Decimal] = []
    fx_url = getattr(settings, "fx_api_url", "") or ""
    deadline = time.monotonic() + SHELF_DEADLINE
    workers = max(2, len(jobs) + 1)
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        fx_future = pool.submit(fetch_usd_cny, fx_url)
        futures = {pool.submit(job, needle, settings): (platform, name, region) for job, platform, name, region in jobs}
        pending = set(futures)
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            for future in done:
                platform, name, region = futures[future]
                try:
                    rows, status = future.result()
                except Exception:
                    rows, status = [], _status(platform, name, region, "failed", 0)
                by_id[status["id"]] = _attach_offers(rows, status)
                if status["region"] == "CN":
                    domestic.extend(rows)
                else:
                    us_rows.extend(rows)
                    us_prices.extend(row["usd"] for row in rows if row.get("usd"))
        for future in pending:
            platform, name, region = futures[future]
            future.cancel()
            by_id[platform] = _status(platform, name, region, "failed", 0)
        try:
            fx_wait = max(0.01, deadline - time.monotonic())
            fx = fx_future.result(timeout=fx_wait) or "7.20"
        except Exception:
            fx = "7.20"
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    statuses = _sort_platforms(list(by_id.values()))
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
    ("ebay", "eBay", "US"),
    ("google_shopping", "Google 购物", "US"),
    ("etsy", "Etsy", "US"),
    ("1688", "1688", "CN"),
    ("pinduoduo", "拼多多", "CN"),
    ("jd", "京东", "CN"),
    ("taobao", "淘宝", "CN"),
    ("tmall", "天猫", "CN"),
    ("xianyu", "闲鱼", "CN"),
    ("vipshop", "唯品会", "CN"),
    ("suning", "苏宁", "CN"),
    ("douyin_shop", "抖店", "CN"),
    ("aliexpress", "速卖通", "US"),
    ("amazon", "亚马逊", "US"),
    ("walmart", "沃尔玛", "US"),
    ("bestbuy", "Best Buy", "US"),
    ("tiktok", "TikTok Shop", "US"),
    ("temu", "Temu", "US"),
)
_PINNED = ("ebay", "google_shopping", "etsy")


def _sort_platforms(statuses: list[dict]) -> list[dict]:
    """Live eBay / Google Shopping / Etsy first, then other ok, then failed, then skipped."""
    rank = {"ok": 0, "failed": 1, "reauth": 2, "skipped": 3}

    def key(row: dict) -> tuple:
        pinned = row.get("id") in _PINNED
        live_pin = 0 if pinned and row.get("status") == "ok" else 1
        pin = _PINNED.index(row["id"]) if pinned else 50
        return (live_pin, rank.get(row.get("status") or "", 9), pin, str(row.get("id") or ""))

    return sorted(statuses, key=key)


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


def _post(url: str, *, data: dict | None = None, content: bytes | None = None, headers: dict | None = None, params: dict | None = None) -> dict | None:
    try:
        response = httpx.post(url, params=params, data=data, content=content, headers=headers, timeout=TIMEOUT, follow_redirects=True)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _get(url: str, *, params: dict | None = None, headers: dict | None = None, timeout: float | None = None) -> dict | None:
    try:
        response = httpx.get(url, params=params, headers=headers, timeout=timeout or TIMEOUT, follow_redirects=True)
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


def _vipshop_sign(secret: str, params: dict) -> str:
    raw = "".join(f"{key}{params[key]}" for key in sorted(params) if key != "sign")
    return hmac.new(secret.encode(), raw.encode(), hashlib.md5).hexdigest().upper()


def _vipshop_goods(body: dict | None) -> list:
    if not isinstance(body, dict):
        return []
    stack: list = [body]
    seen: set[int] = set()
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, list):
            if node and all(isinstance(item, dict) for item in node[:3]):
                sample = {str(key).lower() for key in node[0]}
                if sample & {"goodsid", "goods_id", "goodsid"} or sample & {"goodsname", "goods_name"}:
                    return [item for item in node if isinstance(item, dict)]
            stack.extend(item for item in node if isinstance(item, (dict, list)))
            continue
        if isinstance(node, dict):
            for key in ("goodsInfoList", "goodsList", "goods_info_list", "list"):
                value = node.get(key)
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    return [item for item in value if isinstance(item, dict)]
            stack.extend(value for value in node.values() if isinstance(value, (dict, list)))
    return []


def _vipshop(query: str, settings) -> tuple[list, dict]:
    app_key = getattr(settings, "vipshop_app_key", "") or ""
    secret = getattr(settings, "vipshop_app_secret", "") or ""
    token = getattr(settings, "vipshop_access_token", "") or ""
    if not (app_key and secret):
        return _skip("vipshop", "唯品会", "CN")
    params = {
        "service": "com.vip.adp.api.open.service.UnionGoodsService",
        "method": "query",
        "version": "1.0.0",
        "timestamp": str(int(time.time())),
        "format": "json",
        "appKey": app_key,
    }
    if token:
        params["accessToken"] = token
    params["sign"] = _vipshop_sign(secret, params)
    payload = json.dumps(
        {
            "keyword": query,
            "page": 1,
            "pageSize": 8,
            "requestId": uuid.uuid4().hex,
            "openId": "default_open_id",
            "realCall": True,
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    body = _post(
        "https://vop.vipapis.com",
        params=params,
        content=payload.encode(),
        headers={"Content-Type": "application/json"},
    )
    goods = _vipshop_goods(body)
    if body is None:
        return _fail("vipshop", "唯品会", "CN")
    rows = []
    for product in goods:
        title = str(product.get("goodsName") or product.get("goods_name") or product.get("name") or "")
        external = str(product.get("goodsId") or product.get("goods_id") or product.get("id") or "")
        cost = _amount(product.get("vipPrice") or product.get("vip_price") or product.get("price"))
        if not title or not external or cost is None:
            continue
        store = product.get("storeInfo") or product.get("store_info") or {}
        shop = store.get("storeName") or store.get("store_name") if isinstance(store, dict) else ""
        rows.append(
            _domestic(
                "vipshop",
                external,
                title,
                cost,
                str(shop or product.get("brandName") or "唯品会"),
                str(product.get("destUrl") or product.get("dest_url") or product.get("url") or ""),
                str(product.get("categoryName") or product.get("cat1stName") or ""),
            )
        )
    return rows[:8], _status("vipshop", "唯品会", "CN", "ok", len(rows[:8]))


def _suning_sign(secret: str, method: str, timestamp: str, app_key: str, version: str, payload: str) -> str:
    digest = base64.b64encode(payload.encode()).decode()
    raw = f"{secret}{method}{timestamp}{app_key}{version}{digest}"
    return hashlib.md5(raw.encode()).hexdigest()


def _suning_goods(body: dict | None) -> list:
    if not isinstance(body, dict):
        return []
    inner = ((body.get("sn_responseContent") or {}).get("sn_body") or {})
    for node in inner.values() if isinstance(inner, dict) else []:
        if not isinstance(node, dict):
            continue
        goods = node.get("commodityList") or node.get("commodity") or node.get("commoditys")
        if isinstance(goods, list):
            return [item for item in goods if isinstance(item, dict)]
        if isinstance(goods, dict):
            return [goods]
    return []


def _suning(query: str, settings) -> tuple[list, dict]:
    app_key = getattr(settings, "suning_app_key", "") or ""
    secret = getattr(settings, "suning_app_secret", "") or ""
    if not (app_key and secret):
        return _skip("suning", "苏宁", "CN")
    method = "suning.netalliance.searchcommodity.query"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    version = "v1.2"
    payload = json.dumps(
        {"sn_request": {"sn_body": {"querySearchcommodity": {"keyword": query, "pageIndex": "1", "size": "8"}}}},
        separators=(",", ":"),
        ensure_ascii=False,
    )
    headers = {
        "Content-Type": "application/json",
        "appMethod": method,
        "appRequestTime": timestamp,
        "format": "json",
        "appKey": app_key,
        "versionNo": version,
        "signInfo": _suning_sign(secret, method, timestamp, app_key, version, payload),
    }
    body = _post("https://open.suning.com/api/http/sopRequest", content=payload.encode(), headers=headers)
    if body is None:
        return _fail("suning", "苏宁", "CN")
    rows = []
    for product in _suning_goods(body):
        title = str(product.get("commodityName") or product.get("commodityname") or product.get("name") or "")
        external = str(product.get("commodityCode") or product.get("commoditycode") or product.get("cmmdtyCode") or "")
        cost = _amount(product.get("snPrice") or product.get("price") or product.get("salePrice"))
        if not title or not external or cost is None:
            continue
        rows.append(
            _domestic(
                "suning",
                external,
                title,
                cost,
                str(product.get("supplierName") or product.get("vendorName") or product.get("shopName") or "苏宁"),
                str(product.get("commodityUrl") or product.get("productUrl") or product.get("url") or ""),
                str(product.get("firstSaleCategoryName") or ""),
            )
        )
    return rows[:8], _status("suning", "苏宁", "CN", "ok", len(rows[:8]))


def _jinritemai_sign(secret: str, params: dict) -> str:
    pieces = "".join(f"{key}{params[key]}" for key in sorted(params) if key not in {"sign", "access_token"})
    raw = f"{secret}{pieces}{secret}"
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()


def _douyin_shop_price(product: dict) -> Decimal | None:
    raw = product.get("coupon_price") or product.get("price") or product.get("product_price")
    amount = _amount(raw)
    if amount is None:
        return None
    if isinstance(raw, int) or (isinstance(raw, str) and raw.isdigit()):
        return amount / Decimal("100")
    return amount


def _douyin_shop(query: str, settings) -> tuple[list, dict]:
    app_key = getattr(settings, "douyin_shop_app_key", "") or ""
    secret = getattr(settings, "douyin_shop_app_secret", "") or ""
    token = getattr(settings, "douyin_shop_access_token", "") or ""
    if not (app_key and secret and token):
        return _skip("douyin_shop", "抖店", "CN")
    biz = json.dumps({"page": 1, "page_size": 8, "title": query}, separators=(",", ":"), ensure_ascii=False)
    params = {
        "method": "buyin.kolMaterialsProductsSearch",
        "app_key": app_key,
        "access_token": token,
        "param_json": biz,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "v": "2",
        "sign_method": "hmac-sha256",
    }
    params["sign"] = _jinritemai_sign(secret, params)
    body = _post("https://openapi-fxg.jinritemai.com/buyin/kolMaterialsProductsSearch", params=params)
    if body is None or (body.get("code") not in (None, 0, "0", 10000, "10000") and "data" not in body):
        return _fail("douyin_shop", "抖店", "CN")
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    products = data.get("products") or data.get("product_list") or []
    if not isinstance(products, list):
        return _fail("douyin_shop", "抖店", "CN")
    rows = []
    for product in products:
        if not isinstance(product, dict):
            continue
        title = str(product.get("title") or product.get("product_name") or product.get("name") or "")
        external = str(product.get("product_id") or product.get("id") or "")
        cost = _douyin_shop_price(product)
        if not title or not external or cost is None:
            continue
        rows.append(
            _domestic(
                "douyin_shop",
                external,
                title,
                cost,
                str(product.get("shop_name") or "抖店"),
                str(product.get("detail_url") or product.get("url") or ""),
            )
        )
    return rows[:8], _status("douyin_shop", "抖店", "CN", "ok", len(rows[:8]))


def _xianyu(query: str, settings) -> tuple[list, dict]:
    """闲鱼：TOP 合作方搜索。公开自助申请常被拒；无钥匙跳过。"""
    app_key = getattr(settings, "xianyu_app_key", "") or ""
    secret = getattr(settings, "xianyu_app_secret", "") or ""
    session = getattr(settings, "xianyu_session", "") or ""
    method = (getattr(settings, "xianyu_search_method", "") or "alibaba.idle.isv.item.search").strip()
    if not (app_key and secret):
        return _skip("xianyu", "闲鱼", "CN")
    params = {
        "method": method,
        "app_key": app_key,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        "q": query,
        "keyword": query,
        "title": query,
        "page_size": "8",
        "page_no": "1",
    }
    if session:
        params["session"] = session
    params["sign"] = _md5_sign(secret, params)
    body = _post("https://eco.taobao.com/router/rest", data=params)
    if body is None or body.get("error_response"):
        return _fail("xianyu", "闲鱼", "CN")
    rows = []
    for product in _xianyu_items(body):
        title = str(
            product.get("title")
            or product.get("item_title")
            or product.get("itemTitle")
            or product.get("name")
            or ""
        )
        external = str(
            product.get("item_id")
            or product.get("itemId")
            or product.get("idle_item_id")
            or product.get("id")
            or ""
        )
        cost = _amount(
            product.get("price")
            or product.get("reserve_price")
            or product.get("sold_price")
            or product.get("item_price")
        )
        if cost is None:
            fen = _amount(product.get("price_fen") or product.get("priceInCent"))
            if fen is not None:
                cost = fen / Decimal("100")
        if not title or not external or cost is None:
            continue
        seller = str(
            product.get("seller_nick")
            or product.get("user_nick")
            or product.get("nick")
            or product.get("seller")
            or "闲鱼"
        )
        url = str(product.get("item_url") or product.get("url") or product.get("detail_url") or "")
        if not url:
            url = f"https://www.goofish.com/item?id={external}"
        rows.append(_domestic("xianyu", external, title, cost, seller, url))
    return rows[:8], _status("xianyu", "闲鱼", "CN", "ok", len(rows[:8]))


def _xianyu_items(body: dict) -> list:
    """Walk TOP response for the first list of product-like dicts."""
    stack = [body]
    seen: set[int] = set()
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, list):
            if node and all(isinstance(item, dict) for item in node[:3]):
                sample = node[0]
                keys = {str(key).lower() for key in sample}
                if keys & {"title", "item_title", "itemtitle", "name"} and keys & {
                    "price",
                    "reserve_price",
                    "sold_price",
                    "item_price",
                    "price_fen",
                    "priceincent",
                    "item_id",
                    "itemid",
                    "id",
                }:
                    return [item for item in node if isinstance(item, dict)]
            for item in node:
                if isinstance(item, (dict, list)):
                    stack.append(item)
            continue
        if isinstance(node, dict):
            for value in node.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
                elif isinstance(value, str) and value[:1] in "{[":
                    try:
                        parsed = json.loads(value)
                    except ValueError:
                        continue
                    if isinstance(parsed, (dict, list)):
                        stack.append(parsed)
    return []


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


def _bestbuy(query: str, settings) -> tuple[list, dict]:
    """Best Buy Products API：邮箱自助拿 Key，易批。"""
    api_key = getattr(settings, "bestbuy_api_key", "") or ""
    if not api_key:
        return _skip("bestbuy", "Best Buy", "US")
    plan = ebay_search_plan(query)
    tokens = [token for token in re.findall(r"[A-Za-z0-9+\-]{2,}", plan["q"]) if token.lower() not in _STOP][:6]
    if not tokens:
        tokens = [plan["q"][:40].strip() or query[:40].strip() or "phone"]
    search = "&".join(f"search={token}" for token in tokens)
    body = _get(
        f"https://api.bestbuy.com/v1/products({search})",
        params={
            "format": "json",
            "show": "sku,name,salePrice,url,manufacturer",
            "pageSize": "8",
            "apiKey": api_key,
        },
    )
    if body is None:
        return _fail("bestbuy", "Best Buy", "US")
    rows = []
    for product in body.get("products") or []:
        if not isinstance(product, dict):
            continue
        title = str(product.get("name") or "")
        external = str(product.get("sku") or "")
        price = _amount(product.get("salePrice"))
        if not title or not external or price is None:
            continue
        brand = str(product.get("manufacturer") or "Best Buy")
        rows.append(_us("bestbuy", external, title, price, brand, str(product.get("url") or "")))
    return rows[:8], _status("bestbuy", "Best Buy", "US", "ok", len(rows[:8]))


def _etsy_price(product: dict) -> Decimal | None:
    price_info = product.get("price")
    if isinstance(price_info, dict):
        amount = _amount(price_info.get("amount"))
        divisor = _amount(price_info.get("divisor")) or Decimal("100")
        currency = str(price_info.get("currency_code") or "USD").upper()
        if amount is None or divisor <= 0 or currency != "USD":
            return None
        return amount / divisor
    return _amount(price_info)


def _etsy(query: str, settings) -> tuple[list, dict]:
    """Etsy Open API v3：listings/active。官方要求 x-api-key 为 keystring:shared_secret。"""
    keystring = (getattr(settings, "etsy_api_keystring", "") or os.environ.get("ETSY_API_KEYSTRING") or "").strip()
    shared = (getattr(settings, "etsy_shared_secret", "") or os.environ.get("ETSY_SHARED_SECRET") or "").strip()
    if not keystring:
        return _skip("etsy", "Etsy", "US")
    plan = ebay_search_plan(query)
    params = {
        "keywords": plan["q"][:80] or query[:80],
        "limit": "25",
        "sort_on": "score",
    }
    if plan.get("max_price"):
        params["min_price"] = "1"
        params["max_price"] = str(max(1, int(plan["max_price"])))
    header = f"{keystring}:{shared}" if shared else keystring
    body = _get(
        "https://api.etsy.com/v3/application/listings/active",
        params=params,
        headers={"x-api-key": header, "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    if body is None:
        return _fail("etsy", "Etsy", "US")
    rows = []
    for product in body.get("results") or []:
        if not isinstance(product, dict):
            continue
        title = str(product.get("title") or "")
        external = str(product.get("listing_id") or "")
        price = _etsy_price(product)
        if not title or not external or price is None:
            continue
        shop = str((product.get("shop") or {}).get("shop_name") or product.get("shop_id") or "Etsy")
        url = str(product.get("url") or f"https://www.etsy.com/listing/{external}")
        rows.append(_us("etsy", external, title, price, str(shop), url))
    return rows[:25], _status("etsy", "Etsy", "US", "ok", len(rows[:25]))


def _google_shopping(query: str, settings) -> tuple[list, dict]:
    """SerpAPI Google Shopping：注册拿 Key 即用，免费档约 250 次/月。"""
    api_key = (getattr(settings, "serpapi_api_key", "") or os.environ.get("SERPAPI_API_KEY") or "").strip()
    if not api_key:
        return _skip("google_shopping", "Google 购物", "US")
    plan = ebay_search_plan(query)
    body = _get(
        "https://serpapi.com/search.json",
        params={
            "engine": "google_shopping",
            "q": plan["q"][:120] or query[:120],
            "gl": "us",
            "hl": "en",
            "api_key": api_key,
        },
        timeout=TIMEOUT,
    )
    if body is None or body.get("error"):
        return _fail("google_shopping", "Google 购物", "US")
    rows = []
    for product in body.get("shopping_results") or []:
        if not isinstance(product, dict):
            continue
        title = str(product.get("title") or "")
        external = str(product.get("product_id") or product.get("position") or "")
        price = _amount(product.get("extracted_price"))
        if not title or not external or price is None:
            continue
        source = str(product.get("source") or "Google Shopping")
        url = str(product.get("product_link") or product.get("link") or "")
        rows.append(_us("google_shopping", external, title, price, source, url))
    return rows[:8], _status("google_shopping", "Google 购物", "US", "ok", len(rows[:8]))


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
    client_id = (getattr(settings, "ebay_client_id", "") or os.environ.get("EBAY_CLIENT_ID") or "").strip()
    secret = (getattr(settings, "ebay_client_secret", "") or os.environ.get("EBAY_CLIENT_SECRET") or "").strip()
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
