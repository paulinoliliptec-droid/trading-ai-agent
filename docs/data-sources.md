# Fontes de dados e corretoras

Verificado a 22/10/2026 a partir do ambiente de desenvolvimento (pedidos reais, sem credenciais).

| Fonte | Uso no projeto | Acesso | Estado verificado |
|---|---|---|---|
| **Dukascopy** (datafeed público) | Histórico EUR/USD, velas horárias **bid e ask** (spread real) | Sem conta | Funcionou no 1.º pedido; depois limitou a cadência (429) e deixou de aceitar ligações durante um período. O adaptador guarda cada mês em cache e repete com espera. |
| **Coinbase Exchange** (público) | Histórico BTC/USD, velas horárias | Sem conta | HTTP 200 |
| **Kraken** (público, via CCXT) | Preço atual BTC/USD e EUR/USD; velas recentes | Sem conta | 200; OHLC público limitado às **últimas 720 velas** por intervalo |
| **OANDA v20** (Practice) | Velas e preços EUR/USD com bid/ask; candidata a corretora Forex | Token de conta Practice | 401 sem token (esperado). **Precisa de conta.** |

## Notas por fonte

- **Dukascopy**: horas de mercado fechado chegam com volume 0 e preço parado; são removidas. É um feed de um
  banco (Dukascopy Bank SA), não do interbancário agregado: adequado para investigação. Confirmar os termos de
  utilização antes de qualquer uso comercial dos dados.
- **Kraken EUR/USD** é um mercado de uma bolsa cripto (par ZEURZUSD), não o mercado cambial à vista. Serve como
  proxy de preço atual para o paper trading Forex enquanto não houver OANDA; os custos reais de Forex vêm do
  spread da Dukascopy.
- **Coinbase**: as velas não trazem bid/ask; o spread é um pressuposto (`spread_bps` em `configs/default.toml`).

## Corretoras candidatas (para execução futura, hoje só simulação)

| Mercado | Corretora | API | Portugal / UE | Observações |
|---|---|---|---|---|
| Forex | OANDA (OANDA Europe) | v20 REST/streaming | Confirmar elegibilidade de residentes em Portugal junto da OANDA Europe | Ambiente Practice gratuito; adaptador de leitura feito |
| Forex | Interactive Brokers | TWS API / Client Portal | Disponível na UE | API mais complexa; alternativa robusta |
| Cripto | Kraken | REST/WebSocket; CCXT | Kraken tem entidade na UE | Taxa taker de entrada ~0,25% (confirmar por conta) |
| Cripto | Coinbase (Advanced Trade) | REST/WebSocket; CCXT | Disponível na UE | Taxas de retalho altas para estratégias horárias |
| Cripto | Várias, via **CCXT** | Biblioteca unificada | Depende da bolsa | Usada para os dados públicos da Kraken |

Os limites de alavancagem do retalho na UE (ESMA, CFD) entram no risco: 30:1 em pares de moedas principais.
Cripto à vista é simulada sem alavancagem.
