from decimal import Decimal

from config.settings import Settings
from db.store import DocumentStore

from app.services.common import median, percentile, within_window
from app.services.profit import rate


RATE_TARGETS = {
    "net_margin": ("N%", "0.1500", False),
    "act_r": ("ActR", "0.5000", False),
    "tr": ("TR", "0.9500", False),
    "open_r": ("OR", "0.4000", False),
    "ar": ("AR", "0.0800", True),
    "qr": ("QR", "0.6000", False),
    "act_r_cold": ("ActR_cold", "0.2500", False),
    "rec_r": ("RecR", "0.1000", False),
}
TIMING_TARGETS = {"ana_t": 120, "lead_t": 180, "acq_t": 3 * 86400, "act_t": 86400, "rec_t": 86400}


def _rate(numerator: int, denominator: int):
    if denominator <= 0:
        return None
    return rate(Decimal(numerator) / Decimal(denominator))


def middle_band(values: list):
    """Drop both tails, then average from the middle of the remaining users."""
    ordered = sorted(values)
    count = len(ordered)
    if count >= 4:
        cut = count // 4
        return ordered[cut : count - cut]
    if count == 3:
        return ordered[1:2]
    return ordered


def middle_mean(values: list[Decimal]) -> Decimal | None:
    band = middle_band(values)
    if not band:
        return None
    return sum(band, Decimal("0")) / Decimal(len(band))


KPI_BANDS = ((10, 90), (20, 80), (30, 70))


def percentile_band(values: list, low: float, high: float) -> list:
    """Keep values between the two percentiles. Fewer than four samples stay whole."""
    ordered = sorted(values)
    if len(ordered) < 4:
        return ordered
    scores = [float(item) for item in ordered]
    floor = percentile(scores, low)
    ceiling = percentile(scores, high)
    if floor is None or ceiling is None:
        return ordered
    return [item for item in ordered if floor <= float(item) <= ceiling]


def _mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def _invalid_reason(user: dict) -> str | None:
    if user.get("deleted_at"):
        return "deleted"
    if user.get("status") not in {None, "active"}:
        return "inactive"
    principal = str(user.get("cloudbase_user_id") or user.get("principal") or user.get("id") or "")
    if principal.startswith("demo"):
        return "demo"
    email = str(user.get("email") or "")
    if email.endswith("@example.com"):
        return "example"
    if not user.get("tenant_id"):
        return "no_tenant"
    return None


def snapshot(store: DocumentStore, tenant_id: str, settings: Settings, window_days: int = 30) -> dict:
    analyses = [
        item
        for item in store.query("analysis_reports", tenant_id=tenant_id, limit=500)["items"]
        if within_window(item.get("finished_at") or item.get("created_at"), window_days)
    ]
    leads = [
        item
        for item in store.query("leads", tenant_id=tenant_id, limit=500)["items"]
        if within_window(item["created_at"], window_days)
    ]
    campaigns = store.query("campaigns", tenant_id=tenant_id, limit=200)["items"]
    messages = [
        item
        for item in store.query("outreach_messages", tenant_id=tenant_id, limit=1000)["items"]
        if within_window(item["created_at"], window_days)
    ]
    activations = [
        item
        for item in store.query("activation_jobs", tenant_id=tenant_id, limit=500)["items"]
        if within_window(item.get("enqueued_at") or item["created_at"], window_days)
    ]
    recalls = [
        item
        for item in store.query("recall_jobs", tenant_id=tenant_id, limit=500)["items"]
        if within_window(item.get("triggered_at") or item["created_at"], window_days)
    ]
    imports = [
        item
        for item in store.query("jobs", tenant_id=tenant_id, limit=200, filters={"job_type": "product_import"})["items"]
        if item.get("status") == "succeeded" and within_window(item.get("finished_at") or "", window_days)
    ]

    margins = [Decimal(item["net_margin"]) for item in analyses if item.get("net_margin")]
    acquired = [item for item in analyses if item.get("acquired_at")]
    qualified = [item for item in leads if item.get("quality_score", 0) >= settings.quality_threshold]

    acquisition_messages = [
        item for item in messages if item.get("purpose") == "acquisition" and not item.get("exclude_from_ar")
    ]
    audience = 0
    delivered_people = set()
    opened_people = set()
    delivered_acquisition = []
    for campaign in campaigns:
        if not within_window(campaign.get("approved_at") or "", window_days):
            continue
        if campaign.get("purpose") not in {None, "acquisition"}:
            continue
        ids = set(campaign.get("audience_snapshot", {}).get("lead_ids") or [])
        audience += len(ids)
        for item in acquisition_messages:
            if item.get("campaign_id") == campaign["id"] and item.get("status") == "delivered" and item["lead_id"] in ids:
                delivered_people.add(item["lead_id"])
                delivered_acquisition.append(item)
                if item.get("opened_at"):
                    opened_people.add(item["lead_id"])

    wins = 0
    acq_seconds = []
    for lead_id in delivered_people:
        lead = store.get("leads", lead_id, tenant_id)
        if not lead:
            continue
        marker = lead.get("replied_at") or lead.get("won_at")
        first = min(
            (item["delivered_at"] for item in delivered_acquisition if item["lead_id"] == lead_id and item.get("delivered_at")),
            default=None,
        )
        if marker and first:
            delta = (parse_delta(marker, first))
            if delta is not None and delta <= 14 * 86400:
                wins += 1
                acq_seconds.append(delta)

    sent = [item for item in messages if item.get("status") in {"delivered", "bounced", "complained"}]
    bounced = [item for item in sent if item["status"] == "bounced"]
    complained = [item for item in sent if item["status"] == "complained"]
    delivered_msgs = [item for item in sent if item["status"] == "delivered"]

    ana = []
    for item in analyses:
        if item.get("requested_at") and item.get("finished_at"):
            ana.append(parse_delta(item["finished_at"], item["requested_at"]) or 0)
    lead_t = []
    for job in store.query("jobs", tenant_id=tenant_id, limit=200, filters={"job_type": "lead_discovery"})["items"]:
        if job.get("status") == "succeeded" and job.get("requested_at") and job.get("finished_at"):
            if within_window(job["finished_at"], window_days):
                lead_t.append(parse_delta(job["finished_at"], job["requested_at"]) or 0)

    act_t, rec_t = [], []
    cold_hit = 0
    for job in activations:
        if job.get("delivered_at") and job.get("enqueued_at"):
            act_t.append(parse_delta(job["delivered_at"], job["enqueued_at"]) or 0)
        if _lifecycle_hit(messages, job["id"]):
            cold_hit += 1
    warm_hit = 0
    recall_delivered = 0
    for job in recalls:
        if job.get("delivered_at"):
            recall_delivered += 1
            if job.get("triggered_at"):
                rec_t.append(parse_delta(job["delivered_at"], job["triggered_at"]) or 0)
        lead = store.get("leads", job["lead_id"], tenant_id) if job.get("lead_id") else None
        if job.get("delivered_at") and lead and (lead.get("warmed_at") or lead.get("replied_at") or lead.get("won_at")):
            warm_hit += 1

    import_ok, import_total = 0, 0
    for job in imports:
        result = job.get("result") or {}
        import_ok += int(result.get("imported") or 0)
        import_total += int(result.get("total") or 0)

    delivery_rate = _rate(len(delivered_msgs), len(sent))
    bounce_rate = _rate(len(bounced), len(sent))
    complaint_rate = _rate(len(complained), len(sent))
    tripped = False
    if sent:
        tripped = (
            Decimal(delivery_rate or "0") < Decimal("0.95")
            or Decimal(bounce_rate or "0") >= Decimal("0.015")
            or Decimal(complaint_rate or "0") >= Decimal("0.001")
        )

    net = median(margins)
    return {
        "window_days": window_days,
        "currency_note": "利润由规则引擎计算；分母为 0 时为空",
        "rates": {
            "net_margin": {"code": "N%", "value": rate(net) if net is not None else None, "target": "0.1500"},
            "act_r": {"code": "ActR", "value": _rate(len(acquired), len(analyses)), "target": "0.5000"},
            "tr": {"code": "TR", "value": _rate(len(delivered_people), audience), "target": "0.9500"},
            "open_r": {"code": "OR", "value": _rate(len(opened_people), len(delivered_people)), "target": "0.4000"},
            "ar": {"code": "AR", "value": _rate(wins, len(delivered_people)), "target": "0.0800", "north_star": True},
            "qr": {"code": "QR", "value": _rate(len(qualified), len(leads)), "target": "0.6000"},
            "act_r_cold": {"code": "ActR_cold", "value": _rate(cold_hit, len(activations)), "target": "0.2500"},
            "rec_r": {"code": "RecR", "value": _rate(warm_hit, recall_delivered), "target": "0.1000"},
        },
        "timings_p50_seconds": {
            "ana_t": _p50(ana),
            "lead_t": _p50(lead_t),
            "acq_t": _p50(acq_seconds),
            "act_t": _p50(act_t),
            "rec_t": _p50(rec_t),
        },
        "timing_targets_seconds": dict(TIMING_TARGETS),
        "alerts": {
            "act_t_p95_seconds": percentile(act_t, 0.95),
            "rec_t_p95_seconds": percentile(rec_t, 0.95),
            "act_or_rec_p95_over_72h": _over_72h(act_t, rec_t),
        },
        "redlines": {
            "delivery_rate": delivery_rate,
            "bounce_rate": bounce_rate,
            "complaint_rate": complaint_rate,
            "tripped": tripped,
        },
        "import_success_rate": _rate(import_ok, import_total),
        "counts": {
            "analyses": len(analyses),
            "acquired": len(acquired),
            "leads": len(leads),
            "audience": audience,
            "delivered_people": len(delivered_people),
        },
        "inputs": {
            "analyses": len(analyses),
            "acquired": len(acquired),
            "qualified": len(qualified),
            "leads": len(leads),
            "audience": audience,
            "delivered_people": len(delivered_people),
            "opened_people": len(opened_people),
            "wins": wins,
            "activations": len(activations),
            "cold_hit": cold_hit,
            "recall_delivered": recall_delivered,
            "warm_hit": warm_hit,
        },
    }


def has_acquirers(snap: dict) -> bool:
    counts = snap.get("counts") or {}
    return bool(counts.get("acquired") or counts.get("delivered_people") or counts.get("audience"))


def _measurable(snap: dict) -> bool:
    if has_acquirers(snap):
        return True
    if any((snap.get("counts") or {}).get(key) for key in ("analyses", "leads")):
        return True
    return any(value is not None for value in (snap.get("timings_p50_seconds") or {}).values())


def cohort_average(store: DocumentStore, settings: Settings, window_days: int = 30) -> dict:
    users = store.query("users", limit=500)["items"]
    included = []
    excluded = 0
    for user in users:
        if _invalid_reason(user):
            excluded += 1
            continue
        snap = snapshot(store, user["tenant_id"], settings, window_days)
        if not _measurable(snap):
            excluded += 1
            continue
        included.append(snap)

    def averaged_rate(key: str):
        code, target, north = RATE_TARGETS[key]
        numbers = []
        for snap in included:
            raw = ((snap.get("rates") or {}).get(key) or {}).get("value")
            if raw is not None:
                numbers.append(Decimal(str(raw)))
        mean = middle_mean(numbers)
        row = {"code": code, "value": rate(mean) if mean is not None else None, "target": target}
        if north:
            row["north_star"] = True
        return row

    timings = {}
    for key in TIMING_TARGETS:
        numbers = [snap["timings_p50_seconds"][key] for snap in included if snap["timings_p50_seconds"].get(key) is not None]
        band = middle_band(numbers)
        timings[key] = round(sum(band) / len(band), 3) if band else None

    def averaged_redline(key: str):
        numbers = []
        for snap in included:
            raw = (snap.get("redlines") or {}).get(key)
            if raw is not None:
                numbers.append(Decimal(str(raw)))
        mean = middle_mean(numbers)
        return rate(mean) if mean is not None else None

    delivery_rate = averaged_redline("delivery_rate")
    bounce_rate = averaged_redline("bounce_rate")
    complaint_rate = averaged_redline("complaint_rate")
    tripped = False
    if delivery_rate or bounce_rate or complaint_rate:
        tripped = (
            Decimal(delivery_rate or "1") < Decimal("0.95")
            or Decimal(bounce_rate or "0") >= Decimal("0.015")
            or Decimal(complaint_rate or "0") >= Decimal("0.001")
        )
    return {
        "window_days": window_days,
        "currency_note": "全站有效用户去掉两端后的中间平均。无效用户含演示、停用、删除、示例邮箱，以及窗口内没有报告和获客的账号。",
        "display_source": "platform_average",
        "rates": {key: averaged_rate(key) for key in RATE_TARGETS},
        "timings_p50_seconds": timings,
        "timing_targets_seconds": dict(TIMING_TARGETS),
        "alerts": {"act_or_rec_p95_over_72h": any(snap.get("alerts", {}).get("act_or_rec_p95_over_72h") for snap in included)},
        "redlines": {
            "delivery_rate": delivery_rate,
            "bounce_rate": bounce_rate,
            "complaint_rate": complaint_rate,
            "tripped": tripped,
        },
        "import_success_rate": None,
        "counts": {
            "analyses": sum(snap["counts"]["analyses"] for snap in included),
            "acquired": sum(snap["counts"]["acquired"] for snap in included),
            "leads": sum(snap["counts"]["leads"] for snap in included),
            "audience": sum(snap["counts"]["audience"] for snap in included),
            "delivered_people": sum(snap["counts"]["delivered_people"] for snap in included),
        },
        "basis": {
            "method": "middle",
            "included": len(included),
            "excluded": excluded,
            "note": "先去掉无效用户。剩下的人按这项指标从低到高排序，4 人及以上去掉前后各四分之一，3 人只留中间一个，2 人及以下直接平均。",
        },
        "bands": _kpi_bands(included),
    }


def _metric_numbers(snaps: list[dict], key: str, timing: bool) -> list[Decimal]:
    numbers = []
    for snap in snaps:
        raw = snap["timings_p50_seconds"].get(key) if timing else ((snap.get("rates") or {}).get(key) or {}).get("value")
        if raw is not None:
            numbers.append(Decimal(str(raw)))
    return numbers


def _kpi_bands(snaps: list[dict]) -> list[dict]:
    bands = []
    for low, high in KPI_BANDS:
        rates = {}
        for key, (code, target, north) in RATE_TARGETS.items():
            samples = _metric_numbers(snaps, key, False)
            kept = percentile_band(samples, low / 100, high / 100)
            mean = _mean(kept)
            row = {
                "code": code,
                "value": rate(mean) if mean is not None else None,
                "target": target,
                "kept": len(kept),
                "samples": len(samples),
            }
            if north:
                row["north_star"] = True
            rates[key] = row
        timings = {}
        for key in TIMING_TARGETS:
            samples = _metric_numbers(snaps, key, True)
            kept = percentile_band(samples, low / 100, high / 100)
            mean = _mean(kept)
            timings[key] = {"value": round(float(mean), 3) if mean is not None else None, "kept": len(kept), "samples": len(samples)}
        bands.append({"band": f"{low}-{high}", "users": len(snaps), "rates": rates, "timings": timings})
    return bands


def _p50(values: list[float]):
    if not values:
        return None
    return round(percentile(values, 0.5) or 0, 3)


def _over_72h(act_t: list[float], rec_t: list[float]) -> bool:
    limit = 72 * 3600
    for series in (act_t, rec_t):
        value = percentile(series, 0.95)
        if value is not None and value > limit:
            return True
    return False


def parse_delta(later: str, earlier: str) -> float | None:
    try:
        return max(0.0, (parse_iso_safe(later) - parse_iso_safe(earlier)).total_seconds())
    except Exception:
        return None


def parse_iso_safe(value: str):
    from app.core.timeutil import parse_iso

    return parse_iso(value)


def _lifecycle_hit(messages: list[dict], lifecycle_id: str) -> bool:
    for item in messages:
        if item.get("lifecycle_job_id") == lifecycle_id and (item.get("opened_at") or item.get("replied_at")):
            return True
    return False
