"""CloudBase document store behavior, without calling the remote database."""

import json

from db.cloudbase_store import CloudBaseStore


class FakeSql:
    def __init__(self):
        self.statements = []
        self.rows: dict[tuple[str, str], str] = {}

    def __call__(self, sql: str) -> dict:
        self.statements.append(sql)
        if sql.lstrip().upper().startswith("SELECT"):
            return {"columns": ["collection", "id", "body"], "rows": [[key[0], key[1], body] for key, body in self.rows.items()]}
        if sql.lstrip().upper().startswith("DELETE"):
            self.rows.pop((_field(sql, "collection"), _field(sql, "id")), None)
            return {"columns": [], "rows": []}
        if "INSERT INTO documents" in sql:
            collection, doc_id, body = _insert_parts(sql)
            self.rows[(collection, doc_id)] = body
        return {"columns": [], "rows": []}


def _field(sql: str, name: str) -> str:
    marker = f"{name} = '"
    start = sql.index(marker) + len(marker)
    end = sql.index("'", start)
    return sql[start:end]


def _insert_parts(sql: str) -> tuple[str, str, str]:
    values = sql.split("VALUES (", 1)[1]
    collection, rest = _quoted(values)
    doc_id, rest = _quoted(rest)
    _, rest = _quoted_or_null(rest)
    body, _rest = _quoted(rest)
    return collection, doc_id, body


def _quoted(text: str) -> tuple[str, str]:
    start = text.index("'") + 1
    chars = []
    index = start
    while index < len(text):
        if text[index] == "'":
            if index + 1 < len(text) and text[index + 1] == "'":
                chars.append("'")
                index += 2
                continue
            return "".join(chars), text[index + 1 :]
        chars.append(text[index])
        index += 1
    raise AssertionError("unclosed sql string")


def _quoted_or_null(text: str) -> tuple[str | None, str]:
    stripped = text.lstrip(" ,")
    if stripped.startswith("NULL"):
        return None, stripped[4:]
    return _quoted(stripped)


def test_register_shaped_insert_roundtrip_stays_in_cache():
    sql = FakeSql()
    store = CloudBaseStore("env-test", execute=sql)
    store.insert("users", {"id": "user_1", "tenant_id": "tenant_1", "email": "a@b.c", "deleted_at": None})
    found = store.find_global("users", email="a@b.c")
    assert found["id"] == "user_1"
    assert any("INSERT INTO documents" in item and "user_1" in item for item in sql.statements)


def test_duplicate_id_is_rejected():
    store = CloudBaseStore("env-test", execute=FakeSql())
    store.insert("users", {"id": "user_1", "tenant_id": "tenant_1", "deleted_at": None})
    try:
        store.insert("users", {"id": "user_1", "tenant_id": "tenant_1", "deleted_at": None})
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate id was inserted")


def test_soft_delete_is_hidden_and_tenant_filter_holds():
    store = CloudBaseStore("env-test", execute=FakeSql())
    store.insert(
        "products",
        {"id": "p1", "tenant_id": "tenant_1", "title": "cup", "created_at": "2026-10-01T00:00:00+00:00", "deleted_at": None},
    )
    store.insert(
        "products",
        {"id": "p2", "tenant_id": "tenant_2", "title": "other", "created_at": "2026-10-01T00:00:01+00:00", "deleted_at": None},
    )
    store.touch("products", "p1", {"deleted_at": "2026-10-01T01:00:00+00:00"})
    assert store.get("products", "p1") is None
    listed = store.query("products", tenant_id="tenant_2")
    assert [item["id"] for item in listed["items"]] == ["p2"]


def test_load_reads_remote_body_json():
    body = {"id": "user_9", "tenant_id": "tenant_9", "email": "remote@b.c", "deleted_at": None}

    def execute(sql: str) -> dict:
        if sql.lstrip().upper().startswith("SELECT"):
            return {"columns": ["collection", "id", "body"], "rows": [["users", "user_9", json.dumps(body)]]}
        return {"columns": [], "rows": []}

    store = CloudBaseStore("env-test", execute=execute)
    found = store.find_global("users", email="remote@b.c")
    assert found["id"] == "user_9"
