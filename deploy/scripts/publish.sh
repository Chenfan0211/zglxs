#!/usr/bin/env bash
set -euo pipefail

release="${1:?usage: publish.sh /srv/douyin-order-python/releases/<timestamp>}"
base="/srv/douyin-order-python"

case "$release" in
  "$base"/releases/*) ;;
  *) echo "release must be under $base/releases/" >&2; exit 2 ;;
esac

test -d "$release"
test -d "$base/shared/env"
test -d "$base/shared/logs"

nginx -t
ln -sfn "$release" "$base/current"
systemctl daemon-reload
systemctl restart douyin-order-api.service
systemctl restart douyin-order-worker.service
systemctl restart douyin-order-scheduler.service
systemctl reload nginx
