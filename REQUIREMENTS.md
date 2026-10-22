# Requisitos

## Funcionais (fase 1)

| ID | Requisito | Estado |
|---|---|---|
| RF-01 | Dois mercados: EUR/USD (Forex) e BTC/USD (cripto) | Feito |
| RF-02 | Interface abstrata de corretora; trocar de plataforma sem mexer no motor | Feito |
| RF-03 | Histórico, preço atual, UTC, falhas e duplicados, OHLCV, spreads e custos por mercado | Feito |
| RF-04 | Ordens simuladas e reconciliação de posições | Feito |
| RF-05 | Modelos A (regras), B (XGBoost), C (GRU) comparados com «não negociar» | Feito |
| RF-06 | Rotulagem triple-barrier, walk-forward com purging/embargo | Feito |
| RF-07 | Motor de risco determinístico com a última palavra e capacidade de não negociar | Feito |
| RF-08 | Kill switch independente | Feito |
| RF-09 | Telegram: notificações e comandos autenticados | Feito (modo seco sem token) |
| RF-10 | MongoDB Atlas para a operação | Implementado, sem credenciais |
| RF-11 | Infraestrutura GCP (Cloud Run, Jobs, Scheduler, GCS, Secret Manager) | Ficheiros prontos, não publicado |
| RF-12 | Base multi-tenant (identidade, risco, credenciais, histórico, permissões) | Modelo feito; sem autenticação ainda |

## Não funcionais

- Nenhuma ordem real; segredos fora do código e dos logs.
- Reprodutibilidade: sementes fixas, manifesto de cada dataset (fonte, período, qualidade, `synthetic=false`).
- Testes automáticos na CI sem acesso à Internet.
- Python 3.11+, dependências em `pyproject.toml`.
