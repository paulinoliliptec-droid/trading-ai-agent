# Trading AI Agent: relatório da fase 3

**Data:** 23/10/2026 · **Modo:** só simulação (observação) · **Utilizador:** só o dono (tenant `pessoal`)

> Resumo executivo. A infraestrutura está **ligada e a correr na Google Cloud** (MongoDB Atlas, Telegram e
> worker em observação). As **quatro hipóteses de investigação** desta fase foram testadas com pré-registo e
> **nenhuma se confirmou**. Ao todo são **81 tentativas**. As 79 de previsão não mostraram vantagem nenhuma; a
> única fonte de retorno real é o carry de funding (H4), mas rende abaixo de uma aplicação sem risco no período
> recente. Não há nenhum modelo aprovado e o sistema continua em observação. Nada aqui é aconselhamento
> financeiro.

---

## 1. Infraestrutura (integração)

| Componente | Estado |
|---|---|
| **MongoDB Atlas** | Ligado. Cluster `trading-ai-m0` (M0 gratuito, AWS US_EAST_1). Utilizador da aplicação com permissão só na base `trading_agent` (uma escrita noutra base é recusada). Acesso de rede só ao IP estático da VM e, temporariamente, ao da Workstation. 9 coleções e 14 índices. |
| **Telegram** | Ligado. `@SerafyAgenticsBot` reutilizado (o webhook antigo do Serafy foi apagado). Só o chat do dono dá comandos. `/status`, `/portfolio`, `/performance`, `/pause`, `/resume` e `/stop` foram testados. Todas as mensagens levam `[TRADING AI]`. |
| **Google Cloud** | Projeto `serafy-agentics` (o que tem faturação). VM `trading-ai-worker` (e2-micro, us-central1) com o worker BTC/USD e o bot. Todos os recursos têm o prefixo `trading-ai`, permissões próprias e segredos no Secret Manager. Nenhum recurso da Serafy foi alterado. |
| **Custo** | ~4 USD/mês com o nível gratuito da e2-micro, 11 a 12 USD/mês sem ele. Atlas: 0. |
| **Docker** | O Compose com Atlas não arranca um MongoDB local; portas só em 127.0.0.1. A imagem passou a encontrar a configuração e os modelos. |
| **Testes** | 86 testes automáticos a passar, mais a verificação ao vivo do circuito Telegram → Atlas → worker (kill switch partilhado, pedido de fecho tratado, sem reprocessar velas depois de um reinício). |
| **SaaS** | A arquitetura multi-tenant mantém-se (tenants, papéis, segredos por tenant). Negociação real e subscrições estão desligadas por construção. |

Bugs anteriores encontrados e corrigidos: a imagem Docker não encontrava a configuração (nenhum contentor
arrancava); os alertas com «<» eram recusados pelo Telegram; o `pytest` não encontrava o pacote `apps`.

Teste de observação de cinco dias: começou a 23/10 e o relatório final está previsto para 27/10
(`python scripts/observation_report.py --dias 5`). Plano em `docs/observacao-5-dias.md`.

---

## 2. Investigação: quatro hipóteses, todas com pré-registo

Regra comum: o critério de sucesso foi escrito e guardado no Git **antes** de correr. Seleção só no período de
desenvolvimento; o teste final só se reporta. Custos reais de retalho (BTC: 25 bps de comissão, 2 de spread e
2 de slippage por lado).

### H1: custos mais baixos no BTC (taxas maker)

**Refutada sem testes novos.** A sensibilidade da fase 2 já mostrava que, mesmo com **custo zero**, nenhuma
configuração tem expectativa bruta com IC95% acima de zero. A melhor tem +4,3 bps, com IC95% de −2,1 a +11,0,
e −26 bps no teste final. Baixar as taxas não cria uma previsão que não existe.

### H3: prever a volatilidade e dimensionar a exposição

Pré-registo: `docs/h3-volatilidade-preregisto.md` · Resultados: `docs/research-results-h3.md`

- A volatilidade é previsível: o HAR-RV bate a média móvel exponencial com significância no BTC. O XGBoost não
  acrescenta nada. No EUR/USD nenhum previsor se destaca.
- Dimensionar a exposição pela volatilidade prevista **reduz o risco** (volatilidade de 48% para 38%, drawdown
  ligeiramente menor), mas **não melhora o Sharpe** face a comprar e manter: −0,06, com IC95% de −0,28 a +0,13,
  no desenvolvimento, e 0,00 no teste final.
- **Não confirmada.** O critério 3 do pré-registo era redundante (o Sharpe não muda com a escala). Ficou
  documentado e não foi corrigido a posteriori.

### H2: informação que as velas não têm (derivados e fluxo de ordens)

Pré-registo: `docs/h2-derivados-preregisto.md` · Resultados: `reports/h2/resultado.md`

Dados novos, públicos e com testes de causalidade, de 2023 a 2026:
- funding rate e prémio do perpétuo (Binance);
- open interest (Bybit);
- volume comprador agressivo do spot (Binance).

Juntaram-se às features da fase 2 (conjunto `v3`).

| Experiência (custos reais) | Operações no desenvolvimento | Líquido bps (IC95%) | Qualifica |
|---|---|---|---|
| 1h, TP 2 / SL 1 | 1 | −94,7 | não |
| 1h, TP 1 / SL 1 | 6 | −90,8 [−112,7; −68,6] | não |
| 4h, TP 2 / SL 1 | 112 | −50,5 [−76,0; −26,1] | não |
| 4h, TP 1 / SL 1 | 0 | — | não |

- **Não confirmada.** Nenhuma das 4 qualificou.
- **Diagnóstico com custo zero:** o AUC fica entre 0,49 e 0,53 com e sem os dados novos (0,50 é o acaso). A
  expectativa bruta com `v3` não é melhor do que com `v2`: é até menor em 3 dos 4 casos no desenvolvimento. Neste
  formato e nestes horizontes, os derivados **não acrescentam poder preditivo sobre a direção**.
- **Reprodutibilidade:** os números da `v2` sem custos coincidem exatamente com os da fase 2.

### H4: carry de funding, neutro ao preço (comprado no spot, vendido no perpétuo)

Pré-registo: `docs/h4-carry-funding-preregisto.md` · Resultados: `reports/h4/resultado.md`

Não prevê nada: recebe o funding que os comprados alavancados pagam aos vendidos. O retorno é calculado sobre o
capital (nocional + 50% de margem) e é líquido de custos (36 bps por lado nas duas pernas) e da variação da base.

| Estratégia «sempre ligada» (escolhida) | Desenvolvimento (2023-01 a 2025-07) | Teste final (2025-07 a 2026-10) |
|---|---|---|
| Retorno anual líquido | **5,7%** | **2,3%** |
| IC95% do retorno diário | [+1,1; +2,1] bps | [+0,3; +0,9] bps |
| Drawdown máximo | −0,2% | −0,3% |
| Funding médio (anual, sobre o nocional) | 8,8% | 4,0% |
| Dias com funding negativo | 6,6% | 18,1% |

- **Não confirmada**, por um critério: o retorno é real e positivo nos dois períodos (critérios 1 e 2 cumpridos),
  mas no teste final fica **abaixo dos 4%** de uma aplicação de liquidez sem risco (critério 3).
- A versão condicional (só com funding alto) rende menos: entra e sai mais vezes e paga mais custos.
- **Tendência:** o funding está a cair (11,8% em 2024, 3,0% em 2026) e os dias negativos estão a aumentar.
  Coincide com a entrada de capital institucional e de ETFs que arbitram esta diferença.
- **Risco não modelado:** no desenvolvimento, o BTC subiu 59% em 30 dias. Com 50% de margem, o perpétuo vendido
  seria liquidado com uma subida de ~40% sem reposição de margem. Executar isto exige monitorização e
  transferências entre contas, além de acesso a perpétuos, que pode não existir a retalho em Portugal.

---

## 3. Conclusão científica

Após **79 tentativas de previsão** com dois mercados (BTC/USD e EUR/USD), horizontes de 15 minutos a 1 dia, três
famílias de modelos e três tipos de informação (preço e volume, volatilidade, derivados e fluxo), **não há
evidência de uma vantagem direcional explorável** com custos de retalho. A única fonte de retorno real
encontrada é **estrutural**, o carry de funding, e está a encolher: no período recente rende menos do que uma
aplicação sem risco, com riscos operacionais que o modelo não cobre. O resultado é consistente: o problema não está na
corretora nem no modelo, mas na falta de informação preditiva sobre a direção nestes horizontes.

Isto **não** prova que não exista vantagem nenhuma. Prova que não existe nas abordagens testadas, com o rigor
aplicado.

## 4. Recomendações

1. **Parar a procura de vantagem direcional** com estes dados e horizontes. Mais configurações do mesmo tipo
   só aumentam o risco de um falso positivo.
2. **Manter o sistema** como infraestrutura validada: observação, alertas e registos. Concluir o teste de cinco
   dias a 27/10 para fechar a validação operacional.
3. **Volatilidade-alvo como ferramenta de risco**, não de lucro. Se o dono quiser uma exposição passiva ao BTC,
   reduz a volatilidade e o drawdown com quase o mesmo Sharpe.
4. **Carry de funding (H4):** não compensa hoje (2,3% ao ano contra 4% sem risco). Vale a pena **monitorizar**:
   se o funding médio de 72 h voltar a níveis de 2024 (acima de ~10% ao ano) de forma sustentada, reavaliar com
   uma conta de derivados real e com reposição de margem. Os dados atualizam-se com `scripts/fetch_derivatives.py`.
5. **Não abrir mais hipóteses de previsão** sem uma fonte de informação genuinamente nova (por exemplo, dados
   pagos de livro de ordens). Cada tentativa a mais aumenta o risco de um falso positivo.

## 5. Pendentes do dono

- Relatório de observação a 27/10.
- Renovar o acesso da Workstation ao Atlas depois de 28/10 (`scripts/atlas_setup.sh`).
- Opcional: retirar o token do bot do serviço `agentos-angola` do projeto `serafy-agentics-fe12b`.
- PRs #2 (integração), #3 (H3), #4 (H2) e #5 (H4) juntos à `main` a 23/10/2026.

## 6. Onde está tudo

| Ficheiro | Conteúdo |
|---|---|
| `docs/fase3-integracao.md` | Detalhe da integração, recursos e bugs |
| `docs/gcp-costs.md` | Recursos GCP criados e custos |
| `docs/h3-volatilidade-preregisto.md`, `docs/research-results-h3.md`, `reports/h3/` | Hipótese 3 |
| `docs/h2-derivados-preregisto.md`, `reports/h2/` | Hipótese 2 |
| `docs/h4-carry-funding-preregisto.md`, `reports/h4/` | Hipótese 4 |
| `ROADMAP.md` | Registo de hipóteses e tentativas |
| `RELATORIO.md` | Relatório da fase 2 (histórico) |
