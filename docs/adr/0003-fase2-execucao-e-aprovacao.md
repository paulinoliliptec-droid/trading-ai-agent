# ADR 0003: uma só conta virtual, seleção pré-registada e aprovação de modelos

**Data:** 22/10/2026 · **Estado:** aceite

## Contexto

A auditoria da fase 2 provou dois defeitos no backtest da fase 1: o resultado de cada operação entrava no equity
no instante do sinal (antes de a operação existir) e um stop atravessado por gap saía ao preço do stop. Havia
ainda duas lógicas de execução diferentes (backtest com barreiras pré-calculadas e `PaperBroker` pontual), o que
permitia ao backtest ser mais otimista do que a simulação. Os limiares de decisão eram escolhidos na mesma janela
usada para o early stopping e para a calibração.

## Decisões

1. **Uma só conta virtual** (`PaperAccount`) executa no backtest (velas, `on_bar`) e na operação (preços,
   `on_quote`). Custos, gaps, margem, quantidades mínimas e vendas a descoberto obedecem às mesmas regras.
2. **Backtest vela a vela**: execução na abertura de t+1, stops dentro da vela, avaliação a mercado no fecho,
   decisão no fecho com o estado da conta nesse instante.
3. **Quatro partes por fold** (treino, validação, calibração, teste) separadas por embargo; **sem limiar
   escolhido**: o retorno esperado vem da calibração e o risco exige expectativa positiva depois de custos.
4. **Seleção pré-registada** no período de desenvolvimento (≥ 30 operações e limite inferior do IC95% da
   expectativa líquida > 0). O teste final só se reporta.
5. **Aprovação de modelos**: `aprovado` só se qualificou no desenvolvimento E é positivo no teste final. Um modelo
   não aprovado corre em observação; não há forma de o promover à mão.

## Consequências

- Os resultados da fase 1 não são comparáveis número a número com os da fase 2 (mudou o motor, o BTC deixou de ter
  vendas a descoberto, a calibração tem janela própria).
- Com menos graus de liberdade (sem limiar escolhido, grelha curta, critério fixo), é mais difícil aparecer um
  falso positivo, e mais provável que o resultado honesto seja «não negociar».
- O backtest fica cerca de 10 vezes mais lento do que a versão vetorizada, o que é aceitável (2 anos de velas
  horárias em menos de 1 s).
