# Trading AI Agent

Investigação quantitativa e **paper trading** para Forex (EUR/USD) e cripto (BTC/USD), em Python.

> **Só simulação.** Não existe nenhum caminho no código para enviar ordens reais: o único executor é o
> `PaperBroker`, e o motor recusa qualquer outro. Nada aqui é aconselhamento financeiro.

## O que faz

1. **Recolhe dados reais** e verifica a qualidade (UTC, duplicados, falhas, velas incoerentes):
   EUR/USD da Dukascopy (velas horárias com bid e ask), BTC/USD da Coinbase, preço atual pela Kraken (CCXT).
   A OANDA v20 (Practice) está pronta e espera um token.
2. **Constrói features sem fuga de informação** e rótulos **triple-barrier** (take-profit, stop-loss, tempo).
3. **Treina e compara três modelos** em validação walk-forward com purging e embargo:
   A, regras (EMA, RSI, momentum, ATR); B, XGBoost calibrado; C, GRU calibrada.
   Compara sempre com «não negociar» e com «comprar e manter».
4. **Backtest com custos** (spread real ou pressuposto, comissões, slippage), passando cada sinal pelo
   **motor de risco**, que tem a última palavra e sabe dizer «não negociar».
5. **Opera em simulação**: kill switch independente, notificações e comandos no Telegram, API e painel.

## Começar

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,nn]"
cp .env.example .env            # preencher só o que houver; nada é obrigatório para investigar
python scripts/fetch_data.py    # recolhe EUR/USD (Dukascopy) e BTC/USD (Coinbase)
python scripts/run_research.py --symbol "BTC/USD" --source coinbase
python scripts/run_research.py --symbol "EUR/USD" --source dukascopy
pytest -q
uvicorn apps.api.main:app --port 8080   # painel em http://localhost:8080
```

Os resultados ficam em `reports/{PAR}_{data}.json` e no painel.

## Documentação

| Documento | Conteúdo |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Camadas, fluxo de dados, regras de investigação |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Requisitos e estado |
| [ROADMAP.md](ROADMAP.md) | Fases e critérios para avançar |
| [SECURITY.md](SECURITY.md) | Princípios de segurança |
| [SAAS_ARCHITECTURE.md](SAAS_ARCHITECTURE.md) | Multi-tenant, modelos comerciais, enquadramento regulatório a validar |
| [docs/data-sources.md](docs/data-sources.md) | Fontes e corretoras verificadas |
| [docs/gcp-costs.md](docs/gcp-costs.md) | Arquitetura GCP e custos por cenário |
| [docs/adr/](docs/adr/) | Decisões de arquitetura |
| [docs/research-results.md](docs/research-results.md) | Resultados da investigação |
