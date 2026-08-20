#!/usr/bin/env bash
# Deploy AegisMed as a scale-to-zero portfolio demo:
#   backend  -> Google Cloud Run (min-instances=0: $0 while idle, wakes on request)
#   frontend -> Firebase Hosting (static/index.html, proxies /api/** to Cloud Run)
#
# No Fireworks API key is used or needed: this deployment always runs in
# demo mode (canned board output), so there's no per-token bill and no
# secret to provide at deploy time.
#
# See docs/DEPLOYMENT.md for the full explanation and one-time setup steps
# (gcloud auth, enabling APIs, firebase login). This script just codifies
# the two deploy commands so redeploys are a single line.
#
# Usage:
#   PROJECT_ID=my-gcp-project REGION=us-central1 ./scripts/deploy.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your GCP project id}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-aegismed}"

ENV_VARS="DEMO_MODE=true,SPECIALIST_SELECTION=${SPECIALIST_SELECTION:-relevant},RATE_LIMIT_PER_MINUTE=${RATE_LIMIT_PER_MINUTE:-20}"

echo "==> Deploying backend to Cloud Run (${SERVICE_NAME}, region ${REGION})"
gcloud run deploy "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --source . \
  --port 8000 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances "${MAX_INSTANCES:-3}" \
  --memory "${MEMORY:-512Mi}" \
  --cpu 1 \
  --set-env-vars "${ENV_VARS}"

echo "==> Deploying frontend to Firebase Hosting"
firebase deploy --only hosting --project "${PROJECT_ID}"

echo "==> Done. Cloud Run scales to zero automatically when idle — no always-on instance to pay for."
