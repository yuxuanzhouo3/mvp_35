from fastapi import Request

from app.services.common import envelope
from app.services.identity import bootstrap, parse_principal, profile, require_permission, require_write


def bind(request: Request, authorization: str | None, *, write: bool = False, permission: str | None = None):
    settings = request.app.state.settings
    store = request.app.state.store
    principal = parse_principal(authorization, settings, store)
    user = store.find_global("users", cloudbase_user_id=principal)
    if user is None and settings.auth_mode == "demo" and principal == "demo-seller":
        sellers = [
            row
            for row in store.query("users", limit=20)["items"]
            if (row.get("status") or "active") == "active"
            and row.get("username") != "admin"
            and row.get("cloudbase_user_id") != "local:admin"
        ]
        if len(sellers) == 1:
            user = sellers[0]
    prof = profile(store, user) if user else bootstrap(store, principal, None)
    if write:
        require_write(prof["role"])
    if permission:
        require_permission(prof["role"], permission)
    return settings, store, prof


def respond(request: Request, data):
    return envelope(data, request.state.request_id)
