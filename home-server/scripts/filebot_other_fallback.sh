#!/usr/bin/env bash
set -eu

INBOX="${1:-/mnt/ByrroServer/ByrroMedia/Other_Inbox}"
OTHER="${2:-/mnt/ByrroServer/ByrroMedia/Other}"
LOG=/home/byrro/logs/filebot_other_fallback.log

log() {
  printf "%s %s\n" "$(date "+%Y-%m-%d %H:%M:%S")" "$*" >> "$LOG"
}

mkdir -p "$(dirname "$LOG")" "$INBOX" "$OTHER"

if [ -z "$(find "$INBOX" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
  log "fallback: inbox empty"
  exit 0
fi

link_directory() {
  src="$1"
  dest="$2"
  src_prefix="${src%/}/"
  find "$src" -mindepth 1 -type d -print0 | while IFS= read -r -d '' dir; do
    rel="${dir#$src_prefix}"
    mkdir -p "$dest/$rel"
  done
  find "$src" -type f -print0 | while IFS= read -r -d '' file; do
    rel="${file#$src_prefix}"
    dest_file="$dest/$rel"
    mkdir -p "$(dirname "$dest_file")"
    if [ -e "$dest_file" ]; then
      log "fallback skip exists: $file -> $dest_file"
      continue
    fi
    ln "$file" "$dest_file"
    log "fallback linked file: $file -> $dest_file"
  done
}

log "fallback start: INBOX=$INBOX OTHER=$OTHER"

for entry in "$INBOX"/*; do
  [ -e "$entry" ] || continue
  base=$(basename "$entry")
  dest="$OTHER/$base"
  if [ -e "$dest" ]; then
    log "fallback skip exists: $entry -> $dest"
    continue
  fi
  if [ -d "$entry" ]; then
    mkdir -p "$dest"
    link_directory "$entry" "$dest"
  else
    ln "$entry" "$dest"
    log "fallback linked file: $entry -> $dest"
  fi
done

log "fallback complete"
