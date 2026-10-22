"""B2–B4 content seeding and intent helpers.

B2 invent/remix drafts need human approve before publish. Contact capture prefers
WeChat, authorized email, or authorized phone. B5 does not publish.
"""

from __future__ import annotations

from app.core.errors import AppError
from app.core.timeutil import iso
from app.services.common import base_doc, new_id

INTENT_HIGH = 70
CONTACT_KEYS = ("wechat", "email", "phone")


def draft_seed(
    store,
    prof: dict,
    *,
    channel: str,
    platform: str,
    mode: str,
    seed_text: str = "",
    remix_notes: str = "",
    seed_analysis_id: str | None = None,
    landing_path: str = "/workspace/acquire",
) -> dict:
    if channel not in {"social", "expo", "agency"}:
        raise AppError("CONTENT_CHANNEL_DENIED", "只有社交、展会、代理可以起草种草", details={"channel": channel})
    if channel == "social" and mode not in {"invent", "remix"}:
        raise AppError("B2_MODE_REQUIRED", "社交种草要选造热点或复刻热点")
    if channel == "expo" and mode not in {"settle", "follow"}:
        raise AppError("B3_MODE_REQUIRED", "展会要选入驻或询盘跟进")
    if channel == "agency" and mode not in {"directory", "outreach"}:
        raise AppError("B4_MODE_REQUIRED", "代理要选搜集平台或私联合约")

    seed = " ".join((seed_text or remix_notes or "跨境选品").split())[:200]
    if mode == "remix":
        body = (
            f"【复刻热点】围绕「{seed}」改写成合规种草短文。"
            f"引导读者填写落地页表单，授权微信、邮箱或手机之一。"
            f"落地页：{landing_path}"
        )
        title = f"复刻 · {seed[:24]}"
    elif mode == "follow":
        body = f"【询盘跟进】针对「{seed}」起草跟进话术，请对方留下微信、邮箱或手机。"
        title = f"跟进 · {seed[:24]}"
    elif mode == "outreach":
        body = f"【代理私联】就「{seed}」起草分销合作与合约沟通要点，确认对方微信/邮箱/手机。"
        title = f"合约 · {seed[:24]}"
    elif mode == "directory":
        body = f"【代理目录】整理「{seed}」相关代理平台与联系入口，供自行联系。"
        title = f"目录 · {seed[:24]}"
    elif mode == "settle":
        body = (
            f"【展位种草】入驻展会后介绍「{seed}」，引导留资。"
            f"落地页：{landing_path}。请授权微信、邮箱或手机。"
        )
        title = f"展位 · {seed[:24]}"
    else:
        body = (
            f"【AI 造热点】根据「{seed}」写一条种草短文，突出跨境卖点。"
            f"文末引导到落地页表单，收集中高意向并加微信或授权邮箱/手机。"
            f"落地页：{landing_path}"
        )
        title = f"造热点 · {seed[:24]}"

    row = store.insert(
        "content_jobs",
        base_doc(
            prof["tenant"]["id"],
            prof["user"]["id"],
            id=new_id("cjob"),
            channel=channel,
            platform=platform,
            mode=mode,
            status="pending_approve",
            title=title,
            body=body,
            seed_text=seed,
            remix_notes=(remix_notes or "")[:500],
            seed_analysis_id=seed_analysis_id or "",
            landing_path=landing_path,
            contact_options=list(CONTACT_KEYS),
            published=False,
            approved_at=None,
        ),
    )
    return _public_job(row)


def list_seed_drafts(store, tenant_id: str, channel: str = "") -> list[dict]:
    found = store.query("content_jobs", tenant_id=tenant_id, limit=50)
    rows = found.get("items") or []
    if channel:
        rows = [row for row in rows if row.get("channel") == channel]
    return [_public_job(row) for row in rows]


def approve_seed(store, tenant_id: str, job_id: str) -> dict:
    row = store.get("content_jobs", job_id)
    if not row or row.get("tenant_id") != tenant_id:
        raise AppError("CONTENT_JOB_NOT_FOUND", "找不到这篇种草稿", 404)
    if row.get("status") == "approved":
        return _public_job(row)
    store.touch(
        "content_jobs",
        job_id,
        {
            "status": "approved",
            "approved_at": iso(),
            "published": False,
            "publish_note": "已批准。官方发布接口按平台权限逐步接通，当前停在已批准草稿。",
        },
    )
    return _public_job(store.get("content_jobs", job_id))


def intent_band(score: int, *, wechat: str = "", email: str = "", phone: str = "") -> str:
    if wechat.strip() or email.strip() or phone.strip():
        if score >= INTENT_HIGH:
            return "high"
        return "mid"
    if score >= INTENT_HIGH:
        return "mid"
    return "low"


def enrich_lead_contacts(row: dict) -> dict:
    """Normalize contact fields and bump score when a contact channel exists."""
    wechat = str(row.get("wechat") or "").strip()
    email = str(row.get("email") or "").strip() or None
    phone = str(row.get("phone") or "").strip()
    score = int(row.get("quality_score") or 0)
    if wechat or email or phone:
        score = max(score, INTENT_HIGH)
    band = intent_band(score, wechat=wechat, email=email or "", phone=phone)
    note_bits = []
    if wechat:
        note_bits.append(f"微信:{wechat}")
    if phone:
        note_bits.append(f"手机:{phone}")
    if email:
        note_bits.append(f"邮箱:{email}")
    note = str(row.get("note") or "")
    if note_bits:
        extra = " · ".join(note_bits)
        note = f"{note} · {extra}".strip(" ·") if note else extra
    return {
        **row,
        "email": email,
        "wechat": wechat,
        "phone": phone,
        "quality_score": score,
        "intent_band": band,
        "note": note[:200],
        "qualified": band in {"high", "mid"},
    }


def mock_landing_leads(channel: str, platform: str, mode: str, query: str = "") -> list[dict]:
    """Demo mid/high intent rows with WeChat / email / phone after seeding funnel."""
    label = (query or mode or platform).strip()[:20] or platform
    base = [
        {
            "company": f"{label}意向客户甲",
            "contact_name": "王经理",
            "email": "wang@example.com",
            "wechat": "wx_wang_ok",
            "phone": "",
            "market": "US",
            "quality_score": 78,
            "platform": platform,
            "source_channel": channel,
            "external_id": f"{platform}-landing-a",
            "note": f"mode={mode} 落地页授权邮箱+微信",
        },
        {
            "company": f"{label}意向客户乙",
            "contact_name": "李采购",
            "email": None,
            "wechat": "",
            "phone": "13800001111",
            "market": "CN",
            "quality_score": 72,
            "platform": platform,
            "source_channel": channel,
            "external_id": f"{platform}-landing-b",
            "note": f"mode={mode} 落地页授权手机",
        },
        {
            "company": f"{label}观望客户",
            "contact_name": "赵看客",
            "email": None,
            "wechat": "",
            "phone": "",
            "market": "US",
            "quality_score": 48,
            "platform": platform,
            "source_channel": channel,
            "external_id": f"{platform}-landing-c",
            "note": f"mode={mode} 未授权联系方式",
        },
    ]
    return [enrich_lead_contacts(item) for item in base]


def mock_agency_directory(platform: str, mode: str) -> list[dict]:
    rows = [
        {
            "company": "华东跨境一级代理",
            "contact_name": "一级·陈总",
            "email": "l1@agency.example",
            "wechat": "agency_l1_chen",
            "phone": "13900002222",
            "market": "CN",
            "quality_score": 80,
            "platform": platform,
            "source_channel": "agency",
            "external_id": f"{platform}-l1",
            "note": f"mode={mode} 一级代理可私联分销",
        },
        {
            "company": "华南二级渠道代理",
            "contact_name": "二级·周经理",
            "email": None,
            "wechat": "agency_l2_zhou",
            "phone": "13700003333",
            "market": "CN",
            "quality_score": 74,
            "platform": platform,
            "source_channel": "agency",
            "external_id": f"{platform}-l2",
            "note": f"mode={mode} 二级代理可谈合约",
        },
    ]
    return [enrich_lead_contacts(item) for item in rows]


def mock_legal_contacts(platform: str, query: str) -> list[dict]:
    word = (query or "贸易").strip()[:20]
    rows = [
        {
            "company": f"{word}有限公司",
            "contact_name": "法人·张三",
            "email": "legal@corp.example",
            "wechat": "",
            "phone": "01088886666",
            "market": "CN",
            "quality_score": 76,
            "platform": platform,
            "source_channel": "enrichment",
            "external_id": f"{platform}-legal-1",
            "note": "法人通信信息，自行联系",
        },
        {
            "company": f"{word}进出口公司",
            "contact_name": "法人·李四",
            "email": None,
            "wechat": "",
            "phone": "02166668888",
            "market": "CN",
            "quality_score": 71,
            "platform": platform,
            "source_channel": "enrichment",
            "external_id": f"{platform}-legal-2",
            "note": "法人电话，自行联系",
        },
    ]
    return [enrich_lead_contacts(item) for item in rows]


def _public_job(row: dict) -> dict:
    return {
        "id": row["id"],
        "channel": row.get("channel") or "",
        "platform": row.get("platform") or "",
        "mode": row.get("mode") or "",
        "status": row.get("status") or "pending_approve",
        "title": row.get("title") or "",
        "body": row.get("body") or "",
        "landing_path": row.get("landing_path") or "",
        "contact_options": row.get("contact_options") or list(CONTACT_KEYS),
        "seed_analysis_id": row.get("seed_analysis_id") or "",
        "published": bool(row.get("published")),
        "publish_note": row.get("publish_note") or "",
        "approved_at": row.get("approved_at"),
    }
