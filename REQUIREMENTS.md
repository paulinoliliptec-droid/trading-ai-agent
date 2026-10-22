# Requisitos

## Funcionais

| ID | Requisito | Estado |
|---|---|---|
| RF-01 | Dois mercados: EUR/USD (Forex) e BTC/USD (cripto) | Feito |
| RF-02 | Interface abstrata de corretora | Feito |
| RF-03 | Histórico, preço atual, UTC, falhas e duplicados, OHLCV, spreads e custos por mercado | Feito |
| RF-04 | Conta virtual: saldo em EUR/USD, capital disponível e comprometido, realizado e não realizado, ordens parciais, SL/TP/tempo, idempotência, persistência, quantidade mínima, venda a descoberto só onde permitida | Feito (fase 2) |
| RF-05 | Backtest cronológico por eventos através da conta virtual | Feito (fase 2) |
| RF-06 | Modelos A (regras), B (XGBoost), C (GRU) e ensemble validado, comparados com «não negociar» e «comprar e manter» | Feito |
| RF-07 | Walk-forward com treino, validação, calibração e teste separados; purging e embargo | Feito (fase 2) |
| RF-08 | Horizontes 15 min (BTC), 1 h, 4 h, 1 d; TP/SL simétrico e assimétrico; features v2 | Feito (fase 2) |
| RF-09 | Incerteza: bootstrap por blocos e Monte Carlo; análise por regime | Feito (fase 2) |
| RF-10 | Componente qualitativa experimental, com regra «publicado até t» | Módulo e testes feitos; sem fonte de dados |
| RF-11 | Motor de risco independente: risco por operação, exposição, perda diária, drawdown, capital mínimo, posições, dados desatualizados, falhas de API, anomalias, expectativa depois de custos | Feito (fase 2) |
| RF-12 | Kill switch partilhado entre worker, API e Telegram, com falha fechada | Feito (fase 2), testado entre processos |
| RF-13 | Agente persistente com recuperação e prevenção de duplicados; treino separado da inferência; modelos versionados | Feito (fase 2) |
| RF-14 | MongoDB Atlas: coleções, índices, registos | Implementado e testado com mongomock; sem credenciais |
| RF-15 | Telegram: notificações (arranque, sinais, operações, resultado, drawdown, limite diário, falhas, relatórios) e comandos autenticados | Feito; sem token (modo seco) |
| RF-16 | GCP: inferência contínua e treino separados | Preparado, não publicado (sem autorização de custos) |
| RF-17 | Multimercado (Forex, cripto, ações, índices, ouro, petróleo, futuros) | Especificações declaradas e desativadas; só EUR/USD e BTC/USD ativos |

## Não funcionais

- Nenhuma ordem real; segredos fora do código e dos logs.
- Reprodutibilidade: sementes fixas, manifesto e SHA-256 dos dados e dos modelos.
- Testes automáticos sem acesso à Internet; lint, bandit e pip-audit.
- Python 3.11+, dependências em `pyproject.toml`.
