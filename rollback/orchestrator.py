"""Full return to the CloudBase document baseline.

Order: flags and traffic, migration down, PITR if down fails or the result is not
baseline, idempotent event replay, AI rules, then verify.
"""

from pathlib import Path

from rollback.ai_fallback import degrade_store
from rollback.baseline import BASELINE_VERSION, ENGINE_CLOUDBASE
from rollback.config_traffic import switch_config, switch_traffic
from rollback.errors import RollbackError
from rollback.events import load_events, replay
from rollback.migrate import migrate_down
from rollback.policy import decide, plan_for
from rollback.snapshot import Journal, ledger_fen, restore_pitr
from rollback.store import load
from rollback.verify import verify_baseline


def rollback_to_cloudbase(
    store_path,
    *,
    home,
    journal_path,
    event_log=None,
    events=None,
    down=None,
) -> dict:
    home = Path(home)
    journal = Journal(journal_path)
    current = load(store_path)
    journal.append(current, moment=None)
    config = switch_config(home, BASELINE_VERSION)
    traffic = switch_traffic(home, BASELINE_VERSION, percent=100)
    used_pitr = False
    down_error = None
    runner = down or migrate_down
    try:
        reverted = runner(store_path, BASELINE_VERSION)
    except Exception as exc:
        down_error = str(exc)
        reverted = []
        _restore_cloudbase_pitr(store_path, journal_path)
        used_pitr = True
    state = load(store_path)
    if (state.get("meta") or {}).get("engine") != ENGINE_CLOUDBASE:
        _restore_cloudbase_pitr(store_path, journal_path)
        used_pitr = True
    batch = list(events) if events is not None else load_events(event_log) if event_log else []
    replay_summary = replay(store_path, batch, home / "dead_letter.jsonl")
    fen_after_replay = ledger_fen(load(store_path))
    second = replay(store_path, batch, home / "dead_letter.jsonl")
    if ledger_fen(load(store_path)) != fen_after_replay:
        raise RollbackError("事件重放第二次改变了账本")
    replay_summary = {"first": replay_summary, "second": second, "ledger_fen": fen_after_replay}
    ai = degrade_store(store_path)
    report = verify_baseline(store_path, config, traffic)
    if not report["ok"]:
        _restore_cloudbase_pitr(store_path, journal_path)
        used_pitr = True
        replay_summary = replay(store_path, batch, home / "dead_letter.jsonl")
        fen_after_replay = ledger_fen(load(store_path))
        second = replay(store_path, batch, home / "dead_letter.jsonl")
        if ledger_fen(load(store_path)) != fen_after_replay:
            raise RollbackError("事件重放第二次改变了账本")
        replay_summary = {"first": replay_summary, "second": second, "ledger_fen": fen_after_replay}
        ai = degrade_store(store_path)
        config = switch_config(home, BASELINE_VERSION)
        traffic = switch_traffic(home, BASELINE_VERSION, percent=100)
        report = verify_baseline(store_path, config, traffic)
    report.update(
        {
            "used_pitr": used_pitr,
            "down_error": down_error,
            "reverted": reverted,
            "replay": replay_summary,
            "ai": ai,
            "target": BASELINE_VERSION,
        }
    )
    if not report["ok"]:
        raise RollbackError("回退后校验失败: " + "; ".join(report["problems"]))
    return report


def rollback_for_signals(store_path, signals: dict, **kwargs) -> dict:
    action = decide(signals)
    plan = plan_for(action)
    if action == "none":
        return {"ok": True, "action": "none", "skipped": True}
    report = rollback_to_cloudbase(store_path, **kwargs)
    report["action"] = plan["action"]
    report["steps"] = plan["steps"]
    return report


def _restore_cloudbase_pitr(store_path, journal_path) -> None:
    entries = Journal(journal_path).entries()
    baseline = [item for item in entries if item.get("engine") == ENGINE_CLOUDBASE]
    if not baseline:
        raise RollbackError("WAL 里没有 CloudBase 基线，无法 PITR")
    moment = baseline[-1]["created_at"]
    restore_pitr(store_path, journal_path, moment, engine=ENGINE_CLOUDBASE)
