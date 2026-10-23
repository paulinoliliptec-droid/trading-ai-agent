# Hipótese 3: prever a volatilidade e usá-la para dimensionar (pré-registo)

Escrito e guardado no Git **antes** de correr a experiência (23/10/2026). Os critérios abaixo não mudam
depois de ver os resultados. Esta hipótese conta como tentativa nova no registo de tentativas (`ROADMAP.md`).

## Porquê

As fases 1 e 2 mostraram que a **direção** do BTC e do EUR/USD não é previsível com vantagem líquida, nem com
custo zero. A volatilidade é, na literatura, muito mais persistente e previsível (agrupamento de volatilidade;
modelo HAR-RV de Corsi, 2009). A pergunta deixa de ser «para onde vai o preço» e passa a ser «quanto vai mexer».
Uma previsão de volatilidade só tem valor económico se melhorar uma decisão: aqui, **quanto expor** a uma
posição simples.

## Dados

- BTC/USD: velas horárias da Coinbase, 2023-01-01 a 2026-10-22 (os mesmos dados das fases anteriores).
- EUR/USD: velas horárias da Dukascopy, só para a parte A (qualidade da previsão). Uma posição comprada
  permanente em EUR/USD não é uma estratégia com sentido económico, por isso não entra na parte B.
- Unidade: o dia UTC. Volatilidade realizada diária `RV_t = sqrt(Σ r_h²)` das 24 velas horárias (pelo menos 20
  presentes). Para o EUR/USD contam só os dias úteis.

## Parte A: qualidade da previsão (um dia à frente)

Previsores, todos ajustados só com dados até ao fim do dia `t` para prever `RV_{t+1}`:

1. **EWMA** (RiskMetrics, λ = 0,94) sobre `RV²`: a referência ingénua.
2. **HAR-RV** em logaritmos: `log RV_{t+1} = b0 + b1·log RV_t + b2·log RV_sem + b3·log RV_mês` (OLS). As janelas
   são de 7 e 30 dias no BTC e de 5 e 22 no EUR/USD.
3. **XGBoost** com as features do HAR, mais a volatilidade das últimas 6 horas, a semivariância negativa do dia,
   o |retorno| diário, a amplitude e o volume relativo, a prever `log RV_{t+1}`.

Validação: janela de treino a crescer, com os primeiros 365 dias só para treino (252 no EUR/USD) e reajuste a
cada 30 dias. Cada previsão usa apenas modelos ajustados com alvos já conhecidos. O período fora da amostra
divide-se em **desenvolvimento** (primeiros 2/3) e **teste final** (último 1/3).

Perdas: QLIKE sobre a variância (robusta a ruído na volatilidade realizada) e o erro quadrático em `log RV`.
A previsão em variância dos modelos logarítmicos leva a correção de *smearing* estimada no treino.

## Parte B: valor económico no BTC (dimensionamento por volatilidade-alvo)

- Exposição comprada no BTC à vista: `w_t = min(1, σ_alvo / σ̂_{t+1})`, com uma volatilidade-alvo de 40% ao ano.
  Sem alavancagem (w ≤ 1) e sem posições vendidas, como no `configs/default.toml`.
- A decisão é tomada no fecho do dia `t` e aplica-se ao retorno do dia `t+1`. Rebalanceia só se |Δw| ≥ 0,10.
- Custos: |Δw| × (comissão + spread + slippage do BTC em `configs/default.toml`: 25 + 2 + 2 bps por lado).
- Referências: **comprar e manter** (w = 1) e **exposição constante** igual à exposição média da estratégia no
  mesmo período (para separar o efeito de reduzir a exposição do efeito de a fazer variar).

Tentativas: 3 (uma por previsor). **Seleção:** o previsor com o melhor Sharpe líquido no desenvolvimento.

## Critério de sucesso (fixo)

A hipótese é **confirmada** só se o previsor escolhido cumprir os três pontos:

1. **Desenvolvimento:** a diferença de Sharpe líquido entre a volatilidade-alvo e o comprar e manter tem o IC95%
   inteiramente acima de zero (bootstrap estacionário emparelhado dos retornos diários, blocos médios de 20 dias,
   2000 réplicas).
2. **Teste final:** essa diferença de Sharpe é positiva. Só se reporta: não volta a escolher nada.
3. **Contra a exposição constante:** a diferença de Sharpe também é positiva no desenvolvimento. Se não for, o
   ganho vem só de expor menos, não da previsão.

A parte A é informativa. Um bom resultado de previsão sem valor na parte B **não** confirma a hipótese.

Se a hipótese for confirmada, o passo seguinte é integrar o dimensionamento no agente em observação. Nunca há
aprovação automática para paper trading com posições.
