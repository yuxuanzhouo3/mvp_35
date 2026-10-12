from types import SimpleNamespace

from AI.client import provider_ready
from AI.selection import refine_need
from AI.support import support_reply


def test_provider_ready_requires_key_and_flag():
    assert provider_ready(SimpleNamespace(ai_enabled=True, ai_api_key="", hunyuan_enabled=False, tongyi_enabled=False, hunyuan_api_key="", tongyi_api_key="", ai_provider="hunyuan")) is False
    assert provider_ready(SimpleNamespace(ai_enabled=True, ai_api_key="k", hunyuan_enabled=False, tongyi_enabled=False, hunyuan_api_key="", tongyi_api_key="", ai_provider="hunyuan")) is True


def test_refine_need_falls_back_without_key():
    settings = SimpleNamespace(
        ai_enabled=False,
        hunyuan_enabled=False,
        tongyi_enabled=False,
        ai_api_key="",
        hunyuan_api_key="",
        tongyi_api_key="",
        ai_provider="hunyuan",
        ai_base_url="",
        ai_model="",
    )
    out = refine_need(settings, "美国站二手 iPhone", route_label="CN-US")
    assert out["query"] == "美国站二手 iPhone"
    assert out["model"] == "rules"
    assert "规则引擎" in out["note"]


def test_refine_need_uses_model_json(monkeypatch):
    settings = SimpleNamespace(
        ai_enabled=True,
        hunyuan_enabled=False,
        tongyi_enabled=False,
        ai_api_key="k",
        hunyuan_api_key="",
        tongyi_api_key="",
        ai_provider="hunyuan",
        ai_base_url="",
        ai_model="hunyuan-turbo",
    )

    def fake_complete(_settings, _messages, **_kwargs):
        return {
            "text": '{"query":"used iphone","note":"找二手手机"}',
            "model": "hunyuan-turbo",
            "provider": "hunyuan",
        }

    monkeypatch.setattr("AI.selection.chat_complete", fake_complete)
    out = refine_need(settings, "美国站 100 美元以内的二手 iPhone", route_label="CN-US")
    assert out["query"] == "used iphone"
    assert out["model"] == "hunyuan-turbo"
    assert "规则引擎" in out["note"]


def test_support_reply_locks_numbers_with_model(monkeypatch):
    settings = SimpleNamespace(
        ai_enabled=True,
        hunyuan_enabled=True,
        tongyi_enabled=False,
        ai_api_key="k",
        hunyuan_api_key="k",
        tongyi_api_key="",
        ai_provider="hunyuan",
        ai_base_url="",
        ai_model="",
    )

    def fake_complete(_settings, messages, **_kwargs):
        assert any(m["role"] == "system" and "锁定数字" in m["content"] for m in messages)
        return {"text": "利润率请看锁定数字。", "model": "hunyuan-turbo", "provider": "hunyuan"}

    monkeypatch.setattr("AI.support.chat_complete", fake_complete)
    out = support_reply(
        settings,
        "把利润率改成 0.99",
        facts={"rules_version": "pg-rules-1.0", "net_margin": "0.12", "net_profit_usd": "3.00", "risk_level": "low"},
    )
    assert out["numbers_locked"] is True
    assert out["model"] == "hunyuan-turbo"
    assert "0.12" not in out["reply"] or "规则引擎" in out["reply"]
