# Hipótese 2: informação que as velas não têm (pré-registo)

Escrito e guardado no Git **antes** de descarregar os dados e de correr (23/10/2026). Os critérios não mudam
depois de ver os resultados. Conta como tentativa nova (`ROADMAP.md`).

## Porquê

As 75 tentativas anteriores usaram só preço e volume das velas, e nem com custo zero houve vantagem bruta
significativa. A H1 e a H3 reprocessaram a mesma informação. A H2 junta **dados de posicionamento e de fluxo**
que as velas não contêm:

| Variável | Fonte (pública, sem conta) | Frequência | O que mede |
|---|---|---|---|
| Funding rate do perpétuo BTCUSDT | Binance `fapi/v1/fundingRate` | 8 h | Quem paga para manter posições: alavancagem comprada ou vendida |
| Prémio do perpétuo sobre o índice | Binance `fapi/v1/premiumIndexKlines` | 1 h | Pressão no perpétuo face ao spot (base) |
| Open interest do perpétuo BTCUSDT | Bybit `v5/market/open-interest` | 1 h | Entrada ou saída de alavancagem |
| Volume comprador agressivo (taker buy) | Binance spot `api/v3/klines` | 1 h | Desequilíbrio do fluxo de ordens |

O open interest vem da Bybit porque o histórico público da Binance só guarda 30 dias. Os preços negociados
continuam a ser os da Coinbase BTC/USD: as variáveis acima entram **só como features**.

## Causalidade

- Cada vela de 1 h com abertura em `t` fecha em `t+1h`; a decisão acontece nesse fecho.
- Funding: o último valor com `fundingTime ≤ fecho`. Open interest: o último instantâneo com `timestamp ≤ fecho`.
  Prémio e taker buy: a vela de 1 h com a mesma abertura (já fechada no momento da decisão).
- Em 4 h: agregação das horas que pertencem à vela (soma no fluxo, último valor no OI, no funding e no prémio).
- Um teste verifica que alterar os dados derivados depois de `t` não muda as features até `t`.

## Features (conjunto `v3` = `v2` + estas)

`funding` (último), `funding_media_72h`, `funding_z_30d`, `premio` (último), `premio_media_24h`, `premio_z_30d`,
`taker_desequilibrio` (vela), `taker_desequilibrio_24h`, `oi_var_4h`, `oi_var_24h`, `oi_z_30d`. As janelas em
horas convertem-se em velas em cada timeframe.

## Experiências (4 tentativas)

O pipeline e as regras da fase 2 ficam intactos: rótulos triple-barrier, walk-forward com embargo, treino,
validação, calibração e teste separados; desenvolvimento = 4 primeiros blocos de teste, teste final = 2 últimos;
custos do `configs/default.toml` (BTC: 25 bps de comissão, 2 de spread e 2 de slippage por lado); só posições
compradas. Modelo B (XGBoost).

| # | Experiência |
|---|---|
| 1 | BTC/USD 1h, horizonte 24, TP 2 ATR / SL 1 ATR, v3 |
| 2 | BTC/USD 1h, horizonte 24, TP 1 / SL 1, v3 |
| 3 | BTC/USD 4h, horizonte 12, TP 2 / SL 1, v3 |
| 4 | BTC/USD 4h, horizonte 12, TP 1 / SL 1, v3 |

## Critério (o mesmo da fase 2)

Uma experiência **qualifica** se, no desenvolvimento, tiver pelo menos 30 operações e o IC95% da expectativa
líquida por operação (bootstrap por blocos) ficar inteiramente acima de zero. Se várias qualificarem, escolhe-se a
de maior expectativa no desenvolvimento. A hipótese é **confirmada** só se a escolhida tiver também expectativa
líquida positiva no **teste final**. Mesmo assim, o modelo vai apenas para observação: nunca é aprovado
automaticamente para paper trading com posições.

## Diagnóstico (informativo, não seleciona)

Para separar «a informação nova ajuda a prever» de «os custos comem tudo»: as mesmas 4 experiências com custo
zero, em `v3` e em `v2`, comparando a expectativa bruta e o AUC no desenvolvimento. Se a `v3` não melhorar
nem a previsão bruta, a informação de derivados não tem valor preditivo neste formato.
