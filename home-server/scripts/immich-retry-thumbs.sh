#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=${ENV_FILE:-/home/byrro/.config/immich/retry-thumbs.env}
SINCE_MINUTES=${SINCE_MINUTES:-60}
MAX_FAILS=${MAX_FAILS:-3}
TMP_IDS="$(mktemp)"
cleanup() { rm -f "$TMP_IDS"; }
trap cleanup EXIT

if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

if [ -z "${IMMICH_URL:-}" ] || [ -z "${IMMICH_TOKEN:-}" ] || [ "${IMMICH_TOKEN}" = "__SET_ME__" ]; then
  echo "[immich-retry-thumbs] IMMICH_URL/IMMICH_TOKEN not set; skipping." >&2
  exit 0
fi

# Use API key header for non-JWT tokens; user-token header for JWTs
if [[ "$IMMICH_TOKEN" == *.*.* ]]; then
  AUTH_HEADER_NAME="x-immich-user-token"
else
  AUTH_HEADER_NAME="x-api-key"
fi
NTFY_URL=${NTFY_URL:-}
NTFY_USER=${NTFY_USER:-}
NTFY_PASS=${NTFY_PASS:-}

if ! docker logs immich-server --since "${SINCE_MINUTES}m" 2>&1 \
  | grep -F "AssetGenerateThumbnails" \
  | grep -oE '[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}' \
  | sort -u > "$TMP_IDS"; then
  echo "[immich-retry-thumbs] Failed to parse docker logs." >&2
  exit 1
fi

COUNT=$(wc -l < "$TMP_IDS")
if [ "$COUNT" -eq 0 ]; then
  echo "[immich-retry-thumbs] No recent thumbnail failures in last ${SINCE_MINUTES}m." >&2
  exit 0
fi

echo "[immich-retry-thumbs] Found $COUNT asset(s) with thumbnail failures in last ${SINCE_MINUTES}m." >&2

while IFS= read -r ASSET_ID; do
  [ -n "$ASSET_ID" ] || continue
  docker exec immich-server sh -c "find /data/encoded-video -name '${ASSET_ID}*-MP.mp4' -delete" || true

  BODY_THUMB="{\"name\":\"regenerate-thumbnail\",\"assetIds\":[\"${ASSET_ID}\"]}"
  if curl -fsS -X POST "${IMMICH_URL}/api/assets/jobs" \
    -H "${AUTH_HEADER_NAME}: ${IMMICH_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$BODY_THUMB" >/dev/null; then
    echo "[immich-retry-thumbs] Requeued thumbnails for ${ASSET_ID}." >&2
  else
    echo "[immich-retry-thumbs] Failed to requeue thumbnails for ${ASSET_ID}." >&2
  fi
  sleep 0.3

  BODY_META="{\"name\":\"refresh-metadata\",\"assetIds\":[\"${ASSET_ID}\"]}"
  curl -fsS -X POST "${IMMICH_URL}/api/assets/jobs" \
    -H "${AUTH_HEADER_NAME}: ${IMMICH_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$BODY_META" \
    >/dev/null || true
  sleep 0.2

done < "$TMP_IDS"

if [ -n "$NTFY_URL" ] && [ "$COUNT" -ge "$MAX_FAILS" ]; then
  MSG="Immich thumbnail failures: ${COUNT} in last ${SINCE_MINUTES}m. Requeued automatically."
  if [ -n "$NTFY_USER" ] && [ -n "$NTFY_PASS" ]; then
    echo "$MSG" | curl -fsS -u "${NTFY_USER}:${NTFY_PASS}" -d @- "$NTFY_URL" || true
  else
    echo "$MSG" | curl -fsS -d @- "$NTFY_URL" || true
  fi
fi

exit 0
