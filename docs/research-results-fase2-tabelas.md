# Resultados da fase 2: tabelas

> Gerado por `scripts/report_fase2.py` a partir de `reports/fase2/*.json`. Valores em pontos base (bps) por operação,
> depois de custos, salvo indicação. **Desenvolvimento** = períodos usados para comparar; **teste final** = só reportado.

## BTC/USD

### Custos face ao movimento esperado

| Experiência | Custo ida e volta (bps) | ATR mediano (%) | Custo em ATR | Prob. ponto morto | TP-primeiro observado | Bruto médio do rótulo (bps) |
|---|---|---|---|---|---|---|
| BTCUSD_15m_h16_tp1_sl1_v2 | 56,0 | 0,278 | 2,013 | 1,507 | 0,469 | -1,3 |
| BTCUSD_15m_h16_tp2_sl1_v2 | 56,0 | 0,278 | 2,013 | 1,004 | 0,268 | -1,3 |
| BTCUSD_1d_h10_tp1_sl1_v2 | 56,0 | 3,479 | 0,161 | 0,581 | 0,473 | -1,5 |
| BTCUSD_1d_h10_tp2_sl1_v2 | 56,0 | 3,427 | 0,163 | 0,388 | 0,252 | -6,8 |
| BTCUSD_1h_h24_tp1_sl1_v2 | 56,0 | 0,626 | 0,894 | 0,947 | 0,484 | -0,4 |
| BTCUSD_1h_h24_tp2_sl1_v1 | 56,0 | 0,627 | 0,893 | 0,631 | 0,311 | 0,7 |
| BTCUSD_1h_h24_tp2_sl1_v2 | 56,0 | 0,626 | 0,894 | 0,631 | 0,310 | 0,6 |
| BTCUSD_1h_h24_tp2_sl1_v2_janela8760 | 56,0 | 0,626 | 0,894 | 0,631 | 0,310 | 0,6 |
| BTCUSD_4h_h12_tp1_sl1_v2 | 56,0 | 1,277 | 0,439 | 0,719 | 0,478 | -0,6 |
| BTCUSD_4h_h12_tp2_sl1_v2 | 56,0 | 1,277 | 0,439 | 0,479 | 0,274 | 4,5 |

### Resultados por experiência e modelo

| Experiência | Modelo | Ops (dev) | Bruto | Custo | Líquido | IC95% líquido | AUC | Brier skill | Qualifica | Ops (teste final) | Líquido (teste final) | Retorno teste final (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSD_15m_h16_tp1_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| BTCUSD_15m_h16_tp1_sl1_v2 | B_xgboost | 0 | – | – | – | – | 0,488 | -0,0054 | não | 0 | – | 0,00 |
| BTCUSD_15m_h16_tp1_sl1_v2 | C_gru | 0 | – | – | – | – | 0,497 | -0,0014 | não | 0 | – | 0,00 |
| BTCUSD_15m_h16_tp1_sl1_v2 | D_ensemble_BC | 0 | – | – | – | – | 0,490 | -0,0048 | não | 0 | – | 0,00 |
| BTCUSD_15m_h16_tp2_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| BTCUSD_15m_h16_tp2_sl1_v2 | B_xgboost | 0 | – | – | – | – | 0,521 | -0,0124 | não | 0 | – | 0,00 |
| BTCUSD_15m_h16_tp2_sl1_v2 | C_gru | 10 | -9,9 | 56,0 | -65,9 | [-79,1; -53,7] | 0,535 | -0,0028 | não | 9 | -55,5 | -0,99 |
| BTCUSD_15m_h16_tp2_sl1_v2 | D_ensemble_BC | 34 | -2,0 | 56,0 | -58,0 | [-63,4; -52,3] | 0,536 | -0,0124 | não | 10 | -55,9 | -1,11 |
| BTCUSD_1d_h10_tp1_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| BTCUSD_1d_h10_tp1_sl1_v2 | B_xgboost | 61 | -58,7 | 55,8 | -114,5 | [-213,1; -18,0] | 0,513 | -0,1475 | não | 9 | -47,2 | -0,84 |
| BTCUSD_1d_h10_tp1_sl1_v2 | C_gru | 77 | -16,2 | 55,9 | -72,1 | [-139,1; -6,2] | 0,534 | -0,1658 | não | 10 | 2,8 | 0,01 |
| BTCUSD_1d_h10_tp1_sl1_v2 | D_ensemble_BC | 77 | 7,6 | 56,0 | -48,4 | [-113,7; 18,3] | 0,543 | -0,2641 | não | 14 | -73,0 | -1,62 |
| BTCUSD_1d_h10_tp2_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| BTCUSD_1d_h10_tp2_sl1_v2 | B_xgboost | 60 | -84,5 | 55,7 | -140,2 | [-244,4; -33,4] | 0,425 | -0,1574 | não | 11 | -110,5 | -1,51 |
| BTCUSD_1d_h10_tp2_sl1_v2 | C_gru | 60 | -30,0 | 55,9 | -85,9 | [-165,0; -5,0] | 0,549 | -0,3455 | não | 20 | -77,5 | -1,90 |
| BTCUSD_1d_h10_tp2_sl1_v2 | D_ensemble_BC | 56 | -25,8 | 55,9 | -81,7 | [-177,8; 5,5] | 0,528 | -0,3615 | não | 20 | -39,7 | -0,93 |
| BTCUSD_1h_h24_tp1_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp1_sl1_v2 | B_xgboost | 6 | -34,0 | 55,9 | -89,8 | [-109,5; -70,2] | 0,492 | -0,0128 | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp1_sl1_v2 | C_gru | 11 | 4,2 | 56,0 | -51,8 | [-87,2; -15,2] | 0,493 | -0,0187 | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp1_sl1_v2 | D_ensemble_BC | 16 | -7,0 | 56,0 | -63,0 | [-90,7; -33,5] | 0,493 | -0,0233 | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp2_sl1_v1 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp2_sl1_v1 | B_xgboost | 3 | 50,9 | 56,1 | -5,3 | – | 0,505 | -0,0110 | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp2_sl1_v1 | C_gru | 7 | 104,8 | 56,3 | 48,5 | [-47,2; 145,2] | 0,516 | -0,0058 | não | 4 | -24,1 | -0,19 |
| BTCUSD_1h_h24_tp2_sl1_v1 | D_ensemble_BC | 22 | 34,1 | 56,1 | -22,0 | [-62,7; 29,2] | 0,513 | -0,0116 | não | 4 | -24,1 | -0,19 |
| BTCUSD_1h_h24_tp2_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp2_sl1_v2 | B_xgboost | 1 | -56,7 | 55,8 | -112,5 | – | 0,503 | -0,0137 | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp2_sl1_v2 | C_gru | 4 | -22,5 | 55,9 | -78,4 | – | 0,510 | -0,0151 | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp2_sl1_v2 | D_ensemble_BC | 24 | -10,8 | 56,0 | -66,8 | [-93,0; -39,9] | 0,509 | -0,0187 | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp2_sl1_v2_janela8760 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| BTCUSD_1h_h24_tp2_sl1_v2_janela8760 | B_xgboost | 4 | -15,8 | 55,9 | -71,8 | – | 0,510 | -0,0086 | não | 17 | -79,5 | -2,67 |
| BTCUSD_1h_h24_tp2_sl1_v2_janela8760 | C_gru | 80 | 25,1 | 56,1 | -30,9 | [-51,8; -6,6] | 0,520 | -0,0100 | não | 1 | -29,9 | -0,06 |
| BTCUSD_1h_h24_tp2_sl1_v2_janela8760 | D_ensemble_BC | 70 | 22,7 | 56,0 | -33,3 | [-56,0; -9,6] | 0,520 | -0,0139 | não | 11 | -94,7 | -2,07 |
| BTCUSD_4h_h12_tp1_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| BTCUSD_4h_h12_tp1_sl1_v2 | B_xgboost | 0 | – | – | – | – | 0,517 | -0,0026 | não | 2 | -105,5 | -0,42 |
| BTCUSD_4h_h12_tp1_sl1_v2 | C_gru | 28 | -13,2 | 55,9 | -69,1 | [-116,5; -24,9] | 0,499 | -0,0336 | não | 11 | -78,3 | -1,56 |
| BTCUSD_4h_h12_tp1_sl1_v2 | D_ensemble_BC | 36 | 13,6 | 56,0 | -42,5 | [-88,7; -1,5] | 0,515 | -0,0310 | não | 6 | -170,8 | -1,70 |
| BTCUSD_4h_h12_tp2_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| BTCUSD_4h_h12_tp2_sl1_v2 | B_xgboost | 52 | -0,3 | 56,0 | -56,3 | [-92,3; -16,9] | 0,523 | -0,0029 | não | 47 | -55,0 | -5,12 |
| BTCUSD_4h_h12_tp2_sl1_v2 | C_gru | 0 | – | – | – | – | 0,538 | -0,0042 | não | 12 | 4,8 | 0,03 |
| BTCUSD_4h_h12_tp2_sl1_v2 | D_ensemble_BC | 52 | -0,3 | 56,0 | -56,3 | [-92,3; -16,9] | 0,539 | -0,0044 | não | 48 | -67,3 | -6,38 |

### Referências (mesmos períodos; «não negociar» = 0%)

| Intervalo | Período | Datas | Comprar e manter (%) | Max DD comprar e manter (%) |
|---|---|---|---|---|
| 15m | desenvolvimento | 2025-07-29 a 2026-05-25 | -34,78 | -52,30 |
| 15m | teste_final | 2026-05-25 a 2026-10-22 | 4,90 | -25,43 |
| 1d | desenvolvimento | 2024-10-18 a 2026-02-17 | -1,40 | -49,65 |
| 1d | teste_final | 2026-02-18 a 2026-10-19 | 23,21 | -28,80 |
| 1h | desenvolvimento | 2024-07-14 a 2026-01-18 | 58,32 | -34,89 |
| 1h | teste_final | 2026-01-18 a 2026-10-22 | -14,36 | -39,03 |
| 4h | desenvolvimento | 2024-07-26 a 2026-01-22 | 30,89 | -34,48 |
| 4h | teste_final | 2026-01-22 a 2026-10-22 | -8,41 | -35,23 |

### Estabilidade do XGBoost por fold (AUC no treino vs fora da amostra, Brier skill, ECE)

| Experiência | AUC treino (média) | AUC fora (média) | AUC fora (mín–máx) | Brier skill (média) | ECE (média) |
|---|---|---|---|---|---|
| BTCUSD_15m_h16_tp1_sl1_v2 | 0,573 | 0,494 | 0,482–0,508 | -0,0047 | 0,0181 |
| BTCUSD_15m_h16_tp2_sl1_v2 | 0,601 | 0,532 | 0,509–0,548 | -0,0081 | 0,0248 |
| BTCUSD_1d_h10_tp1_sl1_v2 | 0,716 | 0,452 | 0,375–0,539 | -0,1530 | 0,1742 |
| BTCUSD_1d_h10_tp2_sl1_v2 | 0,674 | 0,472 | 0,345–0,588 | -0,1812 | 0,1348 |
| BTCUSD_1h_h24_tp1_sl1_v2 | 0,620 | 0,498 | 0,479–0,523 | -0,0103 | 0,0292 |
| BTCUSD_1h_h24_tp2_sl1_v1 | 0,617 | 0,521 | 0,491–0,549 | -0,0087 | 0,0363 |
| BTCUSD_1h_h24_tp2_sl1_v2 | 0,651 | 0,501 | 0,486–0,514 | -0,0135 | 0,0394 |
| BTCUSD_1h_h24_tp2_sl1_v2_janela8760 | 0,660 | 0,512 | 0,476–0,546 | -0,0112 | 0,0383 |
| BTCUSD_4h_h12_tp1_sl1_v2 | 0,648 | 0,517 | 0,442–0,572 | -0,0154 | 0,0667 |
| BTCUSD_4h_h12_tp2_sl1_v2 | 0,701 | 0,540 | 0,461–0,651 | -0,0491 | 0,0681 |

### Regimes (XGBoost, desenvolvimento): líquido em bps por terço

| Experiência | Vol. rel. baixa | média | alta | Tendência baixa | média | alta | AUC por volatilidade (baixa/média/alta) |
|---|---|---|---|---|---|---|---|
| BTCUSD_1d_h10_tp1_sl1_v2 | -107,3 (16) | -35,4 (21) | -188,6 (24) | -63,0 (19) | -56,4 (20) | -211,9 (22) | 0,527/0,573/0,432 |
| BTCUSD_1d_h10_tp2_sl1_v2 | -11,3 (26) | -168,2 (16) | -301,4 (18) | -9,3 (18) | -113,9 (16) | -247,0 (26) | 0,530/0,494/0,272 |
| BTCUSD_1h_h24_tp1_sl1_v2 | -114,3 (1) | -85,0 (5) | – | -84,4 (5) | -117,2 (1) | – | 0,492/0,479/0,502 |
| BTCUSD_1h_h24_tp2_sl1_v2 | – | -112,5 (1) | – | – | – | -112,5 (1) | 0,464/0,509/0,523 |
| BTCUSD_1h_h24_tp2_sl1_v2_janela8760 | 37,6 (1) | -108,2 (3) | – | – | – | -71,8 (4) | 0,471/0,522/0,529 |
| BTCUSD_4h_h12_tp2_sl1_v2 | -94,7 (12) | -41,9 (19) | -47,4 (21) | -82,7 (16) | -44,6 (12) | -44,5 (24) | 0,459/0,529/0,557 |

### Consistência entre rótulo e execução simulada (XGBoost, desenvolvimento)

| Experiência | Operações | Saída igual à barreira do rótulo (%) |
|---|---|---|
| BTCUSD_1d_h10_tp1_sl1_v2 | 61 | 98,4 |
| BTCUSD_1d_h10_tp2_sl1_v2 | 60 | 100,0 |
| BTCUSD_1h_h24_tp1_sl1_v2 | 6 | 100,0 |
| BTCUSD_1h_h24_tp2_sl1_v1 | 3 | 100,0 |
| BTCUSD_1h_h24_tp2_sl1_v2 | 1 | 100,0 |
| BTCUSD_1h_h24_tp2_sl1_v2_janela8760 | 4 | 100,0 |
| BTCUSD_4h_h12_tp2_sl1_v2 | 52 | 96,2 |

### Seleção pré-registada e simulação com 100 €

- Critério: desenvolvimento: >= 30 operações e IC95% inferior da expectativa líquida > 0 (bootstrap por blocos).
- Combinações avaliadas (configuração × modelo): 40.
- Escolhida: **nenhuma**.
- Melhor no desenvolvimento (com ≥ 30 operações, qualificada ou não): BTCUSD_1h_h24_tp2_sl1_v2_janela8760 / C_gru.
- Simulação com 100 € (conta em EUR, risco de produção): configuração BTCUSD_1h_h24_tp2_sl1_v2_janela8760 / C_gru.

  - desenvolvimento: 80 operações, retorno -5,12%, líquido -30,9 bps/op, max DD -5,55%, vetos {'probabilidade': 12051, 'expectativa': 12685}
  - teste_final: 1 operações, retorno -0,06%, líquido -29,9 bps/op, max DD -0,06%, vetos {'probabilidade': 6421, 'expectativa': 6637}

## EUR/USD

### Custos face ao movimento esperado

| Experiência | Custo ida e volta (bps) | ATR mediano (%) | Custo em ATR | Prob. ponto morto | TP-primeiro observado | Bruto médio do rótulo (bps) |
|---|---|---|---|---|---|---|
| EURUSD_1d_h10_tp1_sl1_v2 | 0,8 | 0,677 | 0,013 | 0,506 | 0,534 | 5,3 |
| EURUSD_1d_h10_tp2_sl1_v2 | 0,8 | 0,679 | 0,013 | 0,338 | 0,288 | 8,2 |
| EURUSD_1h_h24_tp1_sl1_v2 | 0,7 | 0,112 | 0,066 | 0,533 | 0,497 | 0,1 |
| EURUSD_1h_h24_tp2_sl1_v1 | 0,7 | 0,112 | 0,066 | 0,355 | 0,323 | 0,1 |
| EURUSD_1h_h24_tp2_sl1_v2 | 0,7 | 0,112 | 0,066 | 0,355 | 0,322 | 0,1 |
| EURUSD_1h_h24_tp2_sl1_v2_janela6240 | 0,7 | 0,112 | 0,066 | 0,355 | 0,322 | 0,1 |
| EURUSD_4h_h12_tp1_sl1_v2 | 0,7 | 0,233 | 0,031 | 0,515 | 0,490 | 0,3 |
| EURUSD_4h_h12_tp2_sl1_v2 | 0,7 | 0,234 | 0,031 | 0,344 | 0,300 | 1,2 |

### Resultados por experiência e modelo

| Experiência | Modelo | Ops (dev) | Bruto | Custo | Líquido | IC95% líquido | AUC | Brier skill | Qualifica | Ops (teste final) | Líquido (teste final) | Retorno teste final (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD_1d_h10_tp1_sl1_v2 | A_regras | 60 | 8,5 | 0,9 | 7,6 | [-10,6; 25,1] | – | – | não | 21 | -5,2 | -0,95 |
| EURUSD_1d_h10_tp1_sl1_v2 | B_xgboost | 131 | -16,9 | 0,9 | -17,8 | [-28,9; -6,4] | 0,390 | -0,1855 | não | 53 | -11,4 | -5,33 |
| EURUSD_1d_h10_tp1_sl1_v2 | C_gru | 114 | -11,5 | 0,9 | -12,4 | [-26,4; 1,6] | 0,460 | -0,2048 | não | 47 | 18,6 | 8,75 |
| EURUSD_1d_h10_tp1_sl1_v2 | D_ensemble_BC | 109 | -21,4 | 0,9 | -22,3 | [-35,8; -8,2] | 0,424 | -0,2923 | não | 51 | 14,7 | 7,41 |
| EURUSD_1d_h10_tp2_sl1_v2 | A_regras | 36 | 13,5 | 0,9 | 12,5 | [-18,5; 50,2] | – | – | não | 17 | 0,1 | 0,25 |
| EURUSD_1d_h10_tp2_sl1_v2 | B_xgboost | 86 | -18,9 | 0,9 | -19,8 | [-33,8; -5,7] | 0,388 | -0,4027 | não | 35 | 12,1 | 3,89 |
| EURUSD_1d_h10_tp2_sl1_v2 | C_gru | 77 | -15,5 | 0,9 | -16,4 | [-33,0; 1,9] | 0,424 | -0,7126 | não | 42 | 1,9 | 1,48 |
| EURUSD_1d_h10_tp2_sl1_v2 | D_ensemble_BC | 77 | -15,5 | 0,9 | -16,4 | [-33,0; 1,9] | 0,446 | -0,6554 | não | 41 | -0,5 | 0,13 |
| EURUSD_1h_h24_tp1_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| EURUSD_1h_h24_tp1_sl1_v2 | B_xgboost | 340 | 0,6 | 1,1 | -0,5 | [-2,6; 1,6] | 0,521 | -0,0148 | não | 170 | -1,0 | -7,37 |
| EURUSD_1h_h24_tp1_sl1_v2 | C_gru | 194 | 0,4 | 0,8 | -0,4 | [-2,6; 1,5] | 0,510 | -0,0049 | não | 67 | 0,3 | 0,04 |
| EURUSD_1h_h24_tp1_sl1_v2 | D_ensemble_BC | 465 | 0,2 | 0,9 | -0,7 | [-2,4; 0,9] | 0,518 | -0,0178 | não | 98 | -0,6 | -3,85 |
| EURUSD_1h_h24_tp2_sl1_v1 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| EURUSD_1h_h24_tp2_sl1_v1 | B_xgboost | 209 | -1,7 | 0,9 | -2,7 | [-6,1; 0,8] | 0,498 | -0,0270 | não | 49 | 0,2 | -0,95 |
| EURUSD_1h_h24_tp2_sl1_v1 | C_gru | 330 | -0,2 | 0,7 | -0,9 | [-2,4; 0,6] | 0,492 | -0,0230 | não | 39 | -6,7 | -8,46 |
| EURUSD_1h_h24_tp2_sl1_v1 | D_ensemble_BC | 626 | -0,5 | 0,8 | -1,3 | [-2,8; 0,3] | 0,494 | -0,0398 | não | 119 | -2,5 | -12,31 |
| EURUSD_1h_h24_tp2_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| EURUSD_1h_h24_tp2_sl1_v2 | B_xgboost | 660 | -0,3 | 0,8 | -1,0 | [-2,2; 0,3] | 0,485 | -0,0255 | não | 98 | 0,7 | 3,47 |
| EURUSD_1h_h24_tp2_sl1_v2 | C_gru | 591 | -0,0 | 0,8 | -0,8 | [-2,2; 0,7] | 0,499 | -0,0214 | não | 401 | -1,3 | -21,98 |
| EURUSD_1h_h24_tp2_sl1_v2 | D_ensemble_BC | 873 | 0,0 | 0,8 | -0,8 | [-2,1; 0,5] | 0,490 | -0,0342 | não | 483 | -1,1 | -22,33 |
| EURUSD_1h_h24_tp2_sl1_v2_janela6240 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| EURUSD_1h_h24_tp2_sl1_v2_janela6240 | B_xgboost | 187 | -5,5 | 0,8 | -6,4 | [-8,8; -4,0] | 0,493 | -0,0142 | não | 157 | -0,6 | -3,44 |
| EURUSD_1h_h24_tp2_sl1_v2_janela6240 | C_gru | 406 | -0,8 | 0,7 | -1,6 | [-3,2; -0,0] | 0,493 | -0,0144 | não | 57 | -1,0 | -2,33 |
| EURUSD_1h_h24_tp2_sl1_v2_janela6240 | D_ensemble_BC | 372 | -1,7 | 0,8 | -2,5 | [-4,4; -0,6] | 0,492 | -0,0189 | não | 158 | -0,2 | -1,02 |
| EURUSD_4h_h12_tp1_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| EURUSD_4h_h12_tp1_sl1_v2 | B_xgboost | 388 | -0,7 | 0,8 | -1,5 | [-4,1; 1,1] | 0,496 | -0,0711 | não | 50 | -2,2 | -2,19 |
| EURUSD_4h_h12_tp1_sl1_v2 | C_gru | 327 | -0,3 | 0,7 | -1,0 | [-3,6; 1,5] | 0,498 | -0,0423 | não | 262 | -1,7 | -7,71 |
| EURUSD_4h_h12_tp1_sl1_v2 | D_ensemble_BC | 489 | -0,1 | 0,7 | -0,8 | [-2,9; 1,1] | 0,495 | -0,0934 | não | 205 | -1,7 | -5,74 |
| EURUSD_4h_h12_tp2_sl1_v2 | A_regras | 0 | – | – | – | – | – | – | não | 0 | – | 0,00 |
| EURUSD_4h_h12_tp2_sl1_v2 | B_xgboost | 437 | -1,2 | 0,8 | -2,0 | [-5,1; 1,1] | 0,512 | -0,0441 | não | 278 | -2,9 | -17,83 |
| EURUSD_4h_h12_tp2_sl1_v2 | C_gru | 416 | -2,3 | 0,8 | -3,1 | [-6,4; 0,3] | 0,464 | -0,0408 | não | 203 | -1,3 | -7,27 |
| EURUSD_4h_h12_tp2_sl1_v2 | D_ensemble_BC | 439 | -1,3 | 0,8 | -2,1 | [-5,4; 1,1] | 0,492 | -0,0656 | não | 273 | -2,3 | -13,82 |

### Referências (mesmos períodos; «não negociar» = 0%)

| Intervalo | Período | Datas | Comprar e manter (%) | Max DD comprar e manter (%) |
|---|---|---|---|---|
| 1d | desenvolvimento | 2024-04-11 a 2025-11-30 | 9,12 | -8,50 |
| 1d | teste_final | 2025-12-01 a 2026-09-27 | -2,20 | -5,66 |
| 1h | desenvolvimento | 2023-11-29 a 2025-10-20 | 5,96 | -9,04 |
| 1h | teste_final | 2025-10-20 a 2026-09-30 | -2,64 | -6,03 |
| 4h | desenvolvimento | 2023-12-18 a 2025-10-24 | 6,55 | -8,95 |
| 4h | teste_final | 2025-10-24 a 2026-09-30 | -2,47 | -5,74 |

### Estabilidade do XGBoost por fold (AUC no treino vs fora da amostra, Brier skill, ECE)

| Experiência | AUC treino (média) | AUC fora (média) | AUC fora (mín–máx) | Brier skill (média) | ECE (média) |
|---|---|---|---|---|---|
| EURUSD_1d_h10_tp1_sl1_v2 | 0,706 | 0,474 | 0,403–0,540 | -0,2688 | 0,2176 |
| EURUSD_1d_h10_tp2_sl1_v2 | 0,656 | 0,514 | 0,402–0,618 | -0,3124 | 0,1812 |
| EURUSD_1h_h24_tp1_sl1_v2 | 0,599 | 0,509 | 0,483–0,542 | -0,0131 | 0,0321 |
| EURUSD_1h_h24_tp2_sl1_v1 | 0,601 | 0,504 | 0,472–0,548 | -0,0170 | 0,0348 |
| EURUSD_1h_h24_tp2_sl1_v2 | 0,606 | 0,491 | 0,452–0,520 | -0,0229 | 0,0361 |
| EURUSD_1h_h24_tp2_sl1_v2_janela6240 | 0,627 | 0,499 | 0,462–0,555 | -0,0107 | 0,0334 |
| EURUSD_4h_h12_tp1_sl1_v2 | 0,668 | 0,497 | 0,451–0,560 | -0,0490 | 0,0719 |
| EURUSD_4h_h12_tp2_sl1_v2 | 0,687 | 0,498 | 0,410–0,563 | -0,0429 | 0,0718 |

### Regimes (XGBoost, desenvolvimento): líquido em bps por terço

| Experiência | Vol. rel. baixa | média | alta | Tendência baixa | média | alta | AUC por volatilidade (baixa/média/alta) |
|---|---|---|---|---|---|---|---|
| EURUSD_1d_h10_tp1_sl1_v2 | -2,6 (34) | -18,4 (29) | -25,1 (68) | -20,2 (50) | -17,2 (42) | -15,5 (39) | 0,561/0,312/0,401 |
| EURUSD_1d_h10_tp2_sl1_v2 | -11,1 (19) | -6,8 (25) | -31,4 (42) | -47,5 (28) | -24,2 (24) | 6,2 (34) | 0,579/0,334/0,379 |
| EURUSD_1h_h24_tp1_sl1_v2 | -1,2 (103) | 0,9 (115) | -1,3 (122) | -2,0 (112) | -0,9 (109) | 1,2 (119) | 0,517/0,531/0,517 |
| EURUSD_1h_h24_tp2_sl1_v2 | -0,5 (231) | -0,2 (242) | -2,8 (187) | -0,8 (243) | -2,2 (198) | -0,2 (219) | 0,500/0,507/0,452 |
| EURUSD_1h_h24_tp2_sl1_v2_janela6240 | -6,5 (57) | -0,2 (57) | -11,1 (73) | -6,1 (56) | -8,2 (66) | -4,8 (65) | 0,508/0,535/0,440 |
| EURUSD_4h_h12_tp1_sl1_v2 | 1,6 (114) | -1,5 (120) | -3,8 (154) | -1,2 (135) | 1,5 (124) | -4,7 (129) | 0,507/0,505/0,474 |
| EURUSD_4h_h12_tp2_sl1_v2 | 1,1 (150) | -0,3 (147) | -7,0 (140) | -0,9 (145) | -2,8 (138) | -2,3 (154) | 0,515/0,497/0,529 |

### Consistência entre rótulo e execução simulada (XGBoost, desenvolvimento)

| Experiência | Operações | Saída igual à barreira do rótulo (%) |
|---|---|---|
| EURUSD_1d_h10_tp1_sl1_v2 | 131 | 100,0 |
| EURUSD_1d_h10_tp2_sl1_v2 | 86 | 98,8 |
| EURUSD_1h_h24_tp1_sl1_v2 | 340 | 96,2 |
| EURUSD_1h_h24_tp2_sl1_v1 | 209 | 97,6 |
| EURUSD_1h_h24_tp2_sl1_v2 | 660 | 97,7 |
| EURUSD_1h_h24_tp2_sl1_v2_janela6240 | 187 | 97,3 |
| EURUSD_4h_h12_tp1_sl1_v2 | 388 | 99,2 |
| EURUSD_4h_h12_tp2_sl1_v2 | 437 | 99,3 |

### Seleção pré-registada e simulação com 100 €

- Critério: desenvolvimento: >= 30 operações e IC95% inferior da expectativa líquida > 0 (bootstrap por blocos).
- Combinações avaliadas (configuração × modelo): 32.
- Escolhida: **nenhuma**.
- Melhor no desenvolvimento (com ≥ 30 operações, qualificada ou não): EURUSD_1d_h10_tp2_sl1_v2 / A_regras.
- Simulação com 100 € (conta em EUR, risco de produção): configuração EURUSD_1d_h10_tp2_sl1_v2 / A_regras.

  - desenvolvimento: 0 operações, retorno 0,00%, líquido – bps/op, max DD 0,00%, vetos {'probabilidade': 281, 'expectativa': 120}
  - teste_final: 0 operações, retorno 0,00%, líquido – bps/op, max DD 0,00%, vetos {'probabilidade': 155, 'expectativa': 76}

