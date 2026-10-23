"""Telegram Bot API: notificações e comandos autenticados.

O token vem de `TELEGRAM_BOT_TOKEN` (ou do Secret Manager); nunca do código. Sem token, o
notificador corre em modo «seco» e só regista o que enviaria. Os comandos só são aceites de
chats em `TELEGRAM_ALLOWED_CHAT_IDS`; qualquer outro recebe uma recusa e fica registado.
"""

from __future__ import annotations

import html
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

import httpx

log = logging.getLogger(__name__)

TAG = "[TRADING AI]"   # o bot é partilhado com outra aplicação: todas as mensagens deste sistema levam esta marca


class BotConflict(RuntimeError):
    """Outro consumidor do mesmo bot (webhook registado ou outro `getUpdates`): não se compete por mensagens."""


class Event(StrEnum):
    STARTED = "Sistema iniciado"
    STOPPED = "Sistema interrompido"
    SIGNAL = "Novo sinal"
    SIGNAL_APPROVED = "Sinal aprovado pelo risco"
    SIGNAL_REJECTED = "Sinal rejeitado pelo risco"
    OPENED = "Operação simulada aberta"
    CLOSED = "Operação simulada encerrada"
    PNL = "Resultado"
    RISK_LIMIT = "Limite de risco atingido"
    DRAWDOWN = "Drawdown"
    DAILY_LIMIT = "Limite diário de perdas atingido"
    TECH_FAILURE = "Falha técnica"
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
        text = f"{TAG} <b>{html.escape(event.value)}</b> [SIMULAÇÃO]\n{html.escape(body)}"   # «0.17 < 0.4» não é HTML
        for chat in self.chat_ids:
            self.sent.append((chat, text))
            if self.dry_run:
                log.info("telegram (seco) → %s: %s", chat, text)
                continue
            try:
                r = self.client.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                                     json={"chat_id": chat, "text": text, "parse_mode": "HTML"})
                if r.status_code != 200:
                    log.warning("telegram recusou a mensagem (%s): %s", r.status_code, r.text[:200])
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
                     performance_fn: Callable[[], str], store=None, tenant_id: str = "default") -> dict[str, CommandHandler]:
    """Só consulta, pausa, retoma e paragem. Nada aqui muda pesos de modelos nem limites de risco."""

    def pause() -> str:
        kill_switch.engage("telegram", "/pause")
        return "Pausado: nenhuma operação nova abre até /resume. As posições abertas continuam com stop e alvo."

    def resume() -> str:
        kill_switch.release("telegram")
        return "Retomado (continua só em simulação)."

    def stop() -> str:
        kill_switch.engage("telegram", "/stop")
        if store is not None:
            store.put(f"command:{tenant_id}:close_all", {"by": "telegram", "done": False})
        return "Parado: kill switch acionado e posições simuladas a fechar no próximo ciclo. Desarmar exige /resume."

    return {"/status": status_fn, "/portfolio": portfolio_fn, "/performance": performance_fn,
            "/pause": pause, "/resume": resume, "/stop": stop}


@dataclass
class TelegramBot:
    """Recebe comandos por long polling (`getUpdates`). Corre num processo próprio: fala com o
    worker só através do estado partilhado (kill switch, pedido de fecho, estado das contas)."""

    token: str
    commands: TelegramCommands
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=40))
    offset: int = 0

    def _reply(self, chat_id: int, text: str) -> None:
        try:
            self.client.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                             json={"chat_id": chat_id, "text": f"{TAG}\n{text}"})
        except httpx.HTTPError as e:
            log.warning("telegram falhou: %s", type(e).__name__)

    def _api(self, method: str, **params) -> dict:
        return self.client.get(f"https://api.telegram.org/bot{self.token}/{method}", params=params).json()

    def check_exclusive(self, delete_webhook: bool = False) -> None:
        """Long polling só funciona sem webhook. Por omissão recusa arrancar se houver um (pode ser de outra
        aplicação); apagá-lo é uma decisão explícita do dono (`delete_webhook=True`)."""
        info = self._api("getWebhookInfo").get("result") or {}
        if info.get("url"):
            if not delete_webhook:
                raise BotConflict("o bot tem um webhook registado (outra aplicação a receber mensagens). "
                                  "Confirmar que está inativa e arrancar com --apagar-webhook.")
            self._api("deleteWebhook", drop_pending_updates="false")
            log.warning("webhook do bot apagado por decisão explícita do dono")

    def poll_once(self) -> int:
        try:
            r = self.client.get(f"https://api.telegram.org/bot{self.token}/getUpdates",
                                params={"offset": self.offset, "timeout": 30, "allowed_updates": '["message"]'})
            body = r.json()
        except (httpx.HTTPError, ValueError) as e:
            log.warning("getUpdates falhou: %s", type(e).__name__)
            return 0
        if r.status_code == 409:  # outro processo a ler o mesmo bot, ou um webhook registado entretanto
            raise BotConflict(body.get("description", "conflito no getUpdates"))
        updates = body.get("result", [])
        for u in updates:
            self.offset = max(self.offset, u["update_id"] + 1)
            msg = u.get("message") or {}
            chat, text = (msg.get("chat") or {}).get("id"), msg.get("text", "")
            if chat is not None and text.startswith("/"):
                self._reply(chat, self.commands.handle(int(chat), text))
        return len(updates)


def account_views(store, tenant_id: str = "default") -> dict[str, Callable[[], str]]:
    """Respostas de consulta a partir do estado partilhado (só leitura)."""

    def contas() -> list[tuple[str, dict]]:
        return [(k.split(":")[-1], store.get(k)) for k in store.keys(f"account:{tenant_id}:")]

    def status() -> str:
        ks = store.get("kill_switch") or {}
        linhas = [f"Modo: SIMULAÇÃO · kill switch {'ACIONADO' if ks.get('engaged') else 'desarmado'}"]
        for sym, _ in contas():
            h = store.get(f"health:{tenant_id}:{sym}") or {}
            linhas.append(f"{sym}: último ciclo {h.get('last_cycle', '?')} · falhas seguidas {h.get('consecutive_errors', 0)}")
        return "\n".join(linhas)

    def portfolio() -> str:
        linhas = []
        for sym, st in contas():
            linhas.append(f"{sym}: saldo {st['cash']:.2f} {st['currency']} · posições {len(st['positions'])}")
            for p in st["positions"].values():
                linhas.append(f"  {'comprado' if p['side'] == 1 else 'vendido'} {p['qty']:g} a {p['entry_price']:.5f} "
                              f"(SL {p['stop_loss']}, TP {p['take_profit']})")
        return "\n".join(linhas) or "Sem contas."

    def performance() -> str:
        linhas = []
        for sym, st in contas():
            tr = st["trades"]
            pnl = sum(t["pnl_account"] for t in tr)
            ganhos = sum(1 for t in tr if t["pnl_account"] > 0)
            linhas.append(f"{sym}: {len(tr)} operações · {ganhos} ganhadoras · resultado {pnl:+.2f} {st['currency']} · "
                          f"pico {st['peak_equity']:.2f}")
        return "\n".join(linhas) or "Sem operações."

    return {"status": status, "portfolio": portfolio, "performance": performance}
