#!/usr/bin/env bash
set -euo pipefail

target="${1:?usage: rollback.sh /srv/douyin-order-python/releases/<timestamp>}"
base="/srv/douyin-order-python"
current="$(readlink "$base/current" || true)"

case "$target" in
  "$base"/releases/*) ;;
  *) echo "rollback target must be under $base/releases/" >&2; exit 2 ;;
esac

echo "current=$current"
test -d "$target"
nginx -t
ln -sfn "$target" "$base/current"
systemctl restart douyin-order-api.service
systemctl restart douyin-order-worker.service
systemctl restart douyin-order-scheduler.service
systemctl reload nginx
