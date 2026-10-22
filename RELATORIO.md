# Relatório da fase 2: Trading AI Agent

**Data:** 22/10/2026 · **Repositório:** `paulinoliliptec-droid/trading-ai-agent` (privado) · **Branch:** `fase-2-auditoria`
**Só simulação.** Nenhuma ordem real, nenhuma credencial com permissão de negociar ou levantar fundos.

> O relatório da fase 1 está no histórico do Git (commit `92c6f74`). Os números dele não são comparáveis um a um
> com os desta fase, porque a auditoria encontrou defeitos no motor que os produziu.

## Resumo

1. A auditoria **provou** cinco defeitos estruturais no backtest e no PaperBroker da fase 1, que tornavam os
   resultados otimistas. O mais grave: o resultado de cada operação entrava no equity **no instante do sinal**.
   Estão todos corrigidos e cobertos por testes.
2. Há agora uma **conta virtual única** (backtest e operação), um **agente persistente** que recupera de falhas e
   não duplica ordens depois de reinícios, **modelos versionados** com aprovação fixa, **MongoDB** e **Telegram**
   implementados e testados, e um **kill switch partilhado** entre processos.
3. Foram testadas **72 combinações** (configuração × modelo) em BTC/USD e EUR/USD, com 4 horizontes, 2 barreiras,
   features novas, ablações e 4 modelos. **Nenhuma tem vantagem estatística líquida.** Mesmo com custo zero, a
   expectativa bruta do XGBoost não é positiva com confiança em nenhuma das 12 configurações testadas assim.
4. Não há modelo aprovado: **o agente corre em observação** e a decisão correta hoje é não negociar.
5. **68 testes passam**, lint, bandit e pip-audit limpos. A CI não ficou ativa: o token do GitHub não tem a permissão
   `workflow`.

## 1. Problemas encontrados

| # | Problema | Gravidade | Prova |
|---|---|---|---|
| P1 | O resultado de cada operação entrava no equity no instante do **sinal**, antes de a operação existir; o equity das velas seguintes já o tinha | **Crítica** (drawdown, Sharpe e limites diários calculados com o futuro) | Equity 0,995 no sinal contra 1,0 uma vela antes, numa operação que só fechou 2 h depois |
| P2 | Um stop atravessado por gap saía ao preço do stop | **Alta** (perdas subestimadas) | Vela que abre a 95 com stop a 99: −1% registado, −5% realista |
| P3 | O backtest simulava **vendas a descoberto em BTC à vista** | **Alta** | 346 sinais vendidos de BTC no período de teste; agora recusados |
| P4 | `PaperBroker` sem saldo, margem, capital disponível, stops, limite temporal, persistência nem proteção contra duplicados | **Alta** (impedia o paper trading contínuo) | Leitura do código; testes novos |
| P5 | Sem marcação a mercado durante a operação e estado da carteira sempre com 0 posições | Média | Leitura do código |
| P6 | Early stopping, calibração e escolha do limiar na **mesma** janela de validação | Média (otimismo na calibração) | Leitura do código |
| P7 | `paper_trade_once.py` retreinava o XGBoost em cada ciclo e misturava fontes (treino na Coinbase, velas da Kraken) | Média | Leitura do código |
| P8 | Kill switch só em ficheiro local: o Telegram e a API, noutros serviços, não o veem | Média | Leitura do código |
| P9 | Probabilidade mínima fixa de 0,40 com TP a 2×ATR, quando a taxa de TP-primeiro ronda 25 a 31%: vetava tudo antes de olhar para a expectativa | Baixa (era conservador) | Vetos «probabilidade» em todos os sinais |
| P10 | Dependência de construção `setuptools` 78.1.0 com 4 vulnerabilidades conhecidas | Baixa | pip-audit |

## 2. Correções implementadas

| Área | O que mudou | Ficheiros | Commit |
|---|---|---|---|
| Backtest | Simulador vela a vela: execução na abertura de t+1, stops dentro da vela (gap sai à abertura; stop e alvo na mesma vela = stop), limite temporal no fecho, equity marcado a mercado, decisão no fecho com o estado da conta nesse instante | `backtesting/engine.py` | `a21aaf8` |
| Conta virtual | Saldo em EUR ou USD com conversão cambial **explícita** (falha sem taxa), capital disponível e comprometido, margem por instrumento, realizado e não realizado, ordens parciais, SL/TP/tempo, idempotência por `client_order_id`, estado persistente, quantidade mínima, venda a descoberto só onde permitida | `execution/paper.py`, `execution/instruments.py` | `a21aaf8` |
| Validação | Treino, validação, calibração e teste separados por embargo, com purging | `backtesting/splits.py` | `a21aaf8` |
| Risco | Capital mínimo, dados desatualizados, falhas de API, condições anómalas, tamanho limitado ao capital disponível, retorno esperado estimado fora do treino | `risk/engine.py` | `a21aaf8`, `866a531` |
| Kill switch | Estado partilhado (SQLite entre processos, MongoDB entre serviços), falha fechada se o estado for ilegível, `/stop` fecha posições | `risk/kill_switch.py`, `persistence/state.py` | `a21aaf8`, `fa36300` |
| Agente | Serviço persistente: preço → última vela fechada → features → inferência com modelo versionado (sem treinar) → risco → ordem simulada → gestão de posições → registos → notificações; claim atómico por vela, contador de falhas persistente, recuperação, relatórios diário e semanal | `agent/worker.py`, `scripts/run_agent.py` | `fa36300` |
| Modelos | Registo versionado com SHA-256 e estado de aprovação fixo; treino separado (`train_model.py`) | `models/registry.py` | `fa36300` |
| Investigação | Pipeline com seleção pré-registada, ablações, bootstrap, Monte Carlo, regimes, consistência rótulo/execução; features v2; 4 horizontes; módulo qualitativo experimental | `research/pipeline.py`, `features/` | `866a531` |
| Persistência | Repositório com coleções e índices (SQLite e MongoDB) | `persistence/repository.py` | `fa36300` |
| Telegram | Eventos novos, bot por long polling num processo próprio, comandos só de consulta, pausa e paragem | `notifications/telegram.py`, `scripts/run_telegram_bot.py` | `fa36300` |
| API | Mesmo kill switch partilhado, `/decisions`, `/portfolio` | `apps/api/main.py` | `fa36300` |
| Dados | 15 min de BTC; reamostragem 4 h e 1 d sem inventar velas; reconciliação entre fontes | `data/resample.py`, `data/reconcile.py` | `866a531`, `e7ded62` |
| Infra e CI | CI com bandit e pip-audit; GCP com treino e inferência separados; mercados futuros desativados; setuptools ≥ 83 | `infra/`, `configs/default.toml` | `4b0a42d` |

Decisões de arquitetura em `docs/adr/0003-fase2-execucao-e-aprovacao.md`.

## 3. Testes executados

`pytest -m "not network"` executado a 22/10/2026: **68 passaram, 0 falharam**, cobertura de 81%
(conta virtual 91%, motor de risco 98%, agente 94%, pipeline 88%). `ruff`: sem erros. `bandit`: sem achados.
`pip-audit`: sem vulnerabilidades conhecidas (o `torch` CPU não é auditável pelo PyPI).

| Pedido | Teste |
|---|---|
| Gestão de capital com 100 € | `test_account.py::test_100_euros_conversao_explicita_e_capital_disponivel`, `test_suficiencia_de_capital_100_euros` |
| Ordens de compra e venda | `test_compra_e_venda_realizam_resultado_com_custos`, `test_venda_a_descoberto_so_onde_e_permitida` |
| Stops e encerramentos | `test_stop_alvo_e_tempo_ao_vivo`, `test_stop_em_gap_sai_a_abertura_nao_ao_stop`, `test_stop_e_alvo_na_mesma_vela_conta_o_stop` |
| Execução parcial | `test_execucao_parcial_e_resto_no_preco_seguinte` |
| Reinício com posição aberta | `test_reinicio_com_posicao_aberta_preserva_tudo`, `test_agent.py::test_posicao_e_gerida_depois_do_reinicio` |
| Recuperação após erro | `test_falhas_de_api_contam_e_o_agente_recupera`, `test_erro_inesperado_nao_mata_o_agente` |
| Idempotência das ordens | `test_ordem_duplicada_nao_executa_duas_vezes`, `test_ciclo_abre_posicao_e_reinicio_nao_duplica` |
| Dados desatualizados | `test_dados_desatualizados_nao_abrem_posicao`, `test_protecoes_operacionais` |
| Falhas de comunicação | `test_falhas_de_api_contam_e_o_agente_recupera`, `test_kill_switch_falha_fechada_se_estado_ilegivel` |
| Kill switch persistente | `test_kill_switch_partilhado_entre_processos` (processo separado), `test_api_status_e_killswitch_exige_token`, `test_stop_do_telegram_fecha_posicoes_e_bloqueia` |
| Correção cronológica do backtest | `test_backtest_chronology.py::test_mudar_o_futuro_nao_muda_o_passado`, `test_entrada_na_abertura_seguinte_e_sem_sobreposicao`, `test_equity_marca_a_mercado_durante_a_operacao`, `test_limite_diario_bloqueia_e_reinicia_no_dia_seguinte` |
| Sem fuga entre treino e teste | `test_sem_fuga_entre_treino_e_teste`, `test_features_nao_veem_o_futuro`, `test_features_v2_nao_veem_o_futuro`, `test_qualitative.py` |
| Os 23 testes da fase 1 | Reproduzidos; 4 atualizados para a interface nova (equity de 1,0 abaixo do capital mínimo; assinaturas de `run_backtest` e `submit`) |

Verificação ao vivo: `scripts/run_agent.py --symbol BTCUSD --ciclos 2` com preços reais da Coinbase. O modelo foi
carregado (estado «rejeitado», por isso em observação) e decidiu sobre a última vela **fechada** (18:00 UTC). O risco
vetou com probabilidade 0,177 e expectativa de −70,7 bps. No 2.º ciclo a vela já estava processada e não houve nova
decisão.

## 4. Datasets

| Dataset | Fonte | Período | Velas | Qualidade |
|---|---|---|---|---|
| BTC/USD 1 h | Coinbase Exchange | 01/01/2023 a 22/10/2026 | 33 364 | 0,04% em falta, 111 duplicados removidos |
| BTC/USD 15 min | Coinbase Exchange | 01/10/2024 a 22/10/2026 | 72 121 | 0,07% em falta, 240 duplicados removidos |
| EUR/USD 1 h (bid + spread real) | Dukascopy | 02/01/2022 a 30/09/2026 | 29 600 | 0,94% em falta (feriados), 0 inválidas |

4 h e 1 d por reamostragem. Manifesto com `synthetic: false` em cada ficheiro; SHA-256 do dataset gravado em cada
modelo. Os dados sintéticos existem só nos testes e estão marcados como tal.

## 5. Experiências e métricas

Desenho fixado antes dos resultados (detalhe em `docs/research-results-fase2.md`):
- **Horizontes:** 15 min (só BTC), 1 h, 4 h e 1 d.
- **Barreiras:** TP 2 / SL 1 e TP 1 / SL 1.
- **Ablações:** features v1 contra v2, e janela de 1 ano contra janela crescente.
- **Modelos:** A (regras), B (XGBoost), C (GRU) e D (ensemble por empilhamento).
- **Validação:** 6 folds walk-forward, dos quais 4 de desenvolvimento e 2 de teste final (só reportado).
- **Incerteza:** IC95% por bootstrap por blocos e Monte Carlo.

**Diagnóstico:**

| Pergunta | Resposta |
|---|---|
| Features? | As v2 não melhoram as v1 (AUC 0,50 contra 0,52 em BTC 1 h). AUC no treino de 0,57 a 0,72 contra 0,43 a 0,54 fora: sobreajuste. Brier skill negativo em todas |
| Horizonte? | Em BTC, abaixo de 4 h o custo é 0,9 a 2 ATR (a 15 min o ponto morto é ≥ 100%). No diário o custo deixa de mandar, mas o modelo sobreajusta (~1 200 velas) |
| Custos? | Inviabilizam o BTC de curto prazo, mas **não são a única causa**: com custo zero, nenhum IC95% da expectativa bruta exclui o zero |
| Calibração estável? | Não: ECE por fold de 0,004 a 0,48; Brier skill até −0,31 |
| Rotulagem correta? | Sim: saída real igual à barreira do rótulo em 96 a 100% das operações simuladas |
| Regimes? | Sem regime consistente (AUC por terço de 0,27 a 0,58, sem padrão) |
| Janelas? | Janela de 1 ano igual à crescente |
| Ensemble? | Às vezes perde menos no desenvolvimento, nunca qualifica, não confirma no teste final |

## 6. Resultado líquido depois de custos

| | BTC/USD (40 combinações) | EUR/USD (32 combinações) |
|---|---|---|
| Qualificadas no desenvolvimento | **0** | **0** |
| Melhor expectativa líquida no desenvolvimento, com ≥ 30 operações | GRU 1 h, janela de 1 ano: −30,9 bps, IC95% [−51,8; −6,6], 80 operações, −5,1% | Regras 1 d, TP 2 / SL 1: +12,5 bps, IC95% [−18,5; +50,2], 36 operações, +2,1% |
| Mesma configuração no teste final | 1 operação, −29,9 bps | 17 operações, +0,1 bps |
| Comprar e manter (desenvolvimento 1 h) | +58,3% (queda máxima de 35%) | +6,0% (queda máxima de 9%) |
| Comprar e manter (teste final 1 h) | −14,4% (queda máxima de 39%) | −2,6% (queda máxima de 6%) |
| Não negociar | 0% | 0% |
| **Simulação 100 € (conta em EUR, risco de produção)** | Desenvolvimento: 80 operações, −5,1%. Teste final: 1 operação, −0,06% | 0 operações nos dois períodos (vetadas por probabilidade e expectativa) |

**Leitura:**
- **Nenhuma estratégia testada é melhor do que não negociar com confiança estatística.**
- Comprar e manter ganhou num período e perdeu no outro, sempre com quedas de 6% a 39%.
- **Alavancagem:** em EUR/USD a 1 h, −1,0 bp por operação com um nocional de 4,3 vezes o capital deu −24% em 660
  operações.

## 7. Estado do Forex

- **Dados:** histórico completo de 01/2022 a 09/2026. Outubro de 2026 falta porque a Dukascopy não publica o ficheiro
  do mês corrente.
- **Recolha:** a Dukascopy limita a cadência; a recolha guarda cada mês em cache e retoma sozinha (o bloqueio de
  hoje foi ultrapassado assim).
- **Modelos:** próprios para EUR/USD, nunca o de BTC.
- **15 minutos:** inviável na Dukascopy (seriam cerca de 3 500 pedidos com limite de cadência).
- **Custos:** spread real dos dados, mediana de 0,34 bps (percentil 90: 0,72); total ida e volta de 0,7 a 1,1 bps.
- **Ao vivo:** exige a **OANDA Practice** (sem token neste ambiente; o agente recusa arrancar EUR/USD sem ela). A Kraken
  EUR/USD não é usada como dados de mercado, porque é outro mercado.
- **Antes de usar a OANDA** com um modelo treinado na Dukascopy: correr `data/reconcile.compare_sources` no período
  comum.

## 8. Estado do MongoDB

- **Sem acesso:** sem URI, sem CLI e sem configuração; nada foi inventado.
- **Implementação:** StateStore e Repository completos, com 8 coleções e índices (únicos onde garantem idempotência),
  `tenant_id` obrigatório.
- **Testes:** contra `mongomock`.
- **Até haver URI:** o agente usa SQLite local com o mesmo contrato.
- **Preparação:** `scripts/mongo_init.py` cria os índices; `docs/mongodb.md` diz exatamente o que é preciso (cluster
  M0, utilizador `readWrite` só na base `trading_agent`, lista de IPs, URI no Secret Manager).

## 9. Estado do Telegram

- **Implementado e testado em modo seco** (sem token neste ambiente).
- **Notificações:**
  - arranque;
  - sinal aprovado ou rejeitado;
  - operação aberta e operação encerrada, com o resultado;
  - drawdown (a metade do limite);
  - limite diário;
  - falha técnica;
  - relatórios diário e semanal.
- **Comandos:** `/status`, `/portfolio`, `/performance`, `/pause`, `/resume` e `/stop`, só de chats autorizados.
  `/stop` aciona o kill switch e fecha as posições simuladas no ciclo seguinte. Nenhum comando altera modelos ou
  limites de risco.
- **Bot:** corre num processo próprio e fala com o agente só pelo estado partilhado.
- **Falta:** `TELEGRAM_BOT_TOKEN` e `TELEGRAM_ALLOWED_CHAT_IDS`.

## 10. Estado da Google Cloud

- **Nenhum recurso criado.**
- **Faturação não verificada:** a conta tem 6 projetos, nenhum de trading. A API de faturação não está ativa no projeto
  por omissão (`dra-kiesse`, outro produto), e ativá-la seria alterar um projeto existente, por isso não se ativou.
  Contas de faturação e créditos ficam por confirmar.
- **Preparado, não executado:** `infra/gcp/deploy.sh` para um **projeto dedicado**:
  - **inferência contínua:** VM e2-micro com o agente e o bot em systemd;
  - **treino:** Cloud Run Job semanal (2 vCPU e 4 GiB), separado da inferência;
  - Cloud Storage para dados e modelos;
  - Secret Manager;
  - conta de serviço com acesso mínimo.
- **Custo estimado (a confirmar na calculadora oficial):** cerca de 0 a 10 USD por mês. A e2-micro pode caber no nível
  gratuito nalgumas regiões dos EUA; fora dele, 7 a 9 USD.

## 11. Limitações conhecidas

- **Investigação:** dois mercados e um período por mercado; 72 combinações. Com o critério fixo, a probabilidade de um
  falso positivo é baixa mas não nula (nenhuma passou).
- **Custos de BTC:** pressupostos (taxa taker de referência), não os da conta real.
- **Dados de que não dispomos:** livro de ordens, funding, on-chain e macro com datas de publicação. O módulo
  qualitativo existe e está testado, mas não tem fonte.
- **Modelos em produção:** a inferência usa o XGBoost; a GRU e o ensemble só existem na investigação.
- **Execução:** a execução parcial só é simulada ao vivo; no backtest os stops executam por inteiro.
- **CI:** não ativa (falta a permissão `workflow`); o ficheiro está em `infra/ci/github-actions-ci.yml`.
- **Artefactos de modelos:** em pickle, com SHA-256 verificado; carregar só os do projeto.

## 12. Próximas ações prioritárias

1. **Não operar com estes modelos.** Manter o agente em observação para validar a operação contínua (estabilidade,
   reinícios, registos) sem arriscar nada.
2. **Fornecer as credenciais que faltam:**
   - OANDA Practice;
   - URI do MongoDB Atlas (M0);
   - token e chat do Telegram;
   - projeto GCP dedicado com faturação autorizada;
   - credencial GitHub com a permissão `workflow`.
3. **Nova hipótese de investigação** (fase 3 em `ROADMAP.md`), por ordem:
   - custos reais e ordens limite em BTC;
   - informação que as velas não têm (funding, fluxo de ordens, on-chain, calendário macro com datas fiáveis);
   - prever a volatilidade em vez da direção.

   Cada hipótese conta como tentativa e o critério não muda.
4. **Reconciliar OANDA com Dukascopy** antes de qualquer EUR/USD ao vivo.
5. **Parecer jurídico** antes de qualquer funcionalidade para terceiros (`SAAS_ARCHITECTURE.md`).

## Ficheiros e relatórios produzidos

- **Investigação:**
  - `reports/fase2/*.json` (18 experiências);
  - `reports/fase2/resumo_BTCUSD.json` e `reports/fase2/resumo_EURUSD.json`;
  - `reports/fase2/sensibilidade_custos.json`;
  - `reports/fase2/experiencias.log`.
- **Documentos:**
  - `docs/research-results-fase2.md` e `docs/research-results-fase2-tabelas.md`;
  - `docs/mongodb.md`;
  - `docs/adr/0003-fase2-execucao-e-aprovacao.md`.
- **Commits na branch:** `a21aaf8`, `fa36300`, `866a531`, `4b0a42d`, `57571ca`, `e7ded62`, `989df1a` e o deste relatório.
