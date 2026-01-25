#!/usr/bin/env bash
set -euo pipefail

JSON=$(curl -s http://127.0.0.1:9222/json/version || true)

if [ -z "$JSON" ]; then
  echo "ERROR: No response from http://127.0.0.1:9222/json/version"
  exit 1
fi

echo "$JSON"

if echo "$JSON" | grep -q '"webSocketDebuggerUrl"'; then
  echo "OK: webSocketDebuggerUrl detected"
  exit 0
fi

echo "ERROR: webSocketDebuggerUrl not found"
exit 1
