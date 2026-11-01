#!/usr/bin/env python3
"""Inspect CloudBase cost drivers, estimate daily spend, optionally scale to zero.

Safe actions only:
- read environment / version / monitor status
- redeploy the current image with MinNum=0 / MaxNum=1 / 0.25C0.5G for mvp35 web and api
- delete failed deploy versions created by that scale attempt
- append daily spend rows to docs/cloudbase-cost.md

Never destroys an environment, freezes a service, or changes mornfront.
Credentials come from the CloudBase CLI login file or process environment.
This script never prints secrets.

Daily auto budget: 0.3 CNY = 3 auto starts x 0.1 CNY.
Cursor --cursor-start can open more the same day.
Platform idle reclaim is ~30 minutes (not configurable to 10).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

MVP35 = "mvp35-d6g2zp4539a542ebc"
MORNFRONT = "cloud1-3gn61ziydcfe6a57"
WATCH = {"pickglobal-web", "pickglobal-api"}
SITE = "https://pickglobal.mornscience.top"
AUTH = Path.home() / ".config/.cloudbase/auth.json"
DOC = Path(__file__).resolve().parents[1] / "docs" / "cloudbase-cost.md"
BUDGET_STATE = Path(__file__).resolve().parents[1] / "docs" / "cloudbase-budget-state.json"
TZ = ZoneInfo("Asia/Shanghai")
# Auto traffic: 3 cold-starts/day, 0.1 CNY each, hard cap 0.3 CNY.
# Cursor --cursor-start bypasses the auto cap for the rest of that open session.
DAILY_BUDGET_YUAN = 0.3
AUTO_STARTS_PER_DAY = 3
YUAN_PER_AUTO_START = 0.1
# Shanghai CloudRun resource points (1000 points = 1 CNY)
CPU_POINTS_PER_CORE_HOUR = 55.0
MEM_POINTS_PER_GB_HOUR = 32.0
TARGET_CPU = 0.25
TARGET_MEM = 0.5
# FastAPI + Postgres client OOMs / hangs health on 0.25C/0.5G (stuck scaleActiveing + 503).
TARGET_API_CPU = 0.5
TARGET_API_MEM = 1.0
# Platform fixed idle window before scale-to-zero under alwaysScale + MinNum=0.
PLATFORM_IDLE_MINUTES = 30
def slot_warm_minutes() -> float:
    """Minutes both 0.25C/0.5G services can stay warm on 0.1 CNY."""
    both = hour_rate_yuan(TARGET_CPU, TARGET_MEM) * 2
    if both <= 0:
        return 100.0
    return YUAN_PER_AUTO_START / both * 60.0


def target_spec(server: str) -> tuple[float, float]:
    if server == "pickglobal-api":
        return TARGET_API_CPU, TARGET_API_MEM
    return TARGET_CPU, TARGET_MEM


def _credential() -> tuple[str, str, str]:
    import os

    secret_id = (os.environ.get("CLOUDBASE_SECRET_ID") or os.environ.get("TENCENTCLOUD_SECRETID") or "").strip()
    secret_key = (os.environ.get("CLOUDBASE_SECRET_KEY") or os.environ.get("TENCENTCLOUD_SECRETKEY") or "").strip()
    token = (os.environ.get("CLOUDBASE_TOKEN") or os.environ.get("TENCENTCLOUD_SESSIONTOKEN") or "").strip()
    if secret_id and secret_key:
        return secret_id, secret_key, token
    if not AUTH.exists():
        raise SystemExit("CloudBase CLI is not logged in. Run tcb login.")
    cred = json.loads(AUTH.read_text()).get("credential") or {}
    secret_id = cred.get("tmpSecretId") or cred.get("secretId") or ""
    secret_key = cred.get("tmpSecretKey") or cred.get("secretKey") or ""
    token = cred.get("tmpToken") or cred.get("token") or ""
    if not secret_id or not secret_key:
        raise SystemExit("CloudBase login file has no temporary secret. Run tcb login.")
    return secret_id, secret_key, token


def call(
    action: str,
    payload: dict,
    *,
    host: str = "tcb.tencentcloudapi.com",
    service: str = "tcb",
    version: str = "2018-06-08",
) -> dict:
    secret_id, secret_key, token = _credential()
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    timestamp = int(time.time())
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    content_type = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{content_type}\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed = hashlib.sha256(body.encode()).hexdigest()
    canonical = "\n".join(["POST", "/", "", canonical_headers, signed_headers, hashed])
    scope = f"{date}/{service}/tc3_request"
    string_to_sign = "\n".join(
        ["TC3-HMAC-SHA256", str(timestamp), scope, hashlib.sha256(canonical.encode()).hexdigest()]
    )
    secret_date = hmac.new(("TC3" + secret_key).encode(), date.encode(), hashlib.sha256).digest()
    secret_service = hmac.new(secret_date, service.encode(), hashlib.sha256).digest()
    secret_signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
    signature = hmac.new(secret_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    headers = {
        "Authorization": (
            f"TC3-HMAC-SHA256 Credential={secret_id}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "Content-Type": content_type,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
        "X-TC-Region": "ap-shanghai",
    }
    if token:
        headers["X-TC-Token"] = token
    req = urllib.request.Request(f"https://{host}", data=body.encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            parsed = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        parsed = json.loads(exc.read().decode())
    response = parsed.get("Response") or parsed
    error = response.get("Error")
    if error:
        raise RuntimeError(f"{action}: {error.get('Code')} {error.get('Message')}")
    return response


def list_versions(env_id: str, server: str) -> list[dict]:
    data = call(
        "DescribeCloudBaseRunServer",
        {"EnvId": env_id, "ServerName": server, "Offset": 0, "Limit": 20},
    )
    return list(data.get("VersionItems") or [])


def live_version(env_id: str, server: str) -> dict | None:
    items = [item for item in list_versions(env_id, server) if int(item.get("FlowRatio") or 0) == 100]
    return items[0] if items else None


def server_config(server: str) -> dict:
    data = call(
        "DescribeCloudRunServerDetail",
        {"EnvId": MVP35, "ServerName": server},
        host="tcbr.tencentcloudapi.com",
        service="tcbr",
        version="2022-02-17",
    )
    return dict(data.get("ServerConfig") or {})


def version_detail(server: str, version_name: str) -> dict:
    return call(
        "DescribeCloudBaseRunServerVersion",
        {"EnvId": MVP35, "ServerName": server, "VersionName": version_name},
    )


def probe_site() -> str:
    req = urllib.request.Request(SITE, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return str(resp.status)
    except urllib.error.HTTPError as exc:
        return str(exc.code)
    except Exception as exc:
        return f"error:{type(exc).__name__}"


def hour_rate_yuan(cpu: float, mem: float) -> float:
    points = cpu * CPU_POINTS_PER_CORE_HOUR + mem * MEM_POINTS_PER_GB_HOUR
    return points / 1000.0


# One script start owns the session until 0.1 CNY of warm time elapses (~100 min).
CURSOR_GRACE_MINUTES = int(round(YUAN_PER_AUTO_START / (hour_rate_yuan(TARGET_CPU, TARGET_MEM) * 2) * 60))


def snapshot(*, probe: bool = True) -> dict:
    envs = {
        item.get("EnvId"): item
        for item in (call("DescribeEnvs", {"Limit": 50, "Offset": 0}).get("EnvList") or [])
    }
    rows = []
    for env_id, servers in ((MVP35, WATCH), (MORNFRONT, {"mornfront"})):
        env = envs.get(env_id) or {}
        for server in sorted(servers):
            try:
                version = live_version(env_id, server)
            except RuntimeError as exc:
                rows.append({"env": env_id, "server": server, "error": str(exc)})
                continue
            row: dict = {
                "env": env_id,
                "alias": env.get("Alias"),
                "status": env.get("Status"),
                "server": server,
                "version": None,
            }
            if not version:
                rows.append(row)
                continue
            detail = {}
            cfg = {}
            if env_id == MVP35:
                try:
                    detail = version_detail(server, version.get("VersionName") or "")
                    cfg = server_config(server)
                except RuntimeError:
                    detail, cfg = {}, {}
            cpu = float(detail.get("Cpu") or cfg.get("Cpu") or 0)
            mem = float(detail.get("Mem") or cfg.get("Mem") or 0)
            rows.append(
                {
                    **row,
                    "version": version.get("VersionName"),
                    "min": version.get("MinReplicas"),
                    "max": version.get("MaxReplicas"),
                    "current": version.get("CurrentReplicas"),
                    "flow": version.get("FlowRatio"),
                    "state": version.get("Status"),
                    "cpu": cpu,
                    "mem": mem,
                    "mode": cfg.get("OperationMode"),
                    "hour_yuan": round(hour_rate_yuan(cpu, mem), 4) if cpu or mem else None,
                }
            )
    return {"site": probe_site() if probe else "skipped", "rows": rows, "at": datetime.now(TZ).isoformat()}


def env_invoke_by_day(day: str) -> dict:
    """Return EnvInvokeNum for one Shanghai calendar day."""
    start = f"{day}T00:00:00+08:00"
    end = f"{day}T23:59:59+08:00"
    daily = call(
        "GetMonitorData",
        {
            "Namespace": "QCE/TCB",
            "MetricName": "EnvInvokeNum",
            "Period": 86400,
            "StartTime": start,
            "EndTime": end,
            "Instances": [{"Dimensions": [{"Name": "envid", "Value": MVP35}]}],
        },
        host="monitor.tencentcloudapi.com",
        service="monitor",
        version="2018-07-24",
    )
    hourly = call(
        "GetMonitorData",
        {
            "Namespace": "QCE/TCB",
            "MetricName": "EnvInvokeNum",
            "Period": 3600,
            "StartTime": start,
            "EndTime": end,
            "Instances": [{"Dimensions": [{"Name": "envid", "Value": MVP35}]}],
        },
        host="monitor.tencentcloudapi.com",
        service="monitor",
        version="2018-07-24",
    )
    daily_vals = ((daily.get("DataPoints") or [{}])[0].get("Values") or [0])
    hourly_vals = (hourly.get("DataPoints") or [{}])[0].get("Values") or []
    nonzero = sum(1 for value in hourly_vals if value)
    return {
        "day": day,
        "invokes": float(daily_vals[0] or 0),
        "active_hours": nonzero,
        "hourly": [float(v or 0) for v in hourly_vals],
    }


def estimate_day_yuan(day: str, *, web_cpu: float, web_mem: float, api_cpu: float, api_mem: float) -> dict:
    """Estimate CloudRun spend from invoke-active hours + platform cool-down.

    Finance bill APIs are not authorized for the current tcb login, so this is
    an upper-bound style estimate: each active hour plus PLATFORM_IDLE_MINUTES
    cool-down is billed for both services at the given sizes.
    """
    traffic = env_invoke_by_day(day)
    active = int(traffic["active_hours"])
    # Cool-down after last traffic in the day; at most one platform window.
    cool_h = PLATFORM_IDLE_MINUTES / 60.0 if active else 0.0
    # If traffic every hour, instances stayed warm ~24h.
    if active >= 20:
        warm_h = 24.0
    else:
        warm_h = min(24.0, active + cool_h)
    web = hour_rate_yuan(web_cpu, web_mem) * warm_h
    api = hour_rate_yuan(api_cpu, api_mem) * warm_h
    total = web + api
    return {
        **traffic,
        "warm_hours": round(warm_h, 2),
        "web_yuan": round(web, 3),
        "api_yuan": round(api, 3),
        "total_yuan": round(total, 3),
        "web_spec": f"{web_cpu}C/{web_mem}G",
        "api_spec": f"{api_cpu}C/{api_mem}G",
        "budget_yuan": DAILY_BUDGET_YUAN,
        "over_budget": total > DAILY_BUDGET_YUAN,
    }


def historical_estimates() -> list[dict]:
    """Yesterday / day-before with known historical specs from cost notes."""
    today = datetime.now(TZ).date()
    out = []
    # Day before yesterday / yesterday relative to "today" in Shanghai.
    # force_warm_h: when min replicas were 1 for most of the day, bill ~24h even if
    # gateway invokes were sparse.
    specs = {
        (today - timedelta(days=2)).isoformat(): {
            "web": (1.0, 2.0),
            "api": (1.0, 2.0),
            "force_warm_h": 24.0,
            "note": "min≈1 大半天常驻",
        },
        (today - timedelta(days=1)).isoformat(): {
            "web": (1.0, 2.0),
            "api": (1.0, 2.0),
            "force_warm_h": 24.0,
            "note": "全天有调用+api曾 min=1",
        },
    }
    for day, meta in specs.items():
        w_cpu, w_mem = meta["web"]
        a_cpu, a_mem = meta["api"]
        try:
            item = estimate_day_yuan(day, web_cpu=w_cpu, web_mem=w_mem, api_cpu=a_cpu, api_mem=a_mem)
            force = meta.get("force_warm_h")
            if force is not None:
                item["warm_hours"] = force
                item["web_yuan"] = round(hour_rate_yuan(w_cpu, w_mem) * force, 3)
                item["api_yuan"] = round(hour_rate_yuan(a_cpu, a_mem) * force, 3)
                item["total_yuan"] = round(item["web_yuan"] + item["api_yuan"], 3)
                item["over_budget"] = item["total_yuan"] > DAILY_BUDGET_YUAN
            item["note"] = meta.get("note") or ""
            out.append(item)
        except Exception as exc:
            out.append({"day": day, "error": str(exc)})
    return out


def _wait_idle(server: str, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        busy = [
            item.get("VersionName")
            for item in list_versions(MVP35, server)
            if item.get("Status") in ("creating", "deleting", "deploying")
        ]
        if not busy:
            return
        time.sleep(5)
    raise RuntimeError(f"{server}: still busy after {timeout}s")


def _delete_failed(server: str, created_after: str) -> list[str]:
    notes = []
    for item in list_versions(MVP35, server):
        name = item.get("VersionName") or ""
        status = item.get("Status")
        created = item.get("CreatedTime") or ""
        flow = int(item.get("FlowRatio") or 0)
        if flow == 100:
            continue
        if status == "deploy_failed" and created >= created_after:
            call(
                "DeleteCloudBaseRunServerVersion",
                {
                    "EnvId": MVP35,
                    "ServerName": server,
                    "VersionName": name,
                    "IsDeleteServer": False,
                    "IsDeleteImage": False,
                },
            )
            notes.append(f"{server} {name}: deleted failed deploy")
    return notes


def cleanup_failed_and_stranded() -> list[str]:
    """Delete deploy_failed versions and non-live versions still holding replicas."""
    notes = []
    for server in sorted(WATCH):
        for item in list_versions(MVP35, server):
            flow = int(item.get("FlowRatio") or 0)
            cur = int(item.get("CurrentReplicas") or 0)
            status = item.get("Status")
            name = item.get("VersionName") or ""
            if flow == 100:
                continue
            if status == "deploy_failed" or (cur > 0 and flow == 0 and status in ("normal", "deploy_failed", "scaleActiveing")):
                try:
                    call(
                        "DeleteCloudBaseRunServerVersion",
                        {
                            "EnvId": MVP35,
                            "ServerName": server,
                            "VersionName": name,
                            "IsDeleteServer": False,
                            "IsDeleteImage": False,
                        },
                    )
                    notes.append(f"{server} {name}: deleted stranded/failed (status={status} cur={cur})")
                except RuntimeError as exc:
                    notes.append(f"{server} {name}: keep ({exc})")
    return notes


def scale_server_to_zero(server: str) -> list[str]:
    notes = []
    version = live_version(MVP35, server)
    if not version:
        return [f"{server}: no 100% traffic version, skipped"]
    name = version.get("VersionName")
    try:
        detail = version_detail(server, name or "")
    except RuntimeError as exc:
        return [f"{server} {name}: {exc}"]
    current_min = int(version.get("MinReplicas") or 0)
    cpu = float(detail.get("Cpu") or 0)
    mem = float(detail.get("Mem") or 0)
    want_cpu, want_mem = target_spec(server)
    need = current_min != 0 or abs(cpu - want_cpu) > 1e-6 or abs(mem - want_mem) > 1e-6
    if not need:
        cfg = server_config(server)
        if cfg.get("OperationMode") == "alwaysScale":
            return [f"{server} {name}: already min=0 {cpu}C/{mem}G alwaysScale"]

    _wait_idle(server)
    image = detail.get("ImageUrl")
    if not image:
        return [f"{server} {name}: no ImageUrl, use console to set min=0 and {want_cpu}C/{want_mem}G"]

    started = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    call(
        "UpdateCloudRunServer",
        {
            "EnvId": MVP35,
            "ServerName": server,
            "DeployInfo": {
                "DeployType": "image",
                "ImageUrl": image,
                "ReleaseType": "FULL",
            },
            "Items": [
                {"Key": "CpuSpecs", "FloatValue": want_cpu},
                {"Key": "MemSpecs", "FloatValue": want_mem},
                {"Key": "MinNum", "IntValue": 0},
                {"Key": "MaxNum", "IntValue": 1},
                {"Key": "OperationMode", "Value": "alwaysScale"},
                # Custom domain HTTP gateway requires PUBLIC; OA/MINIAPP breaks it.
                {"Key": "AccessTypes", "ArrayValue": ["PUBLIC"]},
            ],
        },
        host="tcbr.tencentcloudapi.com",
        service="tcbr",
        version="2022-02-17",
    )
    notes.append(f"{server}: submitted image redeploy MinNum=0 {want_cpu}C/{want_mem}G from {name}")

    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(10)
        live = live_version(MVP35, server)
        if not live:
            continue
        try:
            live_detail = version_detail(server, live.get("VersionName") or "")
        except RuntimeError:
            continue
        live_cpu = float(live_detail.get("Cpu") or 0)
        if (
            int(live.get("MinReplicas") or -1) == 0
            and live.get("Status") == "normal"
            and abs(live_cpu - want_cpu) <= 1e-6
        ):
            notes.append(f"{server}: live {live.get('VersionName')} min=0 {live_cpu}C/{live_detail.get('Mem')}G")
            notes.extend(_delete_failed(server, started[:10]))
            if live.get("VersionName") != name and int(version.get("CurrentReplicas") or 0) >= 0:
                old = [item for item in list_versions(MVP35, server) if item.get("VersionName") == name]
                if old and int(old[0].get("FlowRatio") or 0) == 0:
                    try:
                        call(
                            "DeleteCloudBaseRunServerVersion",
                            {
                                "EnvId": MVP35,
                                "ServerName": server,
                                "VersionName": name,
                                "IsDeleteServer": False,
                                "IsDeleteImage": False,
                            },
                        )
                        notes.append(f"{server} {name}: deleted previous live version")
                    except RuntimeError as exc:
                        notes.append(f"{server} {name}: keep previous version ({exc})")
            return notes
        newest = sorted(list_versions(MVP35, server), key=lambda item: item.get("CreatedTime") or "", reverse=True)
        if newest and newest[0].get("Status") == "deploy_failed" and newest[0].get("VersionName") != name:
            notes.append(f"{server}: redeploy failed ({newest[0].get('VersionName')})")
            notes.extend(_delete_failed(server, started[:10]))
            notes.append(
                f"{server}: set {want_cpu}C/{want_mem}G and min=0 in console — "
                f"https://tcb.cloud.tencent.com/dev?envId={MVP35}#/platform-run/service/detail?serverName={server}&tab=version"
            )
            return notes

    notes.append(f"{server}: timed out waiting for min=0 small size; check console")
    return notes


def scale_to_zero() -> list[str]:
    notes = []
    for server in sorted(WATCH):
        notes.extend(scale_server_to_zero(server))
    return notes


def recent_invokes(minutes: int = 10) -> float:
    end = datetime.now(TZ)
    start = end - timedelta(minutes=max(minutes, 5))
    data = call(
        "GetMonitorData",
        {
            "Namespace": "QCE/TCB",
            "MetricName": "EnvInvokeNum",
            "Period": 60,
            "StartTime": start.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "EndTime": end.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "Instances": [{"Dimensions": [{"Name": "envid", "Value": MVP35}]}],
        },
        host="monitor.tencentcloudapi.com",
        service="monitor",
        version="2018-07-24",
    )
    values = (data.get("DataPoints") or [{}])[0].get("Values") or []
    return float(sum(v for v in values if v is not None))


def today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def _empty_budget_state(day: str | None = None) -> dict:
    return {
        "day": day or today_str(),
        "auto_starts": 0,
        "auto_spend_yuan": 0.0,
        "cursor_starts": 0,
        "closed": False,
        "cursor_open_until": None,
        "was_warm": False,
        "updated_at": datetime.now(TZ).isoformat(),
        "notes": [],
    }


def load_budget_state() -> dict:
    day = today_str()
    if not BUDGET_STATE.exists():
        return _empty_budget_state(day)
    try:
        data = json.loads(BUDGET_STATE.read_text())
    except (json.JSONDecodeError, OSError):
        return _empty_budget_state(day)
    if data.get("day") != day:
        return _empty_budget_state(day)
    data.setdefault("auto_starts", 0)
    data.setdefault("auto_spend_yuan", 0.0)
    data.setdefault("cursor_starts", 0)
    data.setdefault("closed", False)
    data.setdefault("cursor_open_until", None)
    data.setdefault("was_warm", False)
    data.setdefault("notes", [])
    return data


def save_budget_state(state: dict) -> None:
    state["updated_at"] = datetime.now(TZ).isoformat()
    BUDGET_STATE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def mvp35_is_warm(data: dict | None = None) -> bool:
    snap = data or snapshot(probe=False)
    return any(
        row.get("env") == MVP35 and int(row.get("current") or 0) > 0 for row in snap["rows"]
    )


def cursor_session_active(state: dict) -> bool:
    until = state.get("cursor_open_until")
    if not until:
        return False
    try:
        end = datetime.fromisoformat(until)
    except ValueError:
        return False
    if end.tzinfo is None:
        end = end.replace(tzinfo=TZ)
    return datetime.now(TZ) < end


def auto_budget_exhausted(state: dict) -> bool:
    return (
        int(state.get("auto_starts") or 0) >= AUTO_STARTS_PER_DAY
        or float(state.get("auto_spend_yuan") or 0) >= DAILY_BUDGET_YUAN - 1e-9
        or bool(state.get("closed"))
    )


def _update_access(server: str, access: list[str]) -> list[str]:
    notes = []
    _wait_idle(server)
    version = live_version(MVP35, server)
    if not version:
        return [f"{server}: no live version"]
    name = version.get("VersionName") or ""
    detail = version_detail(server, name)
    image = detail.get("ImageUrl")
    if not image:
        return [f"{server}: no ImageUrl"]
    started = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    call(
        "UpdateCloudRunServer",
        {
            "EnvId": MVP35,
            "ServerName": server,
            "DeployInfo": {"DeployType": "image", "ImageUrl": image, "ReleaseType": "FULL"},
            "Items": [
                {"Key": "CpuSpecs", "FloatValue": target_spec(server)[0]},
                {"Key": "MemSpecs", "FloatValue": target_spec(server)[1]},
                {"Key": "MinNum", "IntValue": 0},
                {"Key": "MaxNum", "IntValue": 1},
                {"Key": "OperationMode", "Value": "alwaysScale"},
                {"Key": "AccessTypes", "ArrayValue": access},
                {"Key": "InternalAccess", "Value": "open" if access != ["PUBLIC"] else "close"},
            ],
        },
        host="tcbr.tencentcloudapi.com",
        service="tcbr",
        version="2022-02-17",
    )
    notes.append(f"{server}: submitted AccessTypes={access}")
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(8)
        busy = [
            item.get("VersionName")
            for item in list_versions(MVP35, server)
            if item.get("Status") in ("creating", "deleting", "deploying")
        ]
        if busy:
            continue
        cfg = server_config(server)
        live = live_version(MVP35, server)
        if live and cfg.get("OpenAccessTypes") == access:
            notes.append(f"{server}: live {live.get('VersionName')} access={access}")
            notes.extend(_delete_failed(server, started[:10]))
            return notes
        newest = sorted(list_versions(MVP35, server), key=lambda item: item.get("CreatedTime") or "", reverse=True)
        if newest and newest[0].get("Status") == "deploy_failed":
            notes.append(f"{server}: access change failed ({newest[0].get('VersionName')})")
            notes.extend(_delete_failed(server, started[:10]))
            return notes
    notes.append(f"{server}: timed out waiting for AccessTypes={access}")
    return notes


def budget_close() -> list[str]:
    """Block public (and custom-domain) access so scanners cannot keep waking pods."""
    notes = ["budget close: switch AccessTypes to OA until --cursor-start or next day"]
    for server in sorted(WATCH):
        cfg = server_config(server)
        if cfg.get("OpenAccessTypes") == ["OA"]:
            notes.append(f"{server}: already OA")
            continue
        notes.extend(_update_access(server, ["OA"]))
    notes.extend(cleanup_failed_and_stranded())
    return notes


def budget_open_public() -> list[str]:
    notes = ["budget open: restore AccessTypes PUBLIC"]
    for server in sorted(WATCH):
        cfg = server_config(server)
        if cfg.get("OpenAccessTypes") == ["PUBLIC"]:
            notes.append(f"{server}: already PUBLIC")
            continue
        notes.extend(_update_access(server, ["PUBLIC"]))
    notes.extend(cleanup_failed_and_stranded())
    return notes


def print_budget(state: dict) -> None:
    print(
        f"budget day={state.get('day')} auto_starts={state.get('auto_starts')}/{AUTO_STARTS_PER_DAY} "
        f"auto_spend={float(state.get('auto_spend_yuan') or 0):.2f}/{DAILY_BUDGET_YUAN:.2f} "
        f"cursor_starts={state.get('cursor_starts')} closed={state.get('closed')} "
        f"cursor_active={cursor_session_active(state)}"
    )


def budget_guard() -> list[str]:
    """Track auto cold-starts; close public access after 3 x 0.1 CNY."""
    notes = cleanup_failed_and_stranded()
    state = load_budget_state()
    data = snapshot(probe=False)
    warm = mvp35_is_warm(data)
    cursor_active = cursor_session_active(state)

    if state.get("closed") and not cursor_active:
        notes.append("auto budget closed; ensure OA and skip auto wake accounting")
        for server in sorted(WATCH):
            if server_config(server).get("OpenAccessTypes") != ["OA"]:
                notes.extend(_update_access(server, ["OA"]))
        state["was_warm"] = warm
        save_budget_state(state)
        print_budget(state)
        return notes

    # Cold -> warm without an active cursor session counts as one auto start (0.1 CNY).
    if warm and not state.get("was_warm") and not cursor_active:
        if auto_budget_exhausted(state):
            notes.append("wake ignored: auto budget already exhausted")
            state["closed"] = True
            notes.extend(budget_close())
        else:
            state["auto_starts"] = int(state.get("auto_starts") or 0) + 1
            state["auto_spend_yuan"] = round(
                float(state.get("auto_spend_yuan") or 0) + YUAN_PER_AUTO_START, 2
            )
            notes.append(
                f"auto start #{state['auto_starts']} (+{YUAN_PER_AUTO_START} CNY) "
                f"total auto={state['auto_spend_yuan']}"
            )
            if auto_budget_exhausted(state):
                state["closed"] = True
                notes.append("auto budget reached 0.3 CNY / 3 starts; closing public access after this session idles")
                # Close immediately so a 4th scanner wake cannot start. Current warm
                # pods may finish until platform reclaim; OA blocks new public traffic.
                notes.extend(budget_close())

    if not warm and cursor_active:
        # Cursor session ended by idle; clear grace so later wakes are auto again.
        state["cursor_open_until"] = None
        notes.append("cursor session cleared (services cold)")

    state["was_warm"] = warm
    save_budget_state(state)
    print_budget(state)
    return notes


def cursor_start() -> list[str]:
    """Script wake: one of 3 daily slots (0.1 CNY / ~100 min warm). Max 0.3 CNY/day."""
    notes = []
    state = load_budget_state()
    used = max(int(state.get("auto_starts") or 0), int(state.get("cursor_starts") or 0))
    if cursor_session_active(state):
        notes.append("session already open; not consuming another slot")
    elif used >= AUTO_STARTS_PER_DAY:
        left = slot_warm_minutes()
        raise SystemExit(
            f"today {used}/{AUTO_STARTS_PER_DAY} script starts used "
            f"({float(state.get('auto_spend_yuan') or used * YUAN_PER_AUTO_START):.2f}/"
            f"{DAILY_BUDGET_YUAN:.2f} CNY). Next slot tomorrow. "
            f"Each start ≈ {left:.0f} min both-warm."
        )
    else:
        used += 1
        state["auto_starts"] = used
        state["cursor_starts"] = used
        state["auto_spend_yuan"] = round(used * YUAN_PER_AUTO_START, 2)
        state["closed"] = used >= AUTO_STARTS_PER_DAY
        notes.append(f"script start #{used}/{AUTO_STARTS_PER_DAY} (+{YUAN_PER_AUTO_START} CNY)")

    grace = max(CURSOR_GRACE_MINUTES, 1)
    state["closed"] = False
    state["cursor_open_until"] = (datetime.now(TZ) + timedelta(minutes=grace)).isoformat()
    notes.extend(budget_open_public())
    status = probe_site()
    notes.append(f"site probe -> {status}")
    time.sleep(2)
    state["was_warm"] = mvp35_is_warm()
    state["notes"] = (state.get("notes") or [])[-20:] + [
        f"{datetime.now(TZ).isoformat()} script-start #{state.get('cursor_starts')}"
    ]
    save_budget_state(state)
    print_budget(state)
    until = state.get("cursor_open_until")
    notes.append(
        f"slot {state.get('auto_starts')}/{AUTO_STARTS_PER_DAY} "
        f"({float(state.get('auto_spend_yuan') or 0):.2f}/{DAILY_BUDGET_YUAN:.2f} CNY); "
        f"this 0.1 CNY lasts ~{grace} min both-warm (until {until}); "
        f"idle ~{PLATFORM_IDLE_MINUTES}m then scale to 0. Next start: same command."
    )
    return notes


def enforce_idle(minutes: int = 10) -> list[str]:
    """Budget guard + idle cleanup. Does not HTTP-probe the public site."""
    notes = budget_guard()
    state = load_budget_state()
    if state.get("closed") and not cursor_session_active(state):
        notes.append("closed: skip idle traffic checks")
        return notes

    invokes = recent_invokes(minutes)
    notes.append(f"invokes_last_{minutes}m={invokes}")
    data = snapshot(probe=False)
    warm = [
        row
        for row in data["rows"]
        if row.get("env") == MVP35 and int(row.get("current") or 0) > 0
    ]
    if invokes > 0:
        notes.append("traffic present; leave live replicas alone")
        return notes
    if not warm:
        notes.append("no warm replicas")
        return notes
    notes.append(
        f"no invokes for ~{minutes}m but live still warm "
        f"({', '.join(r['server']+':'+str(r.get('current')) for r in warm)}); "
        f"platform reclaim needs ~{PLATFORM_IDLE_MINUTES}m without domain traffic"
    )
    for server in sorted({row["server"] for row in warm}):
        cfg = server_config(server)
        if int(cfg.get("MinNum") or 0) != 0 or abs(float(cfg.get("Cpu") or 99) - target_spec(server)[0]) > 1e-6:
            notes.extend(scale_server_to_zero(server))
        else:
            notes.append(f"{server}: service config already min=0 small; wait platform idle window")
    return notes


def print_report(data: dict) -> int:
    print(f"site {SITE} -> {data['site']}")
    print(
        f"auto budget {DAILY_BUDGET_YUAN} CNY/day = {AUTO_STARTS_PER_DAY} starts x "
        f"{YUAN_PER_AUTO_START} | cursor-start can spend more | idle ~{PLATFORM_IDLE_MINUTES}m"
    )
    print_budget(load_budget_state())
    bad = 0
    burn = 0.0
    for row in data["rows"]:
        if row.get("error"):
            print(f"{row['env']} {row['server']}: {row['error']}")
            bad += 1
            continue
        version = row.get("version") or "-"
        spec = ""
        if row.get("cpu") is not None:
            spec = f" {row.get('cpu')}C/{row.get('mem')}G mode={row.get('mode')} ~{row.get('hour_yuan')}CNY/h"
        print(
            f"{row.get('alias') or row['env']} {row['server']} {version} "
            f"status={row.get('status')} state={row.get('state')} "
            f"min={row.get('min')} current={row.get('current')} max={row.get('max')} flow={row.get('flow')}{spec}"
        )
        if row["env"] == MVP35:
            if row.get("min") not in (0, None):
                bad += 1
            if abs(float(row.get("cpu") or 0) - target_spec(row["server"])[0]) > 1e-6:
                bad += 1
            if int(row.get("current") or 0) > 0 and row.get("hour_yuan"):
                burn += float(row["hour_yuan"])
    if burn:
        print(f"current warm burn ~{burn:.3f} CNY/h ({burn * 24:.2f} CNY if stays warm 24h)")
        print(f"0.1 CNY start ≈ {YUAN_PER_AUTO_START / burn:.2f} warm-hours at current sizes")
    return bad


def write_spend_table(estimates: list[dict]) -> None:
    if not DOC.exists():
        return
    lines = [
        "## 每日费用（估算）",
        "",
        "临时密钥无费用中心读权限时，用调用活跃小时 × 规格单价估算云托管（不含 Postgres 等）。"
        f"自动日预算 **{DAILY_BUDGET_YUAN} 元**（{AUTO_STARTS_PER_DAY} 次 × {YUAN_PER_AUTO_START} 元）；"
        f"Cursor `--cursor-start` 可加开。平台无流量缩到 0 约 **{PLATFORM_IDLE_MINUTES} 分钟**。",
        "",
        "| 日期 | 调用次数 | 有调用小时 | 估算热着小时 | web 规格 | api 规格 | 估算元 | 超预算 | 备注 |",
        "| --- | ---: | ---: | ---: | --- | --- | ---: | --- | --- |",
    ]
    for item in estimates:
        if item.get("error"):
            lines.append(f"| {item.get('day')} | - | - | - | - | - | error | - | {item['error'][:40]} |")
            continue
        lines.append(
            f"| {item['day']} | {int(item['invokes'])} | {item['active_hours']} | {item['warm_hours']} | "
            f"{item['web_spec']} | {item['api_spec']} | {item['total_yuan']:.2f} | "
            f"{'是' if item['over_budget'] else '否'} | {item.get('note') or ''} |"
        )
    block = "\n".join(lines) + "\n"
    text = DOC.read_text()
    marker_start = "## 每日费用（估算）"
    marker_end = "## 检查记录"
    if marker_start in text and marker_end in text:
        head, rest = text.split(marker_start, 1)
        _, tail = rest.split(marker_end, 1)
        DOC.write_text(head + block + "\n" + marker_end + tail)
    elif marker_end in text:
        DOC.write_text(text.replace(marker_end, block + "\n" + marker_end))
    else:
        DOC.write_text(text.rstrip() + "\n\n" + block)


def write_log(action: str, data: dict) -> None:
    if not DOC.exists():
        return
    by_server = {row["server"]: row for row in data["rows"] if row.get("env") == MVP35}
    web = by_server.get("pickglobal-web") or {}
    api = by_server.get("pickglobal-api") or {}

    def cell(row: dict) -> str:
        if not row.get("version"):
            return "-"
        spec = ""
        if row.get("cpu") is not None:
            spec = f" {row.get('cpu')}C/{row.get('mem')}G"
        return f"{row.get('min')} / {row.get('current')} ({row.get('version')}{spec})"

    day = datetime.now(TZ).strftime("%Y-%m-%d")
    line = f"| {day} | {action} | {cell(web)} | {cell(api)} | {data['site']} | 脚本检查 |\n"
    text = DOC.read_text()
    if line not in text and not text.rstrip().endswith(line.strip()):
        DOC.write_text(text.rstrip() + "\n" + line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scale-to-zero",
        action="store_true",
        help="Redeploy mvp35 live web/api images with MinNum=0 (web 0.25C/0.5G, api 0.5C/1G)",
    )
    parser.add_argument(
        "--enforce-idle",
        type=int,
        nargs="?",
        const=10,
        metavar="MINUTES",
        help="Budget guard + idle cleanup for MINUTES (default 10); do not HTTP-probe site",
    )
    parser.add_argument(
        "--budget-guard",
        action="store_true",
        help="Only run the 0.3 CNY / 3 auto-start guard (no site probe)",
    )
    parser.add_argument(
        "--cursor-start",
        action="store_true",
        help="Script start: consume 1 of 3 daily 0.1 CNY slots, restore PUBLIC, probe site",
    )
    parser.add_argument("--write-log", action="store_true", help="Append the result to docs/cloudbase-cost.md")
    parser.add_argument(
        "--estimate-days",
        action="store_true",
        help="Estimate yesterday and the day before; refresh the daily spend table",
    )
    parser.add_argument("--no-probe", action="store_true", help="Skip HTTP probe of the public site")
    args = parser.parse_args()

    if args.cursor_start:
        for note in cursor_start():
            print(note)
        data = snapshot(probe=False)
        print_report(data)
        if args.write_log:
            write_log("Cursor 启动", data)
        return 0

    if args.budget_guard:
        for note in budget_guard():
            print(note)
        data = snapshot(probe=False)
        if args.write_log:
            write_log("预算闸门", data)
        return 0

    if args.enforce_idle is not None:
        for note in enforce_idle(args.enforce_idle):
            print(note)
        data = snapshot(probe=not args.no_probe and args.write_log)
        if args.write_log:
            print_report(data)
            write_log(f"空闲巡检 {args.enforce_idle}m", data)
        return 0

    if args.scale_to_zero:
        for note in scale_to_zero():
            print(note)
        time.sleep(2)

    if args.estimate_days or args.write_log:
        estimates = historical_estimates()
        print("=== daily spend estimate (CloudRun only) ===")
        for item in estimates:
            if item.get("error"):
                print(item)
                continue
            print(
                f"{item['day']}: invokes={int(item['invokes'])} active_h={item['active_hours']} "
                f"warm_h~{item['warm_hours']} web={item['web_spec']} api={item['api_spec']} "
                f"~{item['total_yuan']:.2f} CNY "
                f"{'>' if item['over_budget'] else '<='} auto-budget {DAILY_BUDGET_YUAN}"
            )
        write_spend_table(estimates)

    data = snapshot(probe=not args.no_probe)
    bad = print_report(data)
    if args.write_log or args.scale_to_zero:
        write_log("最小副本改 0" if args.scale_to_zero else "复查", data)
    if bad and not args.scale_to_zero:
        print(
            "mvp35 still has min>=1 or the live size is off target. "
            "Re-run with --scale-to-zero or resize api in the console."
        )
        return 1
    if bad and args.scale_to_zero:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
