"""Alipay page pay and RSA2 notify verification. A bad signature does not post."""

import base64
import json
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlencode

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.core.errors import AppError
from app.modules.payment import book_verified_payment
from config.settings import Settings
from db.store import DocumentStore


def ready(settings: Settings) -> bool:
    return bool(settings.alipay_app_id and settings.alipay_private_key and _public_key(settings))


def page_pay_url(settings: Settings, *, out_trade_no: str, amount_fen: int, subject: str) -> str:
    if not ready(settings):
        raise AppError("NOT_ENABLED", "支付宝未开通", 501, {"flag": "payment.alipay", "placeholder": True})
    notify = settings.alipay_notify_url or "https://pickglobal.mornscience.top/api/v1/webhooks/alipay"
    params = {
        "app_id": settings.alipay_app_id,
        "method": "alipay.trade.page.pay",
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": notify,
        "biz_content": json.dumps(
            {
                "out_trade_no": out_trade_no,
                "total_amount": f"{Decimal(amount_fen) / Decimal(100):.2f}",
                "subject": subject,
                "product_code": "FAST_INSTANT_TRADE_PAY",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    params["sign"] = _sign(settings.alipay_private_key, params)
    gateway = (settings.alipay_gateway_url or "https://openapi.alipay.com/gateway.do").rstrip("?")
    return f"{gateway}?{urlencode(params)}"


def accept_notification(store: DocumentStore, settings: Settings, params: dict[str, str]) -> dict:
    public_key = _public_key(settings)
    if not public_key or not _verify(public_key, params):
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    trade = params.get("trade_status")
    status = {"TRADE_SUCCESS": "succeeded", "TRADE_FINISHED": "succeeded", "TRADE_CLOSED": "failed"}.get(trade or "")
    if not status:
        raise AppError("INVALID_PAYMENT_STATUS", "无法识别的支付结果")
    amount = params.get("total_amount")
    try:
        amount_fen = int((Decimal(amount) * 100).quantize(Decimal("1"))) if amount else None
    except Exception as exc:
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401) from exc
    external_id = params.get("trade_no") or ""
    if not external_id:
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    return book_verified_payment(
        store,
        payment_id=params.get("out_trade_no") or "",
        status=status,
        external_id=external_id,
        amount_fen=amount_fen,
    )


def _public_key(settings: Settings) -> str:
    return (settings.alipay_alipay_public_key or settings.alipay_public_key or "").strip()


def _sign(private_key: str, params: dict) -> str:
    content = _content(params)
    key = serialization.load_pem_private_key(_pem(private_key, "PRIVATE KEY").encode(), password=None)
    return base64.b64encode(key.sign(content.encode(), padding.PKCS1v15(), hashes.SHA256())).decode()


def _verify(public_key: str, params: dict[str, str]) -> bool:
    signature = params.get("sign") or ""
    if params.get("sign_type") not in {None, "", "RSA2"} or not signature:
        return False
    try:
        key = serialization.load_pem_public_key(_pem(public_key, "PUBLIC KEY").encode())
        key.verify(base64.b64decode(signature), _content(params).encode(), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def _content(params: dict) -> str:
    skipped = {"sign", "sign_type"}
    return "&".join(f"{key}={params[key]}" for key in sorted(params) if key not in skipped and params[key] not in {None, ""})


def _pem(value: str, label: str) -> str:
    text = value.replace("\\n", "\n").strip()
    if "BEGIN" in text:
        return text
    body = "".join(text.split())
    lines = [body[index : index + 64] for index in range(0, len(body), 64)]
    return f"-----BEGIN {label}-----\n" + "\n".join(lines) + f"\n-----END {label}-----"
