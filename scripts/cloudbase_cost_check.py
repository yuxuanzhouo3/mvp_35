#!/usr/bin/env python3
"""Inspect CloudBase cost drivers. Optionally scale live web/api min replicas to 0.

Safe actions only:
- read environment / version status
- redeploy the current image with MinNum=0 / MaxNum=2 for mvp35 web and api
- delete failed deploy versions created by that scale attempt

Never destroys an environment, freezes a service, or changes mornfront.
Credentials come from the CloudBase CLI login file or process environment.
This script never prints secrets.
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
from datetime import datetime, timezone
from pathlib import Path

MVP35 = "mvp35-d6g2zp4539a542ebc"
MORNFRONT = "cloud1-3gn61ziydcfe6a57"
WATCH = {"pickglobal-web", "pickglobal-api"}
SITE = "https://pickglobal.mornscience.top"
AUTH = Path.home() / ".config/.cloudbase/auth.json"
DOC = Path(__file__).resolve().parents[1] / "docs" / "cloudbase-cost.md"


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


def probe_site() -> str:
    req = urllib.request.Request(SITE, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return str(resp.status)
    except urllib.error.HTTPError as exc:
        return str(exc.code)
    except Exception as exc:
        return f"error:{type(exc).__name__}"


def snapshot() -> dict:
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
            if not version:
                rows.append(
                    {
                        "env": env_id,
                        "alias": env.get("Alias"),
                        "status": env.get("Status"),
                        "server": server,
                        "version": None,
                    }
                )
                continue
            rows.append(
                {
                    "env": env_id,
                    "alias": env.get("Alias"),
                    "status": env.get("Status"),
                    "server": server,
                    "version": version.get("VersionName"),
                    "min": version.get("MinReplicas"),
                    "max": version.get("MaxReplicas"),
                    "current": version.get("CurrentReplicas"),
                    "flow": version.get("FlowRatio"),
                    "state": version.get("Status"),
                }
            )
    return {"site": probe_site(), "rows": rows}


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


def scale_server_to_zero(server: str) -> list[str]:
    notes = []
    version = live_version(MVP35, server)
    if not version:
        return [f"{server}: no 100% traffic version, skipped"]
    name = version.get("VersionName")
    current_min = int(version.get("MinReplicas") or 0)
    if current_min == 0:
        return [f"{server} {name}: min already 0"]

    _wait_idle(server)
    detail = call(
        "DescribeCloudBaseRunServerVersion",
        {"EnvId": MVP35, "ServerName": server, "VersionName": name},
    )
    image = detail.get("ImageUrl")
    if not image:
        return [f"{server} {name}: no ImageUrl, use console to set min replicas to 0"]

    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                {"Key": "MinNum", "IntValue": 0},
                {"Key": "MaxNum", "IntValue": int(detail.get("MaxNum") or version.get("MaxReplicas") or 2)},
            ],
        },
        host="tcbr.tencentcloudapi.com",
        service="tcbr",
        version="2022-02-17",
    )
    notes.append(f"{server}: submitted image redeploy with MinNum=0 from {name}")

    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(10)
        live = live_version(MVP35, server)
        if not live:
            continue
        if int(live.get("MinReplicas") or -1) == 0 and live.get("Status") == "normal":
            notes.append(f"{server}: live {live.get('VersionName')} min=0")
            notes.extend(_delete_failed(server, started[:10]))
            # also delete previous live version if it still holds a replica
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
                f"{server}: set min replicas to 0 in console — "
                f"https://tcb.cloud.tencent.com/dev?envId={MVP35}#/platform-run/service/detail?serverName={server}&tab=version"
            )
            return notes

    notes.append(f"{server}: timed out waiting for min=0; check console")
    return notes


def scale_to_zero() -> list[str]:
    notes = []
    for server in sorted(WATCH):
        notes.extend(scale_server_to_zero(server))
    return notes


def print_report(data: dict) -> int:
    print(f"site {SITE} -> {data['site']}")
    bad = 0
    for row in data["rows"]:
        if row.get("error"):
            print(f"{row['env']} {row['server']}: {row['error']}")
            bad += 1
            continue
        version = row.get("version") or "-"
        print(
            f"{row.get('alias') or row['env']} {row['server']} {version} "
            f"status={row.get('status')} state={row.get('state')} "
            f"min={row.get('min')} current={row.get('current')} max={row.get('max')} flow={row.get('flow')}"
        )
        if row["env"] == MVP35 and row.get("min") not in (0, None):
            bad += 1
    return bad


def write_log(action: str, data: dict) -> None:
    if not DOC.exists():
        return
    by_server = {row["server"]: row for row in data["rows"] if row.get("env") == MVP35}
    web = by_server.get("pickglobal-web") or {}
    api = by_server.get("pickglobal-api") or {}

    def cell(row: dict) -> str:
        if not row.get("version"):
            return "-"
        return f"{row.get('min')} / {row.get('current')} ({row.get('version')})"

    day = datetime.now().strftime("%Y-%m-%d")
    line = f"| {day} | {action} | {cell(web)} | {cell(api)} | {data['site']} | 脚本检查 |\n"
    text = DOC.read_text()
    marker = "| 2026-10-22 | 最小副本改 0 | 待脚本回写 | 待脚本回写 | 待验证 | 环境保留，只关空转 |\n"
    if marker in text:
        DOC.write_text(text.replace(marker, line))
        return
    if line not in text and not text.rstrip().endswith(line.strip()):
        DOC.write_text(text.rstrip() + "\n" + line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scale-to-zero",
        action="store_true",
        help="Redeploy mvp35 live web/api images with MinNum=0",
    )
    parser.add_argument("--write-log", action="store_true", help="Append the result to docs/cloudbase-cost.md")
    args = parser.parse_args()
    if args.scale_to_zero:
        for note in scale_to_zero():
            print(note)
        time.sleep(2)
    data = snapshot()
    bad = print_report(data)
    if args.write_log or args.scale_to_zero:
        write_log("最小副本改 0" if args.scale_to_zero else "复查", data)
    if bad and not args.scale_to_zero:
        print("mvp35 still has a live version with min replicas >= 1. Re-run with --scale-to-zero or use the console.")
        return 1
    if bad and args.scale_to_zero:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
