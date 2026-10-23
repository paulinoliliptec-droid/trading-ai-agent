# Trading AI Agent

Investigação quantitativa e **paper trading** autónomo para Forex (EUR/USD) e cripto (BTC/USD), em Python.

> **Só simulação.** Não existe nenhum caminho no código para enviar ordens reais: o único executor é a conta
> virtual (`PaperAccount`), e o motor recusa qualquer outro. Nada aqui é aconselhamento financeiro.

**Estado (22/10/2026):** a infraestrutura de investigação e de operação está pronta e testada; a investigação da
fase 2 **não encontrou vantagem estatística líquida** em nenhuma configuração, por isso não há modelo aprovado e o
agente corre em modo de observação. Detalhe em [RELATORIO.md](RELATORIO.md).

## O que faz

1. **Dados reais** com qualidade verificada: EUR/USD da Dukascopy (velas horárias com bid e ask), BTC/USD da
   Coinbase (1 h e 15 min); reamostragem para 4 h e 1 d sem inventar velas.
2. **Features sem fuga de informação** (v1 e v2: regimes, volatilidade realizada, liquidez, custo em ATR) e
   rótulos **triple-barrier**.
3. **Experiências comparáveis**: modelos A (regras), B (XGBoost), C (GRU) e D (ensemble validado), em walk-forward
   com treino, validação, calibração e teste separados por embargo; seleção pré-registada só no período de
   desenvolvimento; teste final apenas reportado; bootstrap por blocos, Monte Carlo e análise por regime.
4. **Backtest cronológico** vela a vela através da MESMA conta virtual da operação (custos, gaps, margem).
5. **Agente persistente**: preço → última vela fechada → inferência com modelo versionado → risco → ordem simulada
   → gestão de posições → registos → notificações; recupera de falhas, não duplica depois de reinícios.
6. **Risco independente** com a última palavra e kill switch partilhado entre agente, API e Telegram.

## Começar

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,nn]"
cp .env.example .env                                   # nada é obrigatório para investigar
python scripts/fetch_data.py                           # EUR/USD (Dukascopy) e BTC/USD (Coinbase), 1 h
python scripts/fetch_data.py --so BTC/USD --timeframe 15m --btc-desde 2024-10-01
python scripts/run_experiments.py                      # grelha completa (cerca de 45 min em 4 CPU)
python scripts/report_fase2.py                         # tabelas em docs/research-results-fase2-tabelas.md
python scripts/train_model.py --experiencia BTCUSD_4h_h12_tp2_sl1_v2   # grava o modelo com o estado de aprovação
python scripts/run_agent.py --symbol BTC/USD           # agente contínuo (observação se o modelo não for aprovado)
python scripts/capital_check.py                        # 100 € chegam para cada mercado?
pytest -q
uvicorn apps.api.main:app --port 8080                  # API e painel
```

### Modo de observação com Atlas e Telegram (operação pessoal)

```bash
atlas auth login && scripts/atlas_setup.sh             # utilizador readWrite@trading_agent e MONGODB_URI no .env
python scripts/mongo_init.py && python scripts/tenant_init.py
python scripts/run_agent.py --symbol BTC/USD           # observação por omissão: decide e regista, não abre posições
python scripts/run_telegram_bot.py                     # UMA instância por bot; sai se houver webhook ou outro consumidor
docker compose --profile telegram up -d                # o mesmo em contentores, com o Atlas (sem MongoDB local)
python scripts/observation_report.py --dias 5          # relatório do teste de cinco dias (docs/observacao-5-dias.md)
```

## Documentação

| Documento | Conteúdo |
|---|---|
| [RELATORIO_FASE3.md](RELATORIO_FASE3.md) | **Relatório da fase 3: integração, hipóteses H1, H2 e H3, conclusões e recomendações** |
| [RELATORIO.md](RELATORIO.md) | Relatório da fase 2: problemas, correções, testes, resultados, estado e próximos passos |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Camadas, fluxo treino/inferência, regras garantidas pelos testes |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Requisitos e estado |
| [ROADMAP.md](ROADMAP.md) | Fases, hipóteses seguintes e dependências |
| [SECURITY.md](SECURITY.md) | Princípios de segurança |
| [SAAS_ARCHITECTURE.md](SAAS_ARCHITECTURE.md) | Multi-tenant, modelos comerciais, enquadramento regulatório a validar |
| [docs/research-results-fase2.md](docs/research-results-fase2.md) | Leitura dos resultados da fase 2 |
| [docs/research-results-fase2-tabelas.md](docs/research-results-fase2-tabelas.md) | Todas as tabelas (geradas) |
| [docs/mongodb.md](docs/mongodb.md) | Coleções, índices e o que falta para o Atlas |
| [docs/data-sources.md](docs/data-sources.md) | Fontes e corretoras verificadas |
| [docs/gcp-costs.md](docs/gcp-costs.md) | Arquitetura GCP e custos por cenário (operação pessoal no projeto da Serafy) |
| [docs/fase3-integracao.md](docs/fase3-integracao.md) | Resumo da fase 3: Atlas, Telegram, GCP, estado e pendentes |
| [docs/research-results-h3.md](docs/research-results-h3.md) | Hipótese 3 (volatilidade): pré-registo, resultados e leitura |
| [docs/observacao-5-dias.md](docs/observacao-5-dias.md) | Programa do teste de observação de cinco dias |
| [docs/adr/](docs/adr/) | Decisões de arquitetura |
