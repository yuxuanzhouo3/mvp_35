import fcntl
import json
from pathlib import Path
from typing import Any, Callable

from app.core.timeutil import iso


def open_store(settings):
    """JSON file by default. STORAGE_ENGINE=cloudbase uses the remote PostgreSQL documents table."""
    if getattr(settings, "storage_engine", "json") == "cloudbase":
        from db.cloudbase_store import CloudBaseStore

        env_id = getattr(settings, "cloudbase_env_id", "") or ""
        if not env_id:
            raise RuntimeError("CLOUDBASE_ENV_ID is required when STORAGE_ENGINE=cloudbase")
        return CloudBaseStore(env_id, region=getattr(settings, "cloudbase_region", "ap-shanghai") or "ap-shanghai")
    return DocumentStore(settings.data_path)


class DocumentStore:
    """Tenant-scoped document repository.

    The default engine is a JSON file with an exclusive lock. STORAGE_ENGINE=cloudbase
    stores the same documents in remote CloudBase PostgreSQL. Queries that pass
    tenant_id always filter on it.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(".lock")

    def transaction(self, fn: Callable[[dict], Any]) -> Any:
        self.lock_path.touch(exist_ok=True)
        with open(self.lock_path, "a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                data = self._load()
                result = fn(data)
                self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
                return result
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _load(self) -> dict:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return {"collections": {}}
        return json.loads(self.path.read_text())

    def _col(self, data: dict, name: str) -> dict:
        return data.setdefault("collections", {}).setdefault(name, {})

    def insert(self, collection: str, doc: dict) -> dict:
        def op(data: dict) -> dict:
            col = self._col(data, collection)
            if doc["id"] in col:
                raise ValueError(f"duplicate id {doc['id']}")
            col[doc["id"]] = doc
            return doc

        return self.transaction(op)

    def put(self, collection: str, doc: dict) -> dict:
        def op(data: dict) -> dict:
            self._col(data, collection)[doc["id"]] = doc
            return doc

        return self.transaction(op)

    def get(self, collection: str, doc_id: str, tenant_id: str | None = None) -> dict | None:
        def op(data: dict) -> dict | None:
            doc = self._col(data, collection).get(doc_id)
            if not doc or doc.get("deleted_at"):
                return None
            if tenant_id is not None and doc.get("tenant_id") != tenant_id:
                return None
            return doc

        return self.transaction(op)

    def find_global(self, collection: str, **filters: Any) -> dict | None:
        def op(data: dict) -> dict | None:
            for doc in self._col(data, collection).values():
                if doc.get("deleted_at"):
                    continue
                if all(doc.get(key) == value for key, value in filters.items()):
                    return doc
            return None

        return self.transaction(op)

    def query(
        self,
        collection: str,
        *,
        tenant_id: str | None = None,
        filters: dict | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict:
        filters = filters or {}

        def op(data: dict) -> dict:
            rows = []
            for doc in self._col(data, collection).values():
                if doc.get("deleted_at"):
                    continue
                if tenant_id is not None and doc.get("tenant_id") != tenant_id:
                    continue
                if not all(doc.get(key) == value for key, value in filters.items()):
                    continue
                rows.append(doc)
            rows.sort(key=lambda item: (item.get("created_at", ""), item["id"]), reverse=True)
            if cursor:
                rows = [item for item in rows if (item.get("created_at", ""), item["id"]) < _cursor_key(rows, cursor)]
            page = rows[:limit]
            next_cursor = page[-1]["id"] if len(rows) > limit and page else None
            return {"items": page, "next_cursor": next_cursor}

        return self.transaction(op)

    def touch(self, collection: str, doc_id: str, patch: dict) -> dict | None:
        def op(data: dict) -> dict | None:
            doc = self._col(data, collection).get(doc_id)
            if not doc:
                return None
            doc.update(patch)
            doc["updated_at"] = iso()
            doc["version"] = int(doc.get("version") or 1) + 1
            return doc

        return self.transaction(op)


def _cursor_key(rows: list[dict], cursor: str) -> tuple[str, str]:
    for item in rows:
        if item["id"] == cursor:
            return item.get("created_at", ""), item["id"]
    return "", cursor
