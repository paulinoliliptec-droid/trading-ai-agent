# Arquitetura na Google Cloud e estimativa de custos

> **Valores de referência, não orçamento.** Preços de tabela da GCP e do MongoDB Atlas conhecidos até meados de
> 2026, em USD, região europeia, sem impostos. Confirmar na calculadora oficial antes de decidir. Créditos
> promocionais: **não confirmados** (a conta não mostra nenhum ativo para este projeto; ver «Créditos» abaixo).

## Componentes

| Necessidade | Serviço | Porquê |
|---|---|---|
| API e painel | Cloud Run (serviço) | Escala a zero; paga-se o uso |
| Recolha horária de dados | Cloud Run Jobs + Cloud Scheduler | Corre e termina; sem servidor ligado |
| Treino periódico | Cloud Run Job (2 vCPU, 4 GiB), semanal | A grelha completa da fase 2 corre em ~45 min em 4 CPU; um modelo só, em minutos. Nunca na máquina de inferência |
| Paper trading contínuo (inferência) | **VM e2-micro** (1 GB) com o worker e o bot em systemd | Sempre ligado; a inferência (XGBoost já treinado + features) usa poucas centenas de MB. Separado do treino |
| Datasets e modelos | Cloud Storage (Standard) | Parquet e artefactos versionados |
| Credenciais | Secret Manager | Tokens de corretora, Telegram, MongoDB; um segredo por tenant no SaaS |
| Logs e alertas | Cloud Logging e Monitoring | Logs JSON já estruturados pelo código |
| Streaming | Pub/Sub só se houver vários consumidores do mesmo preço | Na fase 1 não é preciso |
| Base operacional | MongoDB Atlas | Ver ADR 0002 |

## Cenários (USD por mês, ordens de grandeza)

| Cenário | Pressupostos | GCP | MongoDB Atlas | Total |
|---|---|---|---|---|
| 1. Desenvolvimento | Recolha horária (2 jobs de segundos), treino semanal, API a zero, < 5 GB em GCS | ~0 a 5 (dentro dos níveis gratuitos do Cloud Run, Scheduler até 3 jobs grátis) | 0 (M0 gratuito, 512 MB) | **0 a 10** |
| 2. Paper trading contínuo | Worker sempre ligado (1 vCPU, 1 GiB), 2 pares, logs moderados | VM e2-small ~13 a 17, ou Cloud Run sempre ligado ~45 a 60; + GCS, Secret Manager, Scheduler ~2 | Flex ~10 a 30 | **25 a 90** |
| 3. SaaS, 100 tenants | Motor partilhado (2 a 4 vCPU), API com tráfego, 1 conta de corretora por tenant, auditoria completa | 150 a 400 | M10/M20 dedicado ~60 a 200 | **250 a 650**, sem contar suporte, segurança e jurídico |

O custo dominante do cenário 3 não é a infraestrutura: é o enquadramento regulatório e a operação (ver
SAAS_ARCHITECTURE.md).

## Verificação feita a 22/10/2026 (só leitura)

- Nenhum projeto da conta é de trading; o projeto ativo por omissão é o `dra-kiesse` (produção de outro produto: não
  se usa).
- A API de faturação não está ativa nesse projeto, por isso **não foi possível ver contas de faturação nem
  créditos** sem alterar um projeto existente. Não se alterou.
- A e2-micro tem um nível gratuito mensal nalgumas regiões dos EUA (us-west1, us-central1, us-east1) segundo a
  documentação pública da Google; **confirmar** na conta antes de contar com ele. Fora disso, ~7 a 9 USD/mês.

## Créditos promocionais

- Google Cloud: o programa de 300 USD é para contas novas; a conta autenticada já tem projetos com faturação.
  Programas para startups (Google for Startups Cloud) exigem candidatura. **Nada foi assumido.**
- MongoDB Atlas: há créditos de arranque em programas para startups; sem conta Atlas configurada, nada verificado.

## Fase 3: operação pessoal no projeto `serafy-agentics` (verificado a 22/10/2026, só leitura)

Por decisão do dono, a aplicação corre no projeto GCP da Serafy Agentics, que já tem faturação. Verificação:

- Há dois projetos da Serafy. **`serafy-agentics`** (n.º 37214601676) tem a faturação ativa (o Secret Manager
  responde) e corre o serviço Cloud Run `agentos-angola` em `europe-west1`. **`serafy-agentics-fe12b`** tem a
  faturação **desligada** (o Secret Manager recusa com `BILLING_DISABLED`): não serve.
- Identidade: `paulinoliliptec@gmail.com` com `roles/owner` em ambos.
- Compute Engine não está ativo no `serafy-agentics`: é a única API a ativar.
- A conta de faturação e os créditos não são visíveis sem ativar a Cloud Billing API (não foi ativada).
- Colisões: os segredos da Serafy são `GEMINI_API_KEY`, `TWILIO_*` e `WHATSAPP_VERIFY_TOKEN`; tudo o que esta
  aplicação cria tem o prefixo `trading-ai` (conta de serviço, segredos, bucket, repositório, IP, VM) e a etiqueta
  `app=trading-ai`. A conta de serviço só tem acesso aos seus próprios segredos e ao seu bucket.

### Custo mensal incremental: operação pessoal (USD, us-central1)

| Componente | Com nível gratuito | Sem nível gratuito |
|---|---|---|
| VM e2-micro (worker BTC/USD + bot), sempre ligada | 0 | ~6,1 |
| Disco 30 GB pd-standard | 0 | ~1,2 |
| IP externo estático (necessário para a lista do Atlas) | ~3,7 | ~3,7 |
| Artifact Registry (~1,5 GB de imagem) | ~0,1 | ~0,1 |
| Cloud Storage (modelos e datasets, < 1 GB) | 0 | < 0,1 |
| Secret Manager (4 segredos, poucos acessos) | 0 | < 0,3 |
| Logging (< 1 GB) e saída de rede (< 1 GB) | 0 | < 0,2 |
| MongoDB Atlas M0 | 0 | 0 |
| **Total** | **~4** | **~11 a 12** |

O nível gratuito da e2-micro é **um por conta de faturação**: se outro projeto na mesma conta já o usar, vale a
coluna da direita. Não foi possível confirmar sem a Cloud Billing API. O treino continua na Workstation, sem
custo na GCP. Se passar para a cloud, um Cloud Run Job semanal de cerca de 45 minutos custa menos de 1 USD por mês.

### Futuro SaaS (separado, não ativo)

Mantém-se o cenário 3 acima (250 a 650 USD por mês para cerca de 100 tenants, sem jurídico nem suporte). Os
componentes que só fazem sentido com clientes ficam desligados: API pública, autenticação de utilizadores,
subscrições, Atlas dedicado (M10 ou superior) e um worker por tenant.

## O que falta para a GCP

1. Decidir o projeto (novo projeto dedicado, por exemplo `trading-ai-agent`, ou um existente). **Criar um projeto
   e associar faturação exige autorização do dono.**
2. Ativar APIs: Cloud Run, Artifact Registry, Cloud Scheduler, Secret Manager, Cloud Storage.
3. Criar os segredos (OANDA Practice, Telegram, MongoDB) e uma conta de serviço com acesso mínimo.
4. `infra/gcp/deploy.sh` (preparado, não executado).

### Implantado a 23/10/2026 (aprovado pelo dono)

No projeto `serafy-agentics`, todos com o prefixo `trading-ai` e a etiqueta `app=trading-ai`:

| Recurso | Nome |
|---|---|
| API ativada | `compute.googleapis.com` (a única nova) |
| Conta de serviço | `trading-ai-agent@serafy-agentics.iam.gserviceaccount.com` (logWriter e artifactregistry.reader no projeto; acesso só aos seus segredos e ao seu bucket) |
| Segredos | `trading-ai-mongodb-uri`, `trading-ai-telegram-bot-token`, `trading-ai-telegram-allowed-chat-ids`, `trading-ai-api-admin-token` |
| Bucket | `gs://serafy-agentics-trading-ai-dados` (us-central1) com `models_artifacts/` |
| Artifact Registry | `us-central1-docker.pkg.dev/serafy-agentics/trading-ai/agent` (~3 GB por imagem, quase todo PyTorch) |
| IP estático | `trading-ai-worker-ip`, autorizado no Atlas como entrada permanente |
| VM | `trading-ai-worker` (e2-micro, us-central1-a, 30 GB pd-standard, swap de 2 GB), sem regras de firewall de entrada |

Nenhum recurso da Serafy foi alterado. Para remover tudo: apagar a VM, o IP, o repositório, o bucket, os 4 segredos e a
conta de serviço com o prefixo `trading-ai`.
