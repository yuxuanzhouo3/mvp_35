"""Per-tenant seller login for B1–B5.

ENV holds the developer App Key/Secret. Each ToB tenant authorizes their own
shop; the OAuth code is exchanged and stored on channel_accounts. Acquisition
reads those tenant tokens. Paste credentials cover platforms without a stable
seller OAuth page (WeCom, Walmart self-keys, B5).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import quote

import httpx

from app.core.errors import AppError
from app.core.timeutil import iso, utcnow
from app.services.common import CHANNELS, base_doc, new_id

B1_MODES = {
    "analyze": "分析订单，找出更多客户",
    "half": "半托管：平台承接一部分订单和客户，卖家保留一部分",
    "full": "全托管：平台接单，卖家只收钱",
}
LOGIN_CHANNELS = ("ecommerce", "social", "expo", "agency", "enrichment")
TIMEOUT = 12

# Platforms that can connect by pasting keys when OAuth is missing or optional.
PASTE_FIELDS = {
    "walmart": ("client_id", "client_secret"),
    "wechat_mini": ("corp_id", "contact_secret", "follow_userid"),
    "qichacha": ("app_key", "secret_key"),
    "tianyancha": ("token",),
    "qixin": ("app_key", "secret_key"),
    "temu": ("access_token",),
}


def list_accounts(store, tenant_id: str, channel: str) -> list[dict]:
    _check_channel(channel)
    found = store.query("channel_accounts", tenant_id=tenant_id, limit=50)
    return [_public(row) for row in (found.get("items") or []) if row.get("channel") == channel]


def account_secrets(store, tenant_id: str, channel: str, platform: str) -> dict | None:
    """Raw tokens for acquisition. Never return this over the API."""
    row = _find(store, tenant_id, channel, platform)
    if not row or (row.get("status") or "") != "connected":
        return None
    meta = row.get("token_meta") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return {
        "access_token": str(row.get("access_token") or ""),
        "refresh_token": str(row.get("refresh_token") or ""),
        "token_meta": meta,
        "mode": str(row.get("mode") or ""),
    }


def begin_login(store, settings, prof: dict, *, channel: str, platform: str, mode: str = "", credentials: dict | None = None) -> dict:
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
    creds = {str(k): str(v).strip() for k, v in (credentials or {}).items() if str(v).strip()}

    if channel == "agency":
        saved = _save(store, tenant_id, user_id, channel, platform, current, {
            "status": "connected",
            "mode": chosen,
            "mode_label": B1_MODES.get(chosen, ""),
            "account_label": platform,
            "connected_at": iso(),
        })
        return _public(saved)

    if creds and platform in PASTE_FIELDS:
        needed = PASTE_FIELDS[platform]
        missing = [name for name in needed if not creds.get(name)]
        if missing:
            raise AppError("LOGIN_CREDENTIALS_REQUIRED", "缺少登录字段", details={"missing": missing})
        fields = _fields_from_paste(platform, creds)
        fields.update({"status": "connected", "mode": chosen, "mode_label": B1_MODES.get(chosen, ""), "connected_at": iso()})
        saved = _save(store, tenant_id, user_id, channel, platform, current, fields)
        return _public(saved)

    if channel == "enrichment":
        url, missing = _authorize_url(settings, channel, platform, _state(settings, tenant_id, channel, platform, chosen))
        if not missing:
            saved = _save(store, tenant_id, user_id, channel, platform, current, {
                "status": "connected",
                "mode": "",
                "mode_label": "",
                "account_label": platform,
                "connected_at": iso(),
                "token_meta": json.dumps({"use_system": True}),
            })
            return _public(saved, authorize_url="", missing="", needs_credentials=True, credential_fields=list(PASTE_FIELDS.get(platform, ())))
        return _public(
            _save(store, tenant_id, user_id, channel, platform, current, {"status": "pending", "mode": "", "mode_label": ""}),
            authorize_url="",
            missing=missing,
            needs_credentials=True,
            credential_fields=list(PASTE_FIELDS.get(platform, ())),
        )

    fields = {"status": "pending", "mode": chosen, "mode_label": B1_MODES.get(chosen, "")}
    saved = _save(store, tenant_id, user_id, channel, platform, current, fields)
    url, missing = _authorize_url(settings, channel, platform, _state(settings, tenant_id, channel, platform, chosen))
    paste = list(PASTE_FIELDS.get(platform, ()))
    return _public(saved, authorize_url=url, missing=missing, needs_credentials=bool(paste and (missing or platform in {"walmart", "wechat_mini", "temu"})), credential_fields=paste)


def complete_login(store, settings, prof: dict, *, state: str, code: str) -> dict:
    if not code.strip():
        raise AppError("LOGIN_CODE_REQUIRED", "平台没有返回授权码")
    payload = _open_state(settings, state)
    if payload["tenant_id"] != prof["tenant"]["id"]:
        raise AppError("LOGIN_STATE_MISMATCH", "这个登录不属于当前账号", 403)
    platform = payload["platform"]
    channel = payload["channel"]
    tokens = _exchange_code(settings, platform, code.strip())
    current = _find(store, payload["tenant_id"], channel, platform)
    saved = _save(
        store,
        payload["tenant_id"],
        prof["user"]["id"],
        channel,
        platform,
        current,
        {
            "status": "connected",
            "mode": payload.get("mode") or "",
            "mode_label": B1_MODES.get(payload.get("mode") or "", ""),
            "connected_at": iso(),
            "account_label": tokens.get("account_label") or platform,
            "access_token": tokens.get("access_token") or "",
            "refresh_token": tokens.get("refresh_token") or "",
            "token_meta": json.dumps(tokens.get("token_meta") or {}),
        },
    )
    return _public(saved)


def _fields_from_paste(platform: str, creds: dict) -> dict:
    if platform == "walmart":
        return {
            "access_token": "",
            "refresh_token": "",
            "account_label": "walmart",
            "token_meta": json.dumps({"client_id": creds["client_id"], "client_secret": creds["client_secret"]}),
        }
    if platform == "wechat_mini":
        return {
            "access_token": "",
            "refresh_token": "",
            "account_label": creds["corp_id"],
            "token_meta": json.dumps({
                "corp_id": creds["corp_id"],
                "contact_secret": creds["contact_secret"],
                "follow_userid": creds["follow_userid"],
            }),
        }
    if platform == "qichacha":
        return {
            "access_token": creds["app_key"],
            "refresh_token": creds["secret_key"],
            "account_label": "qichacha",
            "token_meta": json.dumps({"app_key": creds["app_key"], "secret_key": creds["secret_key"]}),
        }
    if platform == "tianyancha":
        return {
            "access_token": creds["token"],
            "refresh_token": "",
            "account_label": "tianyancha",
            "token_meta": json.dumps({"token": creds["token"]}),
        }
    if platform == "qixin":
        return {
            "access_token": creds["app_key"],
            "refresh_token": creds["secret_key"],
            "account_label": "qixin",
            "token_meta": json.dumps({"app_key": creds["app_key"], "secret_key": creds["secret_key"]}),
        }
    if platform == "temu":
        return {
            "access_token": creds["access_token"],
            "refresh_token": "",
            "account_label": "temu",
            "token_meta": json.dumps({}),
        }
    raise AppError("UNKNOWN_PLATFORM", "这一路没有这个平台", details={"platform": platform})


def _check_channel(channel: str) -> None:
    if channel not in LOGIN_CHANNELS:
        raise AppError("UNKNOWN_CHANNEL", "只有 B1 到 B5 需要登录平台账号", details={"channel": channel})


def _find(store, tenant_id: str, channel: str, platform: str) -> dict | None:
    found = store.query("channel_accounts", tenant_id=tenant_id, limit=50)
    for row in found.get("items") or []:
        if row.get("channel") == channel and row.get("platform") == platform:
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


def _public(row: dict, *, authorize_url: str = "", missing: str = "", needs_credentials: bool = False, credential_fields: list[str] | None = None) -> dict:
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
        "needs_credentials": needs_credentials,
        "credential_fields": credential_fields or [],
        "has_token": bool(row.get("access_token") or (row.get("token_meta") and row.get("token_meta") != "{}")),
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
        ("ecommerce", "amazon"): _amazon_url,
        ("ecommerce", "walmart"): _walmart_url,
        ("ecommerce", "taobao"): _taobao_url,
        ("ecommerce", "pinduoduo"): _pdd_url,
        ("ecommerce", "temu"): _temu_url,
        ("social", "linkedin"): _linkedin_url,
        ("social", "facebook"): _facebook_url,
        ("social", "wechat_mini"): _wecom_url,
        ("social", "douyin"): _douyin_url,
        ("social", "xiaohongshu"): _xhs_url,
        ("social", "kuaishou"): _kuaishou_url,
        ("expo", "alibaba_com"): _alibaba_intl_url,
    }
    builder = builders.get((channel, platform))
    if builder is None:
        return "", f"{platform} 还没有官方登录地址"
    return builder(settings, redirect, encoded_state)


def _amazon_url(settings, redirect: str, state: str) -> tuple[str, str]:
    app_id = getattr(settings, "amazon_sp_application_id", "") or ""
    if not app_id:
        return "", "AMAZON_SP_APPLICATION_ID"
    return f"https://sellercentral.amazon.com/apps/authorize/consent?application_id={quote(app_id, safe='')}&state={state}&redirect_uri={redirect}", ""


def _walmart_url(settings, redirect: str, state: str) -> tuple[str, str]:
    client_id = getattr(settings, "walmart_market_client_id", "") or ""
    if not client_id:
        return "", "WALMART_MARKET_CLIENT_ID"
    return f"https://login.account.wal-mart.com/authorize?responseType=code&clientId={quote(client_id, safe='')}&redirectUri={redirect}&clientType=seller&nonce={state}", ""


def _taobao_url(settings, redirect: str, state: str) -> tuple[str, str]:
    app_key = getattr(settings, "taobao_app_key", "") or ""
    if not app_key:
        return "", "TAOBAO_APP_KEY"
    return f"https://oauth.taobao.com/authorize?response_type=code&client_id={quote(app_key, safe='')}&redirect_uri={redirect}&state={state}", ""


def _pdd_url(settings, redirect: str, state: str) -> tuple[str, str]:
    client_id = getattr(settings, "pdd_client_id", "") or ""
    if not client_id:
        return "", "PDD_CLIENT_ID"
    return f"https://fuwu.pinduoduo.com/service-market/auth?response_type=code&client_id={quote(client_id, safe='')}&redirect_uri={redirect}&state={state}", ""


def _temu_url(settings, redirect: str, state: str) -> tuple[str, str]:
    app_key = getattr(settings, "temu_app_key", "") or ""
    if not app_key:
        return "", "TEMU_APP_KEY"
    return f"https://seller.temu.com/open-platform/client-manage/authorization?appKey={quote(app_key, safe='')}&redirect_uri={redirect}&state={state}", ""


def _linkedin_url(settings, redirect: str, state: str) -> tuple[str, str]:
    client_id = getattr(settings, "linkedin_client_id", "") or ""
    if not client_id:
        return "", "LINKEDIN_CLIENT_ID"
    return f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={quote(client_id, safe='')}&redirect_uri={redirect}&state={state}&scope=r_liteprofile%20r_emailaddress%20r_ads%20r_ads_reporting%20rw_organization_admin", ""


def _facebook_url(settings, redirect: str, state: str) -> tuple[str, str]:
    app_id = getattr(settings, "facebook_app_id", "") or ""
    if not app_id:
        return "", "FACEBOOK_APP_ID"
    return f"https://www.facebook.com/v21.0/dialog/oauth?client_id={quote(app_id, safe='')}&redirect_uri={redirect}&state={state}&scope=pages_show_list,leads_retrieval,pages_manage_ads,pages_read_engagement,business_management", ""


def _wecom_url(settings, redirect: str, state: str) -> tuple[str, str]:
    del redirect, state
    corp = getattr(settings, "wecom_corp_id", "") or ""
    if not corp:
        return "", "WECOM_CORP_ID"
    # Self-built apps use pasted corp secret; OAuth alone cannot grant external-contact API.
    return "", "请粘贴企业微信 corp_id / contact_secret / follow_userid"


def _douyin_url(settings, redirect: str, state: str) -> tuple[str, str]:
    client_key = getattr(settings, "douyin_client_key", "") or ""
    if not client_key:
        return "", "DOUYIN_CLIENT_KEY"
    return f"https://open.douyin.com/platform/oauth/connect?client_key={quote(client_key, safe='')}&response_type=code&scope=user_info,enterprise.leads&redirect_uri={redirect}&state={state}", ""


def _xhs_url(settings, redirect: str, state: str) -> tuple[str, str]:
    app_id = getattr(settings, "xhs_app_id", "") or ""
    if not app_id:
        return "", "XHS_APP_ID"
    return f"https://ark.xiaohongshu.com/ark/authorization?appId={quote(app_id, safe='')}&redirectUri={redirect}&state={state}", ""


def _kuaishou_url(settings, redirect: str, state: str) -> tuple[str, str]:
    app_id = getattr(settings, "kuaishou_app_id", "") or ""
    if not app_id:
        return "", "KUAISHOU_APP_ID"
    return f"https://open.kuaishou.com/oauth2/authorize?app_id={quote(app_id, safe='')}&redirect_uri={redirect}&response_type=code&scope=user_info&state={state}", ""


def _alibaba_intl_url(settings, redirect: str, state: str) -> tuple[str, str]:
    app_key = getattr(settings, "alibaba_intl_app_key", "") or ""
    if not app_key:
        return "", "ALIBABA_INTL_APP_KEY"
    return f"https://oauth.alibaba.com/authorize?response_type=code&client_id={quote(app_key, safe='')}&redirect_uri={redirect}&state={state}&sp=icbu", ""


def _exchange_code(settings, platform: str, code: str) -> dict:
    redirect = _redirect(settings)
    exchangers = {
        "amazon": _ex_amazon,
        "walmart": _ex_walmart,
        "taobao": _ex_taobao,
        "pinduoduo": _ex_pdd,
        "temu": _ex_temu,
        "linkedin": _ex_linkedin,
        "facebook": _ex_facebook,
        "douyin": _ex_douyin,
        "xiaohongshu": _ex_xhs,
        "kuaishou": _ex_kuaishou,
        "alibaba_com": _ex_alibaba_intl,
    }
    exchanger = exchangers.get(platform)
    if exchanger is None:
        raise AppError("LOGIN_EXCHANGE_UNSUPPORTED", "这个平台还不支持用授权码换令牌", details={"platform": platform})
    try:
        return exchanger(settings, code, redirect)
    except AppError:
        raise
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise AppError("LOGIN_TOKEN_EXCHANGE_FAILED", "授权码换令牌失败，请重试登录", details={"platform": platform, "reason": str(exc)[:160]}) from exc


def _form_post(url: str, data: dict) -> dict:
    response = httpx.post(url, data=data, timeout=TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("token response is not an object")
    return body


def _json_post(url: str, payload: dict, headers: dict | None = None) -> dict:
    response = httpx.post(url, json=payload, headers=headers or {}, timeout=TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("token response is not an object")
    return body


def _get_json(url: str, params: dict | None = None, headers: dict | None = None) -> dict:
    response = httpx.get(url, params=params, headers=headers or {}, timeout=TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("token response is not an object")
    return body


def _ex_amazon(settings, code: str, redirect: str) -> dict:
    client_id = getattr(settings, "amazon_sp_client_id", "") or ""
    secret = getattr(settings, "amazon_sp_client_secret", "") or ""
    if not (client_id and secret):
        raise AppError("LOGIN_APP_MISSING", "缺少 AMAZON_SP_CLIENT_ID / AMAZON_SP_CLIENT_SECRET")
    body = _form_post(
        "https://api.amazon.com/auth/o2/token",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect,
            "client_id": client_id,
            "client_secret": secret,
        },
    )
    access = str(body.get("access_token") or "")
    refresh = str(body.get("refresh_token") or "")
    if not (access or refresh):
        raise ValueError("amazon token empty")
    return {"access_token": access, "refresh_token": refresh, "account_label": "amazon", "token_meta": {}}


def _ex_walmart(settings, code: str, redirect: str) -> dict:
    del redirect
    import base64

    client_id = getattr(settings, "walmart_market_client_id", "") or ""
    secret = getattr(settings, "walmart_market_client_secret", "") or ""
    if not (client_id and secret):
        return {"access_token": code, "refresh_token": "", "account_label": "walmart", "token_meta": {"auth_code": code}}
    basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    response = httpx.post(
        "https://marketplace.walmartapis.com/v3/token",
        data={"grant_type": "client_credentials"},
        headers={
            "Authorization": f"Basic {basic}",
            "WM_QOS.CORRELATION_ID": hashlib.md5(code.encode()).hexdigest(),
            "WM_SVC.NAME": "Walmart Marketplace",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    token_body = response.json()
    access = str((token_body or {}).get("access_token") or "")
    return {
        "access_token": access or code,
        "refresh_token": "",
        "account_label": "walmart",
        "token_meta": {"client_id": client_id, "client_secret": secret, "auth_code": code},
    }


def _ex_taobao(settings, code: str, redirect: str) -> dict:
    app_key = getattr(settings, "taobao_app_key", "") or ""
    secret = getattr(settings, "taobao_app_secret", "") or ""
    if not (app_key and secret):
        raise AppError("LOGIN_APP_MISSING", "缺少 TAOBAO_APP_KEY / TAOBAO_APP_SECRET")
    body = _form_post(
        "https://oauth.taobao.com/token",
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": app_key,
            "client_secret": secret,
            "redirect_uri": redirect,
        },
    )
    access = str(body.get("access_token") or "")
    if not access:
        raise ValueError("taobao token empty")
    return {
        "access_token": access,
        "refresh_token": str(body.get("refresh_token") or ""),
        "account_label": str(body.get("taobao_user_nick") or "taobao"),
        "token_meta": {"taobao_user_id": body.get("taobao_user_id")},
    }


def _ex_pdd(settings, code: str, redirect: str) -> dict:
    del redirect
    client_id = getattr(settings, "pdd_client_id", "") or ""
    secret = getattr(settings, "pdd_client_secret", "") or ""
    if not (client_id and secret):
        raise AppError("LOGIN_APP_MISSING", "缺少 PDD_CLIENT_ID / PDD_CLIENT_SECRET")
    params = {
        "type": "pdd.pop.auth.token.create",
        "client_id": client_id,
        "timestamp": str(int(utcnow().timestamp())),
        "data_type": "JSON",
        "code": code,
    }
    raw = secret + "".join(f"{key}{params[key]}" for key in sorted(params)) + secret
    params["sign"] = hashlib.md5(raw.encode()).hexdigest().upper()
    body = _form_post("https://gw-api.pinduoduo.com/api/router", params)
    popped = body.get("pop_auth_token_create_response") or body.get("pop_auth_token_create_response") or body
    if isinstance(popped, dict) and "access_token" not in popped:
        popped = popped.get("pop_auth_token_create_response") or popped
    access = str((popped or {}).get("access_token") or "")
    if not access:
        raise ValueError(str(body.get("error_response") or "pdd token empty")[:160])
    return {
        "access_token": access,
        "refresh_token": str((popped or {}).get("refresh_token") or ""),
        "account_label": str((popped or {}).get("owner_name") or "pinduoduo"),
        "token_meta": {"owner_id": (popped or {}).get("owner_id")},
    }


def _ex_temu(settings, code: str, redirect: str) -> dict:
    del redirect
    app_key = getattr(settings, "temu_app_key", "") or ""
    secret = getattr(settings, "temu_app_secret", "") or ""
    if not (app_key and secret):
        raise AppError("LOGIN_APP_MISSING", "缺少 TEMU_APP_KEY / TEMU_APP_SECRET")
    host = (getattr(settings, "temu_open_host", "") or "https://openapi-b-us.temu.com").rstrip("/")
    params = {
        "type": "bg.open.accesstoken.create",
        "app_key": app_key,
        "timestamp": str(int(utcnow().timestamp())),
        "data_type": "JSON",
        "code": code,
    }
    raw = secret + "".join(f"{key}{params[key]}" for key in sorted(params)) + secret
    params["sign"] = hashlib.md5(raw.encode()).hexdigest().upper()
    body = _form_post(f"{host}/openapi/router", params)
    result = body.get("result") if isinstance(body.get("result"), dict) else body
    access = str((result or {}).get("access_token") or code)
    return {
        "access_token": access,
        "refresh_token": str((result or {}).get("refresh_token") or ""),
        "account_label": str((result or {}).get("mall_id") or "temu"),
        "token_meta": {"mall_id": (result or {}).get("mall_id")},
    }


def _ex_linkedin(settings, code: str, redirect: str) -> dict:
    client_id = getattr(settings, "linkedin_client_id", "") or ""
    secret = getattr(settings, "linkedin_client_secret", "") or ""
    if not (client_id and secret):
        raise AppError("LOGIN_APP_MISSING", "缺少 LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET")
    body = _form_post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect,
            "client_id": client_id,
            "client_secret": secret,
        },
    )
    access = str(body.get("access_token") or "")
    if not access:
        raise ValueError("linkedin token empty")
    ad_account = getattr(settings, "linkedin_ad_account_id", "") or ""
    return {
        "access_token": access,
        "refresh_token": str(body.get("refresh_token") or ""),
        "account_label": "linkedin",
        "token_meta": {"ad_account_id": ad_account},
    }


def _ex_facebook(settings, code: str, redirect: str) -> dict:
    app_id = getattr(settings, "facebook_app_id", "") or ""
    secret = getattr(settings, "facebook_app_secret", "") or ""
    if not (app_id and secret):
        raise AppError("LOGIN_APP_MISSING", "缺少 FACEBOOK_APP_ID / FACEBOOK_APP_SECRET")
    body = _get_json(
        "https://graph.facebook.com/v21.0/oauth/access_token",
        params={"client_id": app_id, "client_secret": secret, "redirect_uri": redirect, "code": code},
    )
    user_token = str(body.get("access_token") or "")
    if not user_token:
        raise ValueError("facebook token empty")
    pages = _get_json("https://graph.facebook.com/v21.0/me/accounts", params={"access_token": user_token})
    first = ((pages.get("data") or []) or [{}])[0] if isinstance(pages.get("data"), list) else {}
    page_id = str(first.get("id") or getattr(settings, "facebook_page_id", "") or "")
    page_token = str(first.get("access_token") or user_token)
    return {
        "access_token": page_token,
        "refresh_token": user_token,
        "account_label": str(first.get("name") or page_id or "facebook"),
        "token_meta": {"page_id": page_id},
    }


def _ex_douyin(settings, code: str, redirect: str) -> dict:
    del redirect
    client_key = getattr(settings, "douyin_client_key", "") or ""
    secret = getattr(settings, "douyin_client_secret", "") or ""
    if not (client_key and secret):
        raise AppError("LOGIN_APP_MISSING", "缺少 DOUYIN_CLIENT_KEY / DOUYIN_CLIENT_SECRET")
    body = _json_post(
        "https://open.douyin.com/oauth/access_token/",
        {
            "client_key": client_key,
            "client_secret": secret,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    access = str((data or {}).get("access_token") or "")
    if not access:
        raise ValueError(str(body.get("message") or "douyin token empty")[:160])
    return {
        "access_token": access,
        "refresh_token": str((data or {}).get("refresh_token") or ""),
        "account_label": str((data or {}).get("open_id") or "douyin"),
        "token_meta": {"open_id": (data or {}).get("open_id")},
    }


def _ex_xhs(settings, code: str, redirect: str) -> dict:
    del redirect
    app_id = getattr(settings, "xhs_app_id", "") or ""
    secret = getattr(settings, "xhs_app_secret", "") or ""
    if not (app_id and secret):
        raise AppError("LOGIN_APP_MISSING", "缺少 XHS_APP_ID / XHS_APP_SECRET")
    body = _json_post(
        "https://ark.xiaohongshu.com/ark/open_api/v3/common_controller",
        {
            "method": "oauth.getAccessToken",
            "appId": app_id,
            "code": code,
        },
        headers={"Content-Type": "application/json"},
    )
    # Some XHS surfaces use a dedicated oauth path; keep a second try shape.
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    access = str((data or {}).get("accessToken") or (data or {}).get("access_token") or "")
    if not access:
        body = _form_post(
            "https://adapi.xiaohongshu.com/api/open/oauth2/access_token",
            {"app_id": app_id, "secret": secret, "code": code},
        )
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        access = str((data or {}).get("access_token") or "")
    if not access:
        raise ValueError("xiaohongshu token empty")
    return {
        "access_token": access,
        "refresh_token": str((data or {}).get("refresh_token") or (data or {}).get("refreshToken") or ""),
        "account_label": "xiaohongshu",
        "token_meta": {},
    }


def _ex_kuaishou(settings, code: str, redirect: str) -> dict:
    app_id = getattr(settings, "kuaishou_app_id", "") or ""
    secret = getattr(settings, "kuaishou_app_secret", "") or ""
    if not (app_id and secret):
        raise AppError("LOGIN_APP_MISSING", "缺少 KUAISHOU_APP_ID / KUAISHOU_APP_SECRET")
    body = _form_post(
        "https://open.kuaishou.com/oauth2/access_token",
        {
            "app_id": app_id,
            "app_secret": secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
        },
    )
    access = str(body.get("access_token") or (body.get("result") or {}).get("access_token") or "")
    if not access and isinstance(body.get("data"), dict):
        access = str(body["data"].get("access_token") or "")
    if not access:
        raise ValueError("kuaishou token empty")
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    return {
        "access_token": access,
        "refresh_token": str((data or {}).get("refresh_token") or ""),
        "account_label": str((data or {}).get("open_id") or "kuaishou"),
        "token_meta": {"open_id": (data or {}).get("open_id")},
    }


def _ex_alibaba_intl(settings, code: str, redirect: str) -> dict:
    del redirect
    app_key = getattr(settings, "alibaba_intl_app_key", "") or ""
    secret = getattr(settings, "alibaba_intl_app_secret", "") or ""
    if not (app_key and secret):
        raise AppError("LOGIN_APP_MISSING", "缺少 ALIBABA_INTL_APP_KEY / ALIBABA_INTL_APP_SECRET")
    url = f"https://gw.open.1688.com/openapi/http/1/system.oauth2/getToken/{app_key}"
    body = _form_post(
        url,
        {
            "grant_type": "authorization_code",
            "need_refresh_token": "true",
            "client_id": app_key,
            "client_secret": secret,
            "code": code,
        },
    )
    access = str(body.get("access_token") or "")
    if not access:
        raise ValueError("alibaba intl token empty")
    return {
        "access_token": access,
        "refresh_token": str(body.get("refresh_token") or ""),
        "account_label": str(body.get("memberId") or "alibaba_com"),
        "token_meta": {"member_id": body.get("memberId")},
    }
