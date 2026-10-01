import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

STAGES = ("mvp", "svp", "business", "speedup1", "speedup2", "speedup3")

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for entry in (str(ROOT), str(BACKEND)):
    if entry not in sys.path:
        sys.path.insert(0, entry)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path / "store.json"))
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("LEDGER_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("HUNYUAN_ENABLED", "false")
    monkeypatch.setenv("TONGYI_ENABLED", "false")
    monkeypatch.setenv("WECHAT_PAY_MODE", "disabled")
    monkeypatch.setenv("DEMO_SIGNING_HELPER", "false")
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def pytest_collection_modifyitems(config, items):
    del config
    for item in items:
        path = Path(str(item.fspath))
        for stage in STAGES:
            if stage in path.parts:
                item.add_marker(getattr(pytest.mark, stage))
                break
