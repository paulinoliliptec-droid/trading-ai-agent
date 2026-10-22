#!/usr/bin/env bash
# PREPARADO, NÃO EXECUTADO. Publicar gera custos: só com autorização do dono.
# Uso: PROJECT=trading-ai-agent REGION=europe-west1 ./infra/gcp/deploy.sh
set -euo pipefail
: "${PROJECT:?defina PROJECT}"; REGION="${REGION:-europe-west1}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/trading/agent:$(git rev-parse --short HEAD)"

gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com storage.googleapis.com --project "$PROJECT"
gcloud artifacts repositories create trading --repository-format=docker --location "$REGION" --project "$PROJECT" || true
gcloud builds submit --tag "$IMAGE" --project "$PROJECT"

# API e painel: escala a zero.
gcloud run deploy trading-api --image "$IMAGE" --region "$REGION" --project "$PROJECT" \
  --no-allow-unauthenticated --min-instances 0 --max-instances 2 --memory 1Gi \
  --set-secrets API_ADMIN_TOKEN=api-admin-token:latest,TELEGRAM_BOT_TOKEN=telegram-bot-token:latest

# Recolha horária de dados (job que corre e termina).
gcloud run jobs deploy fetch-data --image "$IMAGE" --region "$REGION" --project "$PROJECT" \
  --command python --args scripts/fetch_data.py --memory 1Gi --task-timeout 1800
gcloud scheduler jobs create http fetch-data-hourly --location "$REGION" --project "$PROJECT" \
  --schedule "5 * * * *" --http-method POST \
  --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs/fetch-data:run" \
  --oauth-service-account-email "trading-scheduler@$PROJECT.iam.gserviceaccount.com" || true

# Treino e relatório semanais.
gcloud run jobs deploy research --image "$IMAGE" --region "$REGION" --project "$PROJECT" \
  --command python --args scripts/run_research.py,--symbol,EUR/USD,--source,dukascopy --memory 4Gi --cpu 2 --task-timeout 3600
