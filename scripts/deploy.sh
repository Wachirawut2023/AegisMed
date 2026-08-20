#!/usr/bin/env bash
# Deploy AegisMed as a scale-to-zero portfolio demo:
#   backend  -> Google Cloud Run (min-instances=0: $0 while idle, wakes on request)
#              calling Vertex AI's Gemini API for inference
#   frontend -> Firebase Hosting (static/index.html, proxies /api/** to Cloud Run)
#
# No API key anywhere: Cloud Run's attached service account authenticates to
# Vertex AI automatically (Application Default Credentials), as long as it
# has the roles/aiplatform.user role — this script grants that.
#
# See docs/DEPLOYMENT.md for the full explanation and one-time setup steps
# (gcloud auth, firebase login). This script just codifies the deploy
# commands so redeploys are a single line.
#
# Usage:
#   PROJECT_ID=my-gcp-project REGION=us-central1 ./scripts/deploy.sh
# To force the zero-cost canned demo instead of real Vertex AI calls:
#   DEMO_MODE=true PROJECT_ID=my-gcp-project ./scripts/deploy.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your GCP project id}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-aegismed}"

echo "==> Enabling required APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com aiplatform.googleapis.com \
  --project "${PROJECT_ID}"

echo "==> Granting the Cloud Run runtime service account access to Vertex AI"
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/aiplatform.user" \
  --condition=None \
  --quiet

ENV_VARS="DEMO_MODE=${DEMO_MODE:-auto},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},SPECIALIST_SELECTION=${SPECIALIST_SELECTION:-relevant},RATE_LIMIT_PER_MINUTE=${RATE_LIMIT_PER_MINUTE:-20}"

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
