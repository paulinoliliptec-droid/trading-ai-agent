# Resultados da investigação

> Dados **reais**; nada sintético nos relatórios (`synthetic=false` no manifesto). Resultados fora da amostra,
> depois de custos. Relatórios completos em `reports/`.

## BTC/USD (Coinbase, velas de 1 hora), relatório de 22/10/2026

**Dados:** 33 364 velas, 01/01/2023 a 22/10/2026. Qualidade: 111 duplicados removidos (sobreposição entre
páginas), 13 velas em falta (0,04%), maior intervalo 6 horas.
**Teste fora da amostra:** 28/11/2024 a 22/10/2026 (5 folds walk-forward, purging e embargo de 24 velas).
**Rotulagem:** TP = 2×ATR, SL = 1×ATR, horizonte 24 h. O TP vem primeiro em 31% (comprado) e 30% (vendido).
**Custo ida e volta pressuposto:** 56 bps (taxa taker 25 bps por lado, spread 2 bps, slippage 2 bps por lado).

| Modelo | Operações | Retorno líquido | Acerto | Expectativa por operação | Profit factor | Max DD |
|---|---|---|---|---|---|---|
| A. Regras, com o risco | 0 | 0% | n/a | n/a (vetadas: expectativa negativa) | n/a | 0% |
| A. Regras sem filtro de expectativa (diagnóstico) | 96 | -10,0% | 34,4% | -54,9 bps | 0,39 | -10,0% (parou no limite de drawdown) |
| B. XGBoost | 14 | -1,3% | 42,9% | -48,0 bps | 0,33 | -1,9% |
| C. GRU | 19 | -2,4% | 36,8% | -62,7 bps | 0,38 | -2,5% |
| Não negociar | 0 | 0% | | | | 0% |
| Comprar e manter (referência) | | -15,1% | | | | -53,9% |

**Capacidade preditiva:** ROC-AUC no teste de 0,52 (XGBoost, comprado), 0,50 (XGBoost, vendido), 0,51 e 0,49
(GRU). Calibração quase plana: previsões de 0,24 a 0,39 para taxas observadas de 0,27 a 0,34.

**Leitura.**

1. **Não há vantagem estatística** nestas features, neste horizonte, para prever qual barreira vem primeiro.
   Um AUC de 0,50 a 0,52 é indistinguível do acaso.
2. **Os custos decidem.** O baseline negociado sem filtro tem expectativa de -55 bps por operação, quase igual
   ao custo (56 bps): o resultado bruto é praticamente zero e o custo leva o resto. Com taxas de retalho de
   0,25% por lado, uma estratégia horária em BTC precisa de uma vantagem bruta grande para sobreviver.
3. **O motor de risco fez o que devia:** vetou os 10 051 sinais das regras por expectativa negativa e decidiu
   não negociar, o que no período de teste foi melhor do que todos os modelos e do que comprar e manter.
4. **Amostras pequenas:** 14 e 19 operações não chegam para conclusões sobre B e C; o Sharpe não é calculado
   abaixo de 30 operações.

**O que não se conclui:** que não exista vantagem em BTC. Conclui-se que esta configuração (features técnicas
horárias, TP 2×ATR / SL 1×ATR em 24 h, custos de retalho) não a tem.

## EUR/USD (Dukascopy, bid/ask, 1 hora)

Pendente: a Dukascopy limitou a cadência e depois deixou de aceitar ligações deste endereço durante a
recolha. O recolhedor guarda cada mês em cache e retoma sozinho; a investigação corre quando os dados chegarem.

## Próximas hipóteses a testar (por ordem de custo)

1. Custos mais baixos: taxas maker (ordens limite) ou níveis de volume; refazer com custos reais por conta.
2. Horizontes mais longos (4 h, diário), onde o custo pesa menos face ao movimento esperado.
3. Features de microestrutura e de regime (volatilidade realizada vs implícita, funding, fluxo de ordens).
4. Filtros de regime: negociar só quando a volatilidade justifica o custo.
