from config.settings import Settings
from db.store import DocumentStore

from app.core.errors import AppError
from app.services.common import PLANS, base_doc, new_id


def parse_principal(authorization: str | None, settings: Settings) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("UNAUTHENTICATED", "需要登录", 401)
    token = authorization.split(" ", 1)[1].strip()
    if settings.auth_mode == "demo":
        if token == "demo":
            return "demo-seller"
        if token.startswith("demo:"):
            key = token.split(":", 1)[1].strip()
            if key:
                return f"demo-{key}"
        raise AppError("UNAUTHENTICATED", "演示登录凭证无效", 401)
    raise AppError("AUTH_NOT_CONFIGURED", "CloudBase Auth 尚未配置，当前仅开放演示登录", 503)


def bootstrap(store: DocumentStore, cloudbase_user_id: str, display_name: str | None) -> dict:
    user = store.find_global("users", cloudbase_user_id=cloudbase_user_id)
    if user:
        return profile(store, user)
    user_id = new_id("user")
    tenant_id = new_id("tenant")
    member_id = new_id("member")
    entitlement_id = new_id("ent")
    quota_id = new_id("quota")
    name = (display_name or "演示卖家").strip() or "演示卖家"
    plan = PLANS[0]
    store.insert(
        "users",
        base_doc(tenant_id, user_id, id=user_id, cloudbase_user_id=cloudbase_user_id, display_name=name),
    )
    store.insert(
        "tenants",
        base_doc(tenant_id, user_id, id=tenant_id, name=f"{name}的企业", plan_id=plan["id"]),
    )
    store.insert(
        "tenant_members",
        base_doc(tenant_id, user_id, id=member_id, user_id=user_id, role="owner"),
    )
    store.insert(
        "entitlements",
        base_doc(
            tenant_id,
            user_id,
            id=entitlement_id,
            plan_id=plan["id"],
            modules=["analysis", "leads", "campaigns", "lifecycle", "billing"],
        ),
    )
    store.insert(
        "quota_balances",
        base_doc(
            tenant_id,
            user_id,
            id=quota_id,
            available=dict(plan["quota"]),
            reserved={"analysis": 0, "discovery": 0, "send": 0},
            plan_id=plan["id"],
        ),
    )
    user = store.get("users", user_id)
    return profile(store, user)


def profile(store: DocumentStore, user: dict) -> dict:
    tenant = store.get("tenants", user["tenant_id"])
    member = store.find_global("tenant_members", tenant_id=user["tenant_id"], user_id=user["id"])
    entitlement = store.find_global("entitlements", tenant_id=user["tenant_id"])
    quota = store.find_global("quota_balances", tenant_id=user["tenant_id"])
    return {
        "user": {
            "id": user["id"],
            "display_name": user["display_name"],
            "cloudbase_user_id": user["cloudbase_user_id"],
        },
        "tenant": {"id": tenant["id"], "name": tenant["name"], "plan_id": tenant["plan_id"]},
        "role": member["role"] if member else "viewer",
        "entitlement": entitlement,
        "quota": {
            "available": quota["available"] if quota else {},
            "reserved": quota["reserved"] if quota else {},
        },
    }


WRITE_ROLES = {"owner", "admin", "analyst", "marketer"}


def require_write(role: str) -> None:
    if role not in WRITE_ROLES:
        raise AppError("FORBIDDEN", "当前角色不能执行这个操作", 403)
