"""Shelf quotes the pricing and selection algorithms read.

These rows are the stand-in for the domestic and overseas product pricer feeds.
The HTTP paths that publish them live under `/api/v1/sources`.
"""

DOMESTIC_SOURCE = "/api/v1/sources/pricer/domestic"
OVERSEAS_SOURCE = "/api/v1/sources/pricer/overseas"
CATALOG_SOURCE = "/api/v1/sources/catalog"

DOMESTIC_QUOTES = [
    {"id": "cn-1688-cup", "source": "1688", "market": "CN", "currency": "CNY", "sku": "CN-CUP-500", "name": "智能温控水杯 500ml", "category": "家居", "keywords": ["杯", "cup"], "shelf_price": "68.00"},
    {"id": "cn-taobao-cup", "source": "taobao", "market": "CN", "currency": "CNY", "sku": "CN-CUP-500", "name": "智能温控水杯 500ml", "category": "家居", "keywords": ["杯", "cup"], "shelf_price": "89.00"},
    {"id": "cn-pdd-cup", "source": "pinduoduo", "market": "CN", "currency": "CNY", "sku": "CN-CUP-500", "name": "智能温控水杯 500ml", "category": "家居", "keywords": ["杯", "cup"], "shelf_price": "62.00"},
    {"id": "cn-1688-lamp", "source": "1688", "market": "CN", "currency": "CNY", "sku": "CN-LAMP-01", "name": "折叠露营灯", "category": "户外", "keywords": ["灯", "lamp"], "shelf_price": "39.00"},
    {"id": "cn-taobao-lamp", "source": "taobao", "market": "CN", "currency": "CNY", "sku": "CN-LAMP-01", "name": "折叠露营灯", "category": "户外", "keywords": ["灯", "lamp"], "shelf_price": "55.00"},
    {"id": "cn-1688-pet", "source": "1688", "market": "CN", "currency": "CNY", "sku": "CN-PET-02", "name": "宠物缓流饮水器", "category": "宠物", "keywords": ["宠", "pet"], "shelf_price": "52.00"},
    {"id": "cn-taobao-pet", "source": "taobao", "market": "CN", "currency": "CNY", "sku": "CN-PET-02", "name": "宠物缓流饮水器", "category": "宠物", "keywords": ["宠", "pet"], "shelf_price": "79.00"},
]

OVERSEAS_QUOTES = [
    {"id": "us-amazon-cup", "source": "amazon", "market": "US", "currency": "USD", "sku": "CN-CUP-500", "name": "智能温控水杯 500ml", "category": "家居", "keywords": ["杯", "cup"], "shelf_price": "44.99"},
    {"id": "us-walmart-cup", "source": "walmart", "market": "US", "currency": "USD", "sku": "CN-CUP-500", "name": "智能温控水杯 500ml", "category": "家居", "keywords": ["杯", "cup"], "shelf_price": "41.99"},
    {"id": "hk-hktv-cup", "source": "hktvmall", "market": "HK", "currency": "USD", "sku": "CN-CUP-500", "name": "智能温控水杯 500ml", "category": "家居", "keywords": ["杯", "cup"], "shelf_price": "38.00"},
    {"id": "au-amazon-cup", "source": "amazon", "market": "AU", "currency": "USD", "sku": "CN-CUP-500", "name": "智能温控水杯 500ml", "category": "家居", "keywords": ["杯", "cup"], "shelf_price": "49.00"},
    {"id": "us-amazon-lamp", "source": "amazon", "market": "US", "currency": "USD", "sku": "CN-LAMP-01", "name": "折叠露营灯", "category": "户外", "keywords": ["灯", "lamp"], "shelf_price": "34.99"},
    {"id": "us-walmart-lamp", "source": "walmart", "market": "US", "currency": "USD", "sku": "CN-LAMP-01", "name": "折叠露营灯", "category": "户外", "keywords": ["灯", "lamp"], "shelf_price": "29.99"},
    {"id": "au-amazon-lamp", "source": "amazon", "market": "AU", "currency": "USD", "sku": "CN-LAMP-01", "name": "折叠露营灯", "category": "户外", "keywords": ["灯", "lamp"], "shelf_price": "39.00"},
    {"id": "us-amazon-pet", "source": "amazon", "market": "US", "currency": "USD", "sku": "CN-PET-02", "name": "宠物缓流饮水器", "category": "宠物", "keywords": ["宠", "pet"], "shelf_price": "39.99"},
    {"id": "us-walmart-pet", "source": "walmart", "market": "US", "currency": "USD", "sku": "CN-PET-02", "name": "宠物缓流饮水器", "category": "宠物", "keywords": ["宠", "pet"], "shelf_price": "36.50"},
    {"id": "hk-hktv-pet", "source": "hktvmall", "market": "HK", "currency": "USD", "sku": "CN-PET-02", "name": "宠物缓流饮水器", "category": "宠物", "keywords": ["宠", "pet"], "shelf_price": "33.00"},
]


def _public(row: dict) -> dict:
    return {
        "id": row["id"],
        "source": row["source"],
        "market": row["market"],
        "currency": row["currency"],
        "sku": row["sku"],
        "name": row["name"],
        "category": row["category"],
        "shelf_price": row["shelf_price"],
    }


def _blob(row: dict) -> str:
    return " ".join([row["name"], row["sku"], row["category"], row["source"], *row["keywords"]]).lower()


def query_quotes(book: list[dict], *, q: str = "", sku: str = "", market: str | None = None) -> list[dict]:
    needle = q.strip().lower()
    sku_name = sku.strip().upper()
    rows = []
    for row in book:
        if market and row["market"] != market:
            continue
        if sku_name and row["sku"].upper() != sku_name:
            continue
        if needle and needle not in _blob(row):
            continue
        rows.append(_public(row))
    return rows


def match_quotes(book: list[dict], product: dict, *, market: str | None = None) -> list[dict]:
    sku_name = str(product.get("sku") or product.get("normalized_sku") or "").strip().upper()
    name = str(product.get("name") or "").strip().lower()
    category = str(product.get("category") or "").strip().lower()
    exact = []
    fuzzy = []
    for row in book:
        if market and row["market"] != market:
            continue
        if sku_name and row["sku"].upper() == sku_name:
            exact.append(_public(row))
            continue
        keywords = [item.lower() for item in row["keywords"]]
        named = name and (name in row["name"].lower() or row["name"].lower() in name)
        keyed = any(word and (word in name or word in category) for word in keywords)
        if named or keyed:
            fuzzy.append(_public(row))
    return exact or fuzzy
