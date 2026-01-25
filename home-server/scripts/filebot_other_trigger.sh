#!/bin/sh
set -eu

TRIGGER_FILE="/mnt/ByrroServer/docker-data/homeassistant/config/filebot_other_trigger"
LOG_FILE="/home/byrro/logs/filebot_other_trigger.log"

if [ ! -f "$TRIGGER_FILE" ]; then
  exit 0
fi

rm -f "$TRIGGER_FILE"

printf "%s %s\n" "$(date "+%Y-%m-%d %H:%M:%S")" "triggered filebot_other.sh" >> "$LOG_FILE"
/home/byrro/scripts/filebot_other.sh >> /home/byrro/logs/filebot_other.log 2>&1 || true
