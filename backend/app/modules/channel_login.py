"""Per-tenant seller login for B1–B5.

Each ToB user connects their own platform account. Acquisition jobs are not
started here. B1 must pick one operating mode before the login page opens.
"""

import hashlib
import hmac
import json
from urllib.parse import quote

from app.core.errors import AppError
from app.core.timeutil import iso, utcnow
from app.services.common import CHANNELS, base_doc, new_id

B1_MODES = {
    "analyze": "分析订单，找出更多客户",
    "half": "半托管：平台承接一部分订单和客户，卖家保留一部分",
    "full": "全托管：平台接单，卖家只收钱",
}
LOGIN_CHANNELS = ("ecommerce", "social", "expo", "agency", "enrichment")


def list_accounts(store, tenant_id: str, channel: str) -> list[dict]:
    _check_channel(channel)
    found = store.query("channel_accounts", tenant_id=tenant_id, limit=50)
    return [row for row in found.get("items") or [] if row.get("channel") == channel]


def begin_login(store, settings, prof: dict, *, channel: str, platform: str, mode: str = "") -> dict:
    _check_channel(channel)
    if platform not in CHANNELS[channel]:
        raise AppError("UNKNOWN_PLATFORM", "这一路没有这个平台", details={"platform": platform})
    chosen = ""
    if channel == "ecommerce":
        if mode not in B1_MODES:
            raise AppError("B1_MODE_REQUIRED", "电商要先选定分析订单、半托管或全托管", details={"modes": B1_MODES})
        chosen = mode
    tenant_id = prof["tenant"]["id"]
    user_id = prof["user"]["id"]
    current = _find(store, tenant_id, channel, platform)
    fields = {"status": "pending", "mode": chosen, "mode_label": B1_MODES.get(chosen, "")}
    if channel == "agency":
        fields["status"] = "connected"
        fields["account_label"] = platform
        fields["connected_at"] = iso()
    saved = _save(store, tenant_id, user_id, channel, platform, current, fields)
    if channel == "agency":
        return _public(saved, authorize_url="")
    url, missing = _authorize_url(settings, channel, platform, _state(settings, tenant_id, channel, platform, chosen))
    if channel == "enrichment" and not missing:
        saved = _save(store, tenant_id, user_id, channel, platform, saved, {"status": "connected", "connected_at": iso(), "account_label": platform})
        return _public(saved, authorize_url="")
    return _public(saved, authorize_url=url, missing=missing)


def complete_login(store, settings, prof: dict, *, state: str, code: str) -> dict:
    if not code.strip():
        raise AppError("LOGIN_CODE_REQUIRED", "平台没有返回授权码")
    payload = _open_state(settings, state)
    if payload["tenant_id"] != prof["tenant"]["id"]:
        raise AppError("LOGIN_STATE_MISMATCH", "这个登录不属于当前账号", 403)
    current = _find(store, payload["tenant_id"], payload["channel"], payload["platform"])
    saved = _save(
        store,
        payload["tenant_id"],
        prof["user"]["id"],
        payload["channel"],
        payload["platform"],
        current,
        {
            "status": "connected",
            "mode": payload.get("mode") or "",
            "mode_label": B1_MODES.get(payload.get("mode") or "", ""),
            "connected_at": iso(),
            "account_label": payload["platform"],
        },
    )
    return _public(saved, authorize_url="")


def _check_channel(channel: str) -> None:
    if channel not in LOGIN_CHANNELS:
        raise AppError("UNKNOWN_CHANNEL", "只有 B1 到 B5 需要登录平台账号", details={"channel": channel})


def _find(store, tenant_id: str, channel: str, platform: str) -> dict | None:
    for row in list_accounts(store, tenant_id, channel):
        if row.get("platform") == platform:
            return row
    return None


def _save(store, tenant_id: str, user_id: str, channel: str, platform: str, current: dict | None, fields: dict) -> dict:
    if current:
        store.touch("channel_accounts", current["id"], fields)
        return store.get("channel_accounts", current["id"])
    return store.insert(
        "channel_accounts",
        base_doc(tenant_id, user_id, id=new_id("cac"), channel=channel, platform=platform, **fields),
    )


def _public(row: dict, *, authorize_url: str, missing: str = "") -> dict:
    return {
        "id": row["id"],
        "channel": row["channel"],
        "platform": row["platform"],
        "status": row.get("status") or "pending",
        "mode": row.get("mode") or "",
        "mode_label": row.get("mode_label") or "",
        "account_label": row.get("account_label") or "",
        "authorize_url": authorize_url,
        "missing": missing,
    }


def _redirect(settings) -> str:
    origin = (getattr(settings, "public_web_origin", "") or "https://pickglobal.mornscience.top").rstrip("/")
    return f"{origin}/workspace/acquire/connected"


def _state(settings, tenant_id: str, channel: str, platform: str, mode: str) -> str:
    payload = {"tenant_id": tenant_id, "channel": channel, "platform": platform, "mode": mode, "exp": int(utcnow().timestamp()) + 900}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    secret = settings.session_secret or "demo-session-secret"
    signature = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{signature}"


def _open_state(settings, state: str) -> dict:
    raw, _, signature = (state or "").rpartition(".")
    secret = settings.session_secret or "demo-session-secret"
    expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
    if not raw or not hmac.compare_digest(expected, signature):
        raise AppError("LOGIN_STATE_INVALID", "登录状态无效", 400)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError("LOGIN_STATE_INVALID", "登录状态无效", 400) from exc
    if int(payload.get("exp") or 0) < int(utcnow().timestamp()):
        raise AppError("LOGIN_STATE_EXPIRED", "登录已过期，请重新打开平台登录", 400)
    return payload


def _authorize_url(settings, channel: str, platform: str, state: str) -> tuple[str, str]:
    redirect = quote(_redirect(settings), safe="")
    encoded_state = quote(state, safe="")
    if channel == "enrichment":
        needed = {
            "qichacha": ("qichacha_app_key", "QICHACHA_APP_KEY"),
            "tianyancha": ("tianyancha_token", "TIANYANCHA_TOKEN"),
            "qixin": ("qixin_app_key", "QIXIN_APP_KEY"),
        }
        attr, env_name = needed.get(platform, ("", platform))
        if attr and getattr(settings, attr, ""):
            return "", ""
        return "", env_name
    if channel == "expo" and platform != "alibaba_com":
        return "", "该展会没有卖家登录页"
    builders = {
        ("ecommerce", "amazon"): _amazon,
        ("ecommerce", "walmart"): _walmart,
        ("ecommerce", "taobao"): _taobao,
        ("ecommerce", "pinduoduo"): _pdd,
        ("social", "linkedin"): _linkedin,
        ("social", "facebook"): _facebook,
        ("social", "douyin"): _douyin,
        ("expo", "alibaba_com"): _alibaba_intl,
    }
    builder = builders.get((channel, platform))
    if builder is None:
        return "", f"{platform} 还没有官方登录地址"
    return builder(settings, redirect, encoded_state)


def _amazon(settings, redirect: str, state: str) -> tuple[str, str]:
    app_id = getattr(settings, "amazon_sp_application_id", "") or ""
    if not app_id:
        return "", "AMAZON_SP_APPLICATION_ID"
    return f"https://sellercentral.amazon.com/apps/authorize/consent?application_id={quote(app_id, safe='')}&state={state}&redirect_uri={redirect}", ""


def _walmart(settings, redirect: str, state: str) -> tuple[str, str]:
    client_id = getattr(settings, "walmart_market_client_id", "") or ""
    if not client_id:
        return "", "WALMART_MARKET_CLIENT_ID"
    return f"https://login.account.wal-mart.com/authorize?responseType=code&clientId={quote(client_id, safe='')}&redirectUri={redirect}&clientType=seller&nonce={state}", ""


def _taobao(settings, redirect: str, state: str) -> tuple[str, str]:
    app_key = getattr(settings, "taobao_app_key", "") or ""
    if not app_key:
        return "", "TAOBAO_APP_KEY"
    return f"https://oauth.taobao.com/authorize?response_type=code&client_id={quote(app_key, safe='')}&redirect_uri={redirect}&state={state}", ""


def _pdd(settings, redirect: str, state: str) -> tuple[str, str]:
    client_id = getattr(settings, "pdd_client_id", "") or ""
    if not client_id:
        return "", "PDD_CLIENT_ID"
    return f"https://fuwu.pinduoduo.com/service-market/auth?response_type=code&client_id={quote(client_id, safe='')}&redirect_uri={redirect}&state={state}", ""


def _linkedin(settings, redirect: str, state: str) -> tuple[str, str]:
    client_id = getattr(settings, "linkedin_client_id", "") or ""
    if not client_id:
        return "", "LINKEDIN_CLIENT_ID"
    return f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={quote(client_id, safe='')}&redirect_uri={redirect}&state={state}&scope=r_liteprofile%20r_emailaddress", ""


def _facebook(settings, redirect: str, state: str) -> tuple[str, str]:
    app_id = getattr(settings, "facebook_app_id", "") or ""
    if not app_id:
        return "", "FACEBOOK_APP_ID"
    return f"https://www.facebook.com/v21.0/dialog/oauth?client_id={quote(app_id, safe='')}&redirect_uri={redirect}&state={state}&scope=pages_show_list,leads_retrieval", ""


def _douyin(settings, redirect: str, state: str) -> tuple[str, str]:
    client_key = getattr(settings, "douyin_client_key", "") or ""
    if not client_key:
        return "", "DOUYIN_CLIENT_KEY"
    return f"https://open.douyin.com/platform/oauth/connect?client_key={quote(client_key, safe='')}&response_type=code&scope=user_info&redirect_uri={redirect}&state={state}", ""


def _alibaba_intl(settings, redirect: str, state: str) -> tuple[str, str]:
    app_key = getattr(settings, "alibaba_intl_app_key", "") or ""
    if not app_key:
        return "", "ALIBABA_INTL_APP_KEY"
    return f"https://oauth.alibaba.com/authorize?response_type=code&client_id={quote(app_key, safe='')}&redirect_uri={redirect}&state={state}&sp=icbu", ""
