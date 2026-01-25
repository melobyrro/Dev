#!/bin/sh
set -eu

TRIGGER_FILE="/mnt/ByrroServer/docker-data/homeassistant/config/hardlink_other_trigger"
LOG_FILE="/home/byrro/logs/hardlink_other_trigger.log"

if [ ! -f "$TRIGGER_FILE" ]; then
  exit 0
fi

rm -f "$TRIGGER_FILE"

printf "%s %s\n" "$(date "+%Y-%m-%d %H:%M:%S")" "triggered hardlink_other_sweep.sh" >> "$LOG_FILE"
/home/byrro/scripts/hardlink_other_sweep.sh >> /home/byrro/logs/hardlink_other_sweep.log 2>&1 || true
