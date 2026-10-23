# Hipótese 2: resultados (gerado 2026-10-23T00:33 UTC)

Pré-registo: `docs/h2-derivados-preregisto.md`.

## Experiências pré-registadas (custos reais, modelo B, features v3)

| Experiência | Período | Operações | Bruto bps | Líquido bps | IC95% líquido | Retorno % | AUC | Qualifica |
|---|---|---|---|---|---|---|---|---|
| BTCUSD_1h_h24_tp2_sl1_v3 | desenvolvimento | 1 | -38.8 | -94.7 | — | -0.19 | 0.505 | não |
| BTCUSD_1h_h24_tp2_sl1_v3 | teste_final | 0 | — | — | — | 0.00 | 0.528 |  |
| BTCUSD_1h_h24_tp1_sl1_v3 | desenvolvimento | 6 | -34.9 | -90.8 | [-112.7; -68.6] | -1.08 | 0.491 | não |
| BTCUSD_1h_h24_tp1_sl1_v3 | teste_final | 0 | — | — | — | 0.00 | 0.470 |  |
| BTCUSD_4h_h12_tp2_sl1_v3 | desenvolvimento | 112 | 5.5 | -50.5 | [-76.0; -26.1] | -10.73 | 0.516 | não |
| BTCUSD_4h_h12_tp2_sl1_v3 | teste_final | 34 | -30.7 | -86.6 | [-158.2; -25.5] | -5.11 | 0.511 |  |
| BTCUSD_4h_h12_tp1_sl1_v3 | desenvolvimento | 0 | — | — | — | 0.00 | 0.515 | não |
| BTCUSD_4h_h12_tp1_sl1_v3 | teste_final | 5 | 18.3 | -37.7 | [-115.3; +39.9] | -0.38 | 0.487 |  |

**Qualificadas:** nenhuma. **Escolhida:** —. **Hipótese NÃO confirmada.**

## Diagnóstico com custo zero (informativo): a informação nova melhora a previsão?

| Experiência | Features | Operações (dev) | Bruto bps (dev) | IC95% bruto (dev) | AUC dev | Bruto bps (final) | AUC final |
|---|---|---|---|---|---|---|---|
| BTCUSD_1h_h24_tp2_sl1 | v3 | 1252 | 1.0 | [-5.8; +7.5] | 0.504 | -6.3 | 0.528 |
| BTCUSD_1h_h24_tp2_sl1 | v2 | 1168 | 4.3 | [-2.1; +11.0] | 0.504 | -26.0 | 0.506 |
| BTCUSD_1h_h24_tp1_sl1 | v3 | 2108 | 1.0 | [-1.8; +4.0] | 0.491 | — | 0.470 |
| BTCUSD_1h_h24_tp1_sl1 | v2 | 2043 | 0.6 | [-2.2; +3.7] | 0.493 | 10.9 | 0.518 |
| BTCUSD_4h_h12_tp2_sl1 | v3 | 384 | 1.2 | [-16.9; +19.1] | 0.516 | 3.7 | 0.489 |
| BTCUSD_4h_h12_tp2_sl1 | v2 | 244 | 8.0 | [-13.6; +29.6] | 0.523 | -5.2 | 0.499 |
| BTCUSD_4h_h12_tp1_sl1 | v3 | 552 | 0.9 | [-13.2; +14.4] | 0.508 | -8.8 | 0.495 |
| BTCUSD_4h_h12_tp1_sl1 | v2 | 587 | -0.5 | [-13.1; +11.3] | 0.517 | -13.1 | 0.470 |
