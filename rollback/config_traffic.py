import json
from pathlib import Path

from rollback.baseline import BASELINE_VERSION, ENGINE_CLOUDBASE, FLAGS
from rollback.errors import RollbackError

TEMPLATES = Path(__file__).resolve().parent / "config"


def _read_template(version: str) -> dict:
    path = TEMPLATES / f"{version}.json"
    if not path.exists():
        raise RollbackError(f"没有配置版本 {version}")
    return json.loads(path.read_text())


def switch_config(home, version: str = BASELINE_VERSION) -> dict:
    spec = _read_template(version)
    unknown = set(spec.get("flags") or {}) - set(FLAGS)
    if unknown:
        raise RollbackError(f"未知 Feature Flag: {sorted(unknown)}")
    folder = Path(home)
    folder.mkdir(parents=True, exist_ok=True)
    active = dict(spec)
    active["switched_to"] = version
    (folder / "active_config.json").write_text(json.dumps(active, ensure_ascii=False, indent=2) + "\n")
    return active


def active_config(home) -> dict:
    path = Path(home) / "active_config.json"
    if not path.exists():
        return switch_config(home, BASELINE_VERSION)
    return json.loads(path.read_text())


def switch_traffic(
    home,
    version: str = BASELINE_VERSION,
    *,
    percent: int = 100,
    tenant_overrides: dict | None = None,
) -> dict:
    if not 0 <= percent <= 100:
        raise RollbackError("流量百分比必须在 0 到 100")
    spec = _read_template(version)
    route = {
        "selector": {"version": version, "storage_engine": spec["storage_engine"]},
        "percent": percent,
        "canary_percent": 0 if version == BASELINE_VERSION else 100 - percent,
        "tenant_overrides": tenant_overrides or {},
        "baseline": BASELINE_VERSION,
    }
    if version == BASELINE_VERSION and percent == 100:
        route["tenant_overrides"] = {}
        route["canary_percent"] = 0
        route["selector"]["storage_engine"] = ENGINE_CLOUDBASE
    folder = Path(home)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "gateway.json").write_text(json.dumps(route, ensure_ascii=False, indent=2) + "\n")
    return route


def active_traffic(home) -> dict:
    path = Path(home) / "gateway.json"
    if not path.exists():
        return switch_traffic(home, BASELINE_VERSION)
    return json.loads(path.read_text())
