#!/usr/bin/env bash
# One-shot setup for a fresh Ubuntu 24.04 Vultr Cloud Compute VM. Run as root.
#   VULTR_INFERENCE_KEY=... bash setup-vultr.sh
set -euo pipefail
REPO=${REPO:-https://github.com/vidigoat/stunt-double}
IP=$(curl -fsS https://api.ipify.org || hostname -I | awk '{print $1}')
SITE_HOST=${SITE_HOST:-${IP//./-}.sslip.io}

export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get install -y ca-certificates curl gnupg git ufw

# Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
# gVisor
curl -fsSL https://gvisor.dev/archive.key | gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" > /etc/apt/sources.list.d/gvisor.list
apt-get update -y && apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin runsc
runsc install && systemctl restart docker
docker run --rm --runtime=runsc hello-world >/dev/null && echo "gVisor OK"

# Firewall: web only (+ SSH)
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

# App
mkdir -p /opt/stunt-double/data/runs
[ -d /opt/stunt-double/src ] || git clone "$REPO" /opt/stunt-double/src
cd /opt/stunt-double/src && git pull --ff-only
docker build -t stunt-double-sandbox:latest -f sandbox/Dockerfile .
docker build -t stunt-double-browser:latest -f sandbox/Dockerfile.browser . || echo "browser sandbox build failed (browser doubles disabled)"
cd infra
[ -f .env ] || cp .env.example .env
if [ -n "${VULTR_INFERENCE_KEY:-}" ]; then sed -i "s|^VULTR_INFERENCE_KEY=.*|VULTR_INFERENCE_KEY=${VULTR_INFERENCE_KEY}|" .env; fi
grep -q '^SITE_HOST=' .env || echo "SITE_HOST=$SITE_HOST" >> .env   # compose reads it for ${SITE_HOST}
for v in SD_S3_ENDPOINT SD_S3_ACCESS_KEY SD_S3_SECRET_KEY; do   # optional evidence archive on Vultr Object Storage
  if [ -n "${!v:-}" ] && ! grep -q "^$v=" .env; then echo "$v=${!v}" >> .env; fi
done
chmod 600 .env
echo "$SITE_HOST" > /opt/stunt-double/site_host
SITE_HOST=$SITE_HOST docker compose up -d --build

# Continuous deploy: every 2 minutes, redeploy if GitHub main moved.
cat > /etc/systemd/system/stunt-double-update.service <<UNIT
[Unit]
Description=Stunt Double pull-deploy
[Service]
Type=oneshot
ExecStart=/opt/stunt-double/src/infra/update.sh
UNIT
cat > /etc/systemd/system/stunt-double-update.timer <<UNIT
[Unit]
Description=Stunt Double pull-deploy timer
[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload && systemctl enable --now stunt-double-update.timer
echo "Stunt Double is live at https://$SITE_HOST"
