# Resultados da fase 2: leitura

> Dados reais, resultados fora da amostra, depois de custos. Tabelas completas em
> [research-results-fase2-tabelas.md](research-results-fase2-tabelas.md) (geradas a partir de `reports/fase2/`).
> Os números da fase 1 não são comparáveis um a um: mudou o motor de backtest, o BTC deixou de ter vendas a
> descoberto e a calibração passou a ter janela própria (ver ADR 0003).

## Conclusão

**Nenhuma das 72 combinações testadas (configuração × modelo) tem vantagem estatística líquida.** Nenhuma passa o
critério pré-registado no período de desenvolvimento (≥ 30 operações e limite inferior do IC95% da expectativa
líquida acima de zero), e o diagnóstico de custos (XGBoost nas 12 configurações v2 de 1 h, 4 h e 1 d) mostra que,
**mesmo com custo zero, nenhuma tem expectativa bruta positiva com confiança**. O problema não é só a corretora: é que estas features não preveem qual barreira vem
primeiro, em nenhum dos horizontes estudados, em nenhum dos dois mercados.

Consequência prática: não há modelo aprovado; o agente corre em observação. A decisão correta, hoje, é **não
negociar**, e é a que o motor de risco toma sozinho.

## Desenho (fixado antes de ver resultados)

| Elemento | Escolha |
|---|---|
| Mercados | BTC/USD (Coinbase), EUR/USD (Dukascopy, bid/ask) |
| Horizontes | 15 min (só BTC; 4 h de barreira), 1 h (24 h), 4 h (2 dias), 1 d (2 semanas) |
| Barreiras | TP 2×ATR / SL 1×ATR (fase 1) e TP 1×ATR / SL 1×ATR; grelha curta de propósito |
| Ablações | features v1 contra v2; janela de treino de 1 ano contra janela crescente |
| Modelos | A regras, B XGBoost, C GRU, D ensemble por empilhamento ajustado na calibração |
| Validação | 6 folds walk-forward; 4 de desenvolvimento, 2 de teste final (só reportado) |
| Decisão | Sem limiar escolhido: o retorno esperado vem da calibração; o risco exige > 1 bp depois de custos |
| Incerteza | Bootstrap estacionário por blocos (IC95%), Monte Carlo de 2 000 caminhos |
| Total | BTC/USD 10 configurações × 4 modelos = 40; EUR/USD 8 × 4 = 32 |

## Diagnóstico pedido

### 1. As features?

As features v2 (regimes, volatilidade realizada e relativa, liquidez, custo em ATR) **não melhoram** as v1: em
BTC/USD a 1 h o AUC fora da amostra fica em 0,50 (v2) contra 0,52 (v1); em EUR/USD em 0,49 contra 0,50. O AUC no
treino é 0,57 a 0,72 e o de fora da amostra 0,45 a 0,54: o modelo aprende ruído da amostra de treino. O Brier skill
é **negativo em todas as experiências**: as probabilidades calibradas são piores do que prever sempre a taxa base.

### 2. O horizonte de 24 horas?

Mudar o horizonte troca um problema por outro:

| BTC/USD | Custo em ATR | Prob. de ponto morto (TP 2 / SL 1) | TP-primeiro observado | Leitura |
|---|---|---|---|---|
| 15 min | 2,01 | 1,00 | 0,27 | **Impossível**: o custo é o dobro do movimento típico |
| 1 h | 0,89 | 0,63 | 0,31 | O custo come quase um ATR |
| 4 h | 0,44 | 0,48 | 0,27 | Melhor, ainda longe |
| 1 d | 0,16 | 0,39 | 0,25 | O custo deixa de mandar, mas o modelo sobreajusta (AUC 0,45 a 0,47 fora, 0,67 a 0,72 no treino; ~1 200 velas) |

Em EUR/USD o custo é pequeno em todos os horizontes (0,01 a 0,07 ATR) e mesmo assim não há vantagem.

### 3. Os custos tornam a estratégia inviável?

Em BTC/USD com taxas de retalho (0,25% por lado, 56 bps ida e volta), **sim, abaixo de 4 h**. Mas o diagnóstico com
custos a zero (`reports/fase2/sensibilidade_custos.json`) mostra que **não são a única causa**:

| Com custo zero | Operações (dev) | Bruto (dev, bps) | IC95% bruto | Bruto no teste final |
|---|---|---|---|---|
| BTC 1 h, TP 2 / SL 1 | 1 168 | +4,3 | [−2,1; +11,0] | −26,0 |
| BTC 4 h, TP 2 / SL 1 | 244 | +8,0 | [−13,6; +29,6] | −5,2 |
| BTC 1 d, TP 2 / SL 1 | 88 | −49,2 | [−137,6; +41,0] | +42,2 |
| EUR 1 h, TP 2 / SL 1 | 1 129 | −0,02 | [−0,9; +0,9] | +1,3 |
| EUR 4 h, TP 1 / SL 1 | 449 | −0,3 | [−2,7; +2,3] | +0,4 |
| EUR 1 d, TP 2 / SL 1 | 86 | −18,5 | [−31,5; −5,4] | +7,9 |

Nenhum intervalo exclui o zero pelo lado positivo, e o sinal troca entre desenvolvimento e teste final: é o padrão
de ruído, não de vantagem.

### 4. A calibração é estável?

Não. O ECE (erro de calibração) por fold varia entre 0,004 e 0,34 em BTC/USD e entre 0,004 e 0,48 em EUR/USD, com os
valores altos nos horizontes diários (poucas velas por fold); no diário de EUR/USD o Brier skill chega a −0,31.
A isotónica ajustada numa janela de calibração à parte não transporta para o teste porque não há relação estável
entre o score e o resultado.

### 5. A rotulagem triple-barrier está correta?

Sim. Além dos testes unitários (stop e alvo na mesma vela, vendido, fim dos dados), comparou-se a barreira do rótulo
com a saída real de cada operação simulada: **96 a 100% iguais**. As diferenças são saídas por gap (o rótulo assume
o preço do stop, a conta virtual sai à abertura) e vendas no fim dos dados.

### 6. Há regimes em que os modelos funcionam?

Não de forma consistente. O AUC por terço de volatilidade relativa fica entre 0,27 e 0,57 em BTC/USD e entre 0,31 e
0,58 em EUR/USD (os extremos nos diários, com poucas amostras por terço), sem padrão que se repita entre horizontes
ou mercados; os poucos valores acima de 0,55 aparecem em experiências diferentes e em terços
diferentes, o que é o esperado por acaso com dezenas de comparações. Por terço de tendência (eficiência do
movimento), o líquido do XGBoost é negativo em 13 de 13 terços com operações em BTC/USD e em 18 de 21 em EUR/USD.

### 7. As janelas permitem generalizar?

A janela de 1 ano em vez da crescente não muda a conclusão (BTC 1 h: AUC 0,51 contra 0,50; EUR 1 h: 0,50 contra
0,49). O sobreajuste (AUC treino muito acima do de fora) aparece com as duas.

## Erros de classificação, resultados de negociação e custos, em separado

| | BTC/USD | EUR/USD |
|---|---|---|
| Classificação (AUC fora da amostra, XGBoost) | 0,43 a 0,54 | 0,39 a 0,52 |
| Brier skill | −0,005 a −0,18 | −0,01 a −0,31 |
| Expectativa bruta por operação (dev, todos os modelos com operações) | −84 a +105 bps (o +105 com 7 operações) | −21 a +13 bps |
| Custo por operação | 56 bps | 0,7 a 1,1 bps |
| Expectativa líquida (dev) | −140 a +48 bps (o único positivo, GRU v1 1 h, tem 7 operações e IC95% [−47; +145]) | −22 a +12,5 bps (o melhor, A regras 1 d, tem 36 operações e IC95% [−18,5; +50,2]) |

**Nota sobre a alavancagem.** Em EUR/USD a 1 h o XGBoost perde só 1,0 bp por operação, mas com 660 operações e um
nocional médio de 4,3 vezes o capital (permitido pelo tecto de 30:1 e pelo tamanho calculado pela perda no stop)
isso dá −4 bps de capital por operação e −24% no período. Uma expectativa quase nula não é inofensiva: com
alavancagem e muitas operações, destrói capital.

## Ensemble

O ensemble D (empilhamento ajustado na calibração) às vezes perde menos do que B e C no desenvolvimento (por exemplo
BTC 4 h TP 1 / SL 1: −42 bps contra −69 da GRU), mas continua negativo, nunca qualifica e não confirma no teste
final (−171 bps nessa configuração). Fica registado como testado e rejeitado.

## Simulação com 100 € (conta em EUR, risco de produção)

Na configuração com melhor expectativa no desenvolvimento (BTC/USD: GRU 1 h com janela de 1 ano; EUR/USD: regras
1 d), o risco de produção (probabilidade mínima 0,40 e expectativa depois de custos) **não abriu nenhuma operação**
no teste final de EUR/USD e uma só no de BTC/USD. Os 100 € chegam para as quantidades mínimas dos dois mercados
(`scripts/capital_check.py`): BTC 4,05 USD de mínimo contra 22,65 USD permitidos; EUR/USD 1,13 USD contra 558 USD
(OANDA, 1 unidade). Numa corretora com micro-lote de 1 000 unidades, a perda no stop com a quantidade mínima
ultrapassa os 0,5% de risco por operação.

## Limitações

- Dois mercados, um período (2022 a 2026 em EUR/USD, 2023 a 2026 em BTC/USD); horizonte de 15 min só em BTC.
- Custos de BTC pressupostos (taxa taker de referência), não os da conta real.
- 72 combinações: mesmo com o critério fixo, a probabilidade de um falso positivo não é zero; nenhuma passou.
- Sem dados de livro de ordens, funding, on-chain ou macro com datas de publicação (o módulo qualitativo existe,
  mas não tem fonte).
- A GRU e o ensemble correm só na investigação; a inferência em produção usa o XGBoost (B).
