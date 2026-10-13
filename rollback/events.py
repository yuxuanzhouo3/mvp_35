"""Replay accepted events onto the current store. Replay never sends mail or pays again."""

import json
from pathlib import Path

from rollback.errors import RollbackError
from rollback.store import collections, transaction

ACCEPTED_PREFIX = "1."


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _payment_collection(data: dict) -> str:
    engine = (data.get("meta") or {}).get("engine")
    return "payments" if engine == "postgresql" else "payment_orders"


def _delivery_collection(data: dict) -> str:
    engine = (data.get("meta") or {}).get("engine")
    return "deliveries" if engine == "postgresql" else "outreach_messages"


def _seen_webhook(cols: dict, provider: str, event_id: str) -> bool:
    for doc in (cols.get("webhook_events") or {}).values():
        if doc.get("provider") == provider and doc.get("event_id") == event_id and not doc.get("deleted_at"):
            return True
    return False


def _seen_idempotency(cols: dict, collection: str, tenant_id: str, key: str) -> dict | None:
    for doc in (cols.get(collection) or {}).values():
        if doc.get("deleted_at"):
            continue
        if doc.get("tenant_id") == tenant_id and doc.get("idempotency_key") == key:
            return doc
    return None


def apply_event(data: dict, event: dict) -> str:
    version = str(event.get("version") or "")
    if not version.startswith(ACCEPTED_PREFIX):
        return "dead"
    if event.get("verified") is not True:
        return "dead"
    name = event.get("event")
    tenant_id = event.get("tenant_id")
    provider = event.get("provider") or ""
    event_id = event.get("event_id") or ""
    key = event.get("idempotency_key") or ""
    if not tenant_id or not provider or not event_id or not key:
        return "dead"
    cols = collections(data)
    if _seen_webhook(cols, provider, event_id):
        return "skipped"
    if name == "payment.succeeded":
        collection = _payment_collection(data)
        if _seen_idempotency(cols, collection, tenant_id, key):
            return "skipped"
        amount = int((event.get("payload") or {}).get("amount_fen") or 0)
        if amount <= 0:
            return "dead"
        doc_id = f"ord_{event_id}"
        cols.setdefault(collection, {})[doc_id] = {
            "id": doc_id,
            "tenant_id": tenant_id,
            "provider": provider,
            "event_id": event_id,
            "idempotency_key": key,
            "amount_fen": amount,
            "currency": (event.get("payload") or {}).get("currency") or "CNY",
            "status": "succeeded",
            "deleted_at": None,
        }
    elif name == "campaign.delivered":
        collection = _delivery_collection(data)
        if _seen_idempotency(cols, collection, tenant_id, key):
            return "skipped"
        payload = event.get("payload") or {}
        doc_id = f"msg_{event_id}"
        cols.setdefault(collection, {})[doc_id] = {
            "id": doc_id,
            "tenant_id": tenant_id,
            "provider": provider,
            "event_id": event_id,
            "idempotency_key": key,
            "lead_id": payload.get("lead_id"),
            "campaign_id": payload.get("campaign_id"),
            "status": "delivered",
            "deleted_at": None,
        }
    else:
        return "dead"
    cols.setdefault("webhook_events", {})[f"wh_{provider}_{event_id}"] = {
        "id": f"wh_{provider}_{event_id}",
        "tenant_id": tenant_id,
        "provider": provider,
        "event_id": event_id,
        "idempotency_key": key,
        "event": name,
        "deleted_at": None,
    }
    return "applied"


def replay(store_path, events, dead_letter_path) -> dict:
    dead_path = Path(dead_letter_path)
    summary = {"applied": 0, "skipped": 0, "dead": 0}

    def op(data: dict) -> dict:
        for event in events:
            result = apply_event(data, event)
            summary[result] += 1
            if result == "dead":
                _append_jsonl(dead_path, event)
        return summary

    return transaction(store_path, op)


def load_events(path) -> list[dict]:
    file = Path(path)
    if not file.exists():
        return []
    rows = []
    for line in file.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise RollbackError("事件日志必须是 JSON 对象")
        rows.append(row)
    return rows
