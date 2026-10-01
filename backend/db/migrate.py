"""Apply backend/db/sql/<version>/{up,down}.sql in order.

Each version is one transaction. up.sql records itself in schema_migrations.
down.sql drops the objects that version created.
"""

from pathlib import Path

from db.errors import DbError

SQL_ROOT = Path(__file__).resolve().parent / "sql"


def versions() -> list[str]:
    found = []
    if not SQL_ROOT.is_dir():
        return found
    for path in sorted(SQL_ROOT.iterdir()):
        if (path / "up.sql").is_file() and (path / "down.sql").is_file():
            found.append(path.name)
    return found


def split_sql(script: str) -> list[str]:
    """Split a migration on semicolons, keeping dollar-quoted function bodies intact."""
    statements: list[str] = []
    buffer: list[str] = []
    in_dollar = False
    for line in script.splitlines():
        if not in_dollar and not buffer and (not line.strip() or line.strip().startswith("--")):
            continue
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        buffer.append(line)
        if not in_dollar and line.strip().endswith(";"):
            text = "\n".join(buffer).strip()
            if text:
                statements.append(text)
            buffer = []
    if buffer and "\n".join(buffer).strip():
        raise DbError("SQL_PARSE", "SQL 脚本最后一条语句没有结束")
    return statements


def apply(conn, *, direction: str = "up", target: str | None = None) -> list[str]:
    if direction not in {"up", "down"}:
        raise DbError("INVALID_DIRECTION", "迁移方向只能是 up 或 down")
    ordered = versions()
    applied = set(_applied(conn))
    done: list[str] = []
    if direction == "up":
        for version in ordered:
            if version in applied:
                continue
            _run(conn, version, "up")
            done.append(version)
            if target == version:
                break
        return done
    for version in reversed(ordered):
        if version not in applied:
            continue
        if target is not None and version <= target:
            break
        _run(conn, version, "down")
        done.append(version)
    return done


def _run(conn, version: str, direction: str) -> None:
    path = SQL_ROOT / version / f"{direction}.sql"
    statements = split_sql(path.read_text(encoding="utf-8"))
    with conn.transaction():
        for statement in statements:
            conn.execute(statement)


def _applied(conn) -> list[str]:
    try:
        rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    except Exception:
        conn.rollback()
        return []
    found = []
    for row in rows:
        if isinstance(row, dict):
            found.append(row["version"])
        else:
            found.append(row[0])
    return found
