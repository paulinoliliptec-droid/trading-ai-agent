#!/usr/bin/env bash
# PREPARADO, NÃO EXECUTADO. Cria recursos faturáveis: só com autorização explícita do dono.
# Projeto DEDICADO (não usar projetos existentes). Uso:
#   PROJECT=trading-ai-agent-XXXX REGION=us-central1 ZONE=us-central1-a ./infra/gcp/deploy.sh
#
# Arquitetura (CPU, sem GPU):
#   · inferência contínua: 1 VM e2-micro (worker por mercado + bot do Telegram, systemd), sempre ligada;
#   · treino: Cloud Run Job (2 vCPU, 4 GiB) semanal, separado da inferência; grava modelos no GCS;
#   · dados e modelos: Cloud Storage; estado e registos: MongoDB Atlas (M0); segredos: Secret Manager.
set -euo pipefail
: "${PROJECT:?defina PROJECT}"; REGION="${REGION:-us-central1}"; ZONE="${ZONE:-us-central1-a}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/trading/agent:$(git rev-parse --short HEAD)"
SA="trading-agent@$PROJECT.iam.gserviceaccount.com"

gcloud services enable compute.googleapis.com run.googleapis.com artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com secretmanager.googleapis.com storage.googleapis.com --project "$PROJECT"
gcloud iam service-accounts create trading-agent --project "$PROJECT" || true
for role in roles/secretmanager.secretAccessor roles/storage.objectAdmin roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" --role "$role" --condition=None >/dev/null
done
gcloud storage buckets create "gs://$PROJECT-dados" --location "$REGION" --uniform-bucket-level-access || true
gcloud artifacts repositories create trading --repository-format=docker --location "$REGION" --project "$PROJECT" || true
gcloud builds submit --tag "$IMAGE" --project "$PROJECT"

# Segredos (os valores entram à mão, nunca por este script):
#   printf '%s' "<valor>" | gcloud secrets create mongodb-uri --data-file=- --project "$PROJECT"
#   idem: telegram-bot-token, telegram-allowed-chat-ids, api-admin-token, oanda-api-token, oanda-account-id

# Treino semanal (Cloud Run Job): experiências + treino do modelo escolhido; artefactos para o GCS.
gcloud run jobs deploy treino --image "$IMAGE" --region "$REGION" --project "$PROJECT" --service-account "$SA" \
  --cpu 2 --memory 4Gi --task-timeout 3600 \
  --add-volume name=dados,type=cloud-storage,bucket="$PROJECT-dados" --add-volume-mount volume=dados,mount-path=/app/gcs \
  --command bash \
  --args=-c,"python scripts/fetch_data.py && python scripts/run_experiments.py && (python scripts/train_model.py --escolhido BTC/USD || true) && cp -r models_artifacts reports /app/gcs/" \
  --set-secrets MONGODB_URI=mongodb-uri:latest
gcloud scheduler jobs create http treino-semanal --location "$REGION" --project "$PROJECT" --schedule "0 3 * * 0" \
  --http-method POST --uri "https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT/jobs/treino:run" \
  --oauth-service-account-email "$SA" || true

# Inferência contínua: VM e2-micro com a imagem e os serviços systemd (worker BTC/USD + bot).
gcloud compute instances create trading-worker --project "$PROJECT" --zone "$ZONE" --machine-type e2-micro \
  --service-account "$SA" --scopes cloud-platform --image-family debian-12 --image-project debian-cloud \
  --boot-disk-size 20GB --metadata image="$IMAGE" \
  --metadata-from-file startup-script=infra/gcp/startup-worker.sh,unit-agent=infra/gcp/systemd/trading-agent@.service,unit-telegram=infra/gcp/systemd/trading-telegram.service
