import re
from pathlib import Path

from db.schema import TABLES

SQL = Path(__file__).resolve().parents[2] / "backend" / "db" / "sql" / "0001_core"
UP = (SQL / "up.sql").read_text(encoding="utf-8")
DOWN = (SQL / "down.sql").read_text(encoding="utf-8")


def test_migration_up_and_down_cover_the_same_tables():
    created = set(re.findall(r"CREATE TABLE ([a-z_]+) \(", UP))
    assert created == set(TABLES)
    for name in TABLES:
        assert f"DROP TABLE IF EXISTS {name} CASCADE;" in DOWN
    assert "ENABLE ROW LEVEL SECURITY" in UP
    assert "amount_fen bigint" in UP
    assert "DROP FUNCTION IF EXISTS reject_mutation();" in DOWN
