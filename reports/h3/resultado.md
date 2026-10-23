# Hipótese 3: resultados (gerado 2026-10-23T00:25 UTC)

Pré-registo: `docs/h3-volatilidade-preregisto.md`.

## Parte A: qualidade da previsão do dia seguinte (QLIKE, menor é melhor)

### BTC/USD

| Período | Dias | EWMA QLIKE | HAR QLIKE | XGB QLIKE | R² log (HAR) | XGB − HAR (IC95%) | EWMA − HAR (IC95%) |
|---|---|---|---|---|---|---|---|
| desenvolvimento (2024-01-30 a 2025-11-22) | 662 | 0.4277 | 0.3615 | 0.3939 | 0.081 | +0.032 [+0.002; +0.066] | +0.066 [+0.042; +0.093] |
| teste_final (2025-11-23 a 2026-10-20) | 331 | 0.4598 | 0.4050 | 0.4157 | 0.024 | +0.011 [-0.025; +0.047] | +0.055 [+0.008; +0.108] |

### EUR/USD

| Período | Dias | EWMA QLIKE | HAR QLIKE | XGB QLIKE | R² log (HAR) | XGB − HAR (IC95%) | EWMA − HAR (IC95%) |
|---|---|---|---|---|---|---|---|
| desenvolvimento (2023-01-19 a 2025-07-04) | 638 | 0.2772 | 0.2821 | 0.2779 | 0.012 | -0.004 [-0.033; +0.019] | -0.005 [-0.016; +0.010] |
| teste_final (2025-07-07 a 2026-09-29) | 320 | 0.2655 | 0.2522 | 0.2781 | -0.012 | +0.026 [+0.001; +0.058] | +0.013 [-0.003; +0.031] |

## Parte B: volatilidade-alvo no BTC/USD (líquido de custos)

Alvo 40% ao ano, custo 29 bps por unidade rodada, banda de 0,10.

| Previsor | Período | Sharpe | Retorno % | Vol % | Máx. DD % | Exposição média | Custo %/ano | Sharpe − comprar e manter (IC95%) | Sharpe − exposição constante (IC95%) |
|---|---|---|---|---|---|---|---|---|---|
| EWMA | desenvolvimento | 0.983 | 73.7 | 38.5 | -29.7 | 0.82 | 0.56 | -0.059 [-0.282; +0.132] | -0.059 [-0.282; +0.132] |
| EWMA | teste_final | 0.139 | -1.7 | 37.7 | -36.9 | 0.88 | 0.65 | +0.000 [-0.293; +0.201] | +0.000 [-0.293; +0.201] |
| HAR | desenvolvimento | 0.811 | 52.9 | 37.5 | -28.3 | 0.82 | 5.37 | -0.232 [-0.494; +0.010] | -0.232 [-0.494; +0.010] |
| HAR | teste_final | 0.046 | -4.2 | 35.9 | -35.0 | 0.87 | 4.00 | -0.093 [-0.489; +0.228] | -0.093 [-0.489; +0.228] |
| XGB | desenvolvimento | 0.918 | 70.4 | 41.3 | -30.5 | 0.89 | 8.61 | -0.125 [-0.316; +0.066] | -0.125 [-0.316; +0.066] |
| XGB | teste_final | -0.072 | -8.4 | 37.3 | -39.7 | 0.92 | 5.41 | -0.211 [-0.555; +0.034] | -0.211 [-0.555; +0.034] |
| comprar e manter | desenvolvimento | 1.042 | 102.1 | 48.4 | -32.1 | 1.00 | 0 | | |
| comprar e manter | teste_final | 0.139 | -3.2 | 44.1 | -39.6 | 1.00 | 0 | | |

**Escolhido no desenvolvimento:** EWMA.

| Critério pré-registado | Cumprido |
|---|---|
| 1_dev_ic95_sharpe_vs_bh_acima_de_zero | não |
| 2_final_sharpe_vs_bh_positivo | sim |
| 3_dev_sharpe_vs_constante_positivo | não |

**Hipótese NÃO confirmada.**
