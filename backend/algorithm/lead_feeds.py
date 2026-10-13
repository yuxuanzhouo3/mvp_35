"""Official lead sources for B1–B5.

A platform with its keys missing stays on the five demo leads. A platform with
keys calls only that platform's official API. A failed call does not mix the
demo list back in. Canton Fair, Global Sources, CIIE, and online expos have no
stable public buyer API, so they stay on the demo list.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app.services.common import mock_leads

TIMEOUT = 6


def discover(store, settings, payload: dict, tenant_id: str = "") -> tuple[list[dict], str]:
    channel = payload["channel"]
    query = payload.get("query") or ""
    market = payload.get("target_market") or None
    demo = mock_leads(channel, payload.get("platform"), query, payload.get("seed_analysis_id"), market)
    platform = demo[0]["platform"]
    if channel == "agency":
        pushed = _agency_rows(store, tenant_id, platform)
        if pushed:
            return _stamp_market(pushed, market), "live"
        return demo, "mock"
    live = _live(channel, platform, query, settings)
    if live is None:
        return demo, "mock"
    return _stamp_market(live, market), "live"


def _stamp_market(rows: list[dict], market: str | None) -> list[dict]:
    if not market:
        return rows
    return [{**row, "market": market} for row in rows]


def _agency_rows(store, tenant_id: str, platform: str) -> list[dict]:
    if store is None or not tenant_id:
        return []
    found = store.query("agency_inbox", tenant_id=tenant_id, filters={"platform": platform}, limit=50)
    rows = []
    for item in found["items"]:
        company = str(item.get("company") or "").strip()
        if not company:
            continue
        rows.append(
            _lead(
                "agency",
                platform,
                company,
                str(item.get("contact_name") or ""),
                item.get("email") or None,
                str(item.get("market") or "US"),
                str(item.get("external_id") or item["id"]),
            )
        )
    return rows


def _live(channel: str, platform: str, query: str, settings) -> list[dict] | None:
    callers = {
        ("ecommerce", "amazon"): _amazon,
        ("ecommerce", "walmart"): _walmart,
        ("ecommerce", "taobao"): _taobao,
        ("ecommerce", "pinduoduo"): _pdd,
        ("ecommerce", "temu"): _temu,
        ("social", "linkedin"): _linkedin,
        ("social", "facebook"): _facebook,
        ("social", "wechat_mini"): _wecom,
        ("social", "douyin"): _douyin,
        ("social", "xiaohongshu"): _xhs,
        ("social", "kuaishou"): _kuaishou,
        ("expo", "alibaba_com"): _alibaba_intl,
        ("enrichment", "qichacha"): _qichacha,
        ("enrichment", "tianyancha"): _tianyancha,
        ("enrichment", "qixin"): _qixin,
    }
    caller = callers.get((channel, platform))
    if caller is None:
        return None
    return caller(settings, query)


def _lead(channel: str, platform: str, company: str, contact: str, email: str | None, market: str, external_id: str) -> dict:
    cleaned = company.strip() or external_id or platform
    address = (email or "").strip() or None
    return {
        "company": cleaned[:80],
        "contact_name": (contact or "").strip()[:40],
        "email": address,
        "market": market if market in {"US", "HK", "AU", "CN"} else "US",
        "quality_score": 74 if address else 47,
        "platform": platform,
        "source_channel": channel,
        "external_id": external_id,
        "note": "",
        "exclude_from_ar": False,
    }


def _get(url: str, *, params: dict | None = None, headers: dict | None = None) -> dict | None:
    try:
        response = httpx.get(url, params=params, headers=headers, timeout=TIMEOUT, follow_redirects=True)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _post(url: str, *, data: dict | None = None, json_body: dict | None = None, headers: dict | None = None) -> dict | None:
    try:
        response = httpx.post(url, data=data, json=json_body, headers=headers, timeout=TIMEOUT, follow_redirects=True)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _md5_upper(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest().upper()


def _since(days: int = 7) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _amazon(settings, query: str) -> list[dict] | None:
    del query
    client_id = getattr(settings, "amazon_sp_client_id", "") or ""
    secret = getattr(settings, "amazon_sp_client_secret", "") or ""
    refresh = getattr(settings, "amazon_sp_refresh_token", "") or ""
    if not (client_id and secret and refresh):
        return None
    token_body = _post(
        "https://api.amazon.com/auth/o2/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh, "client_id": client_id, "client_secret": secret},
    )
    token = (token_body or {}).get("access_token")
    if not token:
        return []
    body = _get(
        "https://sellingpartnerapi-na.amazon.com/orders/v0/orders",
        params={"MarketplaceIds": "ATVPDKIKX0DER", "CreatedAfter": _since(), "MaxResultsPerPage": "10"},
        headers={"x-amz-access-token": token},
    )
    rows = []
    for order in (((body or {}).get("payload") or {}).get("Orders") or [])[:8]:
        if not isinstance(order, dict):
            continue
        buyer = order.get("BuyerInfo") or {}
        ship = order.get("ShippingAddress") or {}
        country = str(ship.get("CountryCode") or "US")
        rows.append(
            _lead(
                "ecommerce",
                "amazon",
                str(buyer.get("BuyerName") or ship.get("Name") or order.get("AmazonOrderId") or ""),
                str(buyer.get("BuyerName") or ""),
                buyer.get("BuyerEmail") or None,
                country,
                str(order.get("AmazonOrderId") or ""),
            )
        )
    return rows


def _walmart(settings, query: str) -> list[dict] | None:
    del query
    client_id = getattr(settings, "walmart_market_client_id", "") or ""
    secret = getattr(settings, "walmart_market_client_secret", "") or ""
    if not (client_id and secret):
        return None
    token_body = _post(
        "https://marketplace.walmartapis.com/v3/token",
        data={"grant_type": "client_credentials"},
        headers={
            "Authorization": "Basic " + __import__("base64").b64encode(f"{client_id}:{secret}".encode()).decode(),
            "WM_QOS.CORRELATION_ID": uuid.uuid4().hex,
            "WM_SVC.NAME": "Walmart Marketplace",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    token = (token_body or {}).get("access_token")
    if not token:
        return []
    body = _get(
        "https://marketplace.walmartapis.com/v3/orders",
        params={"createdStartDate": _since(), "limit": "10"},
        headers={
            "WM_SEC.ACCESS_TOKEN": token,
            "WM_QOS.CORRELATION_ID": uuid.uuid4().hex,
            "WM_SVC.NAME": "Walmart Marketplace",
            "Accept": "application/json",
        },
    )
    orders = ((body or {}).get("list") or {}).get("elements") or {}
    rows = []
    for order in (orders.get("order") or [])[:8]:
        if not isinstance(order, dict):
            continue
        ship = ((order.get("shippingInfo") or {}).get("postalAddress") or {})
        rows.append(
            _lead(
                "ecommerce",
                "walmart",
                str(ship.get("name") or order.get("purchaseOrderId") or ""),
                str(ship.get("name") or ""),
                order.get("customerEmailId") or None,
                "US",
                str(order.get("purchaseOrderId") or ""),
            )
        )
    return rows


def _taobao(settings, query: str) -> list[dict] | None:
    del query
    app_key = getattr(settings, "taobao_app_key", "") or ""
    secret = getattr(settings, "taobao_app_secret", "") or ""
    session = getattr(settings, "taobao_session", "") or ""
    if not (app_key and secret and session):
        return None
    params = {
        "method": "taobao.trades.sold.get",
        "app_key": app_key,
        "session": session,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        "fields": "tid,buyer_nick,receiver_name",
        "page_size": "10",
    }
    raw = secret + "".join(f"{key}{params[key]}" for key in sorted(params)) + secret
    params["sign"] = _md5_upper(raw)
    body = _post("https://eco.taobao.com/router/rest", data=params)
    if body is None or body.get("error_response"):
        return []
    trades = ((body.get("trades_sold_get_response") or {}).get("trades") or {}).get("trade") or []
    rows = []
    for trade in trades[:8]:
        if not isinstance(trade, dict):
            continue
        rows.append(
            _lead(
                "ecommerce",
                "taobao",
                str(trade.get("buyer_nick") or trade.get("receiver_name") or trade.get("tid") or ""),
                str(trade.get("receiver_name") or ""),
                None,
                "CN",
                str(trade.get("tid") or ""),
            )
        )
    return rows


def _pdd(settings, query: str) -> list[dict] | None:
    del query
    client_id = getattr(settings, "pdd_client_id", "") or ""
    secret = getattr(settings, "pdd_client_secret", "") or ""
    token = getattr(settings, "pdd_access_token", "") or ""
    if not (client_id and secret and token):
        return None
    end = int(datetime.now().timestamp())
    params = {
        "type": "pdd.order.list.get",
        "client_id": client_id,
        "access_token": token,
        "timestamp": str(end),
        "data_type": "JSON",
        "start_confirm_at": str(end - 7 * 86400),
        "end_confirm_at": str(end),
        "order_status": "5",
        "page": "1",
        "page_size": "10",
    }
    raw = secret + "".join(f"{key}{params[key]}" for key in sorted(params)) + secret
    params["sign"] = _md5_upper(raw)
    body = _post("https://gw-api.pinduoduo.com/api/router", data=params)
    if body is None or body.get("error_response"):
        return []
    orders = ((body.get("order_list_get_response") or {}).get("order_list")) or []
    rows = []
    for order in orders[:8]:
        if not isinstance(order, dict):
            continue
        rows.append(
            _lead(
                "ecommerce",
                "pinduoduo",
                str(order.get("receiver_name") or order.get("order_sn") or ""),
                str(order.get("receiver_name") or ""),
                None,
                "CN",
                str(order.get("order_sn") or ""),
            )
        )
    return rows


def _temu(settings, query: str) -> list[dict] | None:
    del query
    app_key = getattr(settings, "temu_app_key", "") or ""
    secret = getattr(settings, "temu_app_secret", "") or ""
    token = getattr(settings, "temu_access_token", "") or ""
    if not (app_key and secret and token):
        return None
    params = {
        "type": "bg.order.list.get",
        "app_key": app_key,
        "access_token": token,
        "timestamp": str(int(datetime.now().timestamp())),
        "data_type": "JSON",
        "pageNumber": "1",
        "pageSize": "10",
    }
    raw = secret + "".join(f"{key}{params[key]}" for key in sorted(params)) + secret
    params["sign"] = _md5_upper(raw)
    body = _post("https://openapi-b-global.temu.com/openapi/router", data=params)
    if not body:
        return []
    orders = ((body.get("result") or {}).get("pageItems")) or body.get("result") or []
    if isinstance(orders, dict):
        orders = orders.get("orderList") or []
    rows = []
    for order in orders[:8]:
        if not isinstance(order, dict):
            continue
        rows.append(
            _lead(
                "ecommerce",
                "temu",
                str(order.get("mallName") or order.get("parentOrderSn") or order.get("orderSn") or ""),
                "",
                None,
                "US",
                str(order.get("parentOrderSn") or order.get("orderSn") or ""),
            )
        )
    return rows


def _linkedin(settings, query: str) -> list[dict] | None:
    del query
    token = getattr(settings, "linkedin_access_token", "") or ""
    account = getattr(settings, "linkedin_ad_account_id", "") or ""
    if not (token and account):
        return None
    body = _get(
        "https://api.linkedin.com/rest/leadFormResponses",
        params={"q": "owner", "owner": f"(sponsoredAccount:urn:li:sponsoredAccount:{account})", "count": "10"},
        headers={
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": "202506",
            "X-Restli-Protocol-Version": "2.0.0",
        },
    )
    if body is None:
        return []
    rows = []
    for item in (body.get("elements") or [])[:8]:
        if not isinstance(item, dict):
            continue
        answers = item.get("formResponse") or item.get("answers") or {}
        email, company, name = _scan_contact(answers if isinstance(answers, dict) else {"answers": answers})
        rows.append(_lead("social", "linkedin", company or name or str(item.get("id") or ""), name, email, "US", str(item.get("id") or "")))
    return rows


def _facebook(settings, query: str) -> list[dict] | None:
    del query
    page = getattr(settings, "facebook_page_id", "") or ""
    token = getattr(settings, "facebook_page_access_token", "") or ""
    if not (page and token):
        return None
    forms = _get(f"https://graph.facebook.com/v21.0/{page}/leadgen_forms", params={"access_token": token, "limit": "5"})
    if forms is None:
        return []
    rows = []
    for form in (forms.get("data") or [])[:3]:
        if not isinstance(form, dict) or not form.get("id"):
            continue
        leads = _get(
            f"https://graph.facebook.com/v21.0/{form['id']}/leads",
            params={"access_token": token, "limit": "8"},
        )
        for lead in ((leads or {}).get("data") or []):
            fields = {str(item.get("name") or "").lower(): item.get("values", [""])[0] for item in lead.get("field_data") or [] if isinstance(item, dict)}
            email = fields.get("email") or None
            company = fields.get("company_name") or fields.get("company") or fields.get("full_name") or str(lead.get("id") or "")
            rows.append(_lead("social", "facebook", str(company), str(fields.get("full_name") or ""), email, "US", str(lead.get("id") or "")))
    return rows[:8]


def _wecom(settings, query: str) -> list[dict] | None:
    del query
    corp = getattr(settings, "wecom_corp_id", "") or ""
    secret = getattr(settings, "wecom_contact_secret", "") or ""
    userid = getattr(settings, "wecom_follow_userid", "") or ""
    if not (corp and secret and userid):
        return None
    token_body = _get("https://qyapi.weixin.qq.com/cgi-bin/gettoken", params={"corpid": corp, "corpsecret": secret})
    token = (token_body or {}).get("access_token")
    if not token:
        return []
    listed = _get(
        "https://qyapi.weixin.qq.com/cgi-bin/externalcontact/list",
        params={"access_token": token, "userid": userid},
    )
    rows = []
    for external in ((listed or {}).get("external_userid") or [])[:8]:
        detail = _get(
            "https://qyapi.weixin.qq.com/cgi-bin/externalcontact/get",
            params={"access_token": token, "external_userid": external},
        )
        contact = ((detail or {}).get("external_contact") or {})
        rows.append(
            _lead(
                "social",
                "wechat_mini",
                str(contact.get("corp_name") or contact.get("name") or external),
                str(contact.get("name") or ""),
                None,
                "CN",
                str(external),
            )
        )
    return rows


def _douyin(settings, query: str) -> list[dict] | None:
    del query
    token = getattr(settings, "douyin_access_token", "") or ""
    if not token:
        return None
    now = int(datetime.now().timestamp())
    body = _post(
        "https://open.douyin.com/enterprise/leads/user/list/",
        json_body={"start_time": now - 7 * 86400, "end_time": now, "page": 1, "page_size": 10},
        headers={"access-token": token},
    )
    if body is None:
        return []
    data = body.get("data") or {}
    people = data.get("list") or data.get("users") or []
    rows = []
    for person in people[:8]:
        if not isinstance(person, dict):
            continue
        rows.append(
            _lead(
                "social",
                "douyin",
                str(person.get("nickname") or person.get("intention_user_id") or person.get("open_id") or ""),
                str(person.get("nickname") or ""),
                None,
                "CN",
                str(person.get("intention_user_id") or person.get("open_id") or ""),
            )
        )
    return rows


def _xhs(settings, query: str) -> list[dict] | None:
    del query
    token = getattr(settings, "xhs_access_token", "") or ""
    if not token:
        return None
    body = _post(
        "https://adapi.xiaohongshu.com/api/open/jg/clue/list",
        json_body={"page_num": 1, "page_size": 10},
        headers={"Access-Token": token},
    )
    if body is None:
        return []
    rows = []
    for item in ((body.get("data") or {}).get("list") or body.get("data") or [])[:8]:
        if not isinstance(item, dict):
            continue
        rows.append(
            _lead(
                "social",
                "xiaohongshu",
                str(item.get("company") or item.get("name") or item.get("clue_id") or ""),
                str(item.get("name") or ""),
                item.get("email") or None,
                "CN",
                str(item.get("clue_id") or item.get("id") or ""),
            )
        )
    return rows


def _kuaishou(settings, query: str) -> list[dict] | None:
    del query
    token = getattr(settings, "kuaishou_access_token", "") or ""
    if not token:
        return None
    body = _get("https://open.kuaishou.com/openapi/leads/list", params={"access_token": token, "count": "10"})
    if body is None:
        return []
    rows = []
    for item in ((body.get("data") or {}).get("list") or [])[:8]:
        if not isinstance(item, dict):
            continue
        rows.append(
            _lead(
                "social",
                "kuaishou",
                str(item.get("nickname") or item.get("lead_id") or ""),
                str(item.get("nickname") or ""),
                None,
                "CN",
                str(item.get("lead_id") or item.get("id") or ""),
            )
        )
    return rows


def _alibaba_intl(settings, query: str) -> list[dict] | None:
    app_key = getattr(settings, "alibaba_intl_app_key", "") or ""
    secret = getattr(settings, "alibaba_intl_app_secret", "") or ""
    token = getattr(settings, "alibaba_intl_access_token", "") or ""
    if not (app_key and secret and token):
        return None
    import hmac

    path = f"param2/1/com.alibaba.intl/alibaba.intl.inquiry.list/{app_key}"
    params = {"access_token": token, "keyword": query or ""}
    signed = path + "".join(f"{key}{params[key]}" for key in sorted(params))
    params["_aop_signature"] = hmac.new(secret.encode(), signed.encode(), hashlib.sha1).hexdigest().upper()
    body = _post(f"https://gw.api.alibaba.com/openapi/{path}", data=params)
    if not body:
        return []
    items = body.get("inquiries") or body.get("result") or []
    if isinstance(items, dict):
        items = items.get("inquiries") or []
    rows = []
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        country = str(item.get("country") or item.get("buyerCountry") or "US").upper()
        rows.append(
            _lead(
                "expo",
                "alibaba_com",
                str(item.get("companyName") or item.get("buyerName") or item.get("inquiryId") or ""),
                str(item.get("contactName") or ""),
                item.get("email") or None,
                country if country in {"US", "HK", "AU", "CN"} else "US",
                str(item.get("inquiryId") or item.get("id") or ""),
            )
        )
    return rows


def _qichacha(settings, query: str) -> list[dict] | None:
    app_key = getattr(settings, "qichacha_app_key", "") or ""
    secret = getattr(settings, "qichacha_secret_key", "") or ""
    if not (app_key and secret and query.strip()):
        return None if not (app_key and secret) else []
    timespan = str(int(datetime.now().timestamp()))
    body = _get(
        "https://api.qichacha.com/FuzzySearch/GetList",
        params={"key": app_key, "searchKey": query, "pageSize": "5"},
        headers={"Token": _md5_upper(app_key + timespan + secret), "Timespan": timespan},
    )
    if body is None:
        return []
    rows = []
    for item in (body.get("Result") or [])[:5]:
        if not isinstance(item, dict):
            continue
        rows.append(
            _lead(
                "enrichment",
                "qichacha",
                str(item.get("Name") or ""),
                str(item.get("OperName") or ""),
                item.get("Email") or None,
                "CN",
                str(item.get("CreditCode") or item.get("KeyNo") or ""),
            )
        )
    return rows


def _tianyancha(settings, query: str) -> list[dict] | None:
    token = getattr(settings, "tianyancha_token", "") or ""
    if not token:
        return None
    if not query.strip():
        return []
    body = _get(
        "https://open.api.tianyancha.com/services/open/search/2.0",
        params={"word": query, "pageSize": "5", "pageNum": "1"},
        headers={"Authorization": token},
    )
    if body is None:
        return []
    rows = []
    for item in (((body.get("result") or {}).get("items")) or [])[:5]:
        if not isinstance(item, dict):
            continue
        rows.append(
            _lead(
                "enrichment",
                "tianyancha",
                str(item.get("name") or ""),
                str(item.get("legalPersonName") or ""),
                item.get("email") or None,
                "CN",
                str(item.get("creditCode") or item.get("id") or ""),
            )
        )
    return rows


def _qixin(settings, query: str) -> list[dict] | None:
    app_key = getattr(settings, "qixin_app_key", "") or ""
    secret = getattr(settings, "qixin_secret_key", "") or ""
    if not (app_key and secret):
        return None
    if not query.strip():
        return []
    timespan = str(int(datetime.now().timestamp() * 1000))
    body = _get(
        "https://api.qixin.com/APIService/v2/search/advSearch",
        params={"keyword": query},
        headers={
            "Auth-Version": "2.0",
            "appkey": app_key,
            "timestamp": timespan,
            "sign": hashlib.md5((app_key + timespan + secret).encode()).hexdigest(),
        },
    )
    if body is None:
        return []
    data = body.get("data") or {}
    items = data.get("items") or data.get("list") or []
    rows = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        rows.append(
            _lead(
                "enrichment",
                "qixin",
                str(item.get("name") or item.get("companyName") or ""),
                str(item.get("operName") or item.get("legalPerson") or ""),
                item.get("email") or None,
                "CN",
                str(item.get("creditNo") or item.get("credit_no") or item.get("id") or ""),
            )
        )
    return rows


def _scan_contact(payload: dict) -> tuple[str | None, str, str]:
    email, company, name = None, "", ""
    blobs = []
    if isinstance(payload, dict):
        blobs.append(payload)
        for value in payload.values():
            if isinstance(value, list):
                blobs.extend(item for item in value if isinstance(item, dict))
    for item in blobs:
        key = str(item.get("question") or item.get("name") or item.get("questionId") or "").lower()
        value = str(item.get("answer") or item.get("value") or "")
        if "email" in key or "@" in value:
            email = value if "@" in value else email
        if "company" in key or "公司" in key:
            company = value or company
        if "name" in key or "姓名" in key:
            name = value or name
    return email, company, name
