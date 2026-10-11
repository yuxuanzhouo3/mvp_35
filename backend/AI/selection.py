"""Turn a natural-language need into a shelf search query."""

from __future__ import annotations

import json
import re
from typing import Any

from AI.client import chat_complete, provider_ready
from AI.prompts import SELECTION_SYSTEM

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def refine_need(settings, need: str, *, route_label: str = "") -> dict[str, Any]:
    cleaned = " ".join((need or "").split())[:80]
    fallback = {
        "query": cleaned,
        "note": f"按「{cleaned}」检索。金额和利润仍由规则引擎计算。",
        "model": "rules",
        "provider": "rules",
    }
    if not cleaned:
        return fallback
    if not provider_ready(settings):
        return fallback
    user = f"贸易路线：{route_label or '未指定'}\n需求：{cleaned}"
    try:
        result = chat_complete(
            settings,
            [
                {"role": "system", "content": SELECTION_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=300,
        )
    except RuntimeError:
        return fallback
    parsed = _parse(result["text"])
    query = " ".join(str(parsed.get("query") or cleaned).split())[:80] or cleaned
    note = str(parsed.get("note") or "").strip() or f"已把需求整理成检索词「{query}」。"
    note = f"{note} 金额和利润仍由规则引擎计算。"
    return {
        "query": query,
        "note": note,
        "model": result["model"],
        "provider": result["provider"],
    }


def _parse(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK.search(text)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
