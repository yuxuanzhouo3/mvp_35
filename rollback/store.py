import fcntl
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from rollback.baseline import BASELINE_VERSION, ENGINE_CLOUDBASE


def empty_store() -> dict:
    return {
        "collections": {},
        "meta": {
            "engine": ENGINE_CLOUDBASE,
            "schema_version": BASELINE_VERSION,
            "applied": [],
        },
    }


def canonical(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def checksum(data: dict) -> str:
    payload = {"collections": data.get("collections") or {}}
    return hashlib.sha256(canonical(payload).encode()).hexdigest()


def ensure_meta(data: dict) -> dict:
    meta = data.setdefault("meta", {})
    meta.setdefault("engine", ENGINE_CLOUDBASE)
    meta.setdefault("schema_version", BASELINE_VERSION)
    meta.setdefault("applied", [])
    return meta


def load(path: str | Path) -> dict:
    file = Path(path)
    if not file.exists() or file.stat().st_size == 0:
        return empty_store()
    data = json.loads(file.read_text())
    data.setdefault("collections", {})
    ensure_meta(data)
    return data


def save(path: str | Path, data: dict) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_suffix(file.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temp.replace(file)


def transaction(path: str | Path, fn: Callable[[dict], Any]) -> Any:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    lock_path = file.with_suffix(".lock")
    lock_path.touch(exist_ok=True)
    with open(lock_path, "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            data = load(file)
            result = fn(data)
            save(file, data)
            return result
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def collections(data: dict) -> dict:
    return data.setdefault("collections", {})


def docs(data: dict, name: str) -> dict:
    return collections(data).setdefault(name, {})
