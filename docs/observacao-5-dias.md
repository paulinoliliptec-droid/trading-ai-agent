# Teste de observação de cinco dias

Objetivo: verificar a **operação** (dados, decisões, persistência, alertas e controlo de risco) com o tenant
pessoal, o Atlas e o Telegram ligados. **Não é** um teste de vantagem: nenhum modelo tem vantagem líquida
demonstrada (RELATORIO.md) e nenhum é aprovado com base neste período. O agente corre em `--modo observacao`:
regista cada decisão e o veto do risco, mas não abre posições.

| Dia | O quê | Como se verifica |
|---|---|---|
| 1 | Integração: Atlas, índices, tenant pessoal, Telegram, arranque do worker | `scripts/mongo_init.py`, `scripts/tenant_init.py`, `/status` no Telegram, mensagem «[TRADING AI] Sistema iniciado» |
| 2 | Recolha: velas, sinais e decisões a cada vela fechada | `decisions` cresce uma por vela; `events` sem erros; `/status` mostra o último ciclo |
| 3 | Previsões vs movimentos seguintes | `python scripts/observation_report.py --dias 3` (direção, retorno bruto e líquido, Brier) |
| 4 | Falhas: reinício do worker a meio de uma vela, do bot, perda de rede; `/pause`, `/stop`, `/resume` | Sem decisões duplicadas (índice único), kill switch visto pelo worker no ciclo seguinte, alertas de falha técnica |
| 5 | Relatório consolidado | `python scripts/observation_report.py --dias 5` → `reports/observacao/relatorio_<data>.md` |

O relatório inclui: dados recolhidos, sinais, decisões aprovadas e rejeitadas (com os motivos), resultados
simulados (se houver), qualidade preditiva fora da amostra, custos assumidos, erros técnicos e o uso do Atlas
(face aos 512 MB do M0). O consumo da VM vem do Cloud Monitoring (CPU e memória da `trading-ai-worker`).

## Testes do dia 4 (manuais, registados no relatório)

1. `systemctl restart trading-agent@BTCUSD` a meio de uma vela: a vela seguinte é processada uma vez.
2. `/pause`: o `/status` mostra «ACIONADO» e o worker regista o veto «kill switch» no ciclo seguinte. `/resume` desarma.
3. `/stop`: kill switch acionado e pedido de fecho registado (`command:pessoal:close_all`).
4. Arrancar um segundo bot com o mesmo token: o segundo sai com conflito (409) e o primeiro continua.
5. Comando de um chat não autorizado: «Não autorizado.» e um aviso no log.
