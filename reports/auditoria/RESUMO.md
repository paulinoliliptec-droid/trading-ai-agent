# Auditoria retrospetiva das decisões — BTC/USD 1h

Janela: 2026-10-22 22:00 → 2026-11-04 09:00 UTC (fonte: `trading_agent.decisions`, só leitura).
Modelo: `BTCUSD-1h-B_xgboost-20261022T193659Z` (estado no registo: **rejeitado**), modo observação.
Ficheiros: `decisoes_20261022_20261104T1000.csv`, `agregados_20261022_20261104T1000.json`,
`precos_coinbase_20261022_20261104T1000.csv` (a corrida de 2026-11-03 19:00 fica como versão intermédia).

Regras da compra hipotética: entrada na abertura de t+1, TP = +2×ATR(14), SL = −1×ATR(14), limite de 24 velas,
TP e SL na mesma vela contam como SL, custo de 54 bps por operação (o registado na decisão).

## Decisão (rejeitar sempre): correta em 67%

| | Valor |
|---|---|
| Decisões / resolvidas / pendentes | 300 / 295 / 5 |
| Aprovadas | 0 |
| TP / SL / tempo | 85 / 189 / 21 |
| Teriam perdido depois de custos (rejeição correta) | 197 (67%) |
| Teriam dado lucro líquido (oportunidade perdida) | 98, média +39 bps |
| Retorno líquido médio se comprasse sempre | −54 bps (IC95 −62 a −46) |
| Retorno bruto médio (sem custos) | −0,2 bps |
| Probabilidade registada reproduzida | diferença máxima 0,0 |

A rejeição é correta sobretudo por causa dos custos: sem eles a média é ≈ 0. «Nunca comprar» acertaria o mesmo.

## Previsão: sem capacidade de discriminação

| Medida | Valor |
|---|---|
| AUC (probabilidade vs TP) | 0,483 |
| Brier do modelo / de uma previsão constante | 0,203 / 0,205 |
| Correlação de Spearman (retorno esperado vs realizado) | −0,02 |
| Probabilidades distintas | 8 |

| Faixa | n | Prob. média | Freq. TP | Ret. líquido médio |
|---|---|---|---|---|
| 0,10–0,20 | 29 | 0,18 | 0% | −59 bps |
| 0,20–0,30 | 23 | 0,27 | 48% | −41 bps |
| 0,30–0,40 | 243 | 0,34 | 30% | −55 bps |

O resultado depende do dia e não da probabilidade (ex.: 23 out. prob. 0,33 e 0% de TP; 27 out. prob. 0,34 e 83%).
As operações sobrepõem-se (horárias, 24 h cada): a amostra efetiva é de ~13 dias, não de 295 observações.

## Conclusão

- O controlo de risco protegeu: nenhuma compra num período em que o BTC caiu ~3,8%.
- O modelo não acrescenta informação, o que confirma o estado «rejeitado». Não se justifica baixar o limite de 0,40.
- Nada foi reajustado a partir destes resultados. A operação mantém-se em observação.
- Operação saudável: uma decisão por hora sem falhas; 4 falhas pontuais da API da Kraken, recuperadas em ~2 min.
