#!/usr/bin/env bash
# Implantação do Trading AI Agent DENTRO do projeto GCP da Serafy Agentics (faturação já existente),
# isolado por nomes, permissões e segredos próprios. Não toca em nenhum recurso da Serafy.
#
# Por omissão só MOSTRA o que faria. Cria recursos faturáveis apenas com CONFIRMO=sim, e só depois de
# o dono ter aprovado o custo (docs/gcp-costs.md).
#   ./infra/gcp/deploy.sh                       # plano (nada é criado)
#   CONFIRMO=sim ./infra/gcp/deploy.sh          # executa
#
# Operação pessoal (menor custo tecnicamente adequado):
#   · 1 VM e2-micro em us-central1 (nível gratuito da GCP, se ainda não estiver usado na conta de faturação)
#     com o worker BTC/USD em observação e o bot do Telegram, em systemd; IP externo estático (o Atlas M0 só
#     aceita origens listadas);
#   · imagem construída na Workstation e enviada para o Artifact Registry (sem Cloud Build);
#   · modelos e datasets no Cloud Storage; segredos no Secret Manager com prefixo próprio.
# Treino: continua na Workstation nesta fase (sem Cloud Run Job nem Scheduler, que só valem com treino periódico).
set -euo pipefail
PROJECT="${PROJECT:-serafy-agentics}"
REGION="${REGION:-us-central1}"; ZONE="${ZONE:-us-central1-a}"
P=trading-ai                                   # prefixo de TODOS os recursos desta aplicação
SA="$P-agent@$PROJECT.iam.gserviceaccount.com"
BUCKET="$PROJECT-$P-dados"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/$P/agent:$(git rev-parse --short HEAD)"
LABELS="app=$P,owner=pessoal"
SECRETS=("$P-mongodb-uri" "$P-telegram-bot-token" "$P-telegram-allowed-chat-ids" "$P-api-admin-token")

run() { if [[ "${CONFIRMO:-}" == "sim" ]]; then echo "+ $*"; "$@"; else echo "[plano] $*"; fi; }

# 0) Verificações só de leitura: projeto certo, faturação ativa, colisões de nomes.
gcloud projects describe "$PROJECT" --format='value(projectId)' >/dev/null
gcloud billing projects describe "$PROJECT" --billing-project "$PROJECT" --format='value(billingEnabled)' 2>/dev/null \
  | grep -qi true || { echo "Faturação não confirmada em $PROJECT: parar."; exit 1; }
for s in "${SECRETS[@]}"; do
  gcloud secrets describe "$s" --project "$PROJECT" >/dev/null 2>&1 && echo "segredo $s já existe (reutilizado)"
done

# 1) APIs que faltam no projeto (Compute; o resto já está ativo para a Serafy).
run gcloud services enable compute.googleapis.com --project "$PROJECT"

# 2) Identidade própria, com acesso só aos SEUS segredos e ao SEU bucket.
run gcloud iam service-accounts create "$P-agent" --project "$PROJECT" --display-name "Trading AI Agent (paper)"
run gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" --role roles/logging.logWriter --condition=None
run gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" --role roles/artifactregistry.reader --condition=None
for s in "${SECRETS[@]}"; do
  # o valor entra à mão e nunca por este script:  printf '%s' "<valor>" | gcloud secrets versions add $s --data-file=-
  run gcloud secrets create "$s" --project "$PROJECT" --replication-policy automatic --labels "$LABELS"
  run gcloud secrets add-iam-policy-binding "$s" --project "$PROJECT" --member "serviceAccount:$SA" --role roles/secretmanager.secretAccessor
done
run gcloud storage buckets create "gs://$BUCKET" --project "$PROJECT" --location "$REGION" --uniform-bucket-level-access
run gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member "serviceAccount:$SA" --role roles/storage.objectAdmin
run gcloud storage buckets update "gs://$BUCKET" --update-labels "$LABELS"

# 3) Imagem: construída aqui e enviada (evita ativar o Cloud Build no projeto da Serafy).
run gcloud artifacts repositories create "$P" --repository-format=docker --location "$REGION" --project "$PROJECT" --labels "$LABELS"
run gcloud auth configure-docker "$REGION-docker.pkg.dev" --quiet
run docker build -t "$IMAGE" .
run docker push "$IMAGE"
run gcloud storage rsync -r models_artifacts "gs://$BUCKET/models_artifacts"

# 4) IP estático (para a lista de acesso do Atlas) e VM de inferência.
run gcloud compute addresses create "$P-worker-ip" --project "$PROJECT" --region "$REGION"
run gcloud compute instances create "$P-worker" --project "$PROJECT" --zone "$ZONE" --machine-type e2-micro \
  --service-account "$SA" --scopes cloud-platform --image-family debian-12 --image-project debian-cloud \
  --boot-disk-size 30GB --boot-disk-type pd-standard --address "$P-worker-ip" --labels "$LABELS" \
  --no-shielded-secure-boot --tags "$P" \
  --metadata image="$IMAGE",bucket="$BUCKET",prefix="$P" \
  --metadata-from-file startup-script=infra/gcp/startup-worker.sh,unit-agent=infra/gcp/systemd/trading-agent@.service,unit-telegram=infra/gcp/systemd/trading-telegram.service
# Sem regras de firewall de entrada: a VM só faz ligações de saída (Atlas, Telegram, Coinbase). SSH via IAP se preciso.

echo
echo "Depois: adicionar o IP de $P-worker-ip à lista de acesso do Atlas (atlas accessLists create <IP> --projectId …)."
