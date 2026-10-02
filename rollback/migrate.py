"""Forward and reverse migrations between CloudBase documents and the PostgreSQL shape.

The live MVP store is the JSON document file (CloudBase stand-in). Each version
has a matching sql/<version>/up.sql and down.sql for a real PostgreSQL cutover.
"""

from pathlib import Path

from rollback.baseline import (
    BASELINE_VERSION,
    ENGINE_CLOUDBASE,
    ENGINE_POSTGRES,
    MIGRATION_ORDER,
    POSTGRES_ONLY,
    RENAMES,
)
from rollback.errors import RollbackError
from rollback.store import collections, ensure_meta, transaction

SQL_ROOT = Path(__file__).resolve().parent / "sql"


def _move(data: dict, src: str, dst: str) -> None:
    """Move src into dst. Documents already in dst stay there; they belong to the API."""
    cols = collections(data)
    if src not in cols:
        return
    dst_existed = dst in cols
    dst_docs = cols.setdefault(dst, {})
    stayed = {}
    for doc_id, doc in list(cols[src].items()):
        if doc_id in dst_docs:
            stayed[doc_id] = doc
            continue
        cloned = dict(doc)
        marker = dict(cloned.get("_pg") or {})
        marker["migrated_from"] = src
        cloned["_pg"] = marker
        dst_docs[doc_id] = cloned
    if stayed:
        cols[src] = stayed
    else:
        cols.pop(src, None)
        ensure_meta(data).setdefault("removed_collections", []).append(src)
    if not dst_existed and not dst_docs:
        cols.pop(dst, None)


def _unmove(data: dict, dst: str, src: str) -> None:
    cols = collections(data)
    restored = {}
    remaining = {}
    for doc_id, doc in list((cols.get(dst) or {}).items()):
        marker = dict(doc.get("_pg") or {})
        if marker.get("migrated_from") != src:
            remaining[doc_id] = doc
            continue
        cleaned = dict(doc)
        marker.pop("migrated_from", None)
        if marker:
            cleaned["_pg"] = marker
        else:
            cleaned.pop("_pg", None)
        restored[doc_id] = cleaned
    if remaining:
        cols[dst] = remaining
    else:
        cols.pop(dst, None)
    removed = ensure_meta(data).get("removed_collections") or []
    if restored or src in removed:
        current = cols.get(src) or {}
        current.update(restored)
        cols[src] = current


def _stamp_lead(doc: dict, *, expand: bool) -> None:
    marker = dict(doc.get("_pg") or {})
    if expand:
        if "score_v2" not in doc and "quality_score" in doc:
            doc["score_v2"] = doc["quality_score"]
            marker["score_v2_added"] = True
            doc["_pg"] = marker
        return
    if not marker.get("score_v2_added"):
        return
    doc.pop("score_v2", None)
    marker.pop("score_v2_added", None)
    if marker:
        doc["_pg"] = marker
    else:
        doc.pop("_pg", None)


def _merge_recalls(data: dict) -> None:
    cols = collections(data)
    present = [name for name in ("activation_jobs", "recall_jobs") if name in cols]
    if not present:
        return
    recalls = dict(cols.get("recalls") or {})
    for source, trigger in (("activation_jobs", "cold_start"), ("recall_jobs", "churn")):
        if source not in cols:
            continue
        for doc_id, doc in list(cols[source].items()):
            if doc_id in recalls:
                continue
            cloned = dict(doc)
            marker = dict(cloned.get("_pg") or {})
            if "trigger" not in cloned:
                cloned["trigger"] = trigger
                marker["trigger_injected"] = True
            marker["source_collection"] = source
            cloned["_pg"] = marker
            recalls[doc_id] = cloned
            cols[source].pop(doc_id, None)
        if not cols[source]:
            cols.pop(source, None)
    if recalls or "recalls" in cols:
        cols["recalls"] = recalls
    ensure_meta(data)["recall_sources"] = present


def _split_recalls(data: dict) -> None:
    cols = collections(data)
    meta = ensure_meta(data)
    sources = list(meta.pop("recall_sources", []) or [])
    if "recalls" not in cols and not sources:
        return
    for doc_id, doc in list((cols.get("recalls") or {}).items()):
        marker = dict(doc.get("_pg") or {})
        source = marker.get("source_collection")
        if source not in {"activation_jobs", "recall_jobs"}:
            continue
        restored = dict(doc)
        marker.pop("source_collection", None)
        if marker.get("trigger_injected"):
            restored.pop("trigger", None)
            marker.pop("trigger_injected", None)
        if marker:
            restored["_pg"] = marker
        else:
            restored.pop("_pg", None)
        cols.setdefault(source, {})[doc_id] = restored
        cols["recalls"].pop(doc_id, None)
    if not cols.get("recalls"):
        cols.pop("recalls", None)
    for name in sources:
        cols.setdefault(name, {})


def up_0001(data: dict) -> None:
    cols = collections(data)
    for src, dst in RENAMES:
        _move(data, src, dst)
    _merge_recalls(data)
    for doc in (cols.get("leads") or {}).values():
        _stamp_lead(doc, expand=True)
    meta = ensure_meta(data)
    meta["engine"] = ENGINE_POSTGRES
    meta["schema_version"] = "0001_postgres_shape"


def down_0001(data: dict) -> None:
    cols = collections(data)
    _split_recalls(data)
    for src, dst in reversed(RENAMES):
        _unmove(data, dst, src)
    removed = ensure_meta(data).get("removed_collections") or []
    ensure_meta(data)["removed_collections"] = [name for name in removed if name not in collections(data)]
    for doc in (cols.get("leads") or {}).values():
        _stamp_lead(doc, expand=False)
    for name in POSTGRES_ONLY:
        if not cols.get(name):
            cols.pop(name, None)
    meta = ensure_meta(data)
    meta["engine"] = ENGINE_CLOUDBASE
    meta["schema_version"] = BASELINE_VERSION


def up_0002(data: dict) -> None:
    cols = collections(data)
    if "leads" not in cols:
        ensure_meta(data)["schema_version"] = "0002_contract_score"
        return
    for doc in cols["leads"].values():
        if "score_v2" not in doc:
            if "quality_score" not in doc:
                raise RollbackError("leads 缺少 quality_score，不能收缩")
            doc["score_v2"] = doc["quality_score"]
        doc.pop("quality_score", None)
    ensure_meta(data)["schema_version"] = "0002_contract_score"


def down_0002(data: dict) -> None:
    cols = collections(data)
    for doc in (cols.get("leads") or {}).values():
        if "quality_score" not in doc:
            if "score_v2" not in doc:
                raise RollbackError("leads 缺少 score_v2，不能恢复 quality_score")
            doc["quality_score"] = doc["score_v2"]
        doc.pop("score_v2", None)
    meta = ensure_meta(data)
    if "0001_postgres_shape" in meta.get("applied", []):
        meta["schema_version"] = "0001_postgres_shape"


MIGRATIONS = {
    "0001_postgres_shape": (up_0001, down_0001),
    "0002_contract_score": (up_0002, down_0002),
}


def applied(data: dict) -> list[str]:
    return list(ensure_meta(data).get("applied") or [])


def migrate_up(path, target: str | None = None) -> list[str]:
    goal = target or MIGRATION_ORDER[-1]
    if goal not in MIGRATION_ORDER and goal != BASELINE_VERSION:
        raise RollbackError(f"未知 migration: {goal}")

    def op(data: dict) -> list[str]:
        done = []
        for version in MIGRATION_ORDER:
            if version in applied(data):
                continue
            up, _down = MIGRATIONS[version]
            before = _ledger_ids(data)
            up(data)
            after = _ledger_ids(data)
            if before != after:
                raise RollbackError(f"{version} up 改变了账本主键")
            ensure_meta(data).setdefault("applied", []).append(version)
            done.append(version)
            if version == goal:
                break
        return done

    return transaction(path, op)


def migrate_down(path, target: str = BASELINE_VERSION) -> list[str]:
    if target != BASELINE_VERSION and target not in MIGRATION_ORDER:
        raise RollbackError(f"未知回退目标: {target}")

    def op(data: dict) -> list[str]:
        done = []
        current = applied(data)
        while current:
            version = current[-1]
            if target != BASELINE_VERSION and version == target:
                break
            if target != BASELINE_VERSION and MIGRATION_ORDER.index(version) <= MIGRATION_ORDER.index(target):
                break
            _up, down = MIGRATIONS[version]
            before = _ledger_ids(data)
            down(data)
            after = _ledger_ids(data)
            if before != after:
                raise RollbackError(f"{version} down 改变了账本主键")
            current.pop()
            ensure_meta(data)["applied"] = current
            done.append(version)
            if target != BASELINE_VERSION and (not current or current[-1] == target):
                break
        if target == BASELINE_VERSION:
            meta = ensure_meta(data)
            meta["engine"] = ENGINE_CLOUDBASE
            meta["schema_version"] = BASELINE_VERSION
            meta["applied"] = []
            for name in POSTGRES_ONLY:
                if not collections(data).get(name):
                    collections(data).pop(name, None)
        return done

    return transaction(path, op)


def _ledger_ids(data: dict) -> set[tuple[str, str]]:
    found = set()
    for name in ("payment_orders", "payments", "commission_ledger", "raas_ledger"):
        for doc_id, doc in (collections(data).get(name) or {}).items():
            found.add((name if name != "payments" else "payment_orders", doc.get("idempotency_key") or doc_id))
    return found


def sql_pair(version: str) -> tuple[str, str]:
    folder = SQL_ROOT / version
    up = folder / "up.sql"
    down = folder / "down.sql"
    if not up.exists() or not down.exists():
        raise RollbackError(f"{version} 缺少 up.sql 或 down.sql")
    return up.read_text(), down.read_text()
