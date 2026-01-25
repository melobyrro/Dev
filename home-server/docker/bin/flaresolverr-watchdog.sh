#!/usr/bin/env bash
set -euo pipefail

DOCKER=/usr/bin/docker

# Ensure gluetun exists and is running
if ! $DOCKER ps --format "{{.Names}}" | grep -q "^gluetun$"; then
  echo "gluetun not running; skip restart check" >&2
  exit 0
fi

health=$($DOCKER inspect gluetun --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}")
if [ "$health" != "healthy" ]; then
  echo "gluetun health is $health; waiting" >&2
  exit 0
fi

state=$($DOCKER inspect flaresolverr --format "{{.State.Status}}" 2>/dev/null || echo "missing")
if [ "$state" != "running" ]; then
  echo "starting flaresolverr (state=$state)" >&2
  if ! $DOCKER start flaresolverr >/dev/null; then
    echo "failed to start flaresolverr" >&2
    exit 1
  fi
fi
