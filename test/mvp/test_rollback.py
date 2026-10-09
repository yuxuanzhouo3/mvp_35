import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import pytest

from rollback.cli import main
from rollback.code_tag import apply_baseline, changed_paths, head, pin
from rollback.errors import RollbackError
from rollback.events import replay
from rollback.migrate import migrate_down, migrate_up, sql_pair
from rollback.policy import decide, plan_for
from rollback.snapshot import Journal, ledger_fen, restore_pitr, restore_snapshot, take_snapshot
from rollback.store import load, save
from rollback.orchestrator import rollback_to_cloudbase


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=rollback@example.com", "-c", "user.name=rollback", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed() -> dict:
    user = {
        "id": "user_1",
        "tenant_id": "tenant_1",
        "cloudbase_user_id": "cb_demo",
        "display_name": "演示卖家",
        "deleted_at": None,
    }
    product = {
        "id": "prod_1",
        "tenant_id": "tenant_1",
        "cost_cny": "72",
        "target_price_usd": "40",
        "international_freight_usd": "2",
        "fx_usd_cny": "7.2",
        "target_market": "US",
        "tax_regime": "cn_us",
        "origin_country": "CN",
        "deleted_at": None,
    }
    report = {
        "id": "an_1",
        "tenant_id": "tenant_1",
        "product_id": "prod_1",
        "net_margin": "0.4985",
        "net_profit_usd": "19.94",
        "explanation_model": "rules",
        "metrics": {"net_margin": "0.4985", "net_profit_usd": "19.94"},
        "deleted_at": None,
    }
    return {
        "collections": {
            "users": {"user_1": user},
            "tenants": {"tenant_1": {"id": "tenant_1", "tenant_id": "tenant_1", "name": "演示企业"}},
            "quota_balances": {
                "quota_1": {
                    "id": "quota_1",
                    "tenant_id": "tenant_1",
                    "available": {"analysis": 3, "discovery": 3, "send": 3},
                    "reserved": {"analysis": 0, "discovery": 0, "send": 0},
                }
            },
            "products": {"prod_1": product},
            "analysis_reports": {"an_1": report},
            "leads": {
                "lead_1": {
                    "id": "lead_1",
                    "tenant_id": "tenant_1",
                    "email": "buyer@example.com",
                    "quality_score": 80,
                    "deleted_at": None,
                }
            },
            "campaigns": {"camp_1": {"id": "camp_1", "tenant_id": "tenant_1"}},
            "outreach_messages": {},
            "activation_jobs": {"act_1": {"id": "act_1", "tenant_id": "tenant_1", "lead_id": "lead_1"}},
            "recall_jobs": {"rec_1": {"id": "rec_1", "tenant_id": "tenant_1", "lead_id": "lead_1"}},
            "payment_orders": {},
            "commission_ledger": {
                "com_1": {
                    "id": "com_1",
                    "tenant_id": "tenant_1",
                    "idempotency_key": "com-1",
                    "amount_fen": 500,
                    "status": "posted",
                }
            },
            "raas_ledger": {},
            "metric_snapshots": {"kpi_1": {"id": "kpi_1", "tenant_id": "tenant_1", "metric_code": "AR"}},
        },
        "meta": {"engine": "cloudbase_documents", "schema_version": "baseline-cloudbase", "applied": []},
    }


def _events():
    return [
        {
            "event": "payment.succeeded",
            "version": "1.0.0",
            "tenant_id": "tenant_1",
            "provider": "wechat_pay",
            "event_id": "wx-1",
            "idempotency_key": "pay-1",
            "verified": True,
            "payload": {"amount_fen": 9900, "currency": "CNY"},
        },
        {
            "event": "campaign.delivered",
            "version": "1.0.0",
            "tenant_id": "tenant_1",
            "provider": "ses",
            "event_id": "ses-1",
            "idempotency_key": "ses-1",
            "verified": True,
            "payload": {"lead_id": "lead_1", "campaign_id": "camp_1"},
        },
        {
            "event": "payment.succeeded",
            "version": "1.0.0",
            "tenant_id": "tenant_1",
            "provider": "wechat_pay",
            "event_id": "wx-unverified",
            "idempotency_key": "pay-unverified",
            "verified": False,
            "payload": {"amount_fen": 100},
        },
        {
            "event": "payment.succeeded",
            "version": "2.0.0",
            "tenant_id": "tenant_1",
            "provider": "wechat_pay",
            "event_id": "wx-v2",
            "idempotency_key": "pay-v2",
            "verified": True,
            "payload": {"amount_fen": 100},
        },
    ]


def test_migration_roundtrip_restores_cloudbase_names(tmp_path):
    path = tmp_path / "store.json"
    original = _seed()
    save(path, original)
    before = deepcopy(original["collections"])

    assert migrate_up(path) == ["0001_postgres_shape", "0002_contract_score"]
    assert migrate_up(path) == []
    forward = load(path)
    assert forward["meta"]["engine"] == "postgresql"
    assert "selection_reports" in forward["collections"]
    assert "analysis_reports" not in forward["collections"]
    assert "recalls" in forward["collections"]
    assert "quality_score" not in forward["collections"]["leads"]["lead_1"]
    assert forward["collections"]["leads"]["lead_1"]["score_v2"] == 80
    assert ledger_fen(forward) == 500

    assert migrate_down(path) == ["0002_contract_score", "0001_postgres_shape"]
    assert migrate_down(path) == []
    restored = load(path)
    assert restored["meta"]["engine"] == "cloudbase_documents"
    assert restored["meta"]["applied"] == []
    assert restored["collections"] == before
    assert ledger_fen(restored) == 500


def test_live_store_shape_without_meta_roundtrips(tmp_path):
    """The running demo file has no meta and some empty collections."""
    path = tmp_path / "store.json"
    original = {
        "collections": {
            "users": {
                "user_1": {"id": "user_1", "tenant_id": "tenant_1", "cloudbase_user_id": "cb_demo", "deleted_at": None}
            },
            "leads": {
                "lead_1": {
                    "id": "lead_1",
                    "tenant_id": "tenant_1",
                    "email": "buyer@example.com",
                    "quality_score": 88,
                    "deleted_at": None,
                }
            },
            "analysis_reports": {
                "an_1": {"id": "an_1", "tenant_id": "tenant_1", "product_id": "prod_1", "explanation_model": "rules"}
            },
            "products": {"prod_1": {"id": "prod_1", "tenant_id": "tenant_1", "cost_cny": "72", "target_price_usd": "39", "fx_usd_cny": "7.20", "target_market": "US", "tax_regime": "cn_us", "international_freight_usd": "3.2"}},
            "outreach_messages": {"msg_1": {"id": "msg_1", "tenant_id": "tenant_1", "status": "delivered"}},
            "activation_jobs": {"act_1": {"id": "act_1", "tenant_id": "tenant_1"}},
            "recall_jobs": {},
            "suppressions": {},
            "commission_ledger": {
                "com_1": {"id": "com_1", "tenant_id": "tenant_1", "idempotency_key": "com-1", "amount_fen": 1500, "status": "posted"}
            },
            "raas_ledger": {
                "raas_1": {"id": "raas_1", "tenant_id": "tenant_1", "idempotency_key": "raas-1", "amount_fen": 1500, "status": "posted"}
            },
        }
    }
    save(path, original)
    before = deepcopy(original["collections"])
    migrate_up(path)
    assert ledger_fen(load(path)) == 3000
    migrate_down(path)
    restored = load(path)
    assert restored["collections"] == before
    assert restored["meta"]["engine"] == "cloudbase_documents"


def test_app_native_collections_survive_postgres_shape(tmp_path):
    """payments, recalls, and kpi_metrics are written by the JSON API, not only by migrate up."""
    path = tmp_path / "store.json"
    original = {
        "collections": {
            "payment_orders": {
                "ord_old": {"id": "ord_old", "tenant_id": "t1", "idempotency_key": "old", "amount_fen": 100, "status": "posted"}
            },
            "payments": {
                "pay_new": {"id": "pay_new", "tenant_id": "t1", "idempotency_key": "new", "amount_fen": 200, "status": "succeeded"}
            },
            "recalls": {
                "recall_1": {"id": "recall_1", "tenant_id": "t1", "lead_id": "lead_1", "trigger": "churn", "status": "queued"}
            },
            "recall_jobs": {
                "recall_1": {"id": "recall_1", "tenant_id": "t1", "lead_id": "lead_1", "status": "queued"}
            },
            "activation_jobs": {},
            "kpi_metrics": {
                "kpi_1": {"id": "kpi_1", "tenant_id": "t1", "metric_code": "AR", "value": "0.0800"}
            },
            "analysis_reports": {"an_1": {"id": "an_1", "tenant_id": "t1"}},
            "leads": {"lead_1": {"id": "lead_1", "tenant_id": "t1", "email": "buyer@example.com", "quality_score": 80}},
            "outreach_messages": {},
            "metric_snapshots": {},
        }
    }
    save(path, original)
    before = deepcopy(original["collections"])
    migrate_up(path)
    forward = load(path)
    assert forward["collections"]["payments"]["pay_new"]["idempotency_key"] == "new"
    assert "ord_old" in forward["collections"]["payments"]
    assert forward["collections"]["recalls"]["recall_1"]["status"] == "queued"
    assert "kpi_metrics" in forward["collections"]
    migrate_down(path)
    assert load(path)["collections"] == before


def test_sql_pairs_reverse_the_postgres_shape():
    up, down = sql_pair("0001_postgres_shape")
    assert "score_v2" in up
    assert "DROP TABLE IF EXISTS selection_reports" in down
    assert "DROP TABLE IF EXISTS payments" in down
    up2, down2 = sql_pair("0002_contract_score")
    assert "DROP COLUMN IF EXISTS quality_score" in up2
    assert "quality_score = score_v2" in down2
    assert "DROP COLUMN IF EXISTS score_v2" in down2


def test_snapshot_and_pitr_restore_an_earlier_document_state(tmp_path):
    path = tmp_path / "store.json"
    save(path, _seed())
    journal = Journal(tmp_path / "wal.jsonl")
    journal.append(load(path), moment="2026-10-01T00:00:00+00:00")
    shot = take_snapshot(path, tmp_path / "snaps", moment="2026-10-01T00:00:00+00:00")

    data = load(path)
    data["collections"]["leads"]["lead_2"] = {"id": "lead_2", "tenant_id": "tenant_1", "email": "late@example.com"}
    save(path, data)
    journal.append(load(path), moment="2026-10-01T01:00:00+00:00")

    restore_pitr(path, journal.path, "2026-10-01T00:30:00+00:00", engine="cloudbase_documents")
    assert "lead_2" not in load(path)["collections"]["leads"]

    data = load(path)
    data["collections"]["leads"]["lead_3"] = {"id": "lead_3", "tenant_id": "tenant_1", "email": "snap@example.com"}
    save(path, data)
    restore_snapshot(path, shot["path"])
    assert "lead_3" not in load(path)["collections"]["leads"]
    assert load(path)["collections"]["leads"]["lead_1"]["email"] == "buyer@example.com"

    broken = json.loads(Path(shot["path"]).read_text())
    broken["state"]["collections"]["leads"]["lead_1"]["email"] = "tampered@example.com"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(broken))
    with pytest.raises(RollbackError, match="校验和"):
        restore_snapshot(path, bad)


def test_replay_is_idempotent_and_drops_unverified_events(tmp_path):
    path = tmp_path / "store.json"
    save(path, _seed())
    dead = tmp_path / "dead.jsonl"
    first = replay(path, _events(), dead)
    second = replay(path, _events(), dead)
    assert first == {"applied": 2, "skipped": 0, "dead": 2}
    assert second == {"applied": 0, "skipped": 2, "dead": 2}
    assert ledger_fen(load(path)) == 500 + 9900
    orders = load(path)["collections"]["payment_orders"]
    assert len(orders) == 1
    assert load(path)["collections"]["quota_balances"]["quota_1"]["available"]["send"] == 3


def test_full_rollback_returns_to_cloudbase_baseline(tmp_path):
    path = tmp_path / "store.json"
    home = tmp_path / "home"
    journal = Journal(tmp_path / "wal.jsonl")
    save(path, _seed())
    journal.append(load(path), moment="2026-10-01T00:00:00+00:00")
    migrate_up(path)

    report_doc = load(path)["collections"]["selection_reports"]["an_1"]
    report_doc["explanation_model"] = "hunyuan"
    report_doc["model_margin"] = "0.10"
    report_doc["net_margin"] = "0.10"
    report_doc["net_profit_usd"] = "4.00"
    report_doc["metrics"] = {"net_margin": "0.10", "net_profit_usd": "4.00"}
    current = load(path)
    current["collections"]["selection_reports"]["an_1"] = report_doc
    save(path, current)

    report = rollback_to_cloudbase(
        path,
        home=home,
        journal_path=journal.path,
        events=_events(),
    )

    assert report["ok"] is True
    assert report["used_pitr"] is False
    assert report["target"] == "baseline-cloudbase"
    assert report["ledger_fen"] == 500 + 9900
    assert report["replay"]["second"]["applied"] == 0
    assert "an_1" in report["ai"]["degraded"]

    data = load(path)
    cols = data["collections"]
    assert data["meta"]["engine"] == "cloudbase_documents"
    assert data["meta"]["schema_version"] == "baseline-cloudbase"
    assert "selection_reports" not in cols
    assert "payments" not in cols
    assert "recalls" not in cols
    assert cols["analysis_reports"]["an_1"]["explanation_model"] == "rules"
    assert cols["analysis_reports"]["an_1"]["net_profit_usd"] == "19.94"
    assert cols["analysis_reports"]["an_1"]["net_margin"] == "0.4985"
    assert "model_margin" not in cols["analysis_reports"]["an_1"]
    assert cols["leads"]["lead_1"]["quality_score"] == 80
    assert "score_v2" not in cols["leads"]["lead_1"]
    assert "trigger" not in cols["activation_jobs"]["act_1"]
    assert set(cols["payment_orders"]) == {"ord_wx-1"}
    assert set(cols["outreach_messages"]) == {"msg_ses-1"}
    assert cols["users"]["user_1"]["cloudbase_user_id"] == "cb_demo"

    active = json.loads((home / "active_config.json").read_text())
    gateway = json.loads((home / "gateway.json").read_text())
    assert active["storage_engine"] == "cloudbase_documents"
    assert all(value is False for value in active["flags"].values())
    assert gateway["selector"]["version"] == "baseline-cloudbase"
    assert gateway["percent"] == 100
    assert gateway["canary_percent"] == 0
    assert gateway["tenant_overrides"] == {}

    from db.store import DocumentStore

    loaded = DocumentStore(path).get("users", "user_1")
    assert loaded["cloudbase_user_id"] == "cb_demo"
    assert DocumentStore(path).get("analysis_reports", "an_1", "tenant_1")["explanation_model"] == "rules"


def test_failed_down_uses_pitr_then_replays_once(tmp_path):
    path = tmp_path / "store.json"
    journal = Journal(tmp_path / "wal.jsonl")
    save(path, _seed())
    journal.append(load(path), moment="2026-10-01T00:00:00+00:00")
    migrate_up(path)

    def boom(_path, _target):
        raise RuntimeError("down failed")

    report = rollback_to_cloudbase(
        path,
        home=tmp_path / "home",
        journal_path=journal.path,
        events=_events(),
        down=boom,
    )
    assert report["used_pitr"] is True
    assert report["ok"] is True
    assert report["ledger_fen"] == 500 + 9900
    data = load(path)
    assert data["meta"]["engine"] == "cloudbase_documents"
    assert "analysis_reports" in data["collections"]
    assert "selection_reports" not in data["collections"]
    assert len(data["collections"]["payment_orders"]) == 1
    assert data["collections"]["quota_balances"]["quota_1"]["available"]["analysis"] == 3


def test_code_tag_restores_baseline_without_moving_head(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    note = repo / "app.txt"
    note.write_text("baseline\n")
    _git(repo, "add", "app.txt")
    _git(repo, "commit", "-m", "baseline")
    assert pin(repo)
    note.write_text("postgres\n")
    _git(repo, "add", "app.txt")
    _git(repo, "commit", "-m", "forward")
    with pytest.raises(RollbackError, match="拒绝移动标签"):
        pin(repo)
    assert changed_paths(repo) == ["app.txt"]
    before = head(repo)
    assert apply_baseline(repo) == ["app.txt"]
    assert head(repo) == before
    assert note.read_text() == "baseline\n"
    with pytest.raises(RollbackError, match="不在代码回退范围内"):
        apply_baseline(repo, ["rollback/cli.py"])


def test_policy_selects_full_baseline_rollback():
    assert decide({}) == "none"
    assert decide({"error_rate": 0.02}) == "service"
    assert decide({"payment_failure_rate": 0.01}) == "payment"
    assert decide({"margin_drift": 0.06}) == "ai"
    assert decide({"schema_failed": True}) == "storage"
    assert decide({"duplicate_post": True}) == "event"
    plan = plan_for("storage")
    assert plan["target"] == "baseline-cloudbase"
    assert plan["steps"] == ["config", "traffic", "migrate_down", "pitr_if_needed", "replay", "ai_rules", "verify"]


def test_cli_snapshot_and_down(tmp_path, capsys):
    path = tmp_path / "store.json"
    save(path, _seed())
    migrate_up(path)
    assert main(["snapshot", "--store", str(path), "--out", str(tmp_path / "snaps"), "--at", "2026-10-01T00:00:00+00:00"]) == 0
    assert main(["migrate-down", "--store", str(path)]) == 0
    assert load(path)["meta"]["engine"] == "cloudbase_documents"
    captured = capsys.readouterr().out
    assert "baseline-cloudbase" in captured or "reverted" in captured
