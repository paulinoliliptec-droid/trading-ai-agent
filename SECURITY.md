# Segurança

## Princípios

1. **Nenhuma ordem real.** `AppConfig.live_trading_enabled` é sempre `False` e não é lido do ambiente. O único
   `ExecutionVenue` é a conta virtual (`PaperAccount`); `ensure_simulated()` recusa qualquer outro, também no
   arranque do agente. O adaptador da OANDA só lê dados e só aceita o ambiente Practice. Não há credenciais com
   permissão de negociar ou levantar fundos em lado nenhum do projeto.
2. **Segredos fora do código.** Tokens (OANDA, Telegram, MongoDB, API) vêm do ambiente (`.env`, no `.gitignore`)
   ou do Secret Manager. `.env.example` só tem nomes.
3. **Logs sem segredos.** O formatador JSON mascara tokens do Telegram, `Bearer`, URIs `mongodb://` e parâmetros
   `token=`, `secret=`, `password=` (há teste).
4. **Kill switch partilhado e com falha fechada.** Estado em `StateStore` (SQLite entre processos locais, MongoDB
   entre serviços), mais a variável `TRADING_KILL_SWITCH=1` e o ficheiro `data/KILL_SWITCH`. Se o estado partilhado
   não puder ser lido, considera-se acionado. Acionável pelo Telegram (`/pause`, `/stop`) e pela API (com token).
5. **Comandos autenticados e limitados.** O Telegram só aceita comandos de chats em `TELEGRAM_ALLOWED_CHAT_IDS`, e
   os comandos só consultam, pausam, retomam ou param: nenhum altera modelos ou limites de risco. A API exige
   `API_ADMIN_TOKEN` (comparação em tempo constante) para mudar estado.
6. **Modelos íntegros.** Os artefactos usam `joblib` (pickle): carregar um ficheiro adulterado executaria código.
   Por isso cada modelo tem o SHA-256 nos metadados, verificado ao carregar, e só se carregam artefactos produzidos
   por este projeto (diretório local ou bucket próprio com acesso restrito).
7. **Mínimo privilégio na GCP.** Conta de serviço própria com acesso só aos segredos, ao bucket e aos logs.
8. **Isolamento por tenant.** `tenant_id` obrigatório em todos os registos operacionais.

## Verificações automáticas

`bandit` (análise estática) e `pip-audit` (vulnerabilidades conhecidas nas dependências) correm na CI
(`infra/ci/github-actions-ci.yml`). Exceções do bandit justificadas em `pyproject.toml`.

## Reportar uma vulnerabilidade

Repositório privado. Reportar diretamente ao responsável do projeto; não abrir issues públicas.
