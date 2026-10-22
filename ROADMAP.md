# Roadmap

| Fase | Objetivo | Critério para avançar |
|---|---|---|
| **1. Investigação** (atual) | Dados reais, features, modelos A/B/C, backtest com custos, risco | Algum modelo com expectativa líquida positiva e estável em vários folds fora da amostra; caso contrário, iterar ou parar |
| 2. Paper trading contínuo | Worker na GCP com preço em tempo real (OANDA Practice, Kraken), Telegram ligado, registos no Atlas | 3 meses de paper trading coerentes com o backtest (desvio explicado) |
| 3. Endurecimento | Monitorização, alertas, testes de falha da corretora, auditoria completa | Incidentes simulados tratados sem intervenção manual |
| 4. Real com capital próprio (opcional) | Execução real numa conta própria, com limites mínimos | Decisão explícita do dono, revisão de risco, conta da corretora em nome próprio |
| 5. SaaS | Multi-tenant, autenticação, faturação por subscrição | Parecer jurídico e regulatório (CMVM, Banco de Portugal, MiCA) |

## Próximas tarefas (fase 1)

1. Conta OANDA Practice e token, para preço Forex em tempo real e velas com bid/ask da corretora.
2. Mais pares e horizontes, e análise de estabilidade por regime (volatilidade alta/baixa, tendência/lateral).
3. Custos reais por corretora (taxas por nível de volume) em vez de pressupostos.
4. Atlas M0 e ligação do `MongoRepository` ao worker de paper trading.
5. Projeto GCP dedicado (autorização de faturação) e publicação do worker.
