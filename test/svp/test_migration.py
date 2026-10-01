import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from db.errors import DbError
from db.migrate import split_sql, versions
from db.money import require_fen
from db.repository import Database
from db.runners import MemoryRunner, render_claim, render_query
from db.schema import APPEND_TABLES, RLS_TABLES, TABLES, TOUCH_TABLES, declared_statuses

SQL_ROOT = Path(__file__).resolve().parents[2] / "backend" / "db" / "sql"
UP = (SQL_ROOT / "0001_core" / "up.sql").read_text(encoding="utf-8")
DOWN = (SQL_ROOT / "0001_core" / "down.sql").read_text(encoding="utf-8")


def parse_tables(sql: str) -> dict[str, dict]:
    tables = {}
    lines = sql.splitlines()
    index = 0
    while index < len(lines):
        match = re.match(r"CREATE TABLE ([a-z_]+) \(", lines[index])
        if not match:
            index += 1
            continue
        name = match.group(1)
        index += 1
        columns = []
        statuses = None
        while index < len(lines) and not lines[index].strip().startswith(")"):
            stripped = lines[index].strip().rstrip(",")
            index += 1
            if not stripped or stripped.startswith("--"):
                continue
            head = stripped.split()[0]
            if head in {"CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "EXCLUDE"}:
                continue
            columns.append(head)
            if head == "status" and "CHECK (status IN (" in stripped:
                statuses = set(re.findall(r"'([^']+)'", stripped))
        tables[name] = {"columns": columns, "statuses": statuses}
    return tables


def quoted_array(sql: str, marker: str) -> list[str]:
    start = sql.index(marker)
    end = sql.index("]", start)
    return re.findall(r"'([a-z0-9_]+)'", sql[start:end])


def test_migration_matches_catalog():
    parsed = parse_tables(UP)
    assert set(parsed) == set(TABLES)
    for name, spec in TABLES.items():
        assert parsed[name]["columns"] == list(spec.columns)
        expected = declared_statuses(spec)
        if expected is None:
            assert parsed[name]["statuses"] is None
        else:
            assert parsed[name]["statuses"] == expected
    for name in TABLES:
        assert f"DROP TABLE IF EXISTS {name} CASCADE;" in DOWN
    assert quoted_array(UP, "-- tenant_rls") == list(RLS_TABLES)
    assert quoted_array(UP, "-- touch_updated_at") == list(TOUCH_TABLES)
    assert quoted_array(UP, "-- append_only") == list(APPEND_TABLES)
    for snippet in (
        "CREATE UNIQUE INDEX users_tenant_email",
        "CREATE UNIQUE INDEX leads_tenant_email",
        "CREATE UNIQUE INDEX leads_dedupe",
        "CREATE UNIQUE INDEX deliveries_campaign_lead",
        "CREATE UNIQUE INDEX kpi_metrics_period",
        "CREATE INDEX ai_calls_tenant_created",
        "CREATE INDEX audit_logs_tenant_created",
        "USING gin (attributes)",
        "USING gin (metrics)",
        "PARTITION BY RANGE (created_at)",
        "ENABLE ROW LEVEL SECURITY",
        "score_v2 numeric",
        "amount_fen bigint",
        "net_margin numeric",
        "rules_version text",
        "idempotency_key text",
        "reject_mutation",
    ):
        assert snippet in UP
    assert "DROP FUNCTION IF EXISTS reject_mutation();" in DOWN
    assert versions() == ["0001_core"]


def test_sql_splitter_keeps_function_bodies():
    statements = split_sql(UP)
    functions = [item for item in statements if item.startswith("CREATE FUNCTION")]
    assert len(functions) == 3
    touch = next(item for item in functions if "touch_updated_at" in item)
    assert "RETURN NEW;" in touch
    assert touch.strip().endswith("$$;")
    ensure = next(item for item in functions if "ensure_month_partition" in item)
    assert "ENABLE ROW LEVEL SECURITY" in ensure
    assert ensure.strip().endswith("$$;")
    assert all(not item.startswith("--") for item in statements)


def test_queries_are_tenant_scoped_and_keyset():
    sql = render_query(
        "leads",
        "tenant_id",
        ["status"],
        include_global=False,
        soft_delete=True,
        cursor=True,
    )
    assert "tenant_id = %s" in sql
    assert "(created_at, id) < (%s, %s)" in sql
    assert "OFFSET" not in sql
    assert "FOR UPDATE SKIP LOCKED" in render_claim()


def test_money_rejects_bool_and_float():
    with pytest.raises(DbError) as exc:
        require_fen(True, "amount_fen", positive=True)
    assert exc.value.code == "INVALID_AMOUNT"


def test_tenant_isolation_cursor_and_states():
    db = Database(MemoryRunner())
    with db.system() as scope:
        scope.insert("tenants", {"id": "t1", "name": "甲"})
        scope.insert("tenants", {"id": "t2", "name": "乙"})
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    with db.tenant("t1") as scope:
        assert scope.runner.config["app.tenant_id"] == "t1"
        assert scope.runner.config["app.bypass_rls"] == "off"
        for index in range(3):
            scope.insert(
                "products",
                {
                    "id": f"p{index}",
                    "source": "manual",
                    "title": f"货{index}",
                    "sku": f"SKU-{index}",
                    "normalized_sku": f"SKU-{index}",
                    "created_at": base + timedelta(minutes=index),
                },
            )
        page = scope.query("products", limit=2)
        assert [item["id"] for item in page["items"]] == ["p2", "p1"]
        rest = scope.query("products", limit=2, cursor=page["next_cursor"])
        assert [item["id"] for item in rest["items"]] == ["p0"]
        assert rest["next_cursor"] is None
        lead = scope.insert(
            "leads",
            {
                "id": "lead1",
                "source_channel": "ecommerce",
                "email": "buyer@example.com",
                "score": 80,
            },
        )
        assert lead["score_v2"] == Decimal("80")
        with pytest.raises(DbError) as dup:
            scope.insert(
                "leads",
                {"id": "lead2", "source_channel": "social", "email": "buyer@example.com", "score": 10},
            )
        assert dup.value.code == "CONFLICT"
        scope.insert("campaigns", {"id": "c1", "name": "首封", "channel": "email"})
        with pytest.raises(DbError) as jump:
            scope.transition("campaigns", "c1", "sending")
        assert jump.value.code == "INVALID_TRANSITION"
        approved = scope.transition("campaigns", "c1", "pending_approval")
        assert approved["status"] == "pending_approval"
        scope.soft_delete("products", "p0")
        assert scope.get("products", "p0") is None

    with db.tenant("t2") as scope:
        assert scope.get("products", "p2") is None
        with pytest.raises(DbError) as mismatch:
            scope.insert(
                "products",
                {
                    "id": "px",
                    "tenant_id": "t1",
                    "source": "csv",
                    "title": "越权",
                    "sku": "X",
                    "normalized_sku": "X",
                },
            )
        assert mismatch.value.code == "TENANT_MISMATCH"
        with pytest.raises(DbError) as amount:
            scope.insert(
                "selection_reports",
                {
                    "id": "r1",
                    "product_id": "missing",
                    "route": "CN-US",
                    "market": "US",
                    "rules_version": "pg-rules-1.0",
                    "net_margin": 0.5,
                },
            )
        assert amount.value.code == "INVALID_AMOUNT"


def test_ledger_audit_and_job_claim():
    db = Database(MemoryRunner())
    with db.system() as scope:
        scope.insert("tenants", {"id": "t1", "name": "甲"})
    with db.tenant("t1") as scope:
        posted = scope.post_ledger(
            {
                "id": "led1",
                "amount_fen": 1500,
                "subject": "agency_commission",
                "idempotency_key": "pay-1",
                "signature": "signed",
            },
            expected_signature="signed",
        )
        again = scope.post_ledger(
            {
                "id": "led2",
                "amount_fen": 1500,
                "subject": "agency_commission",
                "idempotency_key": "pay-1",
                "signature": "signed",
            },
            expected_signature="signed",
        )
        assert again["id"] == posted["id"]
        with pytest.raises(DbError) as bad:
            scope.post_ledger(
                {
                    "id": "led3",
                    "amount_fen": 1500,
                    "subject": "raas",
                    "idempotency_key": "pay-2",
                    "signature": "nope",
                },
                expected_signature="signed",
            )
        assert bad.value.code == "LEDGER_SIGNATURE_INVALID"
        assert scope.query("ledger_entries", limit=10)["items"] == [posted]
        with pytest.raises(DbError) as clash:
            scope.post_ledger(
                {
                    "id": "led4",
                    "amount_fen": 99,
                    "subject": "agency_commission",
                    "idempotency_key": "pay-1",
                    "signature": "signed",
                },
                expected_signature="signed",
            )
        assert clash.value.code == "IDEMPOTENCY_CONFLICT"
        scope.record_audit({"id": "a1", "action": "login", "resource": "session", "summary": {"ok": True}})
        with pytest.raises(DbError) as locked:
            scope.update("audit_logs", "a1", {"action": "tamper"})
        assert locked.value.code == "APPEND_ONLY"
        scope.insert("jobs", {"id": "j1", "job_type": "product_analysis"})
        with pytest.raises(DbError) as claim:
            scope.claim_jobs()
        assert claim.value.code == "SYSTEM_REQUIRED"
    with db.system() as scope:
        assert scope.runner.config["app.bypass_rls"] == "on"
        claimed = scope.claim_jobs()
        assert claimed[0]["status"] == "running"
        assert claimed[0]["attempts"] == 1


def test_failed_transaction_rolls_back():
    db = Database(MemoryRunner())
    with pytest.raises(RuntimeError):
        with db.system() as scope:
            scope.insert("tenants", {"id": "t1", "name": "甲"})
            raise RuntimeError("boom")
    with db.system() as scope:
        assert scope.get("tenants", "t1") is None


def test_reconcile_books_needs_signed_event_and_invoice():
    db = Database(MemoryRunner())
    with db.system() as scope:
        scope.insert("tenants", {"id": "t1", "name": "甲"})
    with db.tenant("t1") as scope:
        scope.insert(
            "payments",
            {
                "id": "pay1",
                "user_id": "u1",
                "provider": "mock",
                "amount_fen": 1000,
                "currency": "CNY",
                "status": "succeeded",
                "idempotency_key": "k1",
            },
        )
        open_books = scope.reconcile_books()
        assert open_books["balanced"] is False
        assert open_books["unmatched_payment_ids"] == ["pay1"]
        scope.insert(
            "payment_events",
            {
                "id": "ev1",
                "payment_id": "pay1",
                "provider": "mock",
                "external_id": "evt-1",
                "signature_ok": True,
                "status": "processed",
                "idempotency_key": "evt-1",
            },
        )
        scope.insert(
            "invoices",
            {
                "id": "inv1",
                "payment_id": "pay1",
                "amount_fen": 1000,
                "currency": "CNY",
                "status": "issued",
            },
        )
        closed = scope.reconcile_books()
        assert closed["balanced"] is True
        assert closed["payments_fen"] == 1000
        assert closed["invoices_fen"] == 1000
        assert closed["refunds_fen"] == 0


def test_version_conflict():
    class ConflictRunner(MemoryRunner):
        def patch(self, spec, tenant_id, row_id, values, expected_version):
            del spec, tenant_id, row_id, values, expected_version
            return None

    db = Database(ConflictRunner())
    with db.system() as scope:
        scope.insert("tenants", {"id": "t1", "name": "甲"})
    with db.tenant("t1") as scope:
        scope.insert(
            "products",
            {"id": "p1", "source": "catalog", "title": "杯", "sku": "CUP", "normalized_sku": "CUP"},
        )
        with pytest.raises(DbError) as exc:
            scope.update("products", "p1", {"title": "新杯"})
        assert exc.value.code == "VERSION_CONFLICT"
