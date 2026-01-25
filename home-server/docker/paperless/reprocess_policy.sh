#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

docker exec paperless bash -lc "cd /usr/src/paperless/src && python manage.py shell -c 'exec(open(\"/usr/src/paperless/reprocess_policy_code.py\").read())'"
