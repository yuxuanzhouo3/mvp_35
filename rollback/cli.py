import argparse
import json
from pathlib import Path

from rollback.baseline import BASELINE_VERSION
from rollback.ai_fallback import degrade_store
from rollback.code_tag import apply_baseline, changed_paths, pin
from rollback.config_traffic import switch_config, switch_traffic
from rollback.events import load_events, replay
from rollback.migrate import migrate_down, migrate_up
from rollback.orchestrator import rollback_to_cloudbase
from rollback.snapshot import Journal, restore_pitr, restore_snapshot, take_snapshot
from rollback.store import load


def _print(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="回退到 CloudBase 云文档基线")
    sub = parser.add_subparsers(dest="cmd", required=True)

    tag = sub.add_parser("pin-tag", help="给当前 HEAD 打 baseline-cloudbase，不移动已有标签")
    tag.add_argument("--repo", default=".")

    code = sub.add_parser("code", help="按标签恢复代码路径；默认只打印计划")
    code.add_argument("--repo", default=".")
    code.add_argument("--apply", action="store_true")
    code.add_argument("paths", nargs="*")

    up = sub.add_parser("migrate-up")
    up.add_argument("--store", required=True)
    up.add_argument("--to", default=None)
    up.add_argument("--journal", default=None)

    down = sub.add_parser("migrate-down")
    down.add_argument("--store", required=True)
    down.add_argument("--to", default=BASELINE_VERSION)

    snap = sub.add_parser("snapshot")
    snap.add_argument("--store", required=True)
    snap.add_argument("--out", required=True)
    snap.add_argument("--at", default=None)

    restore = sub.add_parser("restore-snapshot")
    restore.add_argument("--store", required=True)
    restore.add_argument("--snapshot", required=True)

    pitr = sub.add_parser("pitr")
    pitr.add_argument("--store", required=True)
    pitr.add_argument("--journal", required=True)
    pitr.add_argument("--at", required=True)
    pitr.add_argument("--engine", default=None)

    cfg = sub.add_parser("config")
    cfg.add_argument("--home", required=True)
    cfg.add_argument("--to", default=BASELINE_VERSION)

    traffic = sub.add_parser("traffic")
    traffic.add_argument("--home", required=True)
    traffic.add_argument("--to", default=BASELINE_VERSION)
    traffic.add_argument("--percent", type=int, default=100)

    ev = sub.add_parser("replay")
    ev.add_argument("--store", required=True)
    ev.add_argument("--events", required=True)
    ev.add_argument("--dead-letter", required=True)

    ai = sub.add_parser("ai-rules")
    ai.add_argument("--store", required=True)

    run = sub.add_parser("run", help="配置、流量、down/PITR、幂等重放、AI 降级到规则")
    run.add_argument("--store", required=True)
    run.add_argument("--home", required=True)
    run.add_argument("--journal", required=True)
    run.add_argument("--events", default=None)

    args = parser.parse_args(argv)
    if args.cmd == "pin-tag":
        _print({"tag": "baseline-cloudbase", "rev": pin(args.repo)})
    elif args.cmd == "code":
        if args.apply:
            _print({"restored": apply_baseline(args.repo, args.paths or None)})
        else:
            _print({"plan": changed_paths(args.repo)})
    elif args.cmd == "migrate-up":
        if args.journal:
            Journal(args.journal).append(load(args.store))
        _print({"applied": migrate_up(args.store, args.to)})
    elif args.cmd == "migrate-down":
        _print({"reverted": migrate_down(args.store, args.to)})
    elif args.cmd == "snapshot":
        body = take_snapshot(args.store, args.out, args.at)
        _print({"path": body["path"], "checksum": body["checksum"], "ledger_fen": body["ledger_fen"]})
    elif args.cmd == "restore-snapshot":
        body = restore_snapshot(args.store, args.snapshot)
        _print({"restored": body["created_at"], "checksum": body["checksum"]})
    elif args.cmd == "pitr":
        entry = restore_pitr(args.store, args.journal, args.at, engine=args.engine)
        _print({"restored": entry["created_at"], "engine": entry["engine"], "checksum": entry["checksum"]})
    elif args.cmd == "config":
        _print(switch_config(args.home, args.to))
    elif args.cmd == "traffic":
        _print(switch_traffic(args.home, args.to, percent=args.percent))
    elif args.cmd == "replay":
        _print(replay(args.store, load_events(args.events), args.dead_letter))
    elif args.cmd == "ai-rules":
        _print(degrade_store(args.store))
    elif args.cmd == "run":
        _print(
            rollback_to_cloudbase(
                args.store,
                home=args.home,
                journal_path=args.journal,
                event_log=args.events,
            )
        )
    else:
        parser.error(args.cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
