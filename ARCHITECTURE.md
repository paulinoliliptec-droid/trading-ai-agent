# Arquitetura

```
 Fontes de dados                     Investigação (offline)                         Operação (paper trading)
 ───────────────                     ──────────────────────                         ────────────────────────
 Dukascopy (EUR/USD bid/ask) ─┐      features/build.py   (só passado)
 Coinbase  (BTC/USD)          ├─► data/quality.py ─► labels/triple_barrier.py (futuro, à parte)
 Kraken/CCXT (preço atual)    │      (UTC, duplicados,   backtesting/splits.py  (walk-forward, purging, embargo)
 OANDA v20 Practice (token)  ─┘       falhas)            models/ A regras · B XGBoost · C GRU
                                │                        backtesting/engine.py ──► risk/engine.py
                                ▼                        backtesting/metrics.py      ▲
                        data/store.py                    reports/*.json              │ última palavra
                        Parquet (local / gs://)                                      │
                        MongoDB Atlas (operação)        Sinal do modelo ──► RiskEngine ──► PaperBroker ──► reconcile()
                                                                              ▲              │
                                                        KillSwitch ───────────┘              ▼
                                                        Telegram (/pause /stop) ◄── notifications/telegram.py
                                                        API FastAPI (/status /performance /killswitch) + painel
```

## Camadas

| Camada | Módulo | Responsabilidade |
|---|---|---|
| Corretoras | `brokers/base.py` | Contratos `MarketDataSource` e `ExecutionVenue`; tipos `Quote`, `Order`, `Fill`, `Position` |
| Dados | `brokers/*`, `data/` | Recolha, normalização UTC, qualidade, armazenamento com manifesto |
| Features | `features/build.py` | Retornos, volatilidade, RSI, EMA, ATR, momentum, posição na amplitude, hora, volume, spread |
| Rótulos | `labels/triple_barrier.py` | TP/SL/tempo, entrada na abertura seguinte, empate TP+SL na mesma vela = SL |
| Validação | `backtesting/splits.py` | Walk-forward, purging por `t1`, embargo |
| Modelos | `models/` | A (regras), B (XGBoost calibrado), C (GRU calibrada) |
| Risco | `risk/` | Motor determinístico com a última palavra; kill switch |
| Execução | `execution/paper.py` | Corretora simulada com spread, slippage, comissões; reconciliação |
| Backtest | `backtesting/engine.py` | Sinal → risco → operação; custos; uma posição de cada vez |
| Operação | `notifications/`, `apps/api`, `apps/dashboard` | Telegram, API, painel |
| SaaS | `tenants/` | Tenant, papéis, referências a segredos |
| Observabilidade | `monitoring/` | Logs JSON com segredos mascarados |

## Regras de investigação (no código e nos testes)

- A feature de t só usa dados até ao fecho de t (teste: mudar o futuro não muda o passado).
- Decisão no fecho de t, entrada na abertura de t+1.
- Treino, validação e teste em ordem cronológica; purging das amostras cujo resultado entra no período seguinte;
  embargo de 24 velas.
- Hiperparâmetros fixos e conservadores; limiar de decisão escolhido só na validação.
- Comparação obrigatória com o baseline de regras, com «não negociar» e com «comprar e manter» no mesmo período.
- Accuracy não é métrica de sucesso; contam expectativa líquida, profit factor, drawdown e estabilidade entre folds.
