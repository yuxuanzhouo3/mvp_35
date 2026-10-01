from fastapi import Request

from app.services.common import envelope
from app.services.identity import bootstrap, parse_principal, profile, require_permission, require_write


def bind(request: Request, authorization: str | None, *, write: bool = False, permission: str | None = None):
    settings = request.app.state.settings
    store = request.app.state.store
    principal = parse_principal(authorization, settings, store)
    user = store.find_global("users", cloudbase_user_id=principal)
    prof = profile(store, user) if user else bootstrap(store, principal, None)
    if write:
        require_write(prof["role"])
    if permission:
        require_permission(prof["role"], permission)
    return settings, store, prof


def respond(request: Request, data):
    return envelope(data, request.state.request_id)
