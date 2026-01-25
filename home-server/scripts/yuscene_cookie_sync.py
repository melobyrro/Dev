#!/usr/bin/env python3
import argparse
import asyncio
import json
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
import websockets


@dataclass(frozen=True)
class Cookie:
    name: str
    value: str


def _get_cdp_targets(browser_url: str) -> List[Dict[str, Any]]:
    resp = requests.get(f"{browser_url}/json", timeout=5)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError("Unexpected CDP /json response shape")
    return data


async def _cdp_get_cookies(ws_url: str, urls: List[str]) -> List[Cookie]:
    next_id = 1

    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024) as ws:
        async def send(method: str, params: Optional[Dict[str, Any]] = None) -> int:
            nonlocal next_id
            msg: Dict[str, Any] = {"id": next_id, "method": method}
            if params is not None:
                msg["params"] = params
            await ws.send(json.dumps(msg))
            current = next_id
            next_id += 1
            return current

        async def recv_until(msg_id: int) -> Dict[str, Any]:
            while True:
                raw = await ws.recv()
                payload = json.loads(raw)
                if isinstance(payload, dict) and payload.get("id") == msg_id:
                    return payload

        await send("Network.enable")

        get_id = await send("Network.getCookies", {"urls": urls})
        resp = await recv_until(get_id)

        if "error" in resp:
            raise RuntimeError(f"CDP error: {resp['error']}")

        result = resp.get("result", {})
        cookies = result.get("cookies", [])
        out: List[Cookie] = []
        for c in cookies:
            if not isinstance(c, dict):
                continue
            name = c.get("name")
            value = c.get("value")
            if isinstance(name, str) and isinstance(value, str):
                out.append(Cookie(name=name, value=value))
        return out


def _format_cookie_header(cookies: List[Cookie], names: List[str]) -> str:
    values_by_name = {c.name: c.value for c in cookies}
    parts = []
    for name in names:
        value = values_by_name.get(name)
        if value:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def _ssh_run(host: str, remote_cmd: str, *, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", host, remote_cmd],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


def _update_autobrr_cookie_over_ssh(host: str, cookie_header: str) -> None:
    remote_py = r"""
import sys
import sqlite3

cookie = sys.stdin.read().strip()
if not cookie:
    raise SystemExit("cookie stdin is empty")

db_path = "/mnt/ByrroServer/docker-data/autobrr/autobrr.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute(
    "UPDATE feed SET cookie = ?, updated_at = CURRENT_TIMESTAMP WHERE name IN ('YuScene', 'YuScene Farm')",
    (cookie,),
)
conn.commit()
print(f"updated_rows={cur.rowcount} cookie_len={len(cookie)}")
"""
    proc = _ssh_run(host, f"sudo -n python3 -c {shlex.quote(remote_py)}", stdin=cookie_header)
    if proc.returncode != 0:
        raise RuntimeError(f"Remote update failed: {proc.stdout}{proc.stderr}")
    print(proc.stdout.strip())


def _restart_autobrr_over_ssh(host: str) -> None:
    proc = _ssh_run(host, "docker restart autobrr >/dev/null && echo restarted=1")
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to restart autobrr: {proc.stdout}{proc.stderr}")
    print(proc.stdout.strip())


def _test_download_over_ssh(host: str, download_url: str) -> None:
    remote_sh = r"""
set -euo pipefail
DB=/mnt/ByrroServer/docker-data/autobrr/autobrr.db
cookie_len=$(sqlite3 "$DB" "select length(coalesce(cookie,'')) from feed where name='YuScene' limit 1;")
echo "db_cookie_len=${cookie_len}"

cookie=$(sqlite3 "$DB" "select cookie from feed where name='YuScene' limit 1;")
code=$(curl -s -o /dev/null -w "%{http_code}" -H "Cookie: ${cookie}" "__URL__")
ctype=$(curl -s -I -H "Cookie: ${cookie}" "__URL__" | tr -d "\r" | grep -i '^content-type:' | head -n 1 | cut -d' ' -f2-)
echo "http_code=${code} content_type=${ctype:-unknown}"
"""
    remote_sh = remote_sh.replace("__URL__", download_url)
    proc = _ssh_run(host, f"bash -lc {shlex.quote(remote_sh)}")
    if proc.returncode != 0:
        raise RuntimeError(f"Remote test failed: {proc.stdout}{proc.stderr}")
    print(proc.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync YuScene login cookies from local Chrome to remote autobrr feed.")
    parser.add_argument("--browser-url", default="http://127.0.0.1:9222")
    parser.add_argument("--host", default="byrro@192.168.1.11")
    parser.add_argument("--url-match", default="yu-scene.net")
    parser.add_argument("--restart-autobrr", action="store_true", default=True)
    parser.add_argument("--no-restart-autobrr", action="store_false", dest="restart_autobrr")
    parser.add_argument("--test-download-url", default="https://yu-scene.net/torrents/download/85958")
    args = parser.parse_args()

    targets = _get_cdp_targets(args.browser_url)
    target = next((t for t in targets if isinstance(t, dict) and args.url_match in str(t.get("url", ""))), None)
    if not target:
        print(f"ERROR: no open Chrome tab matches {args.url_match!r}. Open it in the MCP Chrome window and retry.")
        return 2

    ws_url = target.get("webSocketDebuggerUrl")
    if not isinstance(ws_url, str) or not ws_url:
        print("ERROR: matching tab has no webSocketDebuggerUrl")
        return 2

    cookies = asyncio.run(_cdp_get_cookies(ws_url, [f"https://{args.url_match}/", f"https://{args.url_match}"]))
    cookie_header = _format_cookie_header(cookies, ["XSRF-TOKEN", "laravel_session"])

    if "laravel_session=" not in cookie_header:
        print("ERROR: laravel_session cookie not found; you may not be logged in.")
        return 2

    print("captured_cookie=1")
    _update_autobrr_cookie_over_ssh(args.host, cookie_header)

    if args.restart_autobrr:
        _restart_autobrr_over_ssh(args.host)

    if args.test_download_url:
        _test_download_over_ssh(args.host, args.test_download_url)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
