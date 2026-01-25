#!/bin/bash
set -euo pipefail

COMPOSE_DIR="/home/byrro/docker"
FORWARD_FILE="/mnt/ByrroServer/docker-data/gluetun-tmp/forwarded_port"

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

forwarded_port=$(tr -d '\r\n ' < "$FORWARD_FILE" 2>/dev/null || true)
if ! [[ "$forwarded_port" =~ ^[0-9]+$ ]]; then
  echo "$(timestamp): WARN forwarded_port missing or invalid"
  exit 0
fi

current_port=$(
  docker exec qbittorrent awk -F= '/^Session.*Port=/{print $2; exit}' /config/qBittorrent/qBittorrent.conf 2>/dev/null || true
)

qb_sync_running=$(docker inspect -f '{{.State.Running}}' qb-port-sync 2>/dev/null || echo "false")
actions=()

if [ "$qb_sync_running" != "true" ]; then
  (cd "$COMPOSE_DIR" && docker compose up -d qb-port-sync >/dev/null 2>&1)
  actions+=("started qb-port-sync")
fi

if [ -n "$current_port" ] && [ "$current_port" != "$forwarded_port" ]; then
  (cd "$COMPOSE_DIR" && docker compose restart qb-port-sync >/dev/null 2>&1)
  actions+=("port mismatch -> restarted qb-port-sync")
fi

if [ ${#actions[@]} -eq 0 ]; then
  echo "$(timestamp): ok (qBittorrent port ${current_port:-unknown} matches forwarded ${forwarded_port})"
else
  joined=$(IFS='; '; echo "${actions[*]}")
  echo "$(timestamp): ${joined} (qBittorrent=${current_port:-unknown}, forwarded=${forwarded_port})"
fi
