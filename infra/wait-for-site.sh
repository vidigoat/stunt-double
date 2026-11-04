#!/usr/bin/env bash
# Wait until the deployed site is fully healthy. Usage: bash infra/wait-for-site.sh https://1-2-3-4.sslip.io [timeout_s]
set -euo pipefail
URL="${1:?site url}"; LIMIT="${2:-900}"; t0=$(date +%s)
while :; do
  body=$(curl -fsS --max-time 10 "$URL/api/health" 2>/dev/null || true)
  if [ -n "$body" ]; then
    echo "$(date +%T) $body"
    if echo "$body" | python3 -c 'import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get("sandbox_ready") and d.get("inference_configured") else 1)'; then
      echo "HEALTHY: $URL"; exit 0
    fi
  else
    echo "$(date +%T) not up yet (cloud-init still installing Docker, gVisor, Caddy...)"
  fi
  [ $(( $(date +%s) - t0 )) -lt "$LIMIT" ] || { echo "timed out after ${LIMIT}s"; exit 1; }
  sleep 15
done
