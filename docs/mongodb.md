# MongoDB Atlas

## Estado (22/10/2026)

**Sem acesso.** O ambiente não tem `MONGODB_URI`, nem a CLI do Atlas, nem configuração local. Nenhuma URI ou
credencial foi inventada. Enquanto não houver, o agente usa SQLite local (`data/state.db` e `data/operacao.db`)
com o MESMO contrato; a implementação MongoDB está testada contra `mongomock` (`tests/test_agent.py`).

## O que é preciso (e só isto)

| Item | Onde se obtém | Onde se guarda |
|---|---|---|
| Conta Atlas e um cluster **M0** (gratuito, 512 MB) | cloud.mongodb.com | |
| Utilizador de base de dados com papel `readWrite` só na base `trading_agent` | Atlas → Database Access | |
| Lista de acesso de rede: o IP de saída do worker (VM) e o da estação de trabalho | Atlas → Network Access | |
| A URI `mongodb+srv://<utilizador>:<palavra-passe>@<cluster>/trading_agent?retryWrites=true&w=majority` | Atlas → Connect → Drivers | variável `MONGODB_URI` (`.env` local, nunca no Git) ou segredo `mongodb-uri` no Secret Manager |

Com a variável definida, `default_store()` e `default_repository()` passam a usar o Atlas sem mudar código, e os
índices são criados no primeiro arranque. Para os criar antes: `python scripts/mongo_init.py`.

## Coleções e índices

Todas com `tenant_id` obrigatório e `ts` (UTC). Definidas em `src/trading_agent/persistence/repository.py`.

| Coleção | Conteúdo | Índices |
|---|---|---|
| `decisions` | Cada decisão por vela: proposta do modelo, custo, expectativa, aprovação, motivos, idade dos dados | `(tenant_id, symbol, bar_time)`; **único** `(tenant_id, decision_id)` |
| `orders` | Ordens simuladas (estado, execução, duplicadas) | **único** `(tenant_id, client_order_id)`; `(tenant_id, ts)` |
| `trades` | Operações encerradas, com resultado bruto, custo e líquido | `(tenant_id, symbol, exit_time)` |
| `positions` | Fotografia das posições abertas em cada ciclo | `(tenant_id, symbol, ts)` |
| `equity` | Saldo, equity, capital comprometido e disponível em cada ciclo | `(tenant_id, ts)` |
| `risk_events` | Vetos, limite diário, drawdown | `(tenant_id, ts)`; `(tenant_id, kind, ts)` |
| `events` | Arranques, falhas de API, recuperações, erros, reconciliações | `(tenant_id, ts)`; `(tenant_id, level, ts)` |
| `model_versions` | Modelos carregados (id, estado de aprovação, SHA-256) | **único** `(tenant_id, model_id)` |
| `state` | Estado partilhado: kill switch, contas virtuais, velas processadas, pedidos de fecho | `_id` = chave |

Os índices únicos são a segunda linha de defesa contra duplicados depois de um reinício (a primeira é a
reclamação atómica da vela em `state`).

## O que NÃO vai para o MongoDB

Séries históricas, features e modelos ficam em Parquet e em ficheiros versionados (local ou Cloud Storage):
são lidos inteiros pelo treino e não precisam de consultas por documento (ver `docs/adr/0002-armazenamento.md`).
