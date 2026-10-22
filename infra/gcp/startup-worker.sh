#!/usr/bin/env bash
# Arranque da VM de inferência: instala Docker, lê segredos do Secret Manager e liga os serviços.
set -euo pipefail
meta() { curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
IMAGE=$(meta image); BUCKET=$(meta bucket); P=$(meta prefix)
apt-get update -y && apt-get install -y docker.io
gcloud auth configure-docker "$(echo "$IMAGE" | cut -d/ -f1)" --quiet
secret() { gcloud secrets versions access latest --secret "$P-$1" 2>/dev/null || true; }   # só os segredos com o prefixo próprio
install -d -m 700 /etc/trading
{
  echo "MONGODB_URI=$(secret mongodb-uri)"
  echo "TELEGRAM_BOT_TOKEN=$(secret telegram-bot-token)"
  echo "TELEGRAM_ALLOWED_CHAT_IDS=$(secret telegram-allowed-chat-ids)"
  echo "API_ADMIN_TOKEN=$(secret api-admin-token)"
  echo "TENANT_ID=pessoal"
  echo "TRADING_ENV=observacao"
} > /etc/trading/env && chmod 600 /etc/trading/env
echo "IMAGE=$IMAGE" > /etc/trading/image
mkdir -p /var/lib/trading/models_artifacts
gcloud storage rsync -r "gs://$BUCKET/models_artifacts" /var/lib/trading/models_artifacts || true
meta unit-agent > "/etc/systemd/system/trading-agent@.service"
meta unit-telegram > /etc/systemd/system/trading-telegram.service
systemctl daemon-reload
systemctl enable --now trading-agent@BTCUSD.service trading-telegram.service
