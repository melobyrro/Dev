#!/bin/sh
set -eu

IMAGE=rednoah/filebot
CONFIG=/mnt/ByrroServer/docker-data/filebot
MEDIA=/mnt/ByrroServer/ByrroMedia
INBOX="$MEDIA/Other_Inbox"
INBOX_CONTAINER=/media/Other_Inbox
OUTPUT=/media/Other
UNMATCHED_DIR="$MEDIA/Other/_Unmatched"
LOG_FILE=/home/byrro/logs/filebot_other.log
FALLBACK_SCRIPT=/home/byrro/scripts/filebot_other_fallback.sh
FALLBACK_LOG=/home/byrro/logs/filebot_other_fallback.log
STATUS_SCRIPT=/home/byrro/scripts/filebot_other_status.py
AMC_LOG_CONTAINER=/data/logs/amc.log

LICENSE_PRIMARY="$CONFIG/license.psm"
LICENSE_ALT="$CONFIG/.filebot/license.psm"

log() {
  printf "%s %s\n" "$(date "+%Y-%m-%d %H:%M:%S")" "$*" >> "$LOG_FILE"
}

run_fallback() {
  if [ ! -x "$FALLBACK_SCRIPT" ]; then
    log "fallback script missing: $FALLBACK_SCRIPT"
    return
  fi

  log "fallback: running hardlink helper"
  "$FALLBACK_SCRIPT" "$INBOX" "$MEDIA/Other" >> "$FALLBACK_LOG" 2>&1 || {
    log "fallback script failed"
  }
}

update_status() {
  if [ -x "$STATUS_SCRIPT" ]; then
    "$STATUS_SCRIPT" >> "$LOG_FILE" 2>&1 || true
  fi
}

mkdir -p "$INBOX" "$MEDIA/Other" "$UNMATCHED_DIR" "$CONFIG/logs"

if [ ! -f "$LICENSE_PRIMARY" ] && [ ! -f "$LICENSE_ALT" ]; then
  log "filebot license missing"
  update_status
  exit 1
fi

log "starting filebot other"
filebot_exit=0
docker run --rm   -e PUID="$(id -u)"   -e PGID="$(id -g)"   -e UMASK=002   -v "$CONFIG:/data"   -v "$MEDIA:/media"   "$IMAGE"   -script fn:amc "$INBOX_CONTAINER"   --output "$OUTPUT"   --action move   --conflict auto   --log-file "$AMC_LOG_CONTAINER"   --def "excludeList=/data/amc.txt" "clean=n"   "movieFormat={n} ({y})/{n} ({y})"   "seriesFormat={n}/Season {s}/{n} - {s00e00} - {t}"   || filebot_exit=$?

log "filebot exit: $filebot_exit"

# 0 = success, 100 = no files processed (usually because they are excluded)
if [ "$filebot_exit" -eq 0 ] || [ "$filebot_exit" -eq 100 ]; then
  if [ -n "$(find "$INBOX" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    log "moving remaining files to unmatched"
    for item in "$INBOX"/*; do
      [ -e "$item" ] || continue
      base=$(basename "$item")
      dest="$UNMATCHED_DIR/$base"
      if [ -e "$dest" ]; then
        log "unmatched skip exists: $dest"
        # If it exists, we just remove from inbox to avoid loop
        rm -rf "$item"
        continue
      fi
      mv "$item" "$dest"
      log "unmatched moved: $item -> $dest"
    done
  else
    log "no unmatched items"
  fi
else
  log "filebot failed with unexpected exit code; leaving inbox for retry"
fi

if [ "$filebot_exit" -ne 0 ] && [ "$filebot_exit" -ne 100 ]; then
  run_fallback
else
  log "fallback: not needed"
fi

update_status
exit "$filebot_exit"
