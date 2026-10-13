from app.modules.events import emit
from app.services.common import base_doc, new_id
from app.services.metrics import snapshot


def _show(row: dict) -> dict:
    view = dict(row)
    view["display"] = "—" if row.get("value") is None else row["value"]
    return view


def dashboard_view(snap: dict) -> dict:
    headline_keys = ("net_margin", "act_r", "tr", "open_r", "ar")
    lifecycle_keys = ("qr", "act_r_cold", "rec_r")
    return {
        "screen": "四率 + 北星 AR",
        "headline": {key: _show(snap["rates"][key]) for key in headline_keys},
        "north_star": "ar",
        "timings": {
            "folded": True,
            "p50_seconds": snap["timings_p50_seconds"],
            "targets_seconds": snap["timing_targets_seconds"],
        },
        "redlines": snap["redlines"],
        "alerts": snap["alerts"],
        "lifecycle": {key: _show(snap["rates"][key]) for key in lifecycle_keys},
        "window_days": snap["window_days"],
    }


def build_dashboard(store, settings, prof: dict, window_days: int) -> dict:
    snap = snapshot(store, prof["tenant"]["id"], settings, window_days)
    view = dashboard_view(snap)
    period = f"{window_days}d"
    rows = {**view["headline"], **view["lifecycle"]}
    for row in rows.values():
        store.insert(
            "kpi_metrics",
            base_doc(
                prof["tenant"]["id"],
                prof["user"]["id"],
                id=new_id("kpi"),
                metric_code=row["code"],
                value=row["value"],
                period=period,
                kpi_period=period,
            ),
        )
    emit(store, prof["tenant"]["id"], "kpi.updated", {"period": period}, prof["user"]["id"])
    return view
