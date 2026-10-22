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

## O que falta para a GCP

1. Decidir o projeto (novo projeto dedicado, por exemplo `trading-ai-agent`, ou um existente). **Criar um projeto
   e associar faturação exige autorização do dono.**
2. Ativar APIs: Cloud Run, Artifact Registry, Cloud Scheduler, Secret Manager, Cloud Storage.
3. Criar os segredos (OANDA Practice, Telegram, MongoDB) e uma conta de serviço com acesso mínimo.
4. `infra/gcp/deploy.sh` (preparado, não executado).
