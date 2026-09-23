#!/usr/bin/env bash
# Copy the images and stack files to the server and start (or update) Draftly.
#
#   deploy/ship.sh user@server            # images + config, then up
#   deploy/ship.sh user@server --config   # config only (.env / Caddyfile / compose changed)
#
# The server needs Docker with the compose plugin and ports 80/443 open.
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:?usage: ship.sh user@server [--config]}"
MODE="${2:-}"
REMOTE_DIR="${REMOTE_DIR:-draftly}"
IMAGES="$DEPLOY_DIR/dist/draftly-images.tar.gz"

[ -f "$DEPLOY_DIR/.env" ] || { echo "Missing deploy/.env" >&2; exit 1; }
ssh "$TARGET" "mkdir -p '$REMOTE_DIR' && docker compose version >/dev/null" \
  || { echo "Docker with the compose plugin is not available for $TARGET." >&2; exit 1; }

echo "==> copying stack files"
scp -q "$DEPLOY_DIR/docker-compose.yml" "$DEPLOY_DIR/Caddyfile" "$TARGET:$REMOTE_DIR/"
scp -q "$DEPLOY_DIR/.env" "$TARGET:$REMOTE_DIR/.env"
ssh "$TARGET" "chmod 600 '$REMOTE_DIR/.env'"

if [ "$MODE" != "--config" ]; then
  [ -f "$IMAGES" ] || { echo "Missing $IMAGES (run deploy/build.sh first)." >&2; exit 1; }
  echo "==> copying images ($(du -h "$IMAGES" | cut -f1))"
  scp "$IMAGES" "$TARGET:$REMOTE_DIR/"
  echo "==> loading images"
  ssh "$TARGET" "gunzip -c '$REMOTE_DIR/draftly-images.tar.gz' | docker load && rm '$REMOTE_DIR/draftly-images.tar.gz'"
fi

echo "==> starting stack"
ssh "$TARGET" "cd '$REMOTE_DIR' && docker compose --env-file .env up -d --remove-orphans && docker image prune -f >/dev/null && docker compose ps"
echo "Done. Check: curl -s https://$(sed -n 's/^DOMAIN=//p' "$DEPLOY_DIR/.env" | tail -n 1)/health/ready"
