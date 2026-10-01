from config.settings import Settings
from db.store import DocumentStore

from app.core.errors import AppError
from app.modules.tokens import read_access
from app.services.common import PLANS, base_doc, new_id

PERMISSIONS = [
    "analysis.read",
    "analysis.write",
    "leads.read",
    "leads.write",
    "campaigns.send",
    "billing.write",
    "audit.read",
]

ROLE_PERMISSIONS = {
    "owner": PERMISSIONS,
    "admin": PERMISSIONS,
    "analyst": ["analysis.read", "analysis.write", "leads.read", "audit.read"],
    "marketer": ["leads.read", "leads.write", "campaigns.send"],
    "viewer": ["analysis.read", "leads.read", "audit.read"],
}


def parse_principal(authorization: str | None, settings: Settings, store: DocumentStore | None = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("UNAUTHENTICATED", "需要登录", 401)
    token = authorization.split(" ", 1)[1].strip()
    if token.startswith("pg1."):
        payload = read_access(settings.session_secret, token)
        if store is not None:
            session = store.get("sessions", payload["sid"])
            if not session or session.get("revoked_at"):
                raise AppError("UNAUTHENTICATED", "会话已失效", 401)
        return payload["sub"]
    if settings.auth_mode == "demo":
        if token == "demo":
            return "demo-seller"
        if token.startswith("demo:"):
            key = token.split(":", 1)[1].strip()
            if key:
                return f"demo-{key}"
        raise AppError("UNAUTHENTICATED", "演示登录凭证无效", 401)
    raise AppError("AUTH_NOT_CONFIGURED", "CloudBase Auth 尚未配置，当前仅开放演示登录", 503)


def bootstrap(
    store: DocumentStore,
    cloudbase_user_id: str,
    display_name: str | None,
    *,
    email: str | None = None,
    phone: str | None = None,
    password_hash: str | None = None,
    status: str = "active",
) -> dict:
    user = store.find_global("users", cloudbase_user_id=cloudbase_user_id)
    if user:
        return profile(store, user)
    user_id = new_id("user")
    tenant_id = new_id("tenant")
    member_id = new_id("member")
    entitlement_id = new_id("ent")
    quota_id = new_id("quota")
    role_id = new_id("role")
    name = (display_name or "演示卖家").strip() or "演示卖家"
    plan = PLANS[0]
    store.insert(
        "users",
        base_doc(
            tenant_id,
            user_id,
            id=user_id,
            cloudbase_user_id=cloudbase_user_id,
            display_name=name,
            email=email,
            phone=phone,
            password_hash=password_hash,
            role="owner",
            status=status,
        ),
    )
    store.insert(
        "tenants",
        base_doc(
            tenant_id,
            user_id,
            id=tenant_id,
            name=f"{name}的企业",
            plan_id=plan["id"],
            plan=plan["id"],
            status="active",
            region=None,
        ),
    )
    store.insert(
        "tenant_members",
        base_doc(tenant_id, user_id, id=member_id, user_id=user_id, role="owner"),
    )
    store.insert(
        "roles",
        base_doc(tenant_id, user_id, id=role_id, name="owner", permissions=list(PERMISSIONS)),
    )
    store.insert(
        "permissions",
        base_doc(tenant_id, user_id, id=new_id("perm"), name="owner", permissions=list(PERMISSIONS)),
    )
    store.insert(
        "user_roles",
        base_doc(tenant_id, user_id, id=new_id("ur"), user_id=user_id, role_id=role_id),
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
            "email": user.get("email"),
            "phone": user.get("phone"),
            "status": user.get("status") or "active",
            "role": user.get("role") or (member["role"] if member else "viewer"),
        },
        "tenant": {"id": tenant["id"], "name": tenant["name"], "plan_id": tenant["plan_id"]},
        "role": member["role"] if member else "viewer",
        "permissions": permissions_for(member["role"] if member else "viewer"),
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


def permissions_for(role: str) -> list[str]:
    return list(ROLE_PERMISSIONS.get(role, ()))


def require_permission(role: str, permission: str) -> None:
    if permission not in ROLE_PERMISSIONS.get(role, ()):
        raise AppError("FORBIDDEN", "当前角色没有这个权限", 403, {"permission": permission})
