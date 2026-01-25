#!/bin/bash
set -euo pipefail

DOWNLOADS_BASE="/mnt/ByrroServer/ByrroMedia/downloads"
TARGET_ROOT="/mnt/ByrroServer/ByrroMedia/Other_Inbox"
LOG_FILE="/home/byrro/logs/hardlink_other_sweep.log"
STATUS_SCRIPT="/home/byrro/scripts/hardlink_other_status.py"
STATE_FILE="/home/byrro/logs/hardlink_other_seen.txt"

LOCK_DIR="/tmp/hardlink_other_sweep.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  exit 0
fi
cleanup() {
  rmdir "$LOCK_DIR"
}
trap cleanup EXIT

log() {
  printf "%s %s\n" "$(TZ=America/New_York date "+%Y-%m-%d %H:%M:%S")" "$*" >> "$LOG_FILE"
}

umask 002
mkdir -p "$TARGET_ROOT"

declare -A seen
if [ -f "$STATE_FILE" ]; then
  while IFS=$'\t' read -r path sig; do
    [ -n "${path:-}" ] && seen["$path"]="$sig"
  done < "$STATE_FILE"
fi

log "sweep start"

for category in prowlarr sports; do
  dir="$DOWNLOADS_BASE/$category"
  [ -d "$dir" ] || continue
  find "$dir" -mindepth 1 -maxdepth 1 -print | while IFS= read -r path; do
    [ -e "$path" ] || continue
    sig="$(stat -c '%s|%Y' "$path" 2>/dev/null || true)"
    if [ -n "${seen[$path]-}" ] && [ "${seen[$path]}" = "$sig" ]; then
      log "skip: unchanged $path"
      continue
    fi

    name="$(basename "$path")"
    if [ -d "$path" ]; then
      dest_root="$TARGET_ROOT/$name"
      find "$path" -type f -print | while IFS= read -r src_file; do
        rel_path="${src_file#"$path"/}"
        dest_path="$dest_root/$rel_path"
        dest_dir="$(dirname "$dest_path")"
        mkdir -p "$dest_dir"
        if [ ! -e "$dest_path" ]; then
          ln "$src_file" "$dest_path"
        else
          log "skip: exists $dest_path"
        fi
      done
      log "linked folder: $path -> $dest_root"
    else
      dest_path="$TARGET_ROOT/$name"
      if [ ! -e "$dest_path" ]; then
        ln "$path" "$dest_path"
        log "linked file: $path -> $dest_path"
      else
        log "skip: exists $dest_path"
      fi
    fi

    if [ -n "$sig" ]; then
      seen["$path"]="$sig"
    fi
  done
done

tmp_state="$(mktemp)"
for key in "${!seen[@]}"; do
  printf "%s\t%s\n" "$key" "${seen[$key]}" >> "$tmp_state"
done
mv "$tmp_state" "$STATE_FILE"

plex_refresh() {
  python3 - <<'PY'
import os
import re
import sys
import urllib.request

prefs = "/srv/docker-data/plex/Library/Application Support/Plex Media Server/Preferences.xml"
if not os.path.exists(prefs):
    print("plex refresh: preferences missing")
    sys.exit(0)

text = open(prefs, "r", encoding="utf-8", errors="ignore").read()
match = re.search(r'PlexOnlineToken="([^"]+)"', text)
if not match:
    print("plex refresh: token missing")
    sys.exit(0)

token = match.group(1)

def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            resp.read()
        return True
    except Exception:
        return False

sections_url = f"http://127.0.0.1:32400/library/sections?X-Plex-Token={token}"
try:
    with urllib.request.urlopen(sections_url, timeout=5) as resp:
        data = resp.read().decode("utf-8", "ignore")
except Exception:
    print("plex refresh: sections fetch failed")
    sys.exit(0)

match = re.search(r'<Directory[^>]*key="(\d+)"[^>]*title="Other Videos"', data)
if not match:
    match = re.search(r'<Directory[^>]*key="(\d+)"[^>]*title="Other"', data)
if match:
    key = match.group(1)
    if fetch(f"http://127.0.0.1:32400/library/sections/{key}/refresh?X-Plex-Token={token}"):
        print("plex refresh: triggered for Other")
    else:
        print("plex refresh: request failed")
else:
    if fetch(f"http://127.0.0.1:32400/library/sections/all/refresh?X-Plex-Token={token}"):
        print("plex refresh: triggered for all")
    else:
        print("plex refresh: request failed")
PY
}

plex_refresh >> "$LOG_FILE" 2>&1 || true

if [ -x "$STATUS_SCRIPT" ]; then
  "$STATUS_SCRIPT" >> "$LOG_FILE" 2>&1 || true
fi
