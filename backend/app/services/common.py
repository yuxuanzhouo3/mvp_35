import hashlib
import hmac
import uuid
from decimal import Decimal

from config.settings import Settings
from db.store import DocumentStore

from app.core.errors import AppError
from app.core.timeutil import iso, parse_iso, utcnow
from app.services.profit import MARKET_DEFAULTS, calculate


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def base_doc(tenant_id: str, created_by: str, **fields) -> dict:
    now = iso()
    doc = {
        "tenant_id": tenant_id,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "version": 1,
        "deleted_at": None,
    }
    doc.update(fields)
    return doc


def envelope(data, request_id: str) -> dict:
    return {"data": data, "request_id": request_id}


def sign_ledger(secret: str, idempotency_key: str, amount_fen: int, subject: str) -> str:
    payload = f"{idempotency_key}:{amount_fen}:{subject}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def require_doc(store: DocumentStore, collection: str, doc_id: str, tenant_id: str, code: str, message: str) -> dict:
    doc = store.get(collection, doc_id, tenant_id)
    if not doc:
        raise AppError(code, message, 404)
    return doc


def normalize_sku(sku: str) -> str:
    cleaned = sku.strip().upper()
    if not cleaned:
        raise AppError("INVALID_SKU", "SKU 不能为空")
    return cleaned


def market_patch(body: dict) -> dict:
    allowed = [
        "origin_country",
        "target_market",
        "route",
        "incoterm",
        "tax_regime",
        "cost_currency",
        "price_currency",
        "fx_usd_cny",
        "hs_code_hint",
    ]
    return {key: body[key] for key in allowed if key in body and body[key] is not None}


CATALOG = [
    {
        "id": "cat_cup",
        "name": "智能温控水杯 500ml",
        "sku": "CN-CUP-500",
        "category": "家居",
        "cost_cny": "72.00",
        "packaging_cny": "4.00",
        "domestic_freight_cny": "6.00",
        "international_freight_usd": "3.20",
        "target_price_usd": "39.00",
        "supplier": "义乌日用百货",
    },
    {
        "id": "cat_lamp",
        "name": "折叠露营灯",
        "sku": "CN-LAMP-01",
        "category": "户外",
        "cost_cny": "45.00",
        "packaging_cny": "3.00",
        "domestic_freight_cny": "5.00",
        "international_freight_usd": "4.50",
        "target_price_usd": "29.00",
        "supplier": "深圳光电",
    },
    {
        "id": "cat_pet",
        "name": "宠物缓流饮水器",
        "sku": "CN-PET-02",
        "category": "宠物",
        "cost_cny": "58.00",
        "packaging_cny": "5.00",
        "domestic_freight_cny": "8.00",
        "international_freight_usd": "5.00",
        "target_price_usd": "34.00",
        "supplier": "广州宠物用品",
    },
]

CHANNELS = {
    "ecommerce": ["amazon", "temu", "walmart", "taobao", "pinduoduo"],
    "social": ["linkedin", "facebook", "wechat_mini", "douyin", "xiaohongshu", "kuaishou"],
    "expo": ["online_expo", "alibaba_com", "canton_fair", "global_sources", "ciie"],
    "agency": [f"agent_{index}" for index in range(1, 13)],
    "enrichment": ["qichacha", "tianyancha", "qixin"],
    "geo_seo": ["landing"],
    "content_dh": ["content_factory", "digital_human_placeholder", "offline_qr"],
    "cross_border": ["cn_us", "cn_hk", "cn_au", "domestic"],
    "raas": ["site_success", "app_account"],
}

PLANS = [
    {
        "id": "free",
        "name": "免费体验",
        "amount_fen": 0,
        "period": "month",
        "quota": {"analysis": 50, "discovery": 50, "send": 100},
    },
    {
        "id": "growth",
        "name": "成长",
        "amount_fen": 29900,
        "period": "month",
        "quota": {"analysis": 500, "discovery": 500, "send": 2000},
    },
    {
        "id": "scale",
        "name": "规模",
        "amount_fen": 99900,
        "period": "year",
        "quota": {"analysis": 5000, "discovery": 5000, "send": 20000},
    },
]


def search_catalog(query: str) -> list[dict]:
    needle = query.strip().lower()
    rows = CATALOG
    if needle:
        rows = [
            item
            for item in CATALOG
            if needle in item["name"].lower() or needle in item["sku"].lower() or needle in item["category"].lower()
        ]
    return rows


def mock_leads(channel: str, platform: str | None, query: str, seed: str | None, market: str | None = None) -> list[dict]:
    if channel not in CHANNELS:
        raise AppError("UNKNOWN_CHANNEL", "未知获客通道", details={"channel": channel})
    platforms = CHANNELS[channel]
    chosen = platform or platforms[0]
    if chosen not in platforms:
        raise AppError("UNKNOWN_PLATFORM", "该通道没有这个平台", details={"platform": chosen})
    digest = hashlib.sha256(f"{channel}:{chosen}:{query}:{seed or ''}".encode()).hexdigest()
    companies = ["北辰贸易", "海岸选品", "远航制造", "青禾品牌", "林溪供应链", "星澜电商"]
    if channel == "cross_border":
        markets = ["US", "HK", "AU", "US", "CN"]
    else:
        markets = ["US", "US", "HK", "AU", "US"]
    leads = []
    for index, company in enumerate(companies[:5]):
        score = [88, 74, 66, 58, 47][index]
        chosen_market = market or markets[index]
        email = None if index == 4 else f"{chosen}.{index}@buyer.example"
        if index == 3:
            email = f"bounce.{chosen}.{index}@buyer.example"
        leads.append(
            {
                "company": f"{company}-{chosen}",
                "contact_name": f"联系人{index + 1}",
                "email": email,
                "market": chosen_market,
                "quality_score": score,
                "platform": chosen,
                "source_channel": channel,
                "note": "数智人 DEMO 占位，未购买 10 小时包" if chosen == "digital_human_placeholder" else "",
                "exclude_from_ar": channel == "raas",
                "seed": digest[:12],
            }
        )
    return leads


def product_from_body(body: dict, *, source: str) -> dict:
    sku = normalize_sku(body.get("sku") or "")
    name = (body.get("name") or "").strip()
    if not name:
        raise AppError("INVALID_PRODUCT", "商品名称不能为空")
    fields = {
        "name": name,
        "sku": sku,
        "normalized_sku": sku,
        "category": body.get("category") or "未分类",
        "cost_cny": str(body.get("cost_cny") or "0"),
        "packaging_cny": str(body.get("packaging_cny") or "0"),
        "domestic_freight_cny": str(body.get("domestic_freight_cny") or "0"),
        "international_freight_usd": str(body.get("international_freight_usd") or "0"),
        "target_price_usd": str(body.get("target_price_usd") or "0"),
        "hs_code_hint": body.get("hs_code_hint") or "",
        "source": source,
        "context_version": 1,
        **MARKET_DEFAULTS,
    }
    for key in MARKET_DEFAULTS:
        if body.get(key):
            fields[key] = body[key]
    calculate({**fields, "context_version": 1})
    return fields


TRACKED_FIELDS = set(MARKET_DEFAULTS) | {
    "cost_cny",
    "packaging_cny",
    "domestic_freight_cny",
    "international_freight_usd",
    "target_price_usd",
    "name",
    "category",
    "hs_code_hint",
}
CONTEXT_FIELDS = set(MARKET_DEFAULTS) | {
    "cost_cny",
    "packaging_cny",
    "domestic_freight_cny",
    "international_freight_usd",
    "target_price_usd",
}


def apply_market_change(product: dict, patch: dict) -> dict:
    changed = False
    for key, value in patch.items():
        if key not in TRACKED_FIELDS or value is None:
            continue
        if str(product.get(key)) != str(value):
            product[key] = value
            if key in CONTEXT_FIELDS:
                changed = True
    if changed:
        product["context_version"] = int(product.get("context_version") or 1) + 1
        origin = product.get("origin_country") or "CN"
        product["route"] = f"{origin}-{product.get('target_market') or 'US'}"
        calculate(product)
    return product


def within_window(value: str, days: int) -> bool:
    if not value:
        return False
    moment = parse_iso(value)
    return (utcnow() - moment).total_seconds() <= days * 86400


def quota_reserve(store: DocumentStore, tenant_id: str, module: str, idempotency_key: str) -> None:
    existing = store.find_global("usage_ledger", tenant_id=tenant_id, idempotency_key=idempotency_key)
    if existing:
        return
    usage_id = new_id("usage")

    def op(data: dict) -> None:
        balance = None
        for doc in data["collections"].get("quota_balances", {}).values():
            if doc.get("tenant_id") == tenant_id and not doc.get("deleted_at"):
                balance = doc
                break
        if not balance:
            raise AppError("QUOTA_MISSING", "额度未初始化", 409)
        available = int(balance["available"].get(module, 0)) - int(balance["reserved"].get(module, 0))
        if available < 1:
            raise AppError("QUOTA_EXCEEDED", "本月额度已用完", 402, {"module": module})
        for doc in data["collections"].get("usage_ledger", {}).values():
            if doc.get("tenant_id") == tenant_id and doc.get("idempotency_key") == idempotency_key:
                return
        balance["reserved"][module] = int(balance["reserved"].get(module, 0)) + 1
        balance["updated_at"] = iso()
        data["collections"].setdefault("usage_ledger", {})[usage_id] = base_doc(
            tenant_id,
            "system",
            id=usage_id,
            module=module,
            idempotency_key=idempotency_key,
            status="reserved",
            amount=1,
        )

    store.transaction(op)


def quota_finish(store: DocumentStore, tenant_id: str, module: str, idempotency_key: str, success: bool) -> None:
    def op(data: dict) -> None:
        entry = None
        for doc in data["collections"].get("usage_ledger", {}).values():
            if doc.get("tenant_id") == tenant_id and doc.get("idempotency_key") == idempotency_key:
                entry = doc
                break
        balance = None
        for doc in data["collections"].get("quota_balances", {}).values():
            if doc.get("tenant_id") == tenant_id and not doc.get("deleted_at"):
                balance = doc
                break
        if not entry or not balance or entry.get("status") != "reserved":
            return
        balance["reserved"][module] = max(0, int(balance["reserved"].get(module, 0)) - 1)
        if success:
            balance["available"][module] = max(0, int(balance["available"].get(module, 0)) - 1)
            entry["status"] = "confirmed"
        else:
            entry["status"] = "released"
        balance["updated_at"] = iso()
        entry["updated_at"] = iso()

    store.transaction(op)


def post_signed_ledger(
    store: DocumentStore,
    settings: Settings,
    *,
    collection: str,
    tenant_id: str,
    created_by: str,
    amount_fen: int,
    subject: str,
    idempotency_key: str,
    signature: str,
    meta: dict,
) -> dict:
    if not isinstance(amount_fen, int) or isinstance(amount_fen, bool) or amount_fen <= 0:
        raise AppError("INVALID_AMOUNT", "金额必须是正整数分")
    expected = sign_ledger(settings.ledger_hmac_secret, idempotency_key, amount_fen, subject)
    if not hmac.compare_digest(expected, signature or ""):
        raise AppError("LEDGER_SIGNATURE_INVALID", "验签失败，未入账", 401)
    existing = store.find_global(collection, tenant_id=tenant_id, idempotency_key=idempotency_key)
    if existing:
        return existing
    doc = base_doc(
        tenant_id,
        created_by,
        id=new_id("ledger"),
        amount_fen=amount_fen,
        subject=subject,
        idempotency_key=idempotency_key,
        status="posted",
        **meta,
    )
    return store.insert(collection, doc)


def median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal(2)


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]
