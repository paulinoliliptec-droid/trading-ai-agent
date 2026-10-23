#!/usr/bin/env bash
# Prepara o acesso ao cluster Atlas JÁ existente (não cria projetos nem clusters). Requer `atlas auth login`.
# Cria o utilizador da aplicação (readWrite só em trading_agent), dá acesso temporário ao IP desta máquina e
# escreve MONGODB_URI no .env sem a mostrar. Correr a partir da raiz do repositório.
set -euo pipefail
PROJECT_ID="${ATLAS_PROJECT_ID:-6ada846a7dcd22b453a73fac}"
CLUSTER="${ATLAS_CLUSTER:-trading-ai-m0}"
DB_USER="${ATLAS_DB_USER:-trading-ai-agent}"
ENV_FILE="${ENV_FILE:-.env}"

atlas clusters describe "$CLUSTER" --projectId "$PROJECT_ID" -o json >/dev/null   # falha cedo se o cluster não existir

IP=$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')
EXPIRA=$(date -u -d '+6 days' +%Y-%m-%dT%H:%M:%SZ)
atlas accessLists create "$IP" --type ipAddress --projectId "$PROJECT_ID" --deleteAfter "$EXPIRA" \
  --comment "Workstation (temporario)" -o json >/dev/null || echo "IP já estava na lista de acesso"

if atlas dbusers describe "$DB_USER" --projectId "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Utilizador $DB_USER já existe: a palavra-passe é renovada (a anterior deixa de valer)."
  ACAO=update
else
  ACAO=create
fi
PASS=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
if [[ $ACAO == create ]]; then
  atlas dbusers create --username "$DB_USER" --password "$PASS" --role readWrite@trading_agent \
    --scope "$CLUSTER" --projectId "$PROJECT_ID" -o json >/dev/null
else
  atlas dbusers update "$DB_USER" --password "$PASS" --role readWrite@trading_agent \
    --scope "$CLUSTER" --projectId "$PROJECT_ID" -o json >/dev/null
fi

SRV=$(atlas clusters describe "$CLUSTER" --projectId "$PROJECT_ID" -o json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["connectionStrings"]["standardSrv"])')
HOST=${SRV#mongodb+srv://}
URI="mongodb+srv://$DB_USER:$PASS@$HOST/trading_agent?retryWrites=true&w=majority&appName=trading-ai-agent"
touch "$ENV_FILE" && chmod 600 "$ENV_FILE"
python3 - "$ENV_FILE" "$URI" <<'PY'
import sys, pathlib
p, uri = pathlib.Path(sys.argv[1]), sys.argv[2]
linhas = [l for l in p.read_text().splitlines() if not l.startswith("MONGODB_URI=")]
p.write_text("\n".join(linhas + [f"MONGODB_URI={uri}"]) + "\n")
PY
unset PASS URI
echo "OK: utilizador $DB_USER (readWrite@trading_agent), IP $IP com acesso até $EXPIRA, MONGODB_URI escrita em $ENV_FILE."
