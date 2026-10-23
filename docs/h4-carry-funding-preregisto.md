# Hipótese 4: carry de funding, neutro ao preço (pré-registo)

Escrito e guardado no Git **antes** de correr (23/10/2026). Os critérios não mudam depois de ver os resultados.
Conta como tentativa nova (`ROADMAP.md`).

## Porquê é diferente das anteriores

As hipóteses 1 a 3 e a fase 2 tentaram **prever** a direção ou o risco. A H4 não prevê nada: procura um retorno
**estrutural**. Nos perpétuos, quando o funding é positivo, quem está comprado paga a quem está vendido. A
posição **comprada no spot e vendida no perpétuo**, no mesmo nocional, anula o preço do BTC e recebe o funding.
Os riscos são a variação da base (perpétuo contra o spot), o funding negativo, os custos de entrada e saída e a
margem do perpétuo.

## Dados (já recolhidos para a H2, públicos)

- Funding do BTCUSDT (Binance), eventos de 8 em 8 horas, de 2023-01-01 a 2026-10-22.
- Prémio do perpétuo sobre o índice (Binance), de hora a hora: aproxima a base.

## Modelo da posição (por unidade de nocional, diário)

`PnL_dia = Σ funding recebido no dia − Δ(prémio no fecho do dia) − custos de rotação`

- A perna vendida recebe `+funding` (paga quando o funding é negativo).
- O spot e o índice movem-se juntos; a diferença entre as pernas é a variação do prémio.
- **Capital** = nocional do spot + margem do perpétuo de **50%** do nocional (alavancagem 2× no perpétuo, com
  folga para uma subida de ~40% sem liquidação). O retorno reporta-se sobre esse capital (nocional / 1,5).

## Custos (por lado e por perna, incluindo spread e slippage)

| Cenário | Spot | Perpétuo | Papel |
|---|---|---|---|
| **Principal (conservador)** | 25 + 4 bps (Kraken, como em `configs/default.toml`) | 5 + 2 bps (taker de futuros) | Decide |
| Sensibilidade (barato) | 10 + 2 bps | 2 + 1 bps (maker) | Só se reporta |

Abrir ou fechar a posição custa a soma das duas pernas, uma vez por lado.

## Estratégias (2 tentativas)

1. **Sempre ligada:** entra no primeiro dia e fica.
2. **Condicional:** entra quando a média do funding nas últimas 72 h, anualizada, for > 10% e sai quando for < 0%
   (histerese). Os limiares estão fixos aqui: não são otimizados.

Períodos: **desenvolvimento** = primeiros 2/3 dos dias (de 2023-01-11, depois do arranque da média), **teste
final** = último 1/3. **Seleção:** a estratégia com o maior retorno anual líquido no desenvolvimento, no cenário
principal.

## Critério de sucesso (fixo)

A hipótese é **confirmada** se a estratégia escolhida, no **cenário principal**:

1. **Desenvolvimento:** o IC95% do retorno diário líquido médio (bootstrap estacionário, blocos de 20 dias, 2000
   réplicas) fica inteiramente acima de zero;
2. **Teste final:** o retorno anual líquido sobre o capital é positivo;
3. **Vale o risco:** o retorno anual líquido no teste final supera **4%**, uma referência de liquidez sem risco
   em dólares.

Reporta-se também: o drawdown máximo, a percentagem de dias com funding negativo, a pior variação diária do prémio
e a maior subida do BTC em 30 dias (risco de margem).

## Limites conhecidos (aceites antes de correr)

- O funding e o prémio são da Binance. A conta do dono pode não ter acesso a perpétuos (MiCA e CMVM por
  confirmar). Uma confirmação aqui não significa que seja executável.
- Não modela transferências entre corretoras, juros da margem nem riscos de contraparte.
- Mesmo confirmada, a hipótese vai só para observação (sem ordens reais nem aprovação automática).
