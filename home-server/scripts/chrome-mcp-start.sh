#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_DIR="$ROOT_DIR/.mcp/chrome-profile"

mkdir -p "$PROFILE_DIR"

if pgrep -x "Google Chrome" >/dev/null; then
  if ps -Ao command | grep -F -- "--remote-debugging-port=9222" | grep -F -- "--user-data-dir=$PROFILE_DIR" >/dev/null; then
    echo "Chrome is already running with remote debugging enabled and the repo profile."
    exit 0
  fi
  echo "ERROR: Google Chrome is already running without the expected debug flags or profile. Quit it, then re-run this script."
  exit 1
fi

open -a "Google Chrome" --args \
  --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE_DIR"

echo "Chrome launch requested with remote debugging on port 9222."
