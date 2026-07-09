#!/usr/bin/env bash
# Deploy AegisMed on a fresh AMD Developer Cloud instance.
#
# Console steps first (one-time, in the AMD Developer Cloud UI):
#   1. Launch a GPU or CPU instance (Ubuntu recommended).
#   2. Open inbound port 8000 in the instance's security group / firewall.
#   3. SSH in, then run this script from a clone of the repo:
#        git clone https://github.com/wachirawut2023/AegisMed.git
#        cd AegisMed
#        cp .env.example .env   # add FIREWORKS_API_KEY or set LLM_BASE_URL
#        bash deploy/amd-cloud.sh
#   4. Copy the instance's public IP/hostname — that's your demo URL:
#        http://<instance-public-ip>:8000
#
# What this script does: installs Docker if missing, builds the AegisMed
# image, and runs it detached on port 8000 with --restart unless-stopped so
# it survives instance reboots. Safe to re-run (replaces the old container).
set -euo pipefail

IMAGE_NAME="aegismed"
CONTAINER_NAME="aegismed"
PORT="${PORT:-8000}"

if ! command -v docker &>/dev/null; then
  echo "==> Docker not found — installing..."
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
  echo "==> Docker installed. You may need to log out/in for group membership to apply."
fi

if [ ! -f .env ]; then
  echo "==> No .env found — copying .env.example (demo mode until you add a key)."
  cp .env.example .env
fi

echo "==> Building the image for linux/amd64..."
docker build --platform linux/amd64 -t "$IMAGE_NAME" .

echo "==> Stopping any previous container..."
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

echo "==> Starting AegisMed on port $PORT..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "${PORT}:8000" \
  --env-file .env \
  "$IMAGE_NAME"

echo "==> Waiting for the health check..."
for i in $(seq 1 30); do
  if curl -fsS "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    echo "==> AegisMed is up: http://<this-instance-public-ip>:${PORT}"
    curl -s "http://localhost:${PORT}/health"
    echo
    exit 0
  fi
  sleep 1
done

echo "==> AegisMed did not become healthy in 30s. Check logs with:"
echo "    docker logs $CONTAINER_NAME"
exit 1
