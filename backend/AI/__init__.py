"""Real LLM helpers for 客服 and AI 选品. Amounts stay with the rules engine."""

from AI.client import chat_complete, provider_ready
from AI.selection import refine_need
from AI.support import support_reply

__all__ = ["chat_complete", "provider_ready", "refine_need", "support_reply"]
