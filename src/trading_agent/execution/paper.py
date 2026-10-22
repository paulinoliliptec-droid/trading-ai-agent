"""Conta virtual de paper trading: saldo, margem, posições, ordens, stops e reconciliação.

É o MESMO código no backtest (`on_bar`, velas) e na operação contínua (`on_quote`, preços ao
vivo): o backtest não pode ser mais otimista do que a simulação que se vai correr.

Contabilidade (na moeda da conta, com conversão cambial explícita):
  · saldo (`cash`) = capital inicial + resultados realizados − comissões;
  · equity = saldo + resultado não realizado das posições abertas, ao preço de saída
    (bid para comprado, ask para vendido);
  · capital comprometido = nocional / alavancagem do instrumento (à vista: o nocional todo);
  · capital disponível = equity − capital comprometido.

Execução: compra no ask, venda no bid, mais slippage contra nós e comissão sobre o nocional.
Stops em velas: se a vela ABRE para lá do stop, sai-se à abertura (gap), não ao preço do stop.
Stop e take-profit na mesma vela: conta o stop (não se sabe qual veio primeiro).
Idempotência: o mesmo `client_order_id` nunca executa duas vezes.
Nada aqui fala com uma corretora real: `is_simulated = True` e o motor recusa o resto.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from trading_agent.brokers.base import ExecutionVenue, Fill, Order, OrderStatus, Position, Quote, Side
from trading_agent.execution.instruments import FxConverter, InstrumentSpec


def _iso(t: datetime | None) -> str | None:
    return t.isoformat() if t is not None else None


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


@dataclass
class OpenPosition:
    symbol: str
    side: int                       # 1 comprado, -1 vendido
    qty: float
    entry_price: float              # preço médio de execução (moeda de cotação)
    entry_mid: float                # preço médio de mercado à entrada (para separar custos)
    opened_at: str
    client_order_id: str
    stop_loss: float | None = None
    take_profit: float | None = None
    max_bars: int | None = None
    expires_at: str | None = None
    bars_held: int = 0
    fees_quote: float = 0.0
    meta: dict = field(default_factory=dict)


@dataclass
class OrderResult:
    order: Order
    fill: Fill | None
    duplicate: bool = False
    closed_trade: dict | None = None


class PaperAccount(ExecutionVenue):
    is_simulated = True

    def __init__(self, specs: dict[str, InstrumentSpec], currency: str = "USD", initial_capital: float = 10_000.0,
                 fx: FxConverter | None = None, liquidity: dict[str, float] | None = None):
        self.specs = specs
        self.currency = currency
        self.initial_capital = float(initial_capital)
        self.fx = fx or FxConverter()
        self.liquidity = liquidity or {}          # quantidade máxima executável por preço (execução parcial)
        self.cash = float(initial_capital)
        self.positions_: dict[str, OpenPosition] = {}
        self.orders: dict[str, dict] = {}         # client_order_id → estado da ordem
        self.pending: dict[str, Order] = {}       # ordens por executar ou parcialmente executadas
        self.trades: list[dict] = []              # operações encerradas
        self.fills: list[Fill] = []
        self.marks: dict[str, tuple[float, float]] = {}  # símbolo → (bid, ask)
        self.realized_pnl = 0.0                   # moeda da conta, já com comissões
        self.fees_paid = 0.0
        self.peak_equity = self.initial_capital
        self.day: str | None = None
        self.day_start_equity = self.initial_capital
        self.last_equity = self.initial_capital

    # ---------- conversões e avaliação ----------
    def _spec(self, symbol: str) -> InstrumentSpec:
        if symbol not in self.specs:
            raise KeyError(f"instrumento desconhecido: {symbol}")
        return self.specs[symbol]

    def to_account(self, amount_quote: float, symbol: str) -> float:
        return self.fx.convert(amount_quote, self._spec(symbol).quote_currency, self.currency)

    def to_quote(self, amount_account: float, symbol: str) -> float:
        return self.fx.convert(amount_account, self.currency, self._spec(symbol).quote_currency)

    def _exit_price(self, pos: OpenPosition) -> float:
        bid, ask = self.marks.get(pos.symbol, (pos.entry_mid, pos.entry_mid))
        return bid if pos.side == 1 else ask

    def unrealized(self, symbol: str) -> float:
        pos = self.positions_.get(symbol)
        if pos is None:
            return 0.0
        return self.to_account(pos.side * pos.qty * (self._exit_price(pos) - pos.entry_price), symbol)

    def equity(self) -> float:
        return self.cash + sum(self.unrealized(s) for s in self.positions_)

    def notional(self, symbol: str) -> float:
        pos = self.positions_.get(symbol)
        if pos is None:
            return 0.0
        return self.to_account(pos.qty * self._exit_price(pos), symbol)

    def used_margin(self) -> float:
        return sum(self.notional(s) / self._spec(s).max_leverage for s in self.positions_)

    def available(self) -> float:
        return self.equity() - self.used_margin()

    def exposure_by_symbol(self) -> dict[str, float]:
        eq = self.equity()
        return {s: self.notional(s) / eq for s in self.positions_} if eq > 0 else {}

    def mark(self, now: datetime) -> float:
        """Atualiza pico e início do dia (UTC). Chamar uma vez por vela/ciclo, depois dos preços."""
        eq = self.equity()
        d = now.astimezone(UTC).date().isoformat()
        if d != self.day:
            self.day = d
            self.day_start_equity = self.last_equity  # equity no fim do dia anterior
        self.peak_equity = max(self.peak_equity, eq)
        self.last_equity = eq
        return eq

    # ---------- preços ----------
    def update_quote(self, q: Quote) -> None:
        if q.bid <= 0 or q.ask <= 0 or q.ask < q.bid:
            raise ValueError(f"preço inválido {q.symbol}: bid={q.bid} ask={q.ask}")
        self.marks[q.symbol] = (q.bid, q.ask)
        base, _, quote = q.symbol.partition("/")
        if quote and {base, quote} >= {self.currency} and base != quote:
            self.fx.set_rate(base, quote, q.mid)

    # ---------- ordens ----------
    def _record(self, order: Order) -> None:
        self.orders[order.client_order_id] = {
            "symbol": order.symbol, "side": str(order.side), "quantity": order.quantity, "filled_qty": order.filled_qty,
            "status": str(order.status), "reason": order.reason, "intent": order.intent,
            "stop_loss": order.stop_loss, "take_profit": order.take_profit, "max_bars": order.max_bars,
            "expires_at": _iso(order.expires_at), "sl_distance": order.sl_distance, "tp_distance": order.tp_distance,
            "meta": order.meta,
        }

    def _reject(self, order: Order, reason: str) -> OrderResult:
        order.status, order.reason = OrderStatus.REJECTED, reason
        self._record(order)
        return OrderResult(order, None)

    def submit(self, order: Order, quote: Quote, now: datetime | None = None) -> OrderResult:
        """Ordem a mercado. Idempotente por `client_order_id`."""
        if order.client_order_id in self.orders:
            prev = self.orders[order.client_order_id]
            order.status, order.reason, order.filled_qty = OrderStatus(prev["status"]), "duplicada: ignorada", prev["filled_qty"]
            return OrderResult(order, None, duplicate=True)
        now = now or quote.timestamp
        spec = self._spec(order.symbol)
        if not spec.enabled:
            return self._reject(order, f"instrumento desativado: {spec.disabled_reason}")
        self.update_quote(quote)
        signed = 1 if order.side == Side.BUY else -1
        pos = self.positions_.get(order.symbol)
        if pos is not None and pos.side == signed and order.intent == "open":
            return self._reject(order, "já existe posição neste instrumento")
        if pos is not None and pos.side != signed:
            order.intent = "close"
            order.quantity = min(order.quantity, pos.qty)
        if order.intent == "close" and pos is None:
            return self._reject(order, "sem posição para fechar")
        qty = spec.round_qty(order.quantity) if order.intent == "open" else order.quantity
        if order.intent == "open":
            if qty < spec.min_qty or qty <= 0:
                return self._reject(order, f"quantidade {order.quantity:g} abaixo do mínimo negociável {spec.min_qty:g}")
            if signed == -1 and not spec.allow_short:
                return self._reject(order, "venda a descoberto não permitida neste instrumento (à vista)")
            px = quote.ask if signed == 1 else quote.bid
            required = self.to_account(qty * px, order.symbol) / spec.max_leverage
            fee = self.to_account(qty * px * spec.fee_bps / 1e4, order.symbol)
            if required + fee > self.available() + 1e-12:
                return self._reject(order, f"capital insuficiente: precisa de {required + fee:.2f} {self.currency}, "
                                           f"disponível {self.available():.2f}")
        order.quantity = qty
        order.status = OrderStatus.NEW
        self.pending[order.client_order_id] = order
        self._record(order)
        res = self._execute(order, quote.bid, quote.ask, now)
        return res

    def _execute(self, order: Order, bid: float, ask: float, now: datetime, level: float | None = None) -> OrderResult:
        """Executa (total ou parcialmente) uma ordem pendente. `level` = preço de stop/alvo atingido (do lado executável)."""
        spec = self._spec(order.symbol)
        remaining = order.quantity - order.filled_qty
        cap = self.liquidity.get(order.symbol, math.inf)
        qty = min(remaining, cap)
        if qty <= 0:
            return OrderResult(order, None)
        signed = 1 if order.side == Side.BUY else -1
        slip = spec.slippage_bps / 1e4
        half = (ask - bid) / 2
        if level is None:
            raw = ask if signed == 1 else bid
            mid = (bid + ask) / 2
        else:
            raw = level
            mid = level - half if signed == 1 else level + half  # level está no lado executável
        px = raw * (1 + slip) if signed == 1 else raw * (1 - slip)
        fee_q = px * qty * spec.fee_bps / 1e4
        fee_a = self.to_account(fee_q, order.symbol)
        self.cash -= fee_a
        self.fees_paid += fee_a
        fill = Fill(order.client_order_id, order.symbol, order.side, qty, px, fee_q, now)
        self.fills.append(fill)
        order.filled_qty += qty
        order.status = OrderStatus.FILLED if order.filled_qty >= order.quantity - 1e-12 else OrderStatus.PARTIALLY_FILLED
        if order.status == OrderStatus.FILLED:
            self.pending.pop(order.client_order_id, None)
        closed = None
        if order.intent == "open":
            pos = self.positions_.get(order.symbol)
            if pos is None:
                sl, tp = order.stop_loss, order.take_profit
                if sl is None and order.sl_distance:
                    sl = px - signed * order.sl_distance
                if tp is None and order.tp_distance:
                    tp = px + signed * order.tp_distance
                self.positions_[order.symbol] = OpenPosition(
                    order.symbol, signed, qty, px, mid, _iso(now), order.client_order_id, sl, tp,
                    order.max_bars, _iso(order.expires_at), 0, fee_q, dict(order.meta))
            else:
                tot = pos.qty + qty
                pos.entry_price = (pos.entry_price * pos.qty + px * qty) / tot
                pos.entry_mid = (pos.entry_mid * pos.qty + mid * qty) / tot
                pos.qty, pos.fees_quote = tot, pos.fees_quote + fee_q
        else:
            closed = self._realize(order.symbol, qty, px, mid, fee_q, now, order.reason or "manual")
        self._record(order)
        return OrderResult(order, fill, closed_trade=closed)

    def _realize(self, symbol: str, qty: float, px: float, mid: float, fee_q: float, now: datetime, reason: str) -> dict | None:
        pos = self.positions_[symbol]
        frac = qty / pos.qty
        entry_fee = pos.fees_quote * frac
        pnl_price_q = pos.side * qty * (px - pos.entry_price)
        self.cash += self.to_account(pnl_price_q, symbol)
        self.realized_pnl += self.to_account(pnl_price_q, symbol) - self.to_account(fee_q + entry_fee, symbol)
        gross_mid_q = pos.side * qty * (mid - pos.entry_mid)
        notional_q = qty * pos.entry_price
        net_q = pnl_price_q - fee_q - entry_fee
        trade = {
            "symbol": symbol, "side": pos.side, "qty": qty, "entry_time": pos.opened_at, "exit_time": _iso(now),
            "entry_price": pos.entry_price, "exit_price": px, "reason": reason, "bars_held": pos.bars_held,
            "notional_quote": notional_q, "pnl_quote": net_q, "pnl_account": self.to_account(net_q, symbol),
            "gross_ret": gross_mid_q / notional_q,           # movimento de mercado (preço médio), antes de custos
            "cost_ret": (gross_mid_q - net_q) / notional_q,  # spread + slippage + comissões
            "net_ret": net_q / notional_q,
            "client_order_id": pos.client_order_id, "meta": dict(pos.meta),
        }
        pos.qty -= qty
        pos.fees_quote -= entry_fee
        if pos.qty <= 1e-12:
            del self.positions_[symbol]
            self.trades.append(trade)
            return trade
        trade["parcial"] = True
        self.trades.append(trade)
        return trade

    def close_position(self, symbol: str, quote: Quote, now: datetime, reason: str) -> OrderResult | None:
        pos = self.positions_.get(symbol)
        if pos is None:
            return None
        self.update_quote(quote)
        side = Side.SELL if pos.side == 1 else Side.BUY
        cid = f"{pos.client_order_id}:close"
        if cid in self.pending:
            return self._execute(self.pending[cid], quote.bid, quote.ask, now)
        order = Order(symbol, side, pos.qty, cid, intent="close", reason=reason)
        if cid in self.orders and self.orders[cid]["status"] == str(OrderStatus.FILLED):
            cid = f"{cid}:{len(self.orders)}"  # fecho de um resto deixado por execução parcial
            order.client_order_id = cid
        self.pending[cid] = order
        self._record(order)
        return self._execute(order, quote.bid, quote.ask, now)

    # ---------- operação contínua (preços ao vivo) ----------
    def on_quote(self, q: Quote, now: datetime | None = None) -> list[dict]:
        """Executa restos de ordens parciais e verifica stop, alvo e limite temporal."""
        now = now or q.timestamp
        self.update_quote(q)
        closed: list[dict] = []
        for o in list(self.pending.values()):
            if o.symbol == q.symbol:
                r = self._execute(o, q.bid, q.ask, now)
                if r.closed_trade:
                    closed.append(r.closed_trade)
        pos = self.positions_.get(q.symbol)
        if pos is not None:
            px = q.bid if pos.side == 1 else q.ask
            reason = None
            if pos.stop_loss is not None and (px - pos.stop_loss) * pos.side <= 0:
                reason = "sl"
            elif pos.take_profit is not None and (px - pos.take_profit) * pos.side >= 0:
                reason = "tp"
            elif pos.expires_at and now >= _dt(pos.expires_at):
                reason = "tempo"
            if reason:
                r = self.close_position(q.symbol, q, now, reason)
                if r and r.closed_trade:
                    closed.append(r.closed_trade)
        return closed

    # ---------- backtest (velas) ----------
    def on_bar(self, symbol: str, t_open: datetime, t_close: datetime, o: float, h: float, lo: float, c: float,
               spread: float = 0.0, basis: str = "mid") -> list[dict]:
        """Processa uma vela: entradas pendentes na abertura, stops/alvos dentro da vela, tempo no fecho.

        `basis="bid"`: OHLC são de bid e ask = bid + spread. `basis="mid"`: OHLC são preço médio.
        """
        if basis == "bid":
            bo, bh, bl, bc = o, h, lo, c
        else:
            bo, bh, bl, bc = o - spread / 2, h - spread / 2, lo - spread / 2, c - spread / 2
        ao, ah, al, ac = bo + spread, bh + spread, bl + spread, bc + spread
        closed: list[dict] = []
        # 1) ordens pendentes executam à abertura
        self.marks[symbol] = (bo, ao)
        for ordem in list(self.pending.values()):
            if ordem.symbol == symbol:
                r = self._execute(ordem, bo, ao, t_open)
                if r.closed_trade:
                    closed.append(r.closed_trade)
        pos = self.positions_.get(symbol)
        if pos is not None:
            # 2) stop e alvo dentro da vela (lado executável: bid para comprado, ask para vendido)
            if pos.side == 1:
                xo, xh, xl = bo, bh, bl
                sl_hit_open = pos.stop_loss is not None and xo <= pos.stop_loss
                sl_hit = pos.stop_loss is not None and xl <= pos.stop_loss
                tp_hit_open = pos.take_profit is not None and xo >= pos.take_profit
                tp_hit = pos.take_profit is not None and xh >= pos.take_profit
            else:
                xo, xh, xl = ao, ah, al
                sl_hit_open = pos.stop_loss is not None and xo >= pos.stop_loss
                sl_hit = pos.stop_loss is not None and xh >= pos.stop_loss
                tp_hit_open = pos.take_profit is not None and xo <= pos.take_profit
                tp_hit = pos.take_profit is not None and xl <= pos.take_profit
            exit_level, reason, when = None, None, t_close
            if sl_hit_open:
                exit_level, reason, when = xo, "sl_gap", t_open
            elif tp_hit_open:
                exit_level, reason, when = pos.take_profit, "tp", t_open
            elif sl_hit:
                exit_level, reason = pos.stop_loss, "sl"
            elif tp_hit:
                exit_level, reason = pos.take_profit, "tp"
            if reason:
                closed += self._close_at_level(symbol, exit_level, spread, when, reason)
            else:
                pos.bars_held += 1
                # 3) limite temporal: sai no fecho da vela
                if pos.max_bars is not None and pos.bars_held >= pos.max_bars:
                    self.marks[symbol] = (bc, ac)
                    closed += self._close_at_level(symbol, bc if pos.side == 1 else ac, spread, t_close, "tempo")
        self.marks[symbol] = (bc, ac)
        return closed

    def _close_at_level(self, symbol: str, level: float, spread: float, now: datetime, reason: str) -> list[dict]:
        pos = self.positions_[symbol]
        side = Side.SELL if pos.side == 1 else Side.BUY
        cid = f"{pos.client_order_id}:close"
        order = Order(symbol, side, pos.qty, cid, intent="close", reason=reason)
        self.pending[cid] = order
        self._record(order)
        r = self._execute(order, level - spread / 2, level + spread / 2, now, level=level)
        if order.status != OrderStatus.FILLED:
            # Em backtest não há liquidez parcial nos stops: o resto fecha ao mesmo nível.
            while order.status != OrderStatus.FILLED:
                r = self._execute(order, level - spread / 2, level + spread / 2, now, level=level)
        return [r.closed_trade] if r.closed_trade else []

    def queue_entry(self, order: Order) -> OrderResult:
        """Backtest: ordem decidida no fecho de t, executada na abertura de t+1 (`on_bar`)."""
        if order.client_order_id in self.orders:
            return OrderResult(order, None, duplicate=True)
        spec = self._spec(order.symbol)
        signed = 1 if order.side == Side.BUY else -1
        if order.symbol in self.positions_:
            return self._reject(order, "já existe posição neste instrumento")
        if signed == -1 and not spec.allow_short:
            return self._reject(order, "venda a descoberto não permitida neste instrumento (à vista)")
        order.quantity = spec.round_qty(order.quantity)
        if order.quantity < spec.min_qty or order.quantity <= 0:
            return self._reject(order, f"quantidade abaixo do mínimo negociável {spec.min_qty:g}")
        if order.symbol in self.marks:
            bid, ask = self.marks[order.symbol]
            px = ask if signed == 1 else bid
            required = self.to_account(order.quantity * px, order.symbol) * (1 / spec.max_leverage + spec.fee_bps / 1e4)
            if required > self.available() + 1e-12:
                return self._reject(order, f"capital insuficiente: precisa de {required:.2f} {self.currency}, "
                                           f"disponível {self.available():.2f}")
        self.pending[order.client_order_id] = order
        self._record(order)
        return OrderResult(order, None)

    # ---------- contrato ExecutionVenue ----------
    def positions(self) -> dict[str, Position]:
        return {s: Position(s, p.side * p.qty, p.entry_price, p.stop_loss, p.take_profit, _dt(p.opened_at))
                for s, p in self.positions_.items()}

    # ---------- persistência ----------
    def to_state(self) -> dict:
        return {
            "currency": self.currency, "initial_capital": self.initial_capital, "cash": self.cash,
            "positions": {s: asdict(p) for s, p in self.positions_.items()}, "orders": self.orders,
            "pending": {cid: {**self.orders[cid], "client_order_id": cid} for cid in self.pending},
            "trades": self.trades, "marks": {k: list(v) for k, v in self.marks.items()},
            "fills": [{**asdict(f), "side": str(f.side), "timestamp": _iso(f.timestamp)} for f in self.fills],
            "realized_pnl": self.realized_pnl, "fees_paid": self.fees_paid, "peak_equity": self.peak_equity,
            "day": self.day, "day_start_equity": self.day_start_equity, "last_equity": self.last_equity,
            "fx": [[a, b, r] for (a, b), r in self.fx.rates.items()],
        }

    @classmethod
    def from_state(cls, st: dict, specs: dict[str, InstrumentSpec], liquidity: dict[str, float] | None = None) -> PaperAccount:
        fx = FxConverter({(a, b): r for a, b, r in st.get("fx", [])})
        acc = cls(specs, st["currency"], st["initial_capital"], fx, liquidity)
        acc.cash = st["cash"]
        acc.positions_ = {s: OpenPosition(**p) for s, p in st["positions"].items()}
        acc.orders = st["orders"]
        acc.trades = st["trades"]
        acc.fills = [Fill(f["client_order_id"], f["symbol"], Side(f["side"]), f["quantity"], f["price"], f["fee"], _dt(f["timestamp"]))
                     for f in st.get("fills", [])]
        acc.marks = {k: tuple(v) for k, v in st["marks"].items()}
        acc.realized_pnl, acc.fees_paid = st["realized_pnl"], st["fees_paid"]
        acc.peak_equity, acc.day, acc.day_start_equity = st["peak_equity"], st["day"], st["day_start_equity"]
        acc.last_equity = st["last_equity"]
        for cid, o in st.get("pending", {}).items():
            acc.pending[cid] = Order(o["symbol"], Side(o["side"]), o["quantity"], cid, o.get("stop_loss"), o.get("take_profit"),
                                     status=OrderStatus(o["status"]), reason=o.get("reason", ""), filled_qty=o["filled_qty"],
                                     max_bars=o.get("max_bars"), expires_at=_dt(o.get("expires_at")), intent=o["intent"],
                                     sl_distance=o.get("sl_distance"), tp_distance=o.get("tp_distance"), meta=o.get("meta") or {})
        return acc

    def summary(self) -> dict:
        return {"moeda": self.currency, "capital_inicial": self.initial_capital, "saldo": round(self.cash, 4),
                "equity": round(self.equity(), 4), "capital_comprometido": round(self.used_margin(), 4),
                "capital_disponivel": round(self.available(), 4), "resultado_realizado": round(self.realized_pnl, 4),
                "resultado_nao_realizado": round(sum(self.unrealized(s) for s in self.positions_), 4),
                "comissoes": round(self.fees_paid, 4), "posicoes": len(self.positions_), "operacoes_fechadas": len(self.trades),
                "ordens_pendentes": len(self.pending)}


class PaperBroker(PaperAccount):
    """Compatibilidade com a fase 1: conta em USD com um instrumento genérico por símbolo."""

    def __init__(self, fee_bps: float = 0.0, slippage_bps: float = 0.0, cash: float = 100_000.0, max_leverage: float = 1.0,
                 allow_short: bool = True):
        self._defaults = dict(fee_bps=fee_bps, slippage_bps=slippage_bps, max_leverage=max_leverage, allow_short=allow_short)
        super().__init__({}, "USD", cash)

    def _spec(self, symbol: str) -> InstrumentSpec:
        if symbol not in self.specs:
            base, _, quote = symbol.partition("/")
            self.specs[symbol] = InstrumentSpec(symbol, "generic", base, quote or "USD", 0.0, 1e-12, **self._defaults)
        return self.specs[symbol]


def reconcile(expected: dict[str, float], venue: ExecutionVenue, tolerance: float = 1e-9) -> list[str]:
    """Compara as quantidades que o motor julga ter com as da conta/corretora. Devolve as diferenças."""
    atual = {k: p.quantity for k, p in venue.positions().items()}
    diffs = []
    for sym in sorted(set(expected) | set(atual)):
        e, a = expected.get(sym, 0.0), atual.get(sym, 0.0)
        if abs(e - a) > tolerance:
            diffs.append(f"{sym}: motor={e} corretora={a}")
    return diffs
