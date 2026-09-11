#!/usr/bin/env bash
set -euo pipefail

public_url="${1:-http://127.0.0.1:18084}"
api_url="${2:-http://127.0.0.1:18083}"
base="/srv/douyin-order-python"

test -L "$base/current"
test -d "$base/current/frontend"
test -x "$base/current/.venv/bin/gunicorn"
test -d "$base/shared/env"
test -d "$base/shared/logs"

nginx -t

curl --fail --silent --show-error --max-time 5 "$public_url/"
curl --fail --silent --show-error --max-time 5 \
  "$api_url/internal/health/live"
curl --fail --silent --show-error --max-time 5 \
  "$api_url/internal/migration/status"

for service in \
  douyin-order-api.service \
  douyin-order-worker.service \
  douyin-order-scheduler.service
do
  systemctl is-active --quiet "$service"
done

printf 'deployment checks passed\n'
