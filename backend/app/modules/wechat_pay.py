"""WeChat Pay API v3 notify verification.

Same rules as mvp_1: RSA-SHA256 over the raw body, then AES-256-GCM with the
32-byte API v3 key. A verified SUCCESS or CLOSED notice is the only way this
module posts a subscription, invoice, or payment event.
"""

import base64
import json
import time
import uuid

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.errors import AppError
from app.modules.payment import book_verified_payment
from config.settings import Settings
from db.store import DocumentStore

_CERT_CACHE: dict[str, str] = {}


def accept_wechat_notification(
    store: DocumentStore,
    settings: Settings,
    *,
    body: str,
    timestamp: str | None,
    nonce: str | None,
    signature: str | None,
    serial: str | None,
) -> dict:
    if not timestamp or not nonce or not signature or not serial:
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    public_pem = _platform_public_key(settings, serial)
    if not _rsa_ok(public_pem, timestamp, nonce, body, signature):
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    try:
        notice = json.loads(body)
        resource = notice.get("resource") or {}
        decrypted = json.loads(_decrypt(settings.wechat_pay_api_v3_key, resource))
    except (json.JSONDecodeError, ValueError, AppError):
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401) from None
    trade = decrypted.get("trade_state")
    status = {"SUCCESS": "succeeded", "CLOSED": "failed", "PAYERROR": "failed"}.get(trade or "")
    if not status:
        raise AppError("INVALID_PAYMENT_STATUS", "无法识别的支付结果")
    amount = (decrypted.get("amount") or {}).get("total")
    external_id = decrypted.get("transaction_id") or notice.get("id") or ""
    if not external_id:
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    return book_verified_payment(
        store,
        payment_id=decrypted.get("out_trade_no") or "",
        status=status,
        external_id=external_id,
        amount_fen=int(amount) if amount is not None else None,
    )


def _rsa_ok(public_pem: str, timestamp: str, nonce: str, body: str, signature: str) -> bool:
    try:
        key = serialization.load_pem_public_key(public_pem.encode())
        key.verify(base64.b64decode(signature), f"{timestamp}\n{nonce}\n{body}\n".encode(), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def _decrypt(api_v3_key: str, resource: dict) -> str:
    if resource.get("algorithm") != "AEAD_AES_256_GCM":
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    key = (api_v3_key or "").encode()
    if len(key) != 32:
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    return AESGCM(key).decrypt(
        resource.get("nonce", "").encode(),
        base64.b64decode(resource.get("ciphertext") or ""),
        (resource.get("associated_data") or "").encode(),
    ).decode()


def _platform_public_key(settings: Settings, serial: str) -> str:
    pinned = (settings.wechat_pay_platform_public_key or "").replace("\\n", "\n").strip()
    if pinned:
        return pinned
    cached = _CERT_CACHE.get(serial)
    if cached:
        return cached
    _refresh_platform_certs(settings)
    cached = _CERT_CACHE.get(serial)
    if not cached:
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    return cached


def _refresh_platform_certs(settings: Settings) -> None:
    url_path = "/v3/certificates"
    authorization = _authorization(settings, "GET", url_path, "")
    response = httpx.get(
        f"https://api.mch.weixin.qq.com{url_path}",
        headers={"Accept": "application/json", "Authorization": authorization},
        timeout=20,
    )
    if response.status_code >= 400:
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    for item in response.json().get("data") or []:
        encrypted = item.get("encrypt_certificate") or {}
        serial_no = item.get("serial_no")
        if not serial_no or not encrypted:
            continue
        cert_pem = _decrypt(settings.wechat_pay_api_v3_key, encrypted)
        _CERT_CACHE[serial_no] = _public_from_cert(cert_pem)


def _public_from_cert(cert_pem: str) -> str:
    from cryptography.x509 import load_pem_x509_certificate

    cert = load_pem_x509_certificate(cert_pem.encode())
    return cert.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def create_native_order(settings: Settings, *, out_trade_no: str, amount_fen: int, description: str) -> str:
    if not (
        settings.wechat_pay_appid
        and settings.wechat_pay_mchid
        and settings.wechat_pay_private_key
        and settings.wechat_pay_serial_no
    ):
        raise AppError("NOT_ENABLED", "微信支付未开通", 501, {"flag": "payment.wechat", "placeholder": True})
    notify = settings.wechat_pay_notify_url or "https://pickglobal.mornscience.top/api/v1/webhooks/wechat-pay"
    if not notify.startswith("https://"):
        raise AppError("NOT_ENABLED", "微信支付回调地址未配置", 501, {"flag": "payment.wechat", "placeholder": True})
    url_path = "/v3/pay/transactions/native"
    payload = json.dumps(
        {
            "mchid": settings.wechat_pay_mchid,
            "out_trade_no": out_trade_no,
            "appid": settings.wechat_pay_appid,
            "description": description,
            "notify_url": notify,
            "amount": {"total": amount_fen, "currency": "CNY"},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    authorization = _authorization(settings, "POST", url_path, payload)
    try:
        response = httpx.post(
            f"https://api.mch.weixin.qq.com{url_path}",
            content=payload.encode(),
            headers={"Authorization": authorization, "Accept": "application/json", "Content-Type": "application/json"},
            timeout=20,
        )
        body = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise AppError("WECHAT_PAY_FAILED", "微信支付下单没有完成", 502) from exc
    code_url = body.get("code_url")
    if not code_url:
        raise AppError("WECHAT_PAY_FAILED", "微信支付下单没有完成", 502)
    return code_url


def _authorization(settings: Settings, method: str, url_path: str, body: str) -> str:
    private_pem = (settings.wechat_pay_private_key or "").replace("\\n", "\n").strip()
    mchid = settings.wechat_pay_mchid
    serial_no = settings.wechat_pay_serial_no
    if not private_pem or not mchid or not serial_no:
        raise AppError("PAYMENT_SIGNATURE_INVALID", "验签失败，未入账", 401)
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    message = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n".encode()
    private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
    signature = base64.b64encode(private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())).decode()
    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",nonce_str="{nonce}",'
        f'signature="{signature}",timestamp="{timestamp}",serial_no="{serial_no}"'
    )
