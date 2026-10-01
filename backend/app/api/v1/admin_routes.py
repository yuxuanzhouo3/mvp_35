"""Tenant admin reads for the /admin screens.

Lists come from the document store. Empty tenants return empty lists and zero
counts. Platform user recall is user_recall_campaigns, never recall_jobs.
Creates stay drafts and do not send mail or post a reward ledger.
"""

import hashlib
import secrets

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.api.deps import bind, respond
from app.core.errors import AppError
from app.modules.passwords import hash_password, verify_password
from app.services.common import base_doc, new_id, within_window

router = APIRouter(prefix="/api/v1")

PLACEMENTS = (
    "dashboard_top",
    "pricing_banner",
    "copilot_sidebar",
    "home_mid_banner",
    "report_footer",
)


class AdIn(BaseModel):
    title: str
    placement: str
    media_type: str = "image"


class InvitationIn(BaseModel):
    name: str


class RecallIn(BaseModel):
    name: str


class StatusIn(BaseModel):
    status: str
    reason: str = ""


class SegmentIn(BaseModel):
    name: str
    stage: str | None = None
    query: str | None = None


class SettingsIn(BaseModel):
    environment_label: str | None = None
    timezone: str | None = None
    window_days: int | None = None


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


def _admin_read(request: Request, authorization: str | None):
    _settings, store, prof = bind(request, authorization, permission="audit.read")
    return store, prof


def _admin_write(request: Request, authorization: str | None):
    _settings, store, prof = bind(request, authorization, write=True, permission="audit.read")
    if prof["role"] not in {"owner", "admin"}:
        raise AppError("FORBIDDEN", "只有所有者或管理员可以创建运营记录", 403)
    return store, prof


def _mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return f"{local[:2]}***@{domain}"


def _csv_cell(value: str) -> str:
    text = (value or "").replace('"', '""')
    if text[:1] in "=+-@":
        text = "'" + text
    return f'"{text}"'


def _in_window(row: dict, window_days: int | None) -> bool:
    if window_days is None:
        return True
    return within_window(row.get("created_at") or "", window_days)


def _public_invitation(item: dict) -> dict:
    public = {key: value for key, value in item.items() if key != "code_hash"}
    public["share_path"] = f"/invite/{item['id']}"
    return public


def _public_ad(item: dict) -> dict:
    impressions = int(item.get("impressions") or 0)
    clicks = int(item.get("clicks") or 0)
    public = {key: value for key, value in item.items()}
    public["ctr"] = "—" if impressions <= 0 else f"{clicks / impressions * 100:.2f}%"
    public["conversions"] = int(item.get("conversions") or 0)
    return public


def _require_doc(store, collection: str, doc_id: str, tenant_id: str, code: str, message: str) -> dict:
    doc = store.get(collection, doc_id, tenant_id)
    if not doc:
        raise AppError(code, message, 404)
    return doc


def _audit(store, prof: dict, action: str, resource: str) -> None:
    store.insert(
        "audit_logs",
        base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("audit"),
            user_id=prof["user"]["id"],
            action=action,
            resource=resource,
            ip=None,
            scope="platform",
        ),
    )


@router.get("/admin/users")
def admin_users(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    tenant_id = prof["tenant"]["id"]
    rows = store.query("users", tenant_id=tenant_id, limit=100)["items"]
    items = [
        {
            "id": row["id"],
            "display_name": row.get("display_name"),
            "email_masked": _mask_email(row.get("email")),
            "phone_masked": None,
            "plan_id": prof["tenant"].get("plan_id"),
            "status": row.get("status") or "active",
            "role": row.get("role"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
        for row in rows
    ]
    return respond(request, {"items": items, "total": len(items)})


@router.get("/admin/users/summary")
def admin_users_summary(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    rows = store.query("users", tenant_id=prof["tenant"]["id"], limit=200)["items"]
    return respond(
        request,
        {
            "users": len(rows),
            "suspended": sum(1 for row in rows if row.get("status") == "suspended"),
            "active": sum(1 for row in rows if (row.get("status") or "active") == "active"),
        },
    )


@router.get("/admin/ads/placements")
def admin_placements(request: Request, authorization: str | None = Header(default=None)):
    _admin_read(request, authorization)
    return respond(request, {"items": [{"key": key, "status": "active"} for key in PLACEMENTS]})


@router.get("/admin/ads")
def admin_ads(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    page = store.query("ad_campaigns", tenant_id=prof["tenant"]["id"], limit=50)
    page["items"] = [_public_ad(item) for item in page["items"]]
    return respond(request, page)


@router.post("/admin/ads")
def admin_ads_create(request: Request, body: AdIn, authorization: str | None = Header(default=None)):
    store, prof = _admin_write(request, authorization)
    title = body.title.strip()
    if not title:
        raise AppError("INVALID_AD", "请填写广告名称")
    if body.placement not in PLACEMENTS:
        raise AppError("INVALID_PLACEMENT", "广告位不存在")
    if body.media_type not in {"image", "video"}:
        raise AppError("INVALID_MEDIA", "素材类型只能是 image 或 video")
    doc = store.insert(
        "ad_campaigns",
        base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("ad"),
            title=title,
            placement=body.placement,
            media_type=body.media_type,
            status="draft",
            scope="platform",
            impressions=0,
            clicks=0,
        ),
    )
    _audit(store, prof, "ad.created", doc["id"])
    return respond(request, doc)


@router.get("/admin/invitations")
def admin_invitations(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    page = store.query("invitation_campaigns", tenant_id=prof["tenant"]["id"], limit=50)
    page["items"] = [_public_invitation(item) for item in page["items"]]
    return respond(request, page)


@router.post("/admin/invitations")
def admin_invitations_create(request: Request, body: InvitationIn, authorization: str | None = Header(default=None)):
    store, prof = _admin_write(request, authorization)
    name = body.name.strip()
    if not name:
        raise AppError("INVALID_INVITATION", "请填写邀请活动名称")
    code = secrets.token_hex(4).upper()
    doc = store.insert(
        "invitation_campaigns",
        base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("inv"),
            name=name,
            status="draft",
            scope="platform",
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            invited=0,
            valid=0,
            reward_fen=0,
        ),
    )
    _audit(store, prof, "invitation.created", doc["id"])
    public = _public_invitation(doc)
    public["invite_code"] = code
    return respond(request, public)


@router.get("/admin/analytics")
def admin_analytics(request: Request, window_days: int | None = None, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    tenant_id = prof["tenant"]["id"]
    events = [row for row in store.query("events", tenant_id=tenant_id, limit=200)["items"] if _in_window(row, window_days)]
    counts: dict[str, int] = {}
    for event in events:
        name = event.get("event") or event.get("name") or "unknown"
        counts[name] = counts.get(name, 0) + 1
    users = [row for row in store.query("users", tenant_id=tenant_id, limit=200)["items"] if _in_window(row, window_days)]
    products = [row for row in store.query("products", tenant_id=tenant_id, limit=200)["items"] if _in_window(row, window_days)]
    reports = [row for row in store.query("analysis_reports", tenant_id=tenant_id, limit=200)["items"] if _in_window(row, window_days)]
    leads = [row for row in store.query("leads", tenant_id=tenant_id, limit=200)["items"] if _in_window(row, window_days)]
    return respond(
        request,
        {
            "events": [{"name": name, "count": count} for name, count in sorted(counts.items())],
            "funnel": [
                {"label": "完成注册", "value": len(users)},
                {"label": "导入商品", "value": len(products)},
                {"label": "完成分析", "value": len(reports)},
                {"label": "发现客户", "value": len(leads)},
            ],
            "retention": [],
            "window_days": window_days,
        },
    )


@router.get("/admin/recall")
def admin_recall(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    return respond(request, store.query("user_recall_campaigns", tenant_id=prof["tenant"]["id"], limit=50))


@router.post("/admin/recall")
def admin_recall_create(request: Request, body: RecallIn, authorization: str | None = Header(default=None)):
    store, prof = _admin_write(request, authorization)
    name = body.name.strip()
    if not name:
        raise AppError("INVALID_RECALL", "请填写召回活动名称")
    doc = store.insert(
        "user_recall_campaigns",
        base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("urc"),
            name=name,
            status="draft",
            scope="platform",
            audience=0,
            sent=False,
        ),
    )
    _audit(store, prof, "user_recall.created", doc["id"])
    return respond(request, doc)


@router.get("/admin/audit")
def admin_audit(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    return respond(request, store.query("audit_logs", tenant_id=prof["tenant"]["id"], limit=50))


@router.get("/admin/ads/creatives")
def admin_creatives(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    rows = store.query("ad_campaigns", tenant_id=prof["tenant"]["id"], limit=50)["items"]
    items = [
        {"id": row["id"], "title": row.get("title"), "media_type": row.get("media_type"), "placement": row.get("placement"), "status": row.get("status")}
        for row in rows
    ]
    return respond(request, {"items": items})


@router.get("/admin/ads/{ad_id}")
def admin_ad_detail(ad_id: str, request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    return respond(request, _public_ad(_require_doc(store, "ad_campaigns", ad_id, prof["tenant"]["id"], "AD_NOT_FOUND", "广告不存在")))


@router.post("/admin/ads/{ad_id}/status")
def admin_ad_status(ad_id: str, request: Request, body: StatusIn, authorization: str | None = Header(default=None)):
    store, prof = _admin_write(request, authorization)
    if body.status not in {"draft", "active", "paused", "ended"}:
        raise AppError("INVALID_STATUS", "广告状态无效")
    _require_doc(store, "ad_campaigns", ad_id, prof["tenant"]["id"], "AD_NOT_FOUND", "广告不存在")
    updated = store.touch("ad_campaigns", ad_id, {"status": body.status})
    _audit(store, prof, "ad.status", ad_id)
    return respond(request, _public_ad(updated or {}))


@router.post("/admin/users/export")
def admin_users_export(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_write(request, authorization)
    rows = store.query("users", tenant_id=prof["tenant"]["id"], limit=200)["items"]
    lines = ["id,display_name,email_masked,status,role"]
    for row in rows:
        lines.append(
            ",".join(
                _csv_cell(str(value or ""))
                for value in (
                    row.get("id"),
                    row.get("display_name"),
                    _mask_email(row.get("email")),
                    row.get("status") or "active",
                    row.get("role"),
                )
            )
        )
    csv_text = "\n".join(lines) + "\n"
    doc = store.insert(
        "admin_exports",
        base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("exp"),
            kind="users",
            filename="users.csv",
            body=csv_text,
        ),
    )
    _audit(store, prof, "users.exported", doc["id"])
    return respond(request, {"id": doc["id"], "filename": "users.csv", "body": csv_text})


@router.get("/admin/users/{user_id}")
def admin_user_detail(user_id: str, request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    row = _require_doc(store, "users", user_id, prof["tenant"]["id"], "USER_NOT_FOUND", "用户不存在")
    audits = [
        item
        for item in store.query("audit_logs", tenant_id=prof["tenant"]["id"], limit=20)["items"]
        if item.get("resource") == user_id or item.get("user_id") == user_id
    ]
    return respond(
        request,
        {
            "id": row["id"],
            "display_name": row.get("display_name"),
            "username": row.get("username"),
            "email_masked": _mask_email(row.get("email")),
            "status": row.get("status") or "active",
            "role": row.get("role"),
            "plan_id": prof["tenant"].get("plan_id"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "recent_audit": [{"action": item.get("action"), "created_at": item.get("created_at")} for item in audits[:8]],
        },
    )


@router.post("/admin/users/{user_id}/status")
def admin_user_status(user_id: str, request: Request, body: StatusIn, authorization: str | None = Header(default=None)):
    store, prof = _admin_write(request, authorization)
    if user_id == prof["user"]["id"]:
        raise AppError("FORBIDDEN", "不能停用当前登录账号", 403)
    if body.status not in {"active", "suspended"}:
        raise AppError("INVALID_STATUS", "用户状态无效")
    if len(body.reason.strip()) < 2:
        raise AppError("REASON_REQUIRED", "请填写操作原因")
    _require_doc(store, "users", user_id, prof["tenant"]["id"], "USER_NOT_FOUND", "用户不存在")
    updated = store.touch("users", user_id, {"status": body.status})
    _audit(store, prof, f"user.{body.status}", user_id)
    return respond(request, {"id": updated["id"], "status": updated.get("status")})


@router.get("/admin/segments")
def admin_segments(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    return respond(request, store.query("user_segments", tenant_id=prof["tenant"]["id"], limit=50))


@router.post("/admin/segments")
def admin_segments_create(request: Request, body: SegmentIn, authorization: str | None = Header(default=None)):
    store, prof = _admin_write(request, authorization)
    name = body.name.strip()
    if not name:
        raise AppError("INVALID_SEGMENT", "请填写分群名称")
    rows = store.query("users", tenant_id=prof["tenant"]["id"], limit=200)["items"]
    if body.stage and body.stage not in {"全部阶段", ""}:
        wanted = "suspended" if body.stage == "已停用" else "active"
        rows = [row for row in rows if (row.get("status") or "active") == wanted]
    if body.query:
        needle = body.query.lower()
        rows = [row for row in rows if needle in f"{row.get('id')} {row.get('display_name')} {row.get('email')}".lower()]
    doc = store.insert(
        "user_segments",
        base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("seg"),
            name=name,
            stage=body.stage,
            query=body.query,
            matched=len(rows),
        ),
    )
    _audit(store, prof, "segment.created", doc["id"])
    return respond(request, doc)


@router.get("/admin/invitations/{invitation_id}")
def admin_invitation_detail(invitation_id: str, request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    return respond(
        request,
        _public_invitation(_require_doc(store, "invitation_campaigns", invitation_id, prof["tenant"]["id"], "INVITATION_NOT_FOUND", "邀请活动不存在")),
    )


@router.post("/admin/analytics/export")
def admin_analytics_export(request: Request, window_days: int | None = None, authorization: str | None = Header(default=None)):
    payload = admin_analytics(request, window_days, authorization)
    body = payload["data"]
    store, prof = _admin_read(request, authorization)
    doc = store.insert(
        "admin_exports",
        base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("exp"),
            kind="analytics",
            filename="analytics.json",
            body=body,
        ),
    )
    _audit(store, prof, "analytics.exported", doc["id"])
    return respond(request, {"id": doc["id"], "filename": "analytics.json", "body": body})


@router.post("/admin/recall/pause-all")
def admin_recall_pause_all(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_write(request, authorization)
    paused = 0
    for row in store.query("user_recall_campaigns", tenant_id=prof["tenant"]["id"], limit=100)["items"]:
        if row.get("status") in {"draft", "scheduled", "sending", "active"}:
            store.touch("user_recall_campaigns", row["id"], {"status": "paused", "sent": False})
            paused += 1
    _audit(store, prof, "user_recall.pause_all", "user_recall_campaigns")
    return respond(request, {"paused": paused})


@router.get("/admin/recall/{campaign_id}")
def admin_recall_detail(campaign_id: str, request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    return respond(
        request,
        _require_doc(store, "user_recall_campaigns", campaign_id, prof["tenant"]["id"], "RECALL_NOT_FOUND", "召回活动不存在"),
    )


@router.get("/admin/settings")
def admin_settings(request: Request, authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    return respond(request, _settings_row(store, prof))


@router.patch("/admin/settings")
def admin_settings_update(request: Request, body: SettingsIn, authorization: str | None = Header(default=None)):
    store, prof = _admin_write(request, authorization)
    row = _settings_row(store, prof)
    patch: dict = {}
    if body.environment_label is not None:
        if body.environment_label not in {"TEST", "PRODUCTION"}:
            raise AppError("INVALID_SETTINGS", "环境标识只能是 TEST 或 PRODUCTION")
        patch["environment_label"] = body.environment_label
    if body.timezone is not None:
        zone = body.timezone.strip()
        if not zone or len(zone) > 64:
            raise AppError("INVALID_SETTINGS", "请填写时区")
        patch["timezone"] = zone
    if body.window_days is not None:
        if body.window_days not in {7, 30, 90}:
            raise AppError("INVALID_SETTINGS", "时间窗口只能是 7、30 或 90 天")
        patch["window_days"] = body.window_days
    if not patch:
        raise AppError("EMPTY_PATCH", "没有要更新的设置")
    updated = store.touch("platform_settings", row["id"], patch)
    _audit(store, prof, "settings.updated", row["id"])
    return respond(request, updated)


@router.post("/admin/settings/password")
def admin_settings_password(request: Request, body: PasswordIn, authorization: str | None = Header(default=None)):
    store, prof = _admin_write(request, authorization)
    user = store.get("users", prof["user"]["id"])
    if not user or not verify_password(body.current_password, user.get("password_hash")):
        raise AppError("UNAUTHENTICATED", "当前密码不正确", 401)
    if body.new_password == body.current_password:
        raise AppError("INVALID_PASSWORD", "新密码需要和当前密码不同")
    store.touch("users", user["id"], {"password_hash": hash_password(body.new_password, min_length=4)})
    _audit(store, prof, "settings.password", user["id"])
    return respond(request, {"updated": True})


@router.get("/admin/search")
def admin_search(request: Request, q: str = "", authorization: str | None = Header(default=None)):
    store, prof = _admin_read(request, authorization)
    needle = q.strip().lower()
    tenant_id = prof["tenant"]["id"]

    def hit(row: dict, *fields: str) -> bool:
        if not needle:
            return False
        return needle in " ".join(str(row.get(field) or "") for field in fields).lower()

    users = [
        {"id": row["id"], "label": row.get("display_name") or row["id"], "href": "/admin/users"}
        for row in store.query("users", tenant_id=tenant_id, limit=50)["items"]
        if hit(row, "id", "display_name", "email", "username")
    ]
    ads = [
        {"id": row["id"], "label": row.get("title"), "href": "/admin/ads"}
        for row in store.query("ad_campaigns", tenant_id=tenant_id, limit=50)["items"]
        if hit(row, "id", "title", "placement")
    ]
    invitations = [
        {"id": row["id"], "label": row.get("name"), "href": "/admin/invitations"}
        for row in store.query("invitation_campaigns", tenant_id=tenant_id, limit=50)["items"]
        if hit(row, "id", "name")
    ]
    recalls = [
        {"id": row["id"], "label": row.get("name"), "href": "/admin/recall"}
        for row in store.query("user_recall_campaigns", tenant_id=tenant_id, limit=50)["items"]
        if hit(row, "id", "name")
    ]
    return respond(request, {"users": users, "ads": ads, "invitations": invitations, "recalls": recalls})


def _settings_row(store, prof: dict) -> dict:
    row = store.find_global("platform_settings", tenant_id=prof["tenant"]["id"])
    if row:
        return row
    return store.insert(
        "platform_settings",
        base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("pset"),
            environment_label="TEST",
            timezone="Asia/Shanghai",
            window_days=30,
        ),
    )
