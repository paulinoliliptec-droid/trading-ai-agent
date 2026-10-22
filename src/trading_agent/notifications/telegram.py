"""Telegram Bot API: notificações e comandos autenticados.

O token vem de `TELEGRAM_BOT_TOKEN` (ou do Secret Manager); nunca do código. Sem token, o
notificador corre em modo «seco» e só regista o que enviaria. Os comandos só são aceites de
chats em `TELEGRAM_ALLOWED_CHAT_IDS`; qualquer outro recebe uma recusa e fica registado.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

import httpx

log = logging.getLogger(__name__)


class Event(StrEnum):
    STARTED = "Sistema iniciado"
    STOPPED = "Sistema interrompido"
    SIGNAL = "Novo sinal"
    OPENED = "Operação simulada aberta"
    CLOSED = "Operação simulada encerrada"
    PNL = "Resultado"
    RISK_LIMIT = "Limite de risco atingido"
    BROKER_ERROR = "Erro na API da corretora"
    DAILY = "Relatório diário"
    WEEKLY = "Relatório semanal"


@dataclass
class TelegramNotifier:
    token: str | None
    chat_ids: set[int]
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=10))
    sent: list[tuple[int, str]] = field(default_factory=list)

    @property
    def dry_run(self) -> bool:
        return not self.token

    def notify(self, event: Event, body: str) -> None:
        text = f"<b>{event.value}</b> [SIMULAÇÃO]\n{body}"
        for chat in self.chat_ids:
            self.sent.append((chat, text))
            if self.dry_run:
                log.info("telegram (seco) → %s: %s", chat, text)
                continue
            try:
                self.client.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                                 json={"chat_id": chat, "text": text, "parse_mode": "HTML"})
            except httpx.HTTPError as e:  # uma notificação falhada nunca pára o sistema
                log.warning("telegram falhou: %s", type(e).__name__)


CommandHandler = Callable[[], str]


@dataclass
class TelegramCommands:
    allowed_chat_ids: set[int]
    handlers: dict[str, CommandHandler]

    def handle(self, chat_id: int, text: str) -> str:
        cmd = (text or "").strip().split()[0].split("@")[0].lower() if text else ""
        if chat_id not in self.allowed_chat_ids:
            log.warning("comando recusado de chat não autorizado: %s", chat_id)
            return "Não autorizado."
        h = self.handlers.get(cmd)
        if h is None:
            return "Comandos: /status /portfolio /performance /pause /resume /stop"
        return h()


def default_handlers(kill_switch, status_fn: Callable[[], str], portfolio_fn: Callable[[], str],
                     performance_fn: Callable[[], str]) -> dict[str, CommandHandler]:
    def pause() -> str:
        kill_switch.engage("telegram", "/pause")
        return "Pausado: nenhuma operação nova abre até /resume."

    def resume() -> str:
        kill_switch.release("telegram")
        return "Retomado (continua só em simulação)."

    def stop() -> str:
        kill_switch.engage("telegram", "/stop")
        return "Parado: kill switch acionado. Desarmar exige /resume."

    return {"/status": status_fn, "/portfolio": portfolio_fn, "/performance": performance_fn,
            "/pause": pause, "/resume": resume, "/stop": stop}
