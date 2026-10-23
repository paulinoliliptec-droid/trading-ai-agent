# Fase 3: integração do Atlas, do Telegram e da GCP (23/10/2026)

Operação **pessoal**, só em **observação** (paper trading sem posições abertas enquanto não houver um modelo
aprovado). A arquitetura SaaS mantém-se intacta, com um único tenant ativo: `pessoal`.

## Estado

| Item | Estado |
|---|---|
| MongoDB Atlas | **Ligado.** Cluster `trading-ai-m0` (M0, AWS US_EAST_1) no projeto Atlas existente. Utilizador `trading-ai-agent` só com `readWrite@trading_agent` (uma escrita noutra base é recusada). Lista de acesso: IP estático da VM (permanente) e IP da Workstation (expira a 28/10). 9 coleções e 14 índices, 4 únicos. |
| Telegram | **Ligado.** Bot `@SerafyAgenticsBot` reutilizado. O webhook antigo do Serafy foi apagado e o menu de comandos configurado. Só o chat do dono é autorizado. Os 6 comandos foram testados pelo dono. Todas as mensagens levam `[TRADING AI]`. |
| Segredos | `.env` local (600, fora do Git). Na GCP, 4 segredos `trading-ai-*`, acessíveis só à conta de serviço do trader. Nenhum segredo da Serafy foi lido ou alterado. |
| Docker | `docker-compose.yml` usa o Atlas sem arrancar um MongoDB local; o desenvolvimento usa `docker-compose.local.yml`. Portas só em 127.0.0.1. A imagem passou a encontrar `configs/` e os modelos. |
| Google Cloud | Projeto **`serafy-agentics`**, que tem faturação. O `serafy-agentics-fe12b` tem a faturação desligada. VM `trading-ai-worker` (e2-micro, us-central1) com o worker BTC/USD e o bot, ambos em systemd. Lista de recursos em `docs/gcp-costs.md`. |
| Custo incremental | ~4 USD/mês com o nível gratuito da e2-micro, 11 a 12 USD/mês sem ele. Atlas M0: 0. O SaaS futuro está estimado à parte e não está ativo. |
| Testes | 75 a passar (`pytest`), mais a verificação ao vivo: Atlas, estado partilhado entre processos, comandos do Telegram, pedido de fecho tratado pelo worker e a mesma vela não reprocessada depois de um reinício. |
| Tenant | `pessoal` registado: dono `telegram:<chat>`, negociação real desligada, sem subscrição. |
| Investigação | Hipótese 1 (custos mais baixos no BTC) **refutada** com os dados da fase 2: nem com custo zero há vantagem bruta significativa. A seguir vem a hipótese 3 (volatilidade). |

## Alterações ao código

- **Telegram:** marca `[TRADING AI]` nas mensagens; o bot recusa arrancar com um webhook alheio (só o apaga com `--apagar-webhook`) e sai com um 409, para haver um só consumidor. Os alertas passam a escapar o HTML: os vetos com «<» eram recusados.
- **Tenants:** `TENANT_ID` passa pelo agente, pelo bot e pela API; `Tenant.to_doc()`, a coleção `tenants` e `scripts/tenant_init.py`. O agente arranca em observação por omissão.
- **Observação:** `monitoring/observation.py` e `scripts/observation_report.py` (sinais, vetos agrupados, direção e retorno líquido no horizonte seguinte, Brier, uso do Atlas).
- **Infraestrutura:** `deploy.sh` reescrito para o projeto existente, com prefixo próprio, permissões por recurso e plano por omissão; swap na e2-micro; `scripts/atlas_setup.sh`.
- **Docker:** instalação editável; Compose separado entre Atlas e local.

## Bugs anteriores encontrados

1. A imagem Docker instalava o pacote em `site-packages` e não encontrava `configs/` nem `models_artifacts/`: nenhum contentor arrancava.
2. As notificações em HTML com «<» eram recusadas pelo Telegram (400) sem ficar registado.
3. O `pytest` sem `python -m` não encontrava o pacote `apps`.

## Teste de observação de cinco dias

Dia 1 (integração) concluído a 23/10. Relatório final a 27/10: `python scripts/observation_report.py --dias 5`.
Plano em `docs/observacao-5-dias.md`. Nenhum modelo é aprovado com base neste período.

## Pendentes do dono

- `/resume` no Telegram (o último teste foi `/stop`; enquanto o kill switch estiver acionado, todas as decisões são vetadas).
- Opcional: retirar `TELEGRAM_BOT_TOKEN` do serviço `agentos-angola` do `serafy-agentics-fe12b`, para que um arranque futuro não volte a registar o webhook.
- O token do bot foi partilhado numa conversa; o dono decidiu mantê-lo.
- Renovar o acesso da Workstation ao Atlas depois de 28/10 (`scripts/atlas_setup.sh`).
