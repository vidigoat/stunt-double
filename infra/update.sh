#!/usr/bin/env bash
# Pull-based continuous deploy: redeploy when main moves. Run by a systemd timer.
set -euo pipefail
cd /opt/stunt-double/src
git fetch -q origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  OLD=$(git rev-parse HEAD)
  git reset -q --hard origin/main
  docker build -q -t stunt-double-sandbox:latest -f sandbox/Dockerfile . >/dev/null
  cd infra && SITE_HOST=$(cat /opt/stunt-double/site_host) docker compose up -d --build
  # The Caddyfile is a single-file bind mount; git replaces the file, so only a restart picks up a change.
  if git -C /opt/stunt-double/src diff --name-only "$OLD" HEAD | grep -q '^infra/Caddyfile$'; then
    SITE_HOST=$(cat /opt/stunt-double/site_host) docker compose restart caddy
  fi
  echo "deployed $(git rev-parse --short HEAD)"
fi
