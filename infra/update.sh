#!/usr/bin/env bash
# Pull-based continuous deploy: redeploy when main moves. Run by a systemd timer.
# The deployed commit is recorded only after a successful build, so a failed build (e.g. a transient font fetch)
# is retried on the next run instead of leaving production on the old version until the next push.
set -euo pipefail
STATE=/opt/stunt-double/deployed
cd /opt/stunt-double/src
git fetch -q origin main
TARGET=$(git rev-parse origin/main)
DEPLOYED=$(cat "$STATE" 2>/dev/null || git rev-parse HEAD)
if [ "$DEPLOYED" != "$TARGET" ] || [ ! -f "$STATE" ]; then
  git reset -q --hard "$TARGET"
  docker build -q -t stunt-double-sandbox:latest -f sandbox/Dockerfile . >/dev/null
  docker build -q -t stunt-double-browser:latest -f sandbox/Dockerfile.browser . >/dev/null || echo "browser sandbox build failed"
  cd infra && SITE_HOST=$(cat /opt/stunt-double/site_host) docker compose up -d --build
  # The Caddyfile is a single-file bind mount; git replaces the file, so only a restart picks up a change.
  if ! git -C /opt/stunt-double/src cat-file -e "$DEPLOYED^{commit}" 2>/dev/null \
     || git -C /opt/stunt-double/src diff --name-only "$DEPLOYED" "$TARGET" | grep -q '^infra/Caddyfile$'; then
    SITE_HOST=$(cat /opt/stunt-double/site_host) docker compose restart caddy
  fi
  echo "$TARGET" > "$STATE"
  echo "deployed $(git rev-parse --short "$TARGET")"
fi
