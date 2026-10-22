# Fontes de dados e corretoras

Verificado a 22/10/2026 a partir do ambiente de desenvolvimento (pedidos reais, sem credenciais).

## Datasets usados na fase 2

| Dataset | Fonte | Período | Velas | Qualidade |
|---|---|---|---|---|
| `dukascopy_EURUSD_1h` | Dukascopy (bid + spread real) | 02/01/2022 a 30/09/2026 | 29 600 | 280 em falta (0,94%, sobretudo feriados), maior intervalo 3 dias (fins de semana) |
| `coinbase_BTCUSD_1h` | Coinbase Exchange | 01/01/2023 a 22/10/2026 | 33 364 | 111 duplicados removidos, 13 em falta (0,04%) |
| `coinbase_BTCUSD_15m` | Coinbase Exchange | 01/10/2024 a 22/10/2026 | 72 121 | 240 duplicados removidos, 52 em falta (0,07%) |

Cada dataset tem um manifesto (`*.manifest.json`) com fonte, período, qualidade e `synthetic: false`; o modelo
gravado guarda o SHA-256 do ficheiro com que treinou. 4 h e 1 d obtêm-se por reamostragem (`data/resample.py`).

**Limites conhecidos.** A Dukascopy não publica o ficheiro mensal do mês corrente (outubro de 2026 fica de fora; os
ficheiros diários do mês corrente não foram implementados). EUR/USD em 15 min exigiria ficheiros diários de minutos
(cerca de 3 500 pedidos), inviável com o limite de cadência da Dukascopy: o horizonte de 15 min só foi estudado em
BTC/USD.

**Não misturar fontes sem reconciliação.** O agente ao vivo usa a MESMA fonte do treino (Coinbase para BTC/USD).
Para EUR/USD ao vivo é precisa a OANDA Practice (bid/ask, a mesma convenção da Dukascopy); antes de a usar com um
modelo treinado na Dukascopy há que comparar as duas fontes no período comum (preços, spreads e volume, que na OANDA
é número de ticks). A Kraken EUR/USD é um mercado de uma bolsa cripto: serve apenas como taxa de conversão da conta
em EUR, nunca como dados do mercado negociado.

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
