#!/usr/bin/env bash
# Serve the production build locally exactly like the Docker image does (static + public copied in, so no 400s on chunks).
# Usage: bash web/scripts/serve-standalone.sh [port]   (after `npm run build`; API_URL is baked at build time)
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf .next/standalone/.next/static .next/standalone/public
cp -r .next/static .next/standalone/.next/ && cp -r public .next/standalone/
PORT="${1:-3000}" HOSTNAME=0.0.0.0 exec node .next/standalone/server.js
