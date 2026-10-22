# Relatório de estado: Trading AI Agent

**Data:** 22/10/2026 · **Repositório:** `paulinoliliptec-droid/trading-ai-agent` (privado), branch `main`
**Fase:** 1, investigação e paper trading. **Só simulação: não existe caminho no código para ordens reais.**

> Documento de passagem: resume o que foi construído, os resultados reais obtidos, os bloqueios e as próximas
> ações. Os detalhes técnicos estão nos documentos indicados em cada secção.

## A. O que está construído

### Funcionalidades

| Área | Implementação | Ficheiros |
|---|---|---|
| Interface de corretoras | Contratos abstratos `MarketDataSource` (dados) e `ExecutionVenue` (ordens); tipos `Quote`, `Order`, `Fill`, `Position` | `src/trading_agent/brokers/base.py` |
| Dados BTC/USD | Coinbase Exchange, velas horárias públicas, paginadas | `brokers/crypto/coinbase.py` |
| Dados EUR/USD | Dukascopy, velas horárias com bid e ask (spread real), cache por mês e repetição com espera | `brokers/forex/dukascopy.py` |
| Preço ao vivo | Kraken pela CCXT (BTC/USD e EUR/USD, públicos) | `brokers/crypto/kraken.py` |
| Forex por corretora | OANDA v20, ambiente Practice, só leitura; pronta, falta o token | `brokers/forex/oanda.py` |
| Qualidade de dados | UTC, duplicados, falhas (com horário Forex), velas impossíveis, manifesto por dataset | `data/quality.py`, `data/store.py` |
| Features | Retornos, volatilidade, RSI, EMA, ATR, momentum, posição na amplitude, hora, volume, spread; só passado | `features/build.py` |
| Rótulos | Triple-barrier (TP, SL, tempo), entrada na abertura seguinte, empate TP+SL = SL | `labels/triple_barrier.py` |
| Validação | Walk-forward cronológico, purging por `t1`, embargo de 24 velas | `backtesting/splits.py` |
| Modelos | A: regras (EMA, RSI, momentum); B: XGBoost com calibração isotónica; C: GRU com calibração | `models/` |
| Backtest | Decisão no fecho, entrada na abertura seguinte, custos, cada sinal passa pelo motor de risco | `backtesting/engine.py`, `backtesting/metrics.py` |
| Motor de risco | Determinístico e com a última palavra: confiança, expectativa depois de custos, spread, volatilidade, posições, perda diária, drawdown, alavancagem (ESMA), tamanho pela perda no stop; sabe dizer «não negociar» | `risk/engine.py` |
| Kill switch | Independente (ficheiro ou `TRADING_KILL_SWITCH=1`), acionável pelo Telegram e pela API | `risk/kill_switch.py` |
| Execução | Corretora simulada (spread, slippage, comissões) e reconciliação de posições | `execution/paper.py` |
| Telegram | Notificações e comandos `/status /portfolio /performance /pause /resume /stop`, só de chats autorizados; modo seco sem token | `notifications/telegram.py` |
| API e painel | FastAPI (`/status`, `/performance`, kill switch com token) e painel HTML | `apps/api/main.py`, `apps/dashboard/` |
| Multi-tenant | Tenant com risco, contas, segredos por nome e papéis; negociação real recusada por construção | `tenants/models.py` |
| Observabilidade | Logs JSON com segredos mascarados | `monitoring/logging_setup.py` |

### Testes

`pytest`: **23 de 23 passam**. Destaques:
- mudar os preços futuros não altera nenhuma feature do passado (sem fuga de informação);
- triple-barrier conservador e sem rótulos além do fim dos dados;
- purging e embargo verificados entre treino, validação e teste;
- o motor de risco veta e diz porquê; o kill switch vence qualquer probabilidade;
- qualquer corretora não simulada é recusada; a configuração nunca liga negociação real;
- comandos do Telegram só de chats autorizados; logs sem segredos; a API exige token para mudar estado.

Lint (`ruff`): sem erros.

### Dados reais obtidos

| Mercado | Fonte | Período | Velas | Qualidade |
|---|---|---|---|---|
| BTC/USD | Coinbase Exchange | 01/01/2023 a 22/10/2026 | 33 364 (1 h) | 111 duplicados removidos, 13 em falta (0,04%), maior intervalo 6 h |
| EUR/USD | Dukascopy | 01/2022 a 10/2026 (em curso) | pendente | 14 meses guardados em cache; recolha bloqueada pelo servidor (ver D) |

Ciclo de paper trading ao vivo testado (`scripts/paper_trade_once.py`): BTC/USD a 81 081 USD (Kraken, spread
0,12 bps), probabilidade estimada de 30% nos dois lados; o motor de risco decidiu **não negociar**
(expectativa de -59,5 bps depois de custos) e explicou porquê.

## B. Machine Learning

**Features:** `ret_1, ret_3, ret_6, ret_12, ret_24, vol_24, vol_72, rsi_14, ema_12_48, close_ema_96, atr_pct,
mom_24, range_pos_24, hour_sin, hour_cos, volume_z_72` (e `spread_bps` quando os dados têm bid/ask).

**Rotulagem:** TP = 2×ATR, SL = 1×ATR, horizonte 24 h. **Validação:** 5 folds walk-forward, metade mais recente
da amostra como teste, 15% final do treino como validação (early stopping, calibração, limiar).

### Resultados BTC/USD (teste fora da amostra: 28/11/2024 a 22/10/2026, depois de custos)

Custo ida e volta pressuposto: 56 bps (taxa taker 25 bps por lado, spread 2 bps, slippage 2 bps por lado).

| Modelo | Operações | Retorno líquido | Acerto | Expectativa por operação | Profit factor | Max drawdown |
|---|---|---|---|---|---|---|
| A. Regras, com o risco | 0 (vetadas por expectativa negativa) | 0% | | | | 0% |
| A. Regras sem filtro (diagnóstico) | 96 | -10,0% | 34,4% | -54,9 bps | 0,39 | -10,0% (parou no limite) |
| B. XGBoost | 14 | -1,3% | 42,9% | -48,0 bps | 0,33 | -1,9% |
| C. GRU | 19 | -2,4% | 36,8% | -62,7 bps | 0,38 | -2,5% |
| Não negociar | 0 | 0% | | | | 0% |
| Comprar e manter (referência) | | -15,1% | | | | -53,9% |

**Classificação no teste:** ROC-AUC 0,52 e 0,50 (XGBoost, comprado e vendido), 0,51 e 0,49 (GRU); calibração
quase plana. O TP vem primeiro em cerca de 30% dos casos.

### Leitura

1. **Não há vantagem preditiva** nesta configuração: um AUC entre 0,49 e 0,52 é o nível do acaso.
2. **Os custos decidem:** o resultado bruto das regras é praticamente zero e o custo de 56 bps leva o resto.
3. **O motor de risco fez o que devia:** decidiu não negociar, melhor do que todos os modelos e do que comprar e
   manter no período.
4. **Limitações:** só features técnicas horárias e um horizonte; 14 a 19 operações em B e C são poucas para
   concluir (Sharpe não calculado abaixo de 30 operações); custos de cripto são pressupostos, não da conta real.

Não se conclui que não exista vantagem em BTC; conclui-se que esta configuração não a tem.

## C. Infraestrutura

**Disponível:** Ubuntu 24.04, Python 3.12, XGBoost 3.4, PyTorch 2.14 (CPU), scikit-learn 1.9, CCXT 4.5, Docker,
gcloud com 6 projetos (nenhum de trading), GitHub com token de permissão `repo`.

**Preparado, não publicado:** `Dockerfile`, `docker-compose.yml` (API + MongoDB local),
`infra/gcp/deploy.sh` (Cloud Run para API e painel, Cloud Run Jobs para recolha e treino, Cloud Scheduler,
Secret Manager, Cloud Storage).

**Estimativa de custos mensais** (valores de referência, a confirmar na calculadora oficial):

| Cenário | Custo |
|---|---|
| Desenvolvimento e experimentação | 0 a 10 USD |
| Paper trading contínuo | 25 a 90 USD |
| SaaS com 100 tenants | 250 a 650 USD (sem contar jurídico, suporte e segurança) |

Créditos promocionais da Google Cloud e do MongoDB Atlas: não confirmados.

**Armazenamento (decisão):** Parquet (local ou Cloud Storage) para séries e datasets; MongoDB Atlas para a operação
(sinais, ordens, auditoria, configuração por tenant). Sem base vetorial. Detalhe em `docs/adr/0002-armazenamento.md`.

## D. Próximas ações

### Bloqueios técnicos
1. **EUR/USD:** a Dukascopy limitou a cadência e depois deixou de aceitar ligações deste endereço. 14 meses já estão
   em cache; o recolhedor retoma sozinho e a investigação corre quando os dados estiverem completos.
2. **CI no GitHub:** o token não tem a permissão `workflow`; o ficheiro está em `infra/ci/github-actions-ci.yml`.
   Para ativar, movê-lo para `.github/workflows/ci.yml` com outra credencial ou pela interface web.

### Credenciais e acessos necessários
- Conta OANDA Practice: `OANDA_API_TOKEN` e `OANDA_ACCOUNT_ID` (preço Forex ao vivo e velas com bid/ask).
- MongoDB Atlas: `MONGODB_URI` (o plano gratuito M0 chega para desenvolvimento).
- Telegram: `TELEGRAM_BOT_TOKEN` e `TELEGRAM_ALLOWED_CHAT_IDS`.
- Google Cloud: autorização para criar um projeto dedicado e associar faturação.

### Bloqueios legais
Cobrar por operação ou operar por conta de terceiros exige parecer jurídico prévio: CMVM (DMIF II), Banco de
Portugal e MiCA (Regulamento (UE) 2023/1114). Nada disso está ativado. Análise de partida em
`SAAS_ARCHITECTURE.md`.

### Próximas tarefas de investigação
1. Custos mais baixos: ordens limite (taxa maker) e custos reais por conta.
2. Horizontes mais longos (4 h, diário), onde o custo pesa menos face ao movimento.
3. Filtros de regime: negociar só quando a volatilidade justifica o custo.
4. Investigação EUR/USD assim que os dados estiverem completos.

## Como reproduzir

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,nn]"
python scripts/fetch_data.py                                      # recolhe dados reais
python scripts/run_research.py --symbol "BTC/USD" --source coinbase
python scripts/paper_trade_once.py --symbol "BTC/USD"             # um ciclo ao vivo, só simulação
pytest -q
```

## Documentos relacionados

`README.md`, `ARCHITECTURE.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `SECURITY.md`, `SAAS_ARCHITECTURE.md`,
`docs/data-sources.md`, `docs/gcp-costs.md`, `docs/research-results.md`, `docs/adr/`.
