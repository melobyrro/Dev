#!/bin/sh
set -eu

QBIT_HOST="${QBIT_HOST:-http://127.0.0.1:8181}"
QBIT_USER="${QBIT_USER:-}"
QBIT_PASS="${QBIT_PASS:-}"
INTERVAL="${INTERVAL:-300}"
CATEGORIES="${CATEGORIES:-tv movies}"

if [ -z "$QBIT_USER" ] || [ -z "$QBIT_PASS" ]; then
  echo "qbit-safety-cleaner: QBIT_USER/QBIT_PASS not set" >&2
  exit 1
fi

DANGER_RE='\.(exe|scr|bat|cmd|com|pif|msi|lnk|jar|vbs|js|ps1)$'

login() {
  cookie_file="$1"
  curl -fsS -c "$cookie_file" \
    -d "username=$QBIT_USER&password=$QBIT_PASS" \
    "$QBIT_HOST/api/v2/auth/login" >/dev/null
}

has_danger_on_disk() {
  dir="$1"
  find "$dir" -type f \( \
    -iname '*.exe' -o -iname '*.scr' -o -iname '*.bat' -o -iname '*.cmd' -o -iname '*.com' -o -iname '*.pif' -o -iname '*.msi' -o -iname '*.lnk' -o -iname '*.jar' -o -iname '*.vbs' -o -iname '*.js' -o -iname '*.ps1' \
  \) -print -quit | grep -q .
}

safe_rm_rf() {
  target="$1"
  case "$target" in
    /downloads/*/*) rm -rf "$target" ;;
    *) echo "qbit-safety-cleaner: refusing to delete unsafe path: $target" >&2 ;;
  esac
}

is_danger_path() {
  path="$1"
  echo "$path" | grep -Eiq "$DANGER_RE"
}

while true; do
  cookie_file="$(mktemp)"

  if ! login "$cookie_file"; then
    echo "qbit-safety-cleaner: login failed; retrying in ${INTERVAL}s" >&2
    rm -f "$cookie_file"
    sleep "$INTERVAL"
    continue
  fi

  torrents_json="$(curl -fsS -b "$cookie_file" "$QBIT_HOST/api/v2/torrents/info?filter=all" || echo '[]')"

  for category in $CATEGORIES; do
    echo "$torrents_json" \
      | jq -c --arg cat "$category" '.[] | select((.progress // 0) >= 1 and (.category==$cat or ((.save_path // "") | test("/downloads/" + $cat + "(/|$)"))))' \
      | while read -r tor; do
          hash="$(echo "$tor" | jq -r '.hash')"
          name="$(echo "$tor" | jq -r '(.name // .hash)')"
          save_path="$(echo "$tor" | jq -r '(.save_path // "")')"
          content_path="$(echo "$tor" | jq -r '(.content_path // "")')"

          [ -n "$hash" ] || continue

          danger=false

          # 1) If the torrent itself contains a dangerous file extension (e.g. single-file .scr)
          files_json="$(curl -fsS -b "$cookie_file" "$QBIT_HOST/api/v2/torrents/files?hash=$hash" || echo '[]')"
          if echo "$files_json" | jq -e 'any(.[]; (.name // "") | test("\\.(exe|scr|bat|cmd|com|pif|msi|lnk|jar|vbs|js|ps1)$"; "i"))' >/dev/null 2>&1; then
            danger=true
          fi

          # 2) If unpackerr extracted something dangerous into a per-torrent folder.
          scan_dir="${save_path%/}/$name"
          if [ "$danger" = false ] && [ -d "$scan_dir" ] && has_danger_on_disk "$scan_dir"; then
            danger=true
          fi

          # 3) If qBittorrent's content_path itself is dangerous.
          if [ "$danger" = false ] && [ -n "$content_path" ] && [ "$content_path" != "null" ] && is_danger_path "$content_path"; then
            danger=true
          fi

          if [ "$danger" = true ]; then
            echo "qbit-safety-cleaner: deleting suspicious torrent (dangerous file detected): $name"

            curl -fsS -b "$cookie_file" \
              --data-urlencode "hashes=$hash" \
              --data "deleteFiles=true" \
              "$QBIT_HOST/api/v2/torrents/delete" >/dev/null || true

            if [ -d "$scan_dir" ]; then
              safe_rm_rf "$scan_dir"
            fi

            if [ -f "$content_path" ] && is_danger_path "$content_path"; then
              rm -f "$content_path" || true
            fi
          fi
        done
  done

  rm -f "$cookie_file"
  sleep "$INTERVAL"
done
