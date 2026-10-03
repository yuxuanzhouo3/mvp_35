"""SMTP email codes and Tencent Cloud SMS. Unconfigured channels do not pretend to send."""

import hashlib
import hmac
import json
import smtplib
import time
from datetime import datetime, timezone
from email.message import EmailMessage

import httpx

from app.core.errors import AppError
from config.settings import Settings


def email_ready(settings: Settings) -> bool:
    return bool(settings.auth_email_smtp_host and settings.auth_email_smtp_user and settings.auth_email_smtp_pass)


def sms_ready(settings: Settings) -> bool:
    return bool(
        settings.sms_secret_id
        and settings.sms_secret_key
        and settings.sms_sdk_app_id
        and settings.sms_sign_name
        and settings.sms_template_id
    )


def send_reset_link(settings: Settings, to: str, token: str) -> None:
    from urllib.parse import quote

    origin = (settings.public_web_origin or "https://pickglobal.mornscience.top").rstrip("/")
    link = f"{origin}/reset?token={quote(token)}"
    _smtp(
        settings,
        to,
        "重置 PickGlobal 密码",
        f"请在 1 小时内打开下面的链接设置新密码：\n{link}\n如果不是你本人操作，请忽略这封邮件。",
        failure="重置邮件没有发出",
    )


def deliver_code(settings: Settings, *, email: str | None, phone: str | None, code: str, purpose: str) -> str | None:
    action = {"login": "登录", "register": "注册", "reset_password": "重置密码"}.get(purpose, "验证")
    text = f"您正在进行{action}操作，验证码：{code}。10分钟内有效，请勿泄露给他人。"
    if email and email_ready(settings):
        _smtp(settings, email, f"PickGlobal {action}验证码", text)
        return "email"
    if phone and sms_ready(settings):
        _sms(settings, phone, code)
        return "sms"
    return None


def _smtp(settings: Settings, to: str, subject: str, text: str, failure: str = "验证码邮件没有发出") -> None:
    message = EmailMessage()
    message["From"] = settings.auth_email_from or settings.auth_email_smtp_user
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    port = int(settings.auth_email_smtp_port or 465)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(settings.auth_email_smtp_host, port, timeout=20) as client:
                client.login(settings.auth_email_smtp_user, settings.auth_email_smtp_pass)
                client.send_message(message)
        else:
            with smtplib.SMTP(settings.auth_email_smtp_host, port, timeout=20) as client:
                client.starttls()
                client.login(settings.auth_email_smtp_user, settings.auth_email_smtp_pass)
                client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise AppError("MESSAGE_FAILED", failure, 502) from exc


def sms_failure_message(code: str) -> str:
    if code == "LimitExceeded.PhoneNumberDailyLimit":
        return "这个手机号今天的短信次数已用完，请明天再试，或改用密码登录。"
    if code in {
        "LimitExceeded.PhoneNumberThirtySecondLimit",
        "LimitExceeded.PhoneNumberOneHourLimit",
        "LimitExceeded.DeliveryFrequencyLimit",
    }:
        return "短信发送太频繁，请稍后再试，或改用密码登录。"
    return "验证码短信没有发出"


def _sms(settings: Settings, phone: str, code: str) -> None:
    payload = json.dumps(
        {
            "PhoneNumberSet": [phone if phone.startswith("+") else f"+86{phone}"],
            "SmsSdkAppId": settings.sms_sdk_app_id,
            "SignName": settings.sms_sign_name,
            "TemplateId": settings.sms_template_id,
            "TemplateParamSet": [code],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    headers = _tc3(settings.sms_secret_id, settings.sms_secret_key, payload, settings.sms_region or "ap-guangzhou")
    try:
        response = httpx.post("https://sms.tencentcloudapi.com", content=payload.encode(), headers=headers, timeout=20)
        body = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise AppError("MESSAGE_FAILED", "验证码短信没有发出", 502) from exc
    payload_body = body.get("Response") or {}
    error = payload_body.get("Error") or {}
    statuses = payload_body.get("SendStatusSet") or []
    failed_status = next((item for item in statuses if item.get("Code") != "Ok"), None)
    failed = bool(error) or response.status_code >= 400 or failed_status is not None
    if failed:
        provider_code = str(error.get("Code") or (failed_status or {}).get("Code") or "")
        raise AppError("MESSAGE_FAILED", sms_failure_message(provider_code), 502)


def _tc3(secret_id: str, secret_key: str, payload: str, region: str) -> dict:
    host = "sms.tencentcloudapi.com"
    service = "sms"
    action = "SendSms"
    timestamp = int(time.time())
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    content_type = "application/json; charset=utf-8"
    canonical = "\n".join(
        [
            "POST",
            "/",
            "",
            f"content-type:{content_type}\nhost:{host}\nx-tc-action:{action.lower()}\n",
            "content-type;host;x-tc-action",
            hashlib.sha256(payload.encode()).hexdigest(),
        ]
    )
    scope = f"{date}/{service}/tc3_request"
    string_to_sign = "\n".join(["TC3-HMAC-SHA256", str(timestamp), scope, hashlib.sha256(canonical.encode()).hexdigest()])
    secret_date = hmac.new(("TC3" + secret_key).encode(), date.encode(), hashlib.sha256).digest()
    secret_service = hmac.new(secret_date, service.encode(), hashlib.sha256).digest()
    signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
    signature = hmac.new(signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    return {
        "Authorization": f"TC3-HMAC-SHA256 Credential={secret_id}/{scope}, SignedHeaders=content-type;host;x-tc-action, Signature={signature}",
        "Content-Type": content_type,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": "2021-01-11",
        "X-TC-Region": region,
    }
