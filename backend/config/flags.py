import json
from pathlib import Path

from app.core.errors import AppError

# Section 7 defaults. auth.oauth gates the OAuth entry the same way.
SPEC_FLAGS = {
    "auth.sso": False,
    "auth.mfa": False,
    "auth.oauth": False,
    "auth.miniprogram": False,
    "auth.tenant_switch": False,
    "payment.raas": False,
    "selection.auto_deal": False,
    "acquisition.social": False,
    "acquisition.ecommerce": False,
    "acquisition.expo": False,
    "acquisition.agency": False,
    "ai.agent": False,
    "ai.finetune": False,
    "digital_human": False,
    "geo_seo": False,
    "raas": False,
    "global_multi_active": False,
}


def flags_path() -> Path:
    return Path(__file__).with_name("flags.json")


def load_flags() -> dict[str, bool]:
    flags = dict(SPEC_FLAGS)
    path = flags_path()
    if path.exists():
        raw = json.loads(path.read_text())
        incoming = raw.get("flags", raw)
        for key, value in incoming.items():
            if key in flags:
                flags[key] = bool(value)
    return flags


def require_flag(name: str) -> None:
    if name not in SPEC_FLAGS:
        raise AppError("UNKNOWN_FLAG", "未知功能开关", details={"flag": name})
    if not load_flags()[name]:
        raise AppError("NOT_ENABLED", f"{name} 未开通", 501, {"flag": name, "placeholder": True})
