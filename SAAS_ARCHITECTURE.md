# Arquitetura SaaS multi-tenant (preparação, nada ativado)

> Nesta fase **não há negociação para terceiros nem faturação transacional**. O modelo `Tenant` existe para que
> o código cresça já com isolamento; `Tenant.enable_live_trading()` recusa por construção.

## Isolamento por tenant

| Requisito | Como |
|---|---|
| Identidade e autenticação | Identity Platform / Firebase Auth; o `tenant_id` vem do token, nunca do pedido |
| Configuração de risco própria | `Tenant.risk` (mesmos campos de `RiskLimits`), validada pelo motor de risco |
| Conta de corretora própria | `BrokerAccountRef` por tenant; ambiente `practice` nesta fase |
| Credenciais isoladas | Secret Manager, um segredo por tenant e corretora (`tenants/{id}/oanda-token`); o registo do tenant só guarda o nome |
| Histórico segregado | Todas as coleções MongoDB com `tenant_id` obrigatório e índices por tenant; o repositório recusa escrever sem ele |
| Métricas | Calculadas por tenant a partir das operações dele |
| Auditoria | Coleção `audit` com quem, o quê, quando e porquê (decisões do risco incluídas) |
| Permissões | Papéis `owner`, `analyst`, `viewer` (`tenants/models.py`) |

## Modelos comerciais em estudo

### 1. Subscrição SaaS

O cliente paga pelo software. As decisões e a conta são dele; o sistema dá ferramentas (dados, investigação,
backtests, alertas). É o modelo com menor risco regulatório, **desde que** o serviço não se torne, na prática,
gestão de carteira, consultoria personalizada ou receção e transmissão de ordens.

### 2. Comissão por operação executada

O sistema ganha por cada operação. Implicações:

- **Conflito de interesses:** o fornecedor ganha com o volume, não com o resultado do cliente. Incentiva
  mais operações, o oposto do que o risco pede (e o motor sabe decidir «não negociar»).
- **Enquadramento:** cobrar por operação e executar por conta do cliente aproxima-se de serviços de investimento
  (receção e transmissão de ordens, execução por conta de clientes, gestão de carteiras) na aceção da DMIF II.
- Por isso este modelo **não deve ser ativado** sem parecer jurídico.

## Enquadramento regulatório a validar (Portugal e UE)

> Análise de partida para orientar o parecer jurídico, **não é aconselhamento jurídico**.

| Tema | Entidade | Ponto a validar |
|---|---|---|
| Serviços de investimento em instrumentos financeiros (Forex/CFD) | **CMVM** (DMIF II, Código dos Valores Mobiliários e Regime Jurídico das Empresas de Investimento) | Se executar, transmitir ordens ou gerir de forma automática para clientes exige autorização como empresa de investimento |
| Cripto-ativos | **MiCA** (Regulamento (UE) 2023/1114): autorização como prestador de serviços de cripto-ativos (CASP) | Execução de ordens por conta de clientes, gestão de carteiras e consultoria sobre cripto-ativos são serviços MiCA. Confirmar a autoridade competente designada em Portugal (CMVM e/ou Banco de Portugal) |
| Pagamentos e guarda de fundos | **Banco de Portugal** | O sistema nunca deve deter fundos de clientes; os fundos ficam na corretora do cliente |
| Produtos alavancados para retalho | ESMA / CMVM | Limites de alavancagem (30:1 nos pares principais), avisos de risco obrigatórios |
| Comunicações e marketing | CMVM, MiCA | Proibição de prometer rendibilidade; resultados passados com os avisos devidos |
| Dados pessoais | RGPD / CNPD | Credenciais e históricos de clientes são dados pessoais |

**Recomendação:** começar pela subscrição de software sem execução por conta de terceiros; pedir parecer antes
de qualquer funcionalidade que envie ordens de clientes ou cobre por operação.
