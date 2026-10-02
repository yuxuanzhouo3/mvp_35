"""Memory runner for tests and the PostgreSQL runner used at cutover.

Both speak the same operations. SQL text is built only from catalog identifiers.
Values always travel as parameters.
"""

import re
from copy import deepcopy
from datetime import datetime, timezone

from db.errors import DbError
from db.schema import Table

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def ident(name: str) -> str:
    if not _IDENT.match(name):
        raise DbError("INVALID_IDENTIFIER", "非法标识符")
    return name


def render_insert(table: str, columns: list[str]) -> str:
    quoted = [ident(column) for column in columns]
    marks = ", ".join(["%s"] * len(quoted))
    return f"INSERT INTO {ident(table)} ({', '.join(quoted)}) VALUES ({marks}) RETURNING *"


def render_patch(
    table: str,
    tenant_column: str | None,
    columns: list[str],
    *,
    expected_version: int | None,
    soft_delete: bool,
) -> str:
    assignments = ", ".join(f"{ident(column)} = %s" for column in columns)
    where = ["id = %s"]
    if tenant_column and tenant_column != "id":
        where.append(f"{ident(tenant_column)} = %s")
    if soft_delete:
        where.append("deleted_at IS NULL")
    if expected_version is not None:
        where.append("version = %s")
    return f"UPDATE {ident(table)} SET {assignments} WHERE {' AND '.join(where)} RETURNING *"


def render_query(
    table: str,
    tenant_column: str | None,
    filters: list[str],
    *,
    include_global: bool,
    soft_delete: bool,
    cursor: bool,
) -> str:
    where: list[str] = []
    if tenant_column and include_global:
        where.append(f"({ident(tenant_column)} = %s OR {ident(tenant_column)} IS NULL)")
    elif tenant_column:
        where.append(f"{ident(tenant_column)} = %s")
    if soft_delete:
        where.append("deleted_at IS NULL")
    where.extend(f"{ident(column)} = %s" for column in filters)
    if cursor:
        where.append("(created_at, id) < (%s, %s)")
    clause = " AND ".join(where) if where else "TRUE"
    return (
        f"SELECT * FROM {ident(table)} WHERE {clause} "
        "ORDER BY created_at DESC, id DESC LIMIT %s"
    )


def render_claim() -> str:
    return """
UPDATE jobs
SET status = 'running',
    started_at = now(),
    attempts = attempts + 1,
    version = version + 1,
    updated_at = now()
WHERE id IN (
  SELECT id FROM jobs
  WHERE status = 'created'
    AND deleted_at IS NULL
    AND (scheduled_at IS NULL OR scheduled_at <= now())
  ORDER BY created_at
  FOR UPDATE SKIP LOCKED
  LIMIT %s
)
RETURNING *
""".strip()


class MemoryRunner:
    def __init__(self):
        self.rows: dict[str, list[dict]] = {}
        self.config: dict[str, str] = {}
        self._stack: list[dict[str, list[dict]]] = []

    def begin(self) -> None:
        self._stack.append(deepcopy(self.rows))

    def commit(self) -> None:
        if self._stack:
            self._stack.pop()

    def rollback(self) -> None:
        if self._stack:
            self.rows = self._stack.pop()

    def close(self) -> None:
        return None

    def set_config(self, key: str, value: str) -> None:
        self.config[key] = value

    def insert(self, spec: Table, row: dict) -> dict:
        stored = deepcopy(row)
        for other in self.rows.get(spec.name, []):
            if all(other.get(column) == stored.get(column) for column in spec.primary_key):
                raise DbError("CONFLICT", "唯一键冲突")
        self._ensure_unique(spec, stored, ignore_id=None)
        self.rows.setdefault(spec.name, []).append(stored)
        return deepcopy(stored)

    def get(self, spec: Table, tenant_id: str | None, row_id: str) -> dict | None:
        for row in self.rows.get(spec.name, []):
            if row.get("id") != row_id:
                continue
            if spec.soft_delete and row.get("deleted_at"):
                return None
            if not self._visible(spec, row, tenant_id, include_global=spec.shared_read):
                return None
            return deepcopy(row)
        return None

    def query(
        self,
        spec: Table,
        tenant_id: str | None,
        filters: dict,
        limit: int,
        cursor: tuple[datetime, str] | None,
        *,
        include_global: bool,
    ) -> list[dict]:
        matched = []
        for row in self.rows.get(spec.name, []):
            if spec.soft_delete and row.get("deleted_at"):
                continue
            if not self._visible(spec, row, tenant_id, include_global=include_global):
                continue
            if any(row.get(key) != value for key, value in filters.items()):
                continue
            if cursor and (row.get("created_at"), row.get("id")) >= cursor:
                continue
            matched.append(deepcopy(row))
        matched.sort(key=lambda item: (item.get("created_at"), item.get("id")), reverse=True)
        return matched[:limit]

    def patch(
        self,
        spec: Table,
        tenant_id: str | None,
        row_id: str,
        values: dict,
        expected_version: int | None,
    ) -> dict | None:
        bucket = self.rows.get(spec.name, [])
        for index, row in enumerate(bucket):
            if row.get("id") != row_id:
                continue
            if spec.soft_delete and row.get("deleted_at"):
                return None
            if not self._visible(spec, row, tenant_id):
                return None
            if expected_version is not None and row.get("version") != expected_version:
                return None
            updated = deepcopy(row)
            updated.update(values)
            self._ensure_unique(spec, updated, ignore_id=row_id)
            bucket[index] = updated
            return deepcopy(updated)
        return None

    def claim_jobs(self, limit: int) -> list[dict]:
        now = datetime.now(timezone.utc)
        waiting = []
        for row in self.rows.get("jobs", []):
            if row.get("deleted_at") or row.get("status") != "created":
                continue
            scheduled = row.get("scheduled_at")
            if scheduled is not None and scheduled > now:
                continue
            waiting.append(row)
        waiting.sort(key=lambda item: (item.get("created_at"), item.get("id")))
        claimed = []
        for row in waiting[:limit]:
            row["status"] = "running"
            row["started_at"] = now
            row["attempts"] = int(row.get("attempts") or 0) + 1
            row["version"] = int(row.get("version") or 1) + 1
            row["updated_at"] = now
            claimed.append(deepcopy(row))
        return claimed

    def _visible(self, spec: Table, row: dict, tenant_id: str | None, *, include_global: bool = False) -> bool:
        if spec.tenant_column is None:
            return True
        owner = row.get(spec.tenant_column)
        if tenant_id is None:
            return True
        if owner == tenant_id:
            return True
        return bool(include_global and owner is None)

    def _ensure_unique(self, spec: Table, row: dict, ignore_id: str | None) -> None:
        for columns in spec.uniques:
            if any(row.get(column) is None for column in columns):
                continue
            for other in self.rows.get(spec.name, []):
                if ignore_id is not None and other.get("id") == ignore_id:
                    continue
                if spec.soft_delete and (other.get("deleted_at") or row.get("deleted_at")):
                    continue
                if all(other.get(column) == row.get(column) for column in columns):
                    raise DbError("CONFLICT", "唯一键冲突")


def _adapt(value):
    if isinstance(value, (dict, list)):
        from psycopg.types.json import Jsonb

        return Jsonb(value)
    return value


class PostgresRunner:
    """Executes the rendered statements. RLS still applies for the login role."""

    def __init__(self, conn):
        self.conn = conn

    @classmethod
    def connect(cls, dsn: str) -> "PostgresRunner":
        import psycopg
        from psycopg.rows import dict_row

        if not dsn:
            raise DbError("DATABASE_URL_MISSING", "缺少 DATABASE_URL")
        return cls(psycopg.connect(dsn, row_factory=dict_row))

    def begin(self) -> None:
        return None

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def close(self) -> None:
        self.conn.close()

    def set_config(self, key: str, value: str) -> None:
        self.conn.execute("SELECT set_config(%s, %s, true)", (key, value))

    def insert(self, spec: Table, row: dict) -> dict:
        columns = [column for column in spec.columns if column in row]
        sql = render_insert(spec.name, columns)
        return self._one(sql, tuple(row[column] for column in columns))

    def get(self, spec: Table, tenant_id: str | None, row_id: str) -> dict | None:
        scoped = spec.tenant_column is not None and tenant_id is not None
        sql = render_query(
            spec.name,
            spec.tenant_column if scoped else None,
            ["id"],
            include_global=bool(spec.shared_read and scoped),
            soft_delete=spec.soft_delete,
            cursor=False,
        )
        params: list = []
        if scoped:
            params.append(tenant_id)
        params.extend([row_id, 1])
        return self._one(sql, tuple(params))

    def query(
        self,
        spec: Table,
        tenant_id: str | None,
        filters: dict,
        limit: int,
        cursor: tuple[datetime, str] | None,
        *,
        include_global: bool,
    ) -> list[dict]:
        names = list(filters)
        scoped = spec.tenant_column is not None and tenant_id is not None
        sql = render_query(
            spec.name,
            spec.tenant_column if scoped else None,
            names,
            include_global=bool(include_global and scoped),
            soft_delete=spec.soft_delete,
            cursor=cursor is not None,
        )
        params: list = []
        if scoped:
            params.append(tenant_id)
        params.extend(filters[name] for name in names)
        if cursor is not None:
            params.extend(cursor)
        params.append(limit)
        return self._all(sql, tuple(params))

    def patch(
        self,
        spec: Table,
        tenant_id: str | None,
        row_id: str,
        values: dict,
        expected_version: int | None,
    ) -> dict | None:
        columns = list(values)
        sql = render_patch(
            spec.name,
            spec.tenant_column if tenant_id is not None else None,
            columns,
            expected_version=expected_version,
            soft_delete=spec.soft_delete,
        )
        params: list = list(values.values())
        params.append(row_id)
        if spec.tenant_column and spec.tenant_column != "id" and tenant_id is not None:
            params.append(tenant_id)
        if expected_version is not None:
            params.append(expected_version)
        return self._one(sql, tuple(params))

    def claim_jobs(self, limit: int) -> list[dict]:
        return self._all(render_claim(), (limit,))

    def _one(self, sql: str, params: tuple) -> dict | None:
        rows = self._all(sql, params)
        return rows[0] if rows else None

    def _all(self, sql: str, params: tuple) -> list[dict]:
        import psycopg

        try:
            cursor = self.conn.execute(sql, tuple(_adapt(value) for value in params))
        except psycopg.errors.UniqueViolation as exc:
            raise DbError("CONFLICT", "唯一键冲突") from exc
        if cursor.description is None:
            return []
        return [dict(row) for row in cursor.fetchall()]
