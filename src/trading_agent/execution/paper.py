"""Corretora simulada (paper trading) e reconciliação.

Preenche ordens ao preço de mercado com o lado certo do spread, mais slippage e comissão.
Não há caminho daqui para uma corretora real: `is_simulated = True` e o motor recusa
qualquer venue que não o seja (`ensure_simulated`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from trading_agent.brokers.base import ExecutionVenue, Fill, Order, OrderStatus, Position, Quote, Side


@dataclass
class PaperBroker(ExecutionVenue):
    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    cash: float = 100_000.0
    is_simulated: bool = True
    _positions: dict[str, Position] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)
    realized_pnl: float = 0.0

    def submit(self, order: Order, quote: Quote) -> Fill | None:
        if order.quantity <= 0:
            order.status, order.reason = OrderStatus.REJECTED, "quantidade inválida"
            return None
        slip = self.slippage_bps / 1e4
        px = quote.ask * (1 + slip) if order.side == Side.BUY else quote.bid * (1 - slip)
        fee = px * order.quantity * self.fee_bps / 1e4
        signed = order.quantity if order.side == Side.BUY else -order.quantity
        pos = self._positions.get(order.symbol)
        if pos is None or pos.quantity == 0:
            self._positions[order.symbol] = Position(order.symbol, signed, px, order.stop_loss, order.take_profit, quote.timestamp)
        else:
            new_q = pos.quantity + signed
            if pos.quantity * signed < 0:  # reduz ou fecha
                closed = min(abs(signed), abs(pos.quantity))
                self.realized_pnl += closed * (px - pos.avg_price) * (1 if pos.quantity > 0 else -1)
                if new_q == 0:
                    del self._positions[order.symbol]
                else:
                    pos.quantity = new_q
                    if pos.quantity * signed > 0:  # inverteu
                        pos.avg_price = px
            else:
                pos.avg_price = (pos.avg_price * abs(pos.quantity) + px * abs(signed)) / abs(new_q)
                pos.quantity = new_q
        self.realized_pnl -= fee
        self.cash -= signed * px + fee
        order.status = OrderStatus.FILLED
        fill = Fill(order.client_order_id, order.symbol, order.side, order.quantity, px, fee, quote.timestamp)
        self.fills.append(fill)
        return fill

    def positions(self) -> dict[str, Position]:
        return {k: Position(v.symbol, v.quantity, v.avg_price, v.stop_loss, v.take_profit, v.opened_at) for k, v in self._positions.items()}


def reconcile(expected: dict[str, float], venue: ExecutionVenue, tolerance: float = 1e-9) -> list[str]:
    """Compara as quantidades que o motor julga ter com as da corretora. Devolve as diferenças."""
    atual = {k: p.quantity for k, p in venue.positions().items()}
    diffs = []
    for sym in sorted(set(expected) | set(atual)):
        e, a = expected.get(sym, 0.0), atual.get(sym, 0.0)
        if abs(e - a) > tolerance:
            diffs.append(f"{sym}: motor={e} corretora={a}")
    return diffs
