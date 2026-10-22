"""Bot do Telegram (processo próprio): comandos autenticados de consulta, pausa e paragem.

Uso: TELEGRAM_BOT_TOKEN=… TELEGRAM_ALLOWED_CHAT_IDS=123 python scripts/run_telegram_bot.py
Fala com o worker só pelo estado partilhado (MongoDB Atlas ou data/state.db). Não altera modelos
nem limites de risco.
"""

from __future__ import annotations

import argparse
import logging

from trading_agent.config import Secrets
from trading_agent.monitoring.logging_setup import setup_logging
from trading_agent.notifications.telegram import (
    BotConflict,
    TelegramBot,
    TelegramCommands,
    account_views,
    default_handlers,
)
from trading_agent.persistence.state import default_store
from trading_agent.risk.kill_switch import KillSwitch


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--apagar-webhook", action="store_true",
                    help="apaga um webhook registado no bot (só se a aplicação que o usava estiver inativa)")
    args = ap.parse_args()
    sec = Secrets()
    if not sec.telegram_bot_token or not sec.allowed_chat_ids():
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN e/ou TELEGRAM_ALLOWED_CHAT_IDS (no ambiente ou no Secret Manager).")
    store = default_store()
    v = account_views(store, sec.tenant_id)
    cmds = TelegramCommands(sec.allowed_chat_ids(), default_handlers(KillSwitch(store=store), v["status"], v["portfolio"],
                                                                     v["performance"], store=store, tenant_id=sec.tenant_id))
    bot = TelegramBot(sec.telegram_bot_token.get_secret_value(), cmds)
    try:
        bot.check_exclusive(delete_webhook=args.apagar_webhook)
        while True:
            bot.poll_once()
    except BotConflict as e:  # só uma instância consome o bot; sair é melhor do que roubar mensagens
        logging.getLogger("telegram").error("bot não arrancou: %s", e)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
