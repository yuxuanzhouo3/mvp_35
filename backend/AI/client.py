"""OpenAI-compatible chat client for Hunyuan / Tongyi / OpenAI."""

from __future__ import annotations

import json
from typing import Any

import httpx

PROVIDERS: dict[str, dict[str, str]] = {
    "hunyuan": {
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "default_model": "hunyuan-turbo",
    },
    "tongyi": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
}


def _provider_name(settings) -> str:
    raw = (getattr(settings, "ai_provider", None) or "").strip().lower()
    if raw in PROVIDERS:
        return raw
    if getattr(settings, "tongyi_enabled", False) and (getattr(settings, "tongyi_api_key", "") or getattr(settings, "ai_api_key", "")):
        return "tongyi"
    if getattr(settings, "hunyuan_enabled", False):
        return "hunyuan"
    return "hunyuan"


def _api_key(settings) -> str:
    provider = _provider_name(settings)
    if provider == "tongyi":
        return (getattr(settings, "tongyi_api_key", "") or getattr(settings, "ai_api_key", "") or "").strip()
    if provider == "hunyuan":
        return (getattr(settings, "hunyuan_api_key", "") or getattr(settings, "ai_api_key", "") or "").strip()
    return (getattr(settings, "ai_api_key", "") or getattr(settings, "hunyuan_api_key", "") or "").strip()


def _enabled(settings) -> bool:
    if getattr(settings, "ai_enabled", False):
        return True
    if getattr(settings, "hunyuan_enabled", False):
        return True
    if getattr(settings, "tongyi_enabled", False):
        return True
    return False


def provider_ready(settings) -> bool:
    return _enabled(settings) and bool(_api_key(settings))


def _model(settings) -> str:
    custom = (getattr(settings, "ai_model", None) or "").strip()
    if custom:
        return custom
    return PROVIDERS[_provider_name(settings)]["default_model"]


def _base_url(settings) -> str:
    custom = (getattr(settings, "ai_base_url", None) or "").strip().rstrip("/")
    if custom:
        return custom
    return PROVIDERS[_provider_name(settings)]["base_url"]


def chat_complete(
    settings,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 800,
    timeout: float = 45.0,
) -> dict[str, Any]:
    """Call the configured chat API. Raises RuntimeError when not configured or the call fails."""
    if not provider_ready(settings):
        raise RuntimeError("AI_NOT_CONFIGURED")
    provider = _provider_name(settings)
    model = _model(settings)
    url = f"{_base_url(settings)}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {_api_key(settings)}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"AI_HTTP:{exc}") from exc
    if response.status_code >= 400:
        detail = response.text[:300]
        raise RuntimeError(f"AI_STATUS:{response.status_code}:{detail}")
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("AI_BAD_JSON") from exc
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("AI_EMPTY")
    message = choices[0].get("message") or {}
    text = str(message.get("content") or "").strip()
    if not text:
        raise RuntimeError("AI_EMPTY")
    return {
        "text": text,
        "model": str(body.get("model") or model),
        "provider": provider,
        "raw": body,
    }
