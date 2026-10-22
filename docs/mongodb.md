# MongoDB Atlas

## Estado e recursos (fase 3)

Recursos já criados (não criar outros): organização `6a97478c4b161a79239cafe2`, projeto **Trading AI Agent**
(`6ada846a7dcd22b453a73fac`), cluster **`trading-ai-m0`** (M0 gratuito, AWS `US_EAST_1`). Os 500 USD de créditos
promocionais são do Atlas (não da GCP) e não são precisos enquanto o cluster for M0.

## Ligação pela Atlas CLI (Workstation)

```bash
atlas auth login                                   # interativo: o dono autoriza no navegador
atlas config set project_id 6ada846a7dcd22b453a73fac
scripts/atlas_setup.sh                             # utilizador readWrite só em trading_agent + IP temporário + .env
python scripts/mongo_init.py                       # coleções e índices
```

`scripts/atlas_setup.sh` gera a palavra-passe localmente, escreve a `MONGODB_URI` só no `.env` (permissões 600,
fora do Git) e nunca a imprime. O IP da Workstation entra na lista de acesso com expiração (`--deleteAfter`), porque
o IP de saída pode mudar; o da VM entra como permanente depois de criada (IP estático).

| Item | Valor |
|---|---|
| Utilizador | `trading-ai-agent`, papel `readWrite@trading_agent` (nada mais) |
| Lista de acesso | IP da Workstation (temporário) e IP estático da VM `trading-ai-worker`. Nunca `0.0.0.0/0` |
| URI | `mongodb+srv://trading-ai-agent:<palavra-passe>@<host>/trading_agent?retryWrites=true&w=majority`: `.env` local ou segredo `trading-ai-mongodb-uri` |

Sem `MONGODB_URI`, o agente usa SQLite local (`data/state.db` e `data/operacao.db`) com o MESMO contrato.

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
| `tenants` | Registo do tenant (só o pessoal nesta fase): membros, risco, nomes dos segredos, subscrição | **único** `tenant_id` |
| `model_versions` | Modelos carregados (id, estado de aprovação, SHA-256) | **único** `(tenant_id, model_id)` |
| `state` | Estado partilhado: kill switch, contas virtuais, velas processadas, pedidos de fecho | `_id` = chave |

Os índices únicos são a segunda linha de defesa contra duplicados depois de um reinício (a primeira é a
reclamação atómica da vela em `state`).

## O que NÃO vai para o MongoDB

Séries históricas, features e modelos ficam em Parquet e em ficheiros versionados (local ou Cloud Storage):
são lidos inteiros pelo treino e não precisam de consultas por documento (ver `docs/adr/0002-armazenamento.md`).
