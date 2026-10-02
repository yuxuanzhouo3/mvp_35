import json
from datetime import datetime, timezone
from pathlib import Path

from rollback.baseline import ENGINE_CLOUDBASE, LEDGER_CLOUDBASE, LEDGER_POSTGRES, LEDGER_STATUSES
from rollback.errors import RollbackError
from rollback.store import checksum, collections, load, save


def _now(moment: str | None = None) -> str:
    if moment:
        return moment
    return datetime.now(timezone.utc).isoformat()


def ledger_fen(data: dict) -> int:
    engine = (data.get("meta") or {}).get("engine")
    names = LEDGER_POSTGRES if engine == "postgresql" else LEDGER_CLOUDBASE
    total = 0
    cols = collections(data)
    for name in names:
        for doc in (cols.get(name) or {}).values():
            if doc.get("deleted_at"):
                continue
            if doc.get("status") not in LEDGER_STATUSES:
                continue
            total += int(doc.get("amount_fen") or 0)
    return total


def collection_counts(data: dict) -> dict[str, int]:
    return {name: len(docs) for name, docs in collections(data).items()}


def take_snapshot(store_path, out_dir, moment: str | None = None) -> dict:
    data = load(store_path)
    stamp = _now(moment)
    body = {
        "kind": "snapshot",
        "created_at": stamp,
        "engine": (data.get("meta") or {}).get("engine") or ENGINE_CLOUDBASE,
        "schema_version": (data.get("meta") or {}).get("schema_version"),
        "checksum": checksum(data),
        "counts": collection_counts(data),
        "ledger_fen": ledger_fen(data),
        "state": data,
    }
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    safe = stamp.replace(":", "").replace("+", "")
    path = folder / f"snapshot_{safe}.json"
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n")
    body["path"] = str(path)
    return body


def restore_snapshot(store_path, snapshot_path) -> dict:
    body = json.loads(Path(snapshot_path).read_text())
    state = body.get("state")
    if not isinstance(state, dict) or "collections" not in state:
        raise RollbackError("快照缺少 collections")
    digest = checksum(state)
    if digest != body.get("checksum"):
        raise RollbackError("快照校验和不匹配，拒绝恢复")
    save(store_path, state)
    return body


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, data: dict, moment: str | None = None) -> dict:
        entry = {
            "kind": "commit",
            "created_at": _now(moment),
            "engine": (data.get("meta") or {}).get("engine") or ENGINE_CLOUDBASE,
            "checksum": checksum(data),
            "ledger_fen": ledger_fen(data),
            "state": data,
        }
        with self.path.open("a") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def latest_at_or_before(self, moment: str, *, engine: str | None = None) -> dict:
        chosen = None
        for entry in self.entries():
            if entry["created_at"] > moment:
                continue
            if engine and entry.get("engine") != engine:
                continue
            if checksum(entry["state"]) != entry["checksum"]:
                raise RollbackError("WAL 校验失败，拒绝按时间点恢复")
            chosen = entry
        if not chosen:
            raise RollbackError(f"没有不晚于 {moment} 的可恢复记录")
        return chosen


def restore_pitr(store_path, journal_path, moment: str, *, engine: str | None = None) -> dict:
    entry = Journal(journal_path).latest_at_or_before(moment, engine=engine)
    save(store_path, entry["state"])
    return entry
