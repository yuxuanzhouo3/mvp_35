"""Page-section attention: dwell, continuous clicks, and leaves."""

import re

from db.store import DocumentStore

from app.core.errors import AppError
from app.core.timeutil import iso
from app.services.common import base_doc, new_id, within_window

KINDS = {"dwell", "click", "leave"}
SECTION_LABELS = {
    "top": "首页主视觉",
    "library": "商品库",
    "path-a": "选品路径",
    "analysis": "报告样例",
    "path-b": "获客九路",
    "scenes": "应用场景",
    "faq": "常见问题",
    "devices": "多端工作台",
    "trust": "平台说明",
    "contact": "收尾",
    "workspace": "工作台",
    "report": "选品报告",
    "acquire": "获客经营",
    "billing": "账单",
}
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
        item = grouped.setdefault(
            section,
            {"section": section, "label": SECTION_LABELS.get(section, section), "dwells": 0, "dwell_ms": 0, "click_runs": 0, "clicks": 0, "click_ms": 0, "leaves": 0, "leave_ms": 0},
        )
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
    sections.sort(key=lambda row: (row["attention_ms"], -row["leaves"]), reverse=True)
    best = max(sections, key=lambda row: row["attention_ms"]) if sections else None
    worst = max(sections, key=lambda row: (row["leaves"], -row["avg_dwell_ms"])) if sections else None
    if best and worst and best["section"] == worst["section"] and len(sections) > 1:
        worst = max((row for row in sections if row["section"] != best["section"]), key=lambda row: (row["leaves"], -row["avg_dwell_ms"]))
    return {
        "as_of": iso(),
        "sections": sections,
        "best": _pick(best, "停留和连续点击最多"),
        "worst": _pick(worst, "离开最多，或停留最短"),
    }


def _pick(row: dict | None, reason: str) -> dict | None:
    if not row:
        return None
    return {"section": row["section"], "label": row["label"], "reason": reason, "attention_ms": row["attention_ms"], "leaves": row["leaves"], "avg_dwell_ms": row["avg_dwell_ms"]}
