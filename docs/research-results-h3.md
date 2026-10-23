# Hipótese 3 (volatilidade): leitura dos resultados

Pré-registo: [h3-volatilidade-preregisto.md](h3-volatilidade-preregisto.md). Tabelas completas:
[reports/h3/resultado.md](../reports/h3/resultado.md). Executado a 23/10/2026; código guardado no Git antes de correr.

## Conclusão

**Hipótese NÃO confirmada.** Prever a volatilidade do BTC e reduzir a exposição quando ela sobe **diminui o
risco** mas **não melhora o retorno ajustado ao risco** depois de custos:

| BTC/USD, desenvolvimento | Volatilidade-alvo (EWMA, escolhida) | Comprar e manter |
|---|---|---|
| Sharpe | 0,98 | 1,04 |
| Volatilidade anual | 38,5% | 48,4% |
| Máximo drawdown | −29,7% | −32,1% |
| Diferença de Sharpe (IC95%) | −0,06 [−0,28; +0,13] | |

No teste final, a diferença é 0,000 (0,139 contra 0,139). Nenhum dos três previsores bate o comprar e manter no
Sharpe, em nenhum dos dois períodos, com significância. O HAR e o XGBoost rodam mais (custos de 4% a 9% ao ano)
e ficam piores do que o EWMA.

## Parte A: a volatilidade é previsível, mas pouco no horizonte de um dia

- **BTC:** o HAR é o melhor previsor nos dois períodos (QLIKE mais baixo, com o IC95% do EWMA − HAR acima de
  zero). O XGBoost não acrescenta nada ao HAR: é pior no desenvolvimento e igual no teste final.
- **EUR/USD:** nenhum previsor se distingue dos outros; o R² do log RV fica perto de zero.
- O R² do HAR no BTC (0,08 e 0,02) é baixo face à literatura. A causa principal é sazonal: ao **sábado** a
  volatilidade do BTC é cerca de metade da dos dias úteis (log RV de −4,6 contra −3,8), e o HAR pré-registado não
  tem esse termo. A correlação de um dia para o seguinte é 0,42.

## Falha de desenho no pré-registo (registada, não corrigida a posteriori)

O critério 3 («Sharpe acima da exposição constante») é **idêntico** ao critério 1: o Sharpe não muda quando se
multiplica a série de retornos por uma constante. A comparação certa teria sido de retorno com a mesma
volatilidade, ou de drawdown. Não altera a conclusão, porque o critério 1 já falha. Fica a lição para os próximos
pré-registos.

## O que fica de útil

- A volatilidade-alvo é uma **ferramenta de risco**: com quase o mesmo Sharpe, corta cerca de 10 pontos de
  volatilidade anual e alguns pontos de drawdown. Pode servir para dimensionar uma estratégia que venha a ter
  vantagem, mas não cria vantagem por si.
- Para o BTC, o EWMA chega e o HAR melhora a previsão. O XGBoost não compensa a complexidade.

## Tentativas acumuladas

Fase 2: 72 configurações. H1: 0 novas (respondida com os dados existentes). H3: 3 previsores (1 seleção). Total:
75. Nenhuma qualificou.

## Próximos passos possíveis (cada um é uma tentativa nova, a pré-registar)

1. **H2, informação que as velas não têm** (funding e open interest dos perpétuos, fluxo de ordens): é a única
   hipótese que traz dados novos em vez de reprocessar os mesmos preços.
2. HAR com o efeito do dia da semana, mas só como melhoria de previsão de risco, sem expectativa de vantagem
   económica.
