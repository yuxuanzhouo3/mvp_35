from decimal import Decimal

from rollback.baseline import BASELINE_VERSION, ENGINE_CLOUDBASE, FLAGS, POSTGRES_ONLY
from rollback.snapshot import ledger_fen
from rollback.store import collections, load


def verify_baseline(store_path, config: dict, traffic: dict) -> dict:
    data = load(store_path)
    meta = data.get("meta") or {}
    cols = collections(data)
    problems = []
    if meta.get("engine") != ENGINE_CLOUDBASE:
        problems.append(f"engine={meta.get('engine')}")
    if meta.get("schema_version") != BASELINE_VERSION or meta.get("applied"):
        problems.append(f"schema={meta.get('schema_version')} applied={meta.get('applied')}")
    for name in POSTGRES_ONLY:
        if cols.get(name):
            problems.append(f"仍存在 {name}")
    emails = []
    for doc in (cols.get("leads") or {}).values():
        if doc.get("deleted_at"):
            continue
        email = (doc.get("email") or "").strip().lower()
        if email:
            emails.append((doc.get("tenant_id"), email))
    if len(emails) != len(set(emails)):
        problems.append("leads 邮箱在租户内重复")
    for doc in (cols.get("users") or {}).values():
        if not doc.get("cloudbase_user_id"):
            problems.append(f"用户 {doc.get('id')} 缺少 cloudbase_user_id")
    report_names = "analysis_reports" if "analysis_reports" in cols else "selection_reports"
    for doc in (cols.get(report_names) or {}).values():
        if doc.get("explanation_model") not in {None, "rules"}:
            problems.append(f"报告 {doc.get('id')} 仍走模型 {doc.get('explanation_model')}")
        metrics = doc.get("metrics") or {}
        if metrics.get("net_margin") and doc.get("net_margin") and Decimal(str(doc["net_margin"])) != Decimal(str(metrics["net_margin"])):
            problems.append(f"报告 {doc.get('id')} 利润率与规则不一致")
    flags = config.get("flags") or {}
    for name in FLAGS:
        if flags.get(name) is not False:
            problems.append(f"flag {name} 未关闭")
    if config.get("storage_engine") != ENGINE_CLOUDBASE:
        problems.append("配置存储不是 CloudBase")
    if traffic.get("selector", {}).get("version") != BASELINE_VERSION or traffic.get("percent") != 100:
        problems.append("流量未切回 baseline-cloudbase")
    if traffic.get("canary_percent") not in {0, None}:
        problems.append("金丝雀流量未清零")
    keys = []
    for doc in (cols.get("payment_orders") or {}).values():
        if doc.get("idempotency_key"):
            keys.append((doc.get("tenant_id"), doc["idempotency_key"]))
    if len(keys) != len(set(keys)):
        problems.append("支付幂等键重复")
    return {
        "ok": not problems,
        "problems": problems,
        "engine": meta.get("engine"),
        "ledger_fen": ledger_fen(data),
        "users": len(cols.get("users") or {}),
        "leads": len(cols.get("leads") or {}),
    }
