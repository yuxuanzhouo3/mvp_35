"""客服 replies that keep money fields locked to the rules engine."""

from __future__ import annotations

from typing import Any

from AI.client import chat_complete, provider_ready
from AI.prompts import SUPPORT_SYSTEM


def support_reply(
    settings,
    content: str,
    *,
    history: list[dict[str, str]] | None = None,
    facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    locked = _facts_block(facts)
    fallback_text = _rules_fallback(facts)
    if not provider_ready(settings):
        return {"reply": fallback_text, "model": "rules", "provider": "rules", "numbers_locked": True}
    messages: list[dict[str, str]] = [
        {"role": "system", "content": f"{SUPPORT_SYSTEM}\n\n锁定数字（只可读）：\n{locked}"},
    ]
    for turn in (history or [])[-12:]:
        role = turn.get("role")
        text = (turn.get("content") or "").strip()
        if role in {"user", "assistant"} and text:
            messages.append({"role": role, "content": text[:2000]})
    messages.append({"role": "user", "content": (content or "")[:4000]})
    try:
        result = chat_complete(settings, messages, temperature=0.4, max_tokens=700)
    except RuntimeError:
        return {
            "reply": f"{fallback_text}\n（大模型暂时不可用，已用规则说明回复。）",
            "model": "rules",
            "provider": "rules",
            "numbers_locked": True,
        }
    reply = result["text"]
    if "规则引擎" not in reply and "不会改" not in reply:
        reply = f"{reply}\n\n金额与评分仍以规则引擎锁定数字为准，我不会改写它们。"
    return {
        "reply": reply,
        "model": result["model"],
        "provider": result["provider"],
        "numbers_locked": True,
    }


def _facts_block(facts: dict[str, Any] | None) -> str:
    if not facts:
        return "尚无选品报告。请先导入商品并完成分析。"
    return (
        f"规则版本={facts.get('rules_version')}\n"
        f"利润率={facts.get('net_margin')}\n"
        f"净利润USD={facts.get('net_profit_usd')}\n"
        f"风险={facts.get('risk_level')}\n"
        f"报告ID={facts.get('report_id') or '无'}"
    )


def _rules_fallback(facts: dict[str, Any] | None) -> str:
    if not facts:
        return "还没有完成的选品报告。可以先导入商品并开始分析。金额只会由规则引擎计算。"
    return (
        f"最近一份报告利润率 {facts.get('net_margin')}，净利润 {facts.get('net_profit_usd')} USD，"
        f"风险 {facts.get('risk_level')}。规则版本 {facts.get('rules_version')}。"
        "这些问题里的金额要求已被忽略，模型不能改利润、评分或是否流失。"
        "若要获客，请在报告页使用「一键获客」，发送前仍需人工批准。"
    )
