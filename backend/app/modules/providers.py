from typing import Protocol

from app.core.errors import AppError
from app.services.common import CHANNELS, mock_leads


class LeadSearchQuery(dict):
    """channel, platform, query, seed_analysis_id."""


class LeadProvider(Protocol):
    channel: str

    def search(self, query: dict) -> list[dict]: ...


class MockLeadProvider:
    def __init__(self, channel: str):
        self.channel = channel

    def search(self, query: dict) -> list[dict]:
        return mock_leads(self.channel, query.get("platform"), query.get("query") or "", query.get("seed_analysis_id"))


def provider_for(channel: str) -> MockLeadProvider:
    if channel not in CHANNELS:
        raise AppError("UNKNOWN_CHANNEL", "未知获客通道", details={"channel": channel})
    return MockLeadProvider(channel)


def search_channel(channel: str, platform: str | None, query: str, seed_analysis_id: str | None) -> list[dict]:
    return provider_for(channel).search(
        {"platform": platform, "query": query, "seed_analysis_id": seed_analysis_id}
    )
