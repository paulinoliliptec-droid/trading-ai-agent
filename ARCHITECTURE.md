# Arquitetura

```
 TREINO (offline, Cloud Run Job semanal)                      INFERÊNCIA (contínua, VM e2-micro)
 ───────────────────────────────────────                      ───────────────────────────────────
 Dukascopy (EUR/USD bid/ask 1h)  ─┐                           Coinbase (BTC/USD) / OANDA Practice (EUR/USD)
 Coinbase (BTC/USD 1h e 15m)     ─┤                                  │ velas recentes + cotação
                                  ▼                                  ▼
 data/quality.py → Parquet + manifesto                        agent/worker.py  (ciclo a cada 60 s)
 data/resample.py (4h, 1d)                                      1. posições: SL / TP / tempo / restos parciais
 features/build.py (v1, v2) · labels/triple_barrier.py          2. última vela FECHADA, idade dos dados
 backtesting/splits.py  treino|val|calib|TESTE (embargo)        3. vela já processada? (claim atómico) → sai
 research/pipeline.py   A regras · B XGBoost · C GRU · D        4. features → TrainedPolicy.decide()  (sem treinar)
 backtesting/engine.py  ──► PaperAccount ◄──────────────┐       5. RiskEngine (independente)  ──► veta e diz porquê
 seleção pré-registada (só desenvolvimento)             │       6. PaperAccount.submit (id determinístico)
 scripts/train_model.py ──► models/registry.py ─────────┼──►    7. registos (Repository) · notificações
   artefacto + SHA-256 + estado de aprovação            │       8. estado (StateStore)
                                                        │
                       MESMA conta virtual no backtest e na operação
                                                                     │                ▲
                       StateStore (SQLite local / MongoDB Atlas) ◄───┴──── kill switch, contas, velas processadas
                       Repository (SQLite local / MongoDB Atlas): decisões, ordens, operações, posições,
                       equity, risco, eventos, versões de modelos
                                                                     ▲                ▲
                                     bot do Telegram (processo próprio)        API FastAPI + painel
                                     /status /portfolio /performance           /status /decisions /portfolio
                                     /pause /resume /stop                      /killswitch (com token)
```

## Camadas

| Camada | Módulo | Responsabilidade |
|---|---|---|
| Corretoras e dados | `brokers/` | `MarketDataSource` e `ExecutionVenue`; Coinbase, Dukascopy, Kraken, OANDA Practice (só leitura) |
| Qualidade e reamostragem | `data/quality.py`, `data/resample.py` | UTC, duplicados, falhas, velas impossíveis; 4 h e 1 d sem inventar velas |
| Features | `features/build.py`, `features/qualitative.py` | v1 e v2 (regimes, volatilidade realizada, liquidez, custos); qualitativa experimental |
| Rótulos e validação | `labels/`, `backtesting/splits.py` | Triple-barrier; walk-forward com treino, validação, calibração e teste separados |
| Modelos | `models/` | A regras, B XGBoost, C GRU; registo versionado com aprovação |
| Investigação | `research/pipeline.py` | Experiências, seleção pré-registada, bootstrap, regimes, consistência rótulo/execução |
| Execução | `execution/paper.py`, `execution/instruments.py` | Conta virtual (EUR/USD, margem, SL/TP/tempo, parciais, idempotência, persistência); especificação por instrumento; conversão cambial explícita |
| Backtest | `backtesting/engine.py` | Vela a vela, através da conta virtual; equity marcado a mercado |
| Risco | `risk/` | Motor determinístico e independente; kill switch partilhado com falha fechada |
| Agente | `agent/worker.py` | Ciclo persistente, recuperação, idempotência, relatórios |
| Persistência | `persistence/` | StateStore e Repository (SQLite e MongoDB) |
| Operação | `notifications/`, `apps/api`, `apps/dashboard` | Telegram (notificações e bot), API, painel |

## Regras que o código garante (e que os testes verificam)

- A feature, a decisão e o equity em t usam só dados até ao fecho de t (testes alteram o futuro e comparam).
- Decisão no fecho de t, execução na abertura de t+1; stop atravessado por gap sai à abertura.
- Nenhuma amostra de treino, validação ou calibração tem resultado dentro do teste; embargo entre partes.
- Nada do teste final escolhe parâmetros; nenhum limiar é escolhido: decide a expectativa depois de custos.
- O risco tem a última palavra; o kill switch bloqueia mesmo que o modelo ou a fonte falhem.
- O mesmo `client_order_id` nunca executa duas vezes; a mesma vela nunca é decidida duas vezes.
- Só há execução simulada; um modelo não aprovado corre em observação.
