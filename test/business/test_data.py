import json
from pathlib import Path

from fastapi.testclient import TestClient

from db.repository import Database
from db.runners import MemoryRunner
from test.svp.test_e2e_kpi import test_eight_rates_five_timings_and_redlines

S4 = json.loads((Path(__file__).resolve().parents[2] / "backend" / "config" / "s4-v1.0.0.json").read_text())


def test_eight_rates_five_timings_redlines_and_books(client: TestClient):
    test_eight_rates_five_timings_and_redlines(client)
    assert S4["rollback"]["delivery_rate"] == 0.95
    assert S4["rollback"]["bounce_rate"] == 0.015
    assert S4["rollback"]["complaint_rate"] == 0.001


def test_signed_books_balance_and_redlines_match_the_s2_floors():
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
                "amount_fen": 29900,
                "currency": "CNY",
                "status": "succeeded",
                "idempotency_key": "biz-1",
            },
        )
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
            {"id": "inv1", "payment_id": "pay1", "amount_fen": 29900, "currency": "CNY", "status": "issued"},
        )
        books = scope.reconcile_books()
    assert books["balanced"] is True
    assert books["payments_fen"] == books["invoices_fen"] == 29900
