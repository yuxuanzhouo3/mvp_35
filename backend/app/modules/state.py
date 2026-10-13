from app.core.errors import AppError

TRANSITIONS = {
    "User": {
        "pending": {"active"},
        "active": {"suspended"},
        "suspended": {"active", "deleted"},
        "deleted": set(),
    },
    "Payment": {
        "created": {"pending"},
        "pending": {"succeeded", "failed"},
        "succeeded": {"refunded"},
        "failed": set(),
        "refunded": set(),
    },
    "Report": {
        "draft": {"analyzing"},
        "analyzing": {"completed"},
        "completed": {"acquired"},
        "acquired": set(),
    },
    "Task": {
        "created": {"running"},
        "running": {"paused", "completed", "failed"},
        "paused": {"running"},
        "completed": set(),
        "failed": set(),
    },
    "Lead": {
        "new": {"scored", "qualified"},
        "scored": {"qualified"},
        "qualified": {"contacted"},
        "contacted": {"replied", "lost", "recalled"},
        "replied": {"won", "lost", "recalled"},
        "won": set(),
        "lost": {"recalled"},
        "recalled": set(),
    },
    "Campaign": {
        "draft": {"pending_approval", "scheduled"},
        "pending_approval": {"approved", "draft"},
        "approved": {"sending", "paused"},
        "scheduled": {"sending", "paused"},
        "sending": {"sent", "paused"},
        "sent": {"completed"},
        "paused": {"draft", "approved", "sending"},
        "completed": set(),
    },
    "Recall": {
        "triggered": {"queued"},
        "queued": {"delivered", "failed"},
        "delivered": {"recovered", "failed"},
        "recovered": set(),
        "failed": set(),
    },
}


def can_transition(kind: str, current: str, nxt: str) -> bool:
    return nxt in TRANSITIONS.get(kind, {}).get(current, set())


def transition(kind: str, current: str, nxt: str) -> str:
    if not can_transition(kind, current, nxt):
        raise AppError(
            "INVALID_STATE",
            f"{kind} 不能从 {current} 变为 {nxt}",
            409,
            {"kind": kind, "from": current, "to": nxt},
        )
    return nxt
