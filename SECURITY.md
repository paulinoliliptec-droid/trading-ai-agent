# Segurança

## Princípios

1. **Nenhuma ordem real.** `AppConfig.live_trading_enabled` é sempre `False` e não é lido do ambiente. O único
   `ExecutionVenue` implementado é o `PaperBroker`; `ensure_simulated()` recusa qualquer outro. O adaptador da
   OANDA só lê dados e só aceita o ambiente Practice.
2. **Segredos fora do código.** Tokens (OANDA, Telegram, MongoDB, API) vêm de variáveis de ambiente ou do Secret
   Manager. `.env` está no `.gitignore`; `.env.example` só tem nomes.
3. **Logs sem segredos.** O formatador JSON mascara tokens do Telegram, `Bearer`, URIs `mongodb://` e
   parâmetros `token=`, `secret=`, `password=` (há teste).
4. **Kill switch independente.** Ficheiro de bloqueio ou `TRADING_KILL_SWITCH=1`; acionável pelo Telegram
   (`/pause`, `/stop`) e pela API (com token). O risco consulta-o antes de cada operação.
5. **Comandos autenticados.** O Telegram só aceita comandos de chats em `TELEGRAM_ALLOWED_CHAT_IDS`. A API exige
   `API_ADMIN_TOKEN` (comparação em tempo constante) para mudar estado.
6. **Mínimo privilégio na GCP.** Conta de serviço própria, acesso só aos segredos e ao bucket do projeto.
7. **Isolamento por tenant.** `tenant_id` obrigatório em todos os registos operacionais.

## Reportar uma vulnerabilidade

Repositório privado. Reportar diretamente ao responsável do projeto; não abrir issues públicas.
