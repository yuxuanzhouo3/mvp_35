"""Document repository on the remote CloudBase PostgreSQL `documents` table.

The method names match DocumentStore. Tests keep STORAGE_ENGINE=json.
"""

import json
from typing import Any, Callable

from app.core.timeutil import iso

from db.cloudbase_sql import execute_pg_sql


class CloudBaseStore:
    def __init__(self, env_id: str, *, region: str = "ap-shanghai", execute: Callable[[str], dict] | None = None):
        self.env_id = env_id
        self.region = region
        self._execute = execute
        self._data: dict | None = None

    def transaction(self, fn: Callable[[dict], Any]) -> Any:
        data = self._ensure()
        before = json.dumps(data, ensure_ascii=False, sort_keys=True)
        try:
            result = fn(data)
            after = json.dumps(data, ensure_ascii=False, sort_keys=True)
            if before != after:
                self._flush(json.loads(before), data)
            return result
        except Exception:
            self._data = json.loads(before)
            raise

    def insert(self, collection: str, doc: dict) -> dict:
        def op(data: dict) -> dict:
            col = _col(data, collection)
            if doc["id"] in col:
                raise ValueError(f"duplicate id {doc['id']}")
            col[doc["id"]] = doc
            return doc

        return self.transaction(op)

    def put(self, collection: str, doc: dict) -> dict:
        def op(data: dict) -> dict:
            _col(data, collection)[doc["id"]] = doc
            return doc

        return self.transaction(op)

    def get(self, collection: str, doc_id: str, tenant_id: str | None = None) -> dict | None:
        def op(data: dict) -> dict | None:
            doc = _col(data, collection).get(doc_id)
            if not doc or doc.get("deleted_at"):
                return None
            if tenant_id is not None and doc.get("tenant_id") != tenant_id:
                return None
            return doc

        return self.transaction(op)

    def find_global(self, collection: str, **filters: Any) -> dict | None:
        def op(data: dict) -> dict | None:
            for doc in _col(data, collection).values():
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
            for doc in _col(data, collection).values():
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
            doc = _col(data, collection).get(doc_id)
            if not doc:
                return None
            doc.update(patch)
            doc["updated_at"] = iso()
            doc["version"] = int(doc.get("version") or 1) + 1
            return doc

        return self.transaction(op)

    def _ensure(self) -> dict:
        if self._data is None:
            self._data = self._load()
        return self._data

    def _load(self) -> dict:
        result = self._sql("SELECT collection, id, body::text FROM documents")
        columns = result["columns"]
        data: dict = {"collections": {}}
        for row in result["rows"]:
            record = dict(zip(columns, row))
            body = record["body"]
            if isinstance(body, str):
                body = json.loads(body)
            _col(data, record["collection"])[record["id"]] = body
        return data

    def _flush(self, before: dict, after: dict) -> None:
        previous = _index(before)
        current = _index(after)
        statements = []
        for key, doc in current.items():
            if previous.get(key) != doc:
                statements.append(_upsert(key[0], doc))
        for key in previous:
            if key not in current:
                statements.append(
                    "DELETE FROM documents WHERE collection = "
                    f"{_quote(key[0])} AND id = {_quote(key[1])}"
                )
        for statement in statements:
            self._sql(statement)

    def _sql(self, sql: str) -> dict:
        if self._execute is not None:
            return self._execute(sql)
        return execute_pg_sql(self.env_id, sql, region=self.region)


def _col(data: dict, name: str) -> dict:
    return data.setdefault("collections", {}).setdefault(name, {})


def _index(data: dict) -> dict:
    found = {}
    for name, rows in data.get("collections", {}).items():
        for doc_id, doc in rows.items():
            found[(name, doc_id)] = doc
    return found


def _cursor_key(rows: list[dict], cursor: str) -> tuple[str, str]:
    for item in rows:
        if item["id"] == cursor:
            return item.get("created_at", ""), item["id"]
    return "", cursor


def _upsert(collection: str, doc: dict) -> str:
    body = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    deleted = doc.get("deleted_at")
    created = doc.get("created_at") or iso()
    updated = doc.get("updated_at") or created
    tenant = doc.get("tenant_id")
    tenant_sql = "NULL" if tenant is None else _quote(str(tenant))
    deleted_sql = "NULL" if not deleted else f"{_quote(str(deleted))}::timestamptz"
    return (
        "INSERT INTO documents (collection, id, tenant_id, body, created_at, updated_at, deleted_at) VALUES ("
        f"{_quote(collection)}, {_quote(str(doc['id']))}, {tenant_sql}, {_quote(body)}::jsonb, "
        f"{_quote(str(created))}::timestamptz, {_quote(str(updated))}::timestamptz, {deleted_sql}) "
        "ON CONFLICT (collection, id) DO UPDATE SET tenant_id = EXCLUDED.tenant_id, "
        "body = EXCLUDED.body, updated_at = EXCLUDED.updated_at, deleted_at = EXCLUDED.deleted_at"
    )


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
