# Roadmap

| Fase | Objetivo | Estado | Critério para avançar |
|---|---|---|---|
| 1. Investigação inicial | Dados reais, features, modelos A/B/C, backtest com custos, risco | Feita (22/10/2026) | |
| 2. Auditoria e evolução | Backtest cronológico, conta virtual, agente persistente, horizontes, regimes, MongoDB, Telegram, CI | **Feita (22/10/2026), com resultado negativo: nenhuma configuração tem vantagem líquida** | |
| 3. Nova hipótese | Procurar vantagem onde o custo pesa menos ou onde há informação que as velas não têm (ver abaixo) | Próxima | Uma configuração qualifica no desenvolvimento E é positiva no teste final (a regra do registo de modelos) |
| 4. Paper trading contínuo | Worker na GCP com o modelo aprovado, Telegram e Atlas ligados | Pronto a ligar, à espera de um modelo aprovado e das credenciais | 3 meses de paper trading coerentes com o backtest (desvio explicado) |
| 5. Endurecimento | Monitorização, alertas, testes de falha | | Incidentes simulados tratados sem intervenção manual |
| 6. Real com capital próprio (opcional) | Execução real numa conta própria, limites mínimos | | Decisão explícita do dono, revisão de risco, conta na corretora em nome próprio |
| 7. SaaS | Multi-tenant, autenticação, subscrição | | Parecer jurídico e regulatório (CMVM, Banco de Portugal, MiCA) |

## Fase 3: hipóteses, por ordem de custo e de plausibilidade

1. **Custos de BTC mais baixos e reais.** Com taxa taker de retalho (0,25% por lado) nenhum horizonte compensa.
   Medir a vantagem bruta com ordens limite (taxa maker) e com a tabela real da conta; o diagnóstico de
   sensibilidade (`scripts/cost_sensitivity.py`) diz se vale a pena.
2. **Informação que as velas não têm.** Funding e open interest dos perpétuos, fluxo de ordens (desequilíbrio do
   livro), dados on-chain; em Forex, diferenciais de taxas de juro e calendário macro com datas de publicação
   fiáveis (o módulo qualitativo já respeita a regra «publicado até t»).
3. **Outro alvo.** Prever volatilidade (mais previsível do que a direção) e usá-la para dimensionar ou filtrar uma
   estratégia simples, em vez de prever qual barreira vem primeiro.
4. **Mais mercados com custos baixos** (pares Forex principais, índices) só depois de 1 a 3, para não multiplicar
   tentativas até aparecer um falso positivo.

Cada nova hipótese conta como tentativa: o número de configurações testadas fica registado no resumo e o critério
de seleção não muda.

## Dependências externas

- Token OANDA Practice (EUR/USD ao vivo e reconciliação de fontes).
- URI do MongoDB Atlas.
- Token e chat do Telegram.
- Projeto GCP dedicado com faturação autorizada.
- Credencial GitHub com a permissão `workflow` para ativar a CI.
