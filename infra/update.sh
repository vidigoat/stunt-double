#!/usr/bin/env bash
# Pull-based continuous deploy: redeploy when main moves. Run by a systemd timer.
set -euo pipefail
cd /opt/stunt-double/src
git fetch -q origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  git reset -q --hard origin/main
  docker build -q -t stunt-double-sandbox:latest -f sandbox/Dockerfile . >/dev/null
  cd infra && SITE_HOST=$(cat /opt/stunt-double/site_host) docker compose up -d --build
  echo "deployed $(git rev-parse --short HEAD)"
fi
