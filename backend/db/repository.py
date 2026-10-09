"""Tenant-scoped repository over the PostgreSQL catalog.

Request code uses Database.tenant(tenant_id). The worker uses Database.system()
and still passes tenant_id into every business read or write. claim_jobs is the
only cross-tenant operation, and only the system scope can call it.
"""

import base64
import hmac
from datetime import datetime, timezone

from db.errors import DbError
from db.money import require_decimal, require_fen
from db.runners import MemoryRunner, PostgresRunner
from db.schema import (
    CHANNELS,
    DEFAULT_FLAGS,
    LEDGER_SUBJECTS,
    METRIC_CODES,
    TABLES,
    Table,
)

_IMMUTABLE = {"id", "created_at", "created_by"}
_PRODUCT_SOURCES = frozenset({"manual", "csv", "catalog"})
_RECALL_TRIGGERS = frozenset({"cold_start", "churn"})


def encode_cursor(created_at: datetime, row_id: str) -> str:
    stamp = created_at.astimezone(timezone.utc).isoformat()
    raw = f"{stamp}|{row_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(value: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(value.encode()).decode()
        stamp, row_id = raw.split("|", 1)
        return datetime.fromisoformat(stamp), row_id
    except Exception as exc:
        raise DbError("INVALID_CURSOR", "分页游标无效") from exc


class Database:
    def __init__(self, runner):
        self.runner = runner

    @classmethod
    def connect(cls, dsn: str) -> "Database":
        return cls(PostgresRunner.connect(dsn))

    def tenant(self, tenant_id: str) -> "Scope":
        if not tenant_id:
            raise DbError("TENANT_REQUIRED", "查询必须带 tenant_id")
        return Scope(self.runner, tenant_id)

    def system(self) -> "Scope":
        return Scope(self.runner, None)

    def close(self) -> None:
        self.runner.close()


class Scope:
    def __init__(self, runner, tenant_id: str | None):
        self.runner = runner
        self.tenant_id = tenant_id
        self._open = False

    def __enter__(self) -> "Scope":
        self.runner.begin()
        self._open = True
        if self.tenant_id:
            self.runner.set_config("app.tenant_id", self.tenant_id)
            self.runner.set_config("app.bypass_rls", "off")
        else:
            self.runner.set_config("app.bypass_rls", "on")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._open = False
        if exc_type:
            self.runner.rollback()
            return False
        try:
            self.runner.commit()
        except Exception:
            self.runner.rollback()
            raise
        return False

    def insert(self, table: str, values: dict) -> dict:
        spec = self._table(table)
        row = self._prepare(spec, dict(values), partial=False)
        self._assign_tenant(spec, row)
        return self.runner.insert(spec, row)

    def get(self, table: str, row_id: str, *, tenant_id: str | None = None) -> dict | None:
        spec = self._table(table)
        if "id" not in spec.columns:
            raise DbError("UNPAGED", "这张表没有单列主键")
        bound = self._read_tenant(spec, tenant_id)
        if self.tenant_id and spec.tenant_column == "id" and row_id != self.tenant_id:
            return None
        return self.runner.get(spec, bound, row_id)

    def query(
        self,
        table: str,
        *,
        tenant_id: str | None = None,
        filters: dict | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict:
        spec = self._table(table)
        if "id" not in spec.columns or "created_at" not in spec.columns:
            raise DbError("UNPAGED", "这张表不能游标分页")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
            raise DbError("INVALID_LIMIT", "分页长度必须是 1 到 200")
        bound = self._read_tenant(spec, tenant_id)
        clean = self._filters(spec, filters or {})
        decoded = decode_cursor(cursor) if cursor else None
        rows = self.runner.query(
            spec,
            bound,
            clean,
            limit + 1,
            decoded,
            include_global=spec.shared_read,
        )
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page:
            next_cursor = encode_cursor(page[-1]["created_at"], page[-1]["id"])
        return {"items": page, "next_cursor": next_cursor}

    def update(self, table: str, row_id: str, patch: dict, *, tenant_id: str | None = None) -> dict:
        spec = self._table(table)
        if spec.append_only:
            raise DbError("APPEND_ONLY", "这张表只能追加")
        current = self.get(table, row_id, tenant_id=tenant_id)
        if not current:
            raise DbError("NOT_FOUND", "记录不存在")
        changes = self._prepare(spec, dict(patch), partial=True)
        self._guard_update(spec, current, changes)
        if "version" in spec.columns:
            changes["version"] = int(current.get("version") or 1) + 1
        if "updated_at" in spec.columns and "updated_at" not in changes:
            changes["updated_at"] = datetime.now(timezone.utc)
        bound = self._read_tenant(spec, tenant_id)
        expected = int(current["version"]) if "version" in spec.columns else None
        stored = self.runner.patch(spec, bound, row_id, changes, expected)
        if stored is None:
            raise DbError("VERSION_CONFLICT", "记录已被其他写入更新")
        return stored

    def transition(
        self,
        table: str,
        row_id: str,
        status: str,
        *,
        extra: dict | None = None,
        tenant_id: str | None = None,
    ) -> dict:
        patch = dict(extra or {})
        patch["status"] = status
        return self.update(table, row_id, patch, tenant_id=tenant_id)

    def soft_delete(self, table: str, row_id: str, *, tenant_id: str | None = None) -> dict:
        spec = self._table(table)
        if spec.append_only or not spec.soft_delete:
            raise DbError("APPEND_ONLY", "这张表不能删除")
        return self.update(
            table,
            row_id,
            {"deleted_at": datetime.now(timezone.utc)},
            tenant_id=tenant_id,
        )

    def post_payment(self, values: dict) -> dict:
        amount = require_fen(values.get("amount_fen"), "amount_fen", positive=False)
        key = values.get("idempotency_key")
        if not key:
            raise DbError("IDEMPOTENCY_KEY_REQUIRED", "支付缺少幂等键")
        existing = self._idempotent("payments", key, values.get("tenant_id"), amount, None)
        if existing:
            return existing
        row = dict(values)
        row["amount_fen"] = amount
        return self.insert("payments", row)

    def post_ledger(self, values: dict, *, expected_signature: str) -> dict:
        signature = str(values.get("signature") or "")
        expected = str(expected_signature or "")
        if not signature or not expected or not hmac.compare_digest(signature, expected):
            raise DbError("LEDGER_SIGNATURE_INVALID", "验签失败，未入账")
        amount = require_fen(values.get("amount_fen"), "amount_fen", positive=True)
        key = values.get("idempotency_key")
        if not key:
            raise DbError("IDEMPOTENCY_KEY_REQUIRED", "账本缺少幂等键")
        subject = values.get("subject")
        if subject not in LEDGER_SUBJECTS:
            raise DbError("INVALID_SUBJECT", "账本科目无效")
        existing = self._idempotent("ledger_entries", key, values.get("tenant_id"), amount, subject)
        if existing:
            return existing
        row = dict(values)
        row["amount_fen"] = amount
        row["status"] = "posted"
        return self.insert("ledger_entries", row)

    def save_kpi(self, values: dict) -> dict:
        code = values.get("metric_code")
        period = values.get("period")
        if code not in METRIC_CODES:
            raise DbError("UNKNOWN_METRIC", "未知指标")
        if not period:
            raise DbError("PERIOD_REQUIRED", "指标缺少周期")
        found = self.query(
            "kpi_metrics",
            tenant_id=values.get("tenant_id"),
            filters={"metric_code": code, "period": period},
            limit=1,
        )
        if found["items"]:
            patch = {
                key: values[key]
                for key in ("value", "dimensions", "kpi_period")
                if key in values
            }
            return self.update("kpi_metrics", found["items"][0]["id"], patch, tenant_id=values.get("tenant_id"))
        return self.insert("kpi_metrics", values)

    def record_audit(self, values: dict) -> dict:
        if not values.get("action") or not values.get("resource"):
            raise DbError("AUDIT_REQUIRED", "审计需要 action 和 resource")
        return self.insert("audit_logs", values)

    def record_ai_call(self, values: dict) -> dict:
        if not values.get("model"):
            raise DbError("MODEL_REQUIRED", "AI 调用需要模型名")
        return self.insert("ai_calls", values)

    def reconcile_books(self) -> dict:
        payments = self._pages("payments")
        invoices = self._pages("invoices")
        events = self._pages("payment_events")
        refunds = self._pages("refunds")
        booked = [row for row in payments if row.get("status") in {"succeeded", "refunded"}]
        signed = {
            row["payment_id"]
            for row in events
            if row.get("signature_ok") is True and row.get("status") == "processed"
        }
        issued = {
            row["payment_id"]: int(row["amount_fen"])
            for row in invoices
            if row.get("status") == "issued"
        }
        unmatched = []
        payments_fen = 0
        for row in booked:
            amount = int(row["amount_fen"])
            payments_fen += amount
            if row["id"] not in signed or issued.get(row["id"]) != amount:
                unmatched.append(row["id"])
        invoices_fen = sum(issued.values())
        refunds_fen = sum(int(row["amount_fen"]) for row in refunds if row.get("status") == "succeeded")
        return {
            "balanced": not unmatched and payments_fen == invoices_fen,
            "payments_fen": payments_fen,
            "invoices_fen": invoices_fen,
            "refunds_fen": refunds_fen,
            "unmatched_payment_ids": unmatched,
        }

    def _pages(self, table: str) -> list[dict]:
        rows: list[dict] = []
        cursor = None
        while True:
            page = self.query(table, limit=200, cursor=cursor)
            rows.extend(page["items"])
            cursor = page["next_cursor"]
            if not cursor:
                return rows

    def claim_jobs(self, limit: int = 20) -> list[dict]:
        if self.tenant_id is not None:
            raise DbError("SYSTEM_REQUIRED", "只有系统作用域可以领取任务")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
            raise DbError("INVALID_LIMIT", "领取数量无效")
        self._table("jobs")
        return self.runner.claim_jobs(limit)

    def _idempotent(self, table: str, key: str, tenant_id: str | None, amount: int, subject: str | None):
        found = self.query(table, tenant_id=tenant_id, filters={"idempotency_key": key}, limit=1)
        if not found["items"]:
            return None
        current = found["items"][0]
        if current["amount_fen"] != amount or (subject is not None and current["subject"] != subject):
            raise DbError("IDEMPOTENCY_CONFLICT", "同一幂等键的金额或科目不一致")
        return current

    def _assign_tenant(self, spec: Table, values: dict) -> None:
        if spec.tenant_column is None:
            if self.tenant_id is not None:
                raise DbError("GLOBAL_WRITE", "全局目录只能由系统作用域写入")
            return
        column = spec.tenant_column
        incoming = values.get(column)
        if self.tenant_id is not None:
            if incoming is not None and incoming != self.tenant_id:
                raise DbError("TENANT_MISMATCH", "不能写入其他租户的数据")
            values[column] = self.tenant_id
            return
        if spec.allow_null_tenant and incoming is None:
            values[column] = None
            return
        if not incoming:
            raise DbError("TENANT_REQUIRED", "查询必须带 tenant_id")

    def _read_tenant(self, spec: Table, explicit: str | None) -> str | None:
        if spec.tenant_column is None:
            return None
        if self.tenant_id is not None:
            if explicit not in (None, self.tenant_id):
                raise DbError("TENANT_MISMATCH", "不能读取其他租户的数据")
            return self.tenant_id
        if explicit:
            return explicit
        if spec.tenant_column == "id" or spec.allow_null_tenant or spec.shared_read:
            return None
        raise DbError("TENANT_REQUIRED", "查询必须带 tenant_id")

    def _prepare(self, spec: Table, values: dict, *, partial: bool) -> dict:
        unknown = set(values) - set(spec.columns)
        if unknown:
            raise DbError("UNKNOWN_COLUMN", "未知字段")
        if not partial:
            for column in spec.primary_key:
                if not values.get(column):
                    raise DbError("ID_REQUIRED", "缺少主键")
            now = datetime.now(timezone.utc)
            if "created_at" in spec.columns and "created_at" not in values:
                values["created_at"] = now
            if "updated_at" in spec.columns and "updated_at" not in values:
                values["updated_at"] = now
            if "version" in spec.columns and "version" not in values:
                values["version"] = 1
            if "deleted_at" in spec.columns and "deleted_at" not in values:
                values["deleted_at"] = None
            if spec.initial_status and "status" not in values and "status" in spec.columns:
                values["status"] = spec.initial_status
            for column in spec.json_columns:
                if values.get(column) is None:
                    values[column] = {}
            if spec.name == "tenants":
                values.setdefault("plan", "free")
                if not values.get("feature_flags"):
                    values["feature_flags"] = dict(DEFAULT_FLAGS)
            if spec.name == "jobs" and "attempts" not in values:
                values["attempts"] = 0
            if spec.name == "leads" and "score_v2" not in values and values.get("score") is not None:
                values["score_v2"] = values["score"]
        self._check_values(spec, values)
        return values

    def _check_values(self, spec: Table, values: dict) -> None:
        if "status" in values:
            status = values["status"]
            allowed = spec.transitions if spec.transitions is not None else None
            if allowed is not None and status not in allowed:
                raise DbError("INVALID_STATUS", "状态不在状态机里")
            if spec.statuses is not None and status not in spec.statuses:
                raise DbError("INVALID_STATUS", "状态不在状态机里")
        for column in spec.fen_positive:
            if column in values and values[column] is not None:
                values[column] = require_fen(values[column], column, positive=True)
        for column in spec.fen_columns:
            if column in values and values[column] is not None:
                values[column] = require_fen(values[column], column, positive=False)
        for column in spec.decimal_columns:
            if column in values:
                values[column] = require_decimal(values[column], column)
        if spec.channel_column and spec.channel_column in values and values[spec.channel_column] is not None:
            allowed = CHANNELS | spec.extra_channels
            if values[spec.channel_column] not in allowed:
                raise DbError("UNKNOWN_CHANNEL", "未知获客通道")
        if spec.name == "products" and "source" in values and values["source"] not in _PRODUCT_SOURCES:
            raise DbError("INVALID_SOURCE", "商品来源无效")
        if spec.name == "recalls" and "trigger" in values and values["trigger"] not in _RECALL_TRIGGERS:
            raise DbError("INVALID_TRIGGER", "召回触发类型无效")
        if spec.name == "kpi_metrics" and "metric_code" in values and values["metric_code"] not in METRIC_CODES:
            raise DbError("UNKNOWN_METRIC", "未知指标")
        if spec.name == "leads" and "score" in values and values["score"] is not None:
            score = values["score"]
            if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
                raise DbError("INVALID_SCORE", "线索分必须是 0 到 100 的整数")
        if spec.name == "ledger_entries" and "subject" in values and values["subject"] not in LEDGER_SUBJECTS:
            raise DbError("INVALID_SUBJECT", "账本科目无效")

    def _guard_update(self, spec: Table, current: dict, changes: dict) -> None:
        if not changes:
            raise DbError("EMPTY_PATCH", "没有要更新的字段")
        locked = set(_IMMUTABLE)
        if spec.tenant_column == "tenant_id":
            locked.add("tenant_id")
        for key in changes:
            if key in locked:
                raise DbError("IMMUTABLE_COLUMN", f"不能修改 {key}")
        if "status" in changes and spec.transitions is not None and changes["status"] != current.get("status"):
            allowed = spec.transitions.get(current.get("status"), frozenset())
            if changes["status"] not in allowed:
                raise DbError("INVALID_TRANSITION", "状态不能这样迁移")

    def _filters(self, spec: Table, filters: dict) -> dict:
        clean = {}
        for key, value in filters.items():
            if key in {"tenant_id", "deleted_at"}:
                raise DbError("INVALID_FILTER", "不能用这个字段过滤")
            if key not in spec.columns:
                raise DbError("UNKNOWN_COLUMN", "未知字段")
            clean[key] = value
        return clean

    def _table(self, name: str) -> Table:
        if not self._open:
            raise DbError("SCOPE_CLOSED", "数据库操作必须放在事务里")
        spec = TABLES.get(name)
        if spec is None:
            raise DbError("UNKNOWN_TABLE", "未知表")
        if not spec.operational:
            raise DbError("NOT_OPERATIONAL", "这张表不经过业务仓库")
        return spec


# Imported so tests and callers can build an in-memory database without PostgreSQL.
__all__ = ["Database", "MemoryRunner", "Scope", "decode_cursor", "encode_cursor"]
