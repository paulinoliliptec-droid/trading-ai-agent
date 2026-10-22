# ADR 0001: estrutura do projeto

**Decisão.** Código num pacote único `src/trading_agent/` (layout `src`), com os subpacotes pedidos
(`data`, `features`, `models`, `strategies`, `risk`, `execution`, `brokers/{forex,crypto}`, `backtesting`,
`notifications`, `tenants`, `monitoring`) mais `labels/` para a rotulagem. Aplicações em `apps/` (API e painel).

**Desvios em relação à proposta inicial, e porquê:**

- `models/xgboost/` passou a `models/xgboost_model/`: um pacote chamado `xgboost` dentro do projeto confunde
  a importação da biblioteca com o mesmo nome. Pela mesma razão `models/baseline/` em vez de pôr as regras em
  `strategies/`.
- `labels/` à parte de `features/`: as features só olham para o passado; os rótulos olham para o futuro por
  definição. Separá-los torna a fronteira visível e testável.
- Um pacote instalável (`pip install -e .`) em vez de `src/` com caminhos soltos: os testes, os scripts e a
  API importam o mesmo código.

**Consequências.** Acrescentar uma corretora é escrever um adaptador em `brokers/` que implemente
`MarketDataSource` e, quando houver autorização para isso, `ExecutionVenue`. O motor não muda.
