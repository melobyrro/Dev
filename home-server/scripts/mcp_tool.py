#!/usr/bin/env python3
"""Lightweight MCP client for local testing."""
from __future__ import annotations
import argparse
import json
import os
import select
import subprocess
import sys
import time
from typing import Any, Dict, Optional

Message = Dict[str, Any]
PROTOCOL_VERSION = "2024-11-05"


class _JsonLineBuffer:
    def __init__(self) -> None:
        self._buffer = b""

    def read_message(self, stream, timeout: float) -> Message:
        start = time.time()
        while True:
            nl = self._buffer.find(b"\n")
            if nl != -1:
                line = self._buffer[:nl].strip()
                self._buffer = self._buffer[nl + 1 :]
                if not line:
                    continue
                return json.loads(line.decode())

            remaining = timeout - (time.time() - start)
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for MCP response")
            ready, _, _ = select.select([stream], [], [], remaining)
            if not ready:
                continue
            chunk = stream.read(4096)
            if not chunk:
                raise EOFError("MCP server closed the stream")
            self._buffer += chunk


def _send_message(proc: subprocess.Popen, payload: Message) -> None:
    data = (json.dumps(payload) + "\n").encode()
    proc.stdin.write(data)
    proc.stdin.flush()


def call_tool(command, args, env, tool_name: Optional[str], tool_args: Dict[str, Any], list_only: bool, timeout: float) -> None:
    proc = subprocess.Popen(
        [command, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=False,
        bufsize=0,
        env=env,
    )
    next_id = 1
    buf = _JsonLineBuffer()

    def request(payload: Dict[str, Any]) -> Message:
        nonlocal next_id
        payload.setdefault("jsonrpc", "2.0")
        if "id" not in payload:
            payload["id"] = next_id
            next_id += 1
        _send_message(proc, payload)
        while True:
            msg = buf.read_message(proc.stdout, timeout)
            if msg.get("id") == payload["id"]:
                return msg
            else:
                sys.stderr.write(f"[mcp_tool] notification: {json.dumps(msg)}\n")
                sys.stderr.flush()

    try:
        init = request({
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "clientInfo": {"name": "mcp_tool", "version": "1.0"},
                "capabilities": {}
            }
        })
        print("initialize =>", json.dumps(init))
        _send_message(proc, {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        })
        listed = request({"method": "tools/list", "params": {}})
        print("tools/list =>", json.dumps(listed, indent=2))
        if list_only:
            return
        if tool_name:
            call = request({
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": tool_args
                }
            })
            print("tools/call =>", json.dumps(call, indent=2))
    finally:
        try:
            _send_message(proc, {"jsonrpc": "2.0", "id": next_id, "method": "shutdown", "params": {}})
        except Exception:
            pass
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a simple MCP tool call against a server")
    parser.add_argument("--command", required=True)
    parser.add_argument("--arg", action="append", default=[])
    parser.add_argument("--env", action="append", default=[], help="ENV=VALUE")
    parser.add_argument("--tool")
    parser.add_argument("--tool-args", default="{}")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--list", action="store_true", help="Only list tools")
    args = parser.parse_args()

    env = os.environ.copy()
    for entry in args.env:
        key, _, value = entry.partition("=")
        env[key] = value
    tool_args = json.loads(args.tool_args)

    call_tool(args.command, args.arg, env, args.tool, tool_args, args.list, args.timeout)


if __name__ == "__main__":
    main()
