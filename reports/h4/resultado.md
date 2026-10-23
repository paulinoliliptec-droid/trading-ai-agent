# Hipótese 4: carry de funding (gerado 2026-10-23T00:39 UTC)

Pré-registo: `docs/h4-carry-funding-preregisto.md`.

Períodos: desenvolvimento 2023-01-03 a 2025-07-16 (926 dias); teste_final 2025-07-17 a 2026-10-22 (463 dias).
Retornos sobre o capital (nocional + 50% de margem), líquidos de custos e da variação da base.

| Estratégia | Custos | Período | Retorno anual % | IC95% diário (bps) | Total % | Máx. DD % | Carry %/ano | Base %/ano | Custos % | Dias em posição | Entradas |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sempre | principal (36 bps) | desenvolvimento | 5.66 | [+1.13; +2.08] | 15.44 | -0.21 | 5.85 | -0.00 | 0.48 | 926 | 1 |
| sempre | principal (36 bps) | teste_final | 2.29 | [+0.32; +0.90] | 2.94 | -0.28 | 2.67 | -0.00 | 0.48 | 463 | 1 |
| condicional | principal (36 bps) | desenvolvimento | 4.34 | [+0.67; +1.79] | 11.63 | -0.69 | 5.22 | 0.07 | 2.40 | 650 | 5 |
| condicional | principal (36 bps) | teste_final | 0.51 | [-0.09; +0.39] | 0.64 | -0.48 | 1.23 | 0.03 | 0.96 | 132 | 2 |
| sempre | barato (15 bps) | desenvolvimento | 5.77 | [+1.17; +2.10] | 15.77 | -0.07 | 5.85 | -0.00 | 0.20 | 926 | 1 |
| sempre | barato (15 bps) | teste_final | 2.51 | [+0.40; +0.93] | 3.23 | -0.28 | 2.67 | -0.00 | 0.20 | 463 | 1 |
| condicional | barato (15 bps) | desenvolvimento | 4.89 | [+0.87; +1.91] | 13.21 | -0.28 | 5.22 | 0.07 | 1.00 | 650 | 5 |
| condicional | barato (15 bps) | teste_final | 0.95 | [+0.05; +0.50] | 1.21 | -0.20 | 1.23 | 0.03 | 0.40 | 132 | 2 |

## Riscos observados

| Período | Funding médio %/ano (nocional) | Dias com funding negativo % | Pior Δ diário do prémio (bps) | Maior subida do BTC em 30 dias % |
|---|---|---|---|---|
| desenvolvimento | 8.78 | 6.6 | 11.2 | 58.9 |
| teste_final | 4.00 | 18.1 | 8.1 | 26.9 |

**Escolhida no desenvolvimento (cenário principal):** sempre.

| Critério pré-registado | Cumprido |
|---|---|
| 1_dev_ic95_diario_acima_de_zero | sim |
| 2_final_retorno_anual_positivo | sim |
| 3_final_supera_4pct | não |

**Hipótese NÃO confirmada.**
