"""Page-section attention: dwell, continuous clicks, and leaves."""

import re

from db.store import DocumentStore

from app.core.errors import AppError
from app.core.timeutil import iso
from app.services.common import base_doc, new_id, within_window

KINDS = {"dwell", "click", "leave"}
# Main routes and their child routes. Homepage blocks stay as extra sections.
KNOWN_PAGES = (
    ("home", "首页", "/"),
    ("login", "登录", "/login"),
    ("register", "注册", "/register"),
    ("forgot", "找回密码", "/forgot"),
    ("reset", "重置密码", "/reset"),
    ("login-wechat", "微信登录", "/login/wechat"),
    ("workspace", "工作台", "/workspace"),
    ("workspace-products", "选品分析", "/workspace/products"),
    ("workspace-acquire", "获客经营", "/workspace/acquire"),
    ("acquire-ecommerce", "获客 · 电商平台", "/workspace/acquire/ecommerce"),
    ("acquire-social", "获客 · 社交平台", "/workspace/acquire/social"),
    ("acquire-expo", "获客 · 线上展会", "/workspace/acquire/expo"),
    ("acquire-agency", "获客 · 代理渠道", "/workspace/acquire/agency"),
    ("acquire-enrichment", "获客 · 智慧大脑", "/workspace/acquire/enrichment"),
    ("acquire-geo_seo", "获客 · GEO / SEO", "/workspace/acquire/geo_seo"),
    ("acquire-content_dh", "获客 · 内容与数智人", "/workspace/acquire/content_dh"),
    ("acquire-cross_border", "获客 · 跨境元素", "/workspace/acquire/cross_border"),
    ("acquire-raas", "获客 · RaaS", "/workspace/acquire/raas"),
    ("workspace-billing", "账单", "/workspace/billing"),
    ("report-detail", "报告详情", "/workspace/reports"),
    ("admin", "运营总览", "/admin"),
    ("admin-ads", "广告管理", "/admin/ads"),
    ("admin-users", "用户数据", "/admin/users"),
    ("admin-analytics", "行为分析", "/admin/analytics"),
    ("admin-invitations", "用户邀请", "/admin/invitations"),
    ("admin-recall", "用户召回", "/admin/recall"),
    ("admin-audit", "审计日志", "/admin/audit"),
    ("admin-settings", "平台设置", "/admin/settings"),
    ("admin-search", "搜索结果", "/admin/search"),
    ("admin-login", "管理登录", "/admin/login"),
    ("top", "首页主视觉", "/#top"),
    ("library", "商品库", "/#library"),
    ("path-a", "选品路径", "/#path-a"),
    ("analysis", "报告样例", "/#analysis"),
    ("path-b", "获客九路", "/#path-b"),
    ("scenes", "应用场景", "/#scenes"),
    ("devices", "多端工作台", "/#devices"),
    ("trust", "平台说明", "/#trust"),
    ("faq", "常见问题", "/#faq"),
    ("contact", "收尾", "/#contact"),
)
SECTION_LABELS = {key: label for key, label, _path in KNOWN_PAGES}
_SECTION = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


def record_behavior(store: DocumentStore, *, path: str, section: str, kind: str, duration_ms: int, clicks: int) -> dict:
    cleaned = (section or "").strip().lower()
    if kind not in KINDS or not _SECTION.match(cleaned):
        raise AppError("INVALID_BEHAVIOR", "行为记录缺少区块或类型")
    if duration_ms < 0 or duration_ms > 30 * 60 * 1000 or clicks < 0 or clicks > 200:
        raise AppError("INVALID_BEHAVIOR", "行为时长或点击次数超出范围")
    safe_path = (path or "/")[:120]
    if not safe_path.startswith("/"):
        safe_path = "/"
    return store.insert(
        "page_behaviors",
        base_doc(
            "platform",
            "visitor",
            id=new_id("beh"),
            path=safe_path,
            section=cleaned,
            kind=kind,
            duration_ms=duration_ms,
            clicks=clicks,
        ),
    )


def behavior_summary(store: DocumentStore, window_days: int | None) -> dict:
    rows = store.query("page_behaviors", limit=500)["items"]
    grouped: dict[str, dict] = {}
    for row in rows:
        if window_days is not None:
            try:
                if not within_window(row.get("created_at") or "", window_days):
                    continue
            except ValueError:
                continue
        section = row.get("section") or ""
        if not section:
            continue
        item = grouped.setdefault(section, _blank(section, row.get("path") or ""))
        if row.get("path"):
            item["path"] = row["path"]
        duration = int(row.get("duration_ms") or 0)
        kind = row.get("kind")
        if kind == "dwell":
            item["dwells"] += 1
            item["dwell_ms"] += duration
        elif kind == "click":
            item["click_runs"] += 1
            item["clicks"] += int(row.get("clicks") or 0)
            item["click_ms"] += duration
        elif kind == "leave":
            item["leaves"] += 1
            item["leave_ms"] += duration
    sections = []
    for item in grouped.values():
        visits = item["dwells"] + item["leaves"]
        item["avg_dwell_ms"] = round(item["dwell_ms"] / item["dwells"]) if item["dwells"] else 0
        item["avg_click_ms"] = round(item["click_ms"] / item["click_runs"]) if item["click_runs"] else 0
        item["attention_ms"] = item["dwell_ms"] + item["click_ms"]
        item["visits"] = visits
        sections.append(item)
    for key, _label, path in KNOWN_PAGES:
        if key not in grouped:
            blank = _blank(key, path)
            blank["avg_dwell_ms"] = 0
            blank["avg_click_ms"] = 0
            blank["attention_ms"] = 0
            blank["visits"] = 0
            sections.append(blank)
    sections.sort(key=lambda row: (row["attention_ms"] > 0 or row["leaves"] > 0, row["attention_ms"], -row["leaves"]), reverse=True)
    ranked = [row for row in sections if row["dwells"] or row["click_runs"] or row["leaves"]]
    best = max(ranked, key=lambda row: row["attention_ms"]) if ranked else None
    worst = max(ranked, key=lambda row: (row["leaves"], -row["avg_dwell_ms"])) if ranked else None
    if best and worst and best["section"] == worst["section"] and len(ranked) > 1:
        worst = max((row for row in ranked if row["section"] != best["section"]), key=lambda row: (row["leaves"], -row["avg_dwell_ms"]))
    return {
        "as_of": iso(),
        "sections": sections,
        "best": _pick(best, "停留和连续点击最多"),
        "worst": _pick(worst, "离开最多，或停留最短"),
    }


def search_pages(store: DocumentStore, needle: str, window_days: int | None = 30) -> list[dict]:
    query = needle.strip().lower()
    if not query:
        return []
    rows = behavior_summary(store, window_days)["sections"]
    hits = []
    for row in rows:
        blob = f"{row['section']} {row['label']} {row.get('path') or ''}".lower()
        if query not in blob:
            continue
        hits.append(
            {
                "id": row["section"],
                "label": row["label"],
                "href": f"/admin/analytics?q={row['label']}",
                "path": row.get("path") or "",
                "dwell_ms": row["dwell_ms"],
                "avg_dwell_ms": row["avg_dwell_ms"],
                "clicks": row["clicks"],
                "click_ms": row["click_ms"],
                "leaves": row["leaves"],
                "leave_ms": row["leave_ms"],
            }
        )
    return hits


def _blank(section: str, path: str) -> dict:
    return {
        "section": section,
        "label": SECTION_LABELS.get(section, section),
        "path": path,
        "dwells": 0,
        "dwell_ms": 0,
        "click_runs": 0,
        "clicks": 0,
        "click_ms": 0,
        "leaves": 0,
        "leave_ms": 0,
    }


def _pick(row: dict | None, reason: str) -> dict | None:
    if not row:
        return None
    return {"section": row["section"], "label": row["label"], "reason": reason, "attention_ms": row["attention_ms"], "leaves": row["leaves"], "avg_dwell_ms": row["avg_dwell_ms"]}
