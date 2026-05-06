#!/usr/bin/env bash
# Run in Google Cloud Shell (bash). Configures BigQuery + a service account for reporter-scraper / GitHub Actions.
#
# Usage:
#   chmod +x scripts/setup_gcp_cloud_shell.sh
#   export PROJECT_ID="your-gcp-project-id"   # optional if already: gcloud config set project ...
#   ./scripts/setup_gcp_cloud_shell.sh
#
# Optional overrides:
#   BIGQUERY_DATASET=reporter_scraper   BIGQUERY_LOCATION=US   GCP_SA_NAME=reporter-scraper-github
#   KEY_FILE="$HOME/reporter-scraper-github-sa-key.json"
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null | tr -d '\n')}"
DATASET_ID="${BIGQUERY_DATASET:-reporter_scraper}"
LOCATION="${BIGQUERY_LOCATION:-US}"
SA_ID="${GCP_SA_NAME:-reporter-scraper-github}"
KEY_FILE="${KEY_FILE:-${HOME}/reporter-scraper-github-sa-key.json}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: No GCP project. Run: gcloud config set project YOUR_PROJECT_ID"
  echo "   Or: PROJECT_ID=YOUR_PROJECT_ID $0"
  exit 1
fi

SA_EMAIL="${SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=========================================="
echo "Reporter scraper — GCP setup"
echo "=========================================="
echo "Project:        ${PROJECT_ID}"
echo "BQ dataset:     ${DATASET_ID}  (location: ${LOCATION})"
echo "Service acct:   ${SA_EMAIL}"
echo "Key file:       ${KEY_FILE}"
echo "=========================================="

gcloud config set project "${PROJECT_ID}"

echo ""
echo "[1/5] Enabling BigQuery API..."
gcloud services enable bigquery.googleapis.com --project="${PROJECT_ID}"

echo ""
echo "[2/5] Creating BigQuery dataset (if missing)..."
if bq show "${PROJECT_ID}:${DATASET_ID}" >/dev/null 2>&1; then
  echo "Dataset already exists: ${PROJECT_ID}:${DATASET_ID}"
else
  bq --location="${LOCATION}" mk --dataset "${PROJECT_ID}:${DATASET_ID}"
  echo "Created dataset ${PROJECT_ID}:${DATASET_ID}"
fi

echo ""
echo "[3/5] Creating service account (if missing)..."
if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Service account already exists: ${SA_EMAIL}"
else
  gcloud iam service-accounts create "${SA_ID}" \
    --project="${PROJECT_ID}" \
    --display-name="Reporter scraper (GitHub Actions)"
  echo "Created service account: ${SA_EMAIL}"
fi

echo ""
echo "[4/5] Granting BigQuery roles on project..."
# user: create datasets + run jobs; dataEditor: read/write tables in project datasets
for ROLE in roles/bigquery.user roles/bigquery.dataEditor; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}"
done
echo "Bindings applied for roles/bigquery.user and roles/bigquery.dataEditor"

echo ""
echo "[5/5] Service account JSON key..."
if [[ -f "${KEY_FILE}" ]]; then
  echo "Key file already present (not overwriting): ${KEY_FILE}"
  echo "To regenerate: rm \"${KEY_FILE}\" and run this script again."
else
  gcloud iam service-accounts keys create "${KEY_FILE}" \
    --iam-account="${SA_EMAIL}" \
    --project="${PROJECT_ID}"
  chmod 600 "${KEY_FILE}" || true
  echo "Wrote key to: ${KEY_FILE}"
fi

echo ""
echo "=========================================="
echo "Done."
echo "=========================================="
echo ""
echo "GitHub Actions repository secrets (name -> value):"
echo "  GCP_PROJECT          -> ${PROJECT_ID}"
echo "  GCP_SA_KEY           -> entire contents of: ${KEY_FILE}"
echo "  BIGQUERY_DATASET     -> ${DATASET_ID}   (optional — app defaults to reporter_scraper)"
echo "  TWITTER_API_KEY      -> (your existing key)"
echo ""
echo "Optional repository variable/secret:"
echo "  BIGQUERY_TABLE       -> reporters   (default in code; use legacy name only if you know you need it)"
echo "  BIGQUERY_LOCATION    -> US (default) for dataset creation in bigquery_sync"
echo ""
echo "Table \"reporters\" is created automatically on first scraper run"
echo "(bigquery_sync.ensure_reporters_table_exists)."
echo ""
echo "GCP weekly scheduling (recommended): from repo root in Cloud Shell run:"
echo "  export TWITTER_API_KEY='...'"
echo "  chmod +x scripts/deploy_gcp_scheduler_run_job.sh"
echo "  ./scripts/deploy_gcp_scheduler_run_job.sh"
echo ""
echo "IMPORTANT: Do not commit the JSON key. After adding GCP_SA_KEY to GitHub,"
echo "consider: shred -u \"${KEY_FILE}\"   # or delete the file in Cloud Shell"
echo ""
