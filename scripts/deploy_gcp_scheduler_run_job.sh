#!/usr/bin/env bash
# Deploy reporter-scraper as a Cloud Run Job on a weekly Cloud Scheduler trigger (GCP-native scheduling).
# Run from Google Cloud Shell at repo root after ./scripts/setup_gcp_cloud_shell.sh (BigQuery + dataset).
#
# PREREQS:
#   gcloud auth login && gcloud config set project YOUR_PROJECT
#   export TWITTER_API_KEY="..."   # recommended — stored in Secret Manager and mounted on the job
#
# Usage:
#   chmod +x scripts/deploy_gcp_scheduler_run_job.sh
#   ./scripts/deploy_gcp_scheduler_run_job.sh
#
# Optional env:
#   PROJECT_ID, REGION (default us-central1), JOB_NAME (reporter-scraper-weekly)
#   SCHEDULER_NAME (reporter-scraper-weekly-trigger)
#   BIGQUERY_DATASET (reporter_scraper), SCHEDULE_CRON (default 0 0 * * 1 = Monday 00:00 UTC)
#   RUNTIME_SA (reporter-scraper-runtime), SCHEDULER_SA (reporter-scraper-scheduler)
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null | tr -d '\n')}"
REGION="${REGION:-us-central1}"
JOB_NAME="${JOB_NAME:-reporter-scraper-weekly}"
SCHEDULER_NAME="${SCHEDULER_NAME:-reporter-scraper-weekly-trigger}"
DATASET_ID="${BIGQUERY_DATASET:-reporter_scraper}"
SCHEDULE_CRON="${SCHEDULE_CRON:-0 0 * * 1}"
TIMEZONE="${SCHEDULER_TIMEZONE:-Etc/UTC}"

RUNTIME_SA_ID="${RUNTIME_SA:-reporter-scraper-runtime}"
SCHEDULER_SA_ID="${SCHEDULER_SA:-reporter-scraper-scheduler}"
REGISTRY_REPO="${ARTIFACT_REGISTRY_REPO:-reporter-scraper}"
IMAGE_NAME="${IMAGE_NAME:-reporter-scraper}"
TWITTER_SECRET_ID="${TWITTER_SECRET_ID:-twitter-api-key}"

RUNTIME_SA_EMAIL="${RUNTIME_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SA_EMAIL="${SCHEDULER_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY_REPO}/${IMAGE_NAME}:latest"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: Set PROJECT_ID or run: gcloud config set project YOUR_PROJECT"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"

echo "=========================================="
echo "Deploy: Cloud Run Job + weekly Scheduler"
echo "=========================================="
echo "Project:     ${PROJECT_ID} (${PROJECT_NUMBER})"
echo "Region:      ${REGION}"
echo "Job:         ${JOB_NAME}"
echo "Schedule:    ${SCHEDULE_CRON} (${TIMEZONE})"
echo "Image:       ${IMAGE_TAG}"
echo "=========================================="

gcloud config set project "${PROJECT_ID}"

# New service accounts may take a few seconds before add-iam-policy-binding accepts them.
wait_for_service_account_visible() {
  local email="$1"
  local label="$2"
  local max="${3:-30}"
  local delay="${4:-2}"
  local i
  for ((i=1; i<=max; i++)); do
    if gcloud iam service-accounts describe "${email}" --project="${PROJECT_ID}" &>/dev/null; then
      if ((i > 1)); then
        echo "${label}: OK (${email}) after IAM propagation"
      fi
      return 0
    fi
    echo "${label}: waiting for ${email} (${i}/${max})..."
    sleep "${delay}"
  done
  echo "ERROR: ${label} still not visible: ${email}"
  return 1
}

echo ""
echo "[1/8] Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  --project="${PROJECT_ID}"

echo ""
echo "[2/8] Artifact Registry (Docker) repo..."
if gcloud artifacts repositories describe "${REGISTRY_REPO}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "Repository exists: ${REGISTRY_REPO}"
else
  gcloud artifacts repositories create "${REGISTRY_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Reporter scraper container images" \
    --project="${PROJECT_ID}"
fi

echo ""
echo "[3/8] Build and push image (Cloud Build)..."
gcloud builds submit "${REPO_ROOT}" \
  --project="${PROJECT_ID}" \
  --tag="${IMAGE_TAG}"

echo ""
echo "[4/8] Runtime service account (job identity → BigQuery)..."
if gcloud iam service-accounts describe "${RUNTIME_SA_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "Exists: ${RUNTIME_SA_EMAIL}"
else
  gcloud iam service-accounts create "${RUNTIME_SA_ID}" \
    --project="${PROJECT_ID}" \
    --display-name="Reporter scraper Cloud Run Job"
fi
wait_for_service_account_visible "${RUNTIME_SA_EMAIL}" "Runtime service account"
for ROLE in roles/bigquery.user roles/bigquery.dataEditor; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
    --role="${ROLE}" \
    --quiet
done

echo ""
echo "[5/8] Twitter API key → Secret Manager (optional but recommended)..."
SECRETS_ARGS=()
if [[ -n "${TWITTER_API_KEY:-}" ]]; then
  if gcloud secrets describe "${TWITTER_SECRET_ID}" --project="${PROJECT_ID}" &>/dev/null; then
    echo -n "${TWITTER_API_KEY}" | gcloud secrets versions add "${TWITTER_SECRET_ID}" --data-file=- --project="${PROJECT_ID}"
  else
    echo -n "${TWITTER_API_KEY}" | gcloud secrets create "${TWITTER_SECRET_ID}" \
      --data-file=- \
      --project="${PROJECT_ID}" \
      --replication-policy="automatic"
  fi
  gcloud secrets add-iam-policy-binding "${TWITTER_SECRET_ID}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet
  SECRETS_ARGS=(--set-secrets="TWITTER_API_KEY=${TWITTER_SECRET_ID}:latest")
  echo "Secret ${TWITTER_SECRET_ID} will be mounted as env TWITTER_API_KEY"
else
  echo "WARN: TWITTER_API_KEY not set in shell. Deploying job without Twitter secret."
  echo "      Twitter-dependent steps may fail until you: create secret ${TWITTER_SECRET_ID}, grant accessor to ${RUNTIME_SA_EMAIL}, and:"
  echo "      gcloud run jobs update ${JOB_NAME} --region=${REGION} --set-secrets=TWITTER_API_KEY=${TWITTER_SECRET_ID}:latest"
fi

echo ""
echo "[6/8] Cloud Run Job..."
# Long timeout for many sequential Playwright scrapers; tune CPU/RAM if needed.
if [[ ${#SECRETS_ARGS[@]} -gt 0 ]]; then
  gcloud run jobs deploy "${JOB_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --image="${IMAGE_TAG}" \
    --tasks=1 \
    --parallelism=1 \
    --max-retries=1 \
    --task-timeout=4h \
    --cpu=4 \
    --memory=8Gi \
    --service-account="${RUNTIME_SA_EMAIL}" \
    --set-env-vars="GCP_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},BIGQUERY_DATASET=${DATASET_ID}" \
    "${SECRETS_ARGS[@]}"
else
  gcloud run jobs deploy "${JOB_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --image="${IMAGE_TAG}" \
    --tasks=1 \
    --parallelism=1 \
    --max-retries=1 \
    --task-timeout=4h \
    --cpu=4 \
    --memory=8Gi \
    --service-account="${RUNTIME_SA_EMAIL}" \
    --set-env-vars="GCP_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},BIGQUERY_DATASET=${DATASET_ID}"
fi

echo ""
echo "[7/8] Scheduler invoker service account..."
if gcloud iam service-accounts describe "${SCHEDULER_SA_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "Exists: ${SCHEDULER_SA_EMAIL}"
else
  gcloud iam service-accounts create "${SCHEDULER_SA_ID}" \
    --project="${PROJECT_ID}" \
    --display-name="Reporter scraper Cloud Scheduler (run job)"
fi
wait_for_service_account_visible "${SCHEDULER_SA_EMAIL}" "Scheduler invoker service account"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SCHEDULER_SA_EMAIL}" \
  --role="roles/run.developer" \
  --quiet

echo ""
echo "[8/8] Cloud Scheduler → Run Job (v2 API)..."
RUN_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v2/projects/${PROJECT_NUMBER}/locations/${REGION}/jobs/${JOB_NAME}:run"

if gcloud scheduler jobs describe "${SCHEDULER_NAME}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  gcloud scheduler jobs update http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --schedule="${SCHEDULE_CRON}" \
    --time-zone="${TIMEZONE}" \
    --uri="${RUN_URI}" \
    --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_SA_EMAIL}" \
    --quiet
else
  gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --schedule="${SCHEDULE_CRON}" \
    --time-zone="${TIMEZONE}" \
    --uri="${RUN_URI}" \
    --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_SA_EMAIL}" \
    --quiet
fi

echo ""
echo "=========================================="
echo "Done. Weekly runs are on Cloud Scheduler."
echo "=========================================="
echo "Manual test:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID} --wait"
echo ""
echo "Logs:"
echo "  gcloud logging read 'resource.type=cloud_run_job AND resource.labels.job_name=${JOB_NAME}' --limit=50 --project=${PROJECT_ID}"
echo ""
echo "GitHub Actions: cron disabled in workflow; use workflow_dispatch only if you keep CI for manual runs."
echo ""
