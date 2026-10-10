#!/usr/bin/env bash
set -euo pipefail

public_url="${1:-http://127.0.0.1:18084}"
api_url="${2:-http://127.0.0.1:18083}"
base="/srv/douyin-order-python"
env_file="$base/shared/env/api.env"

if [[ -f "$env_file" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$env_file"
  set +a
fi

test -L "$base/current"
test -f "$base/current/frontend/dist/index.html"
test -x "$base/current/.venv/bin/gunicorn"
test -d "$base/shared/env"
test -d "$base/shared/logs"

nginx -t

curl --fail --silent --show-error --max-time 5 "$public_url/"
curl --fail --silent --show-error --max-time 5 \
  "$api_url/internal/health/live"
curl --fail --silent --show-error --max-time 5 \
  "$api_url/internal/migration/status"

if [[ "${LAIKE_WEBHOOK_ENABLED:-false}" == "false" ]]; then
  webhook_status="$(
    curl --silent --show-error --max-time 5 \
      --output /dev/null --write-out '%{http_code}' \
      -X POST -H 'content-type: application/json' --data '{}' \
      "$api_url/internal/laike/webhook"
  )"
  test "$webhook_status" = "503"
else
  printf 'laike webhook safety probe skipped: LAIKE_WEBHOOK_ENABLED=true\n'
fi

for service in \
  douyin-order-api.service \
  douyin-order-worker.service \
  douyin-order-scheduler.service
do
  systemctl is-active --quiet "$service"
done

printf 'deployment checks passed\n'

