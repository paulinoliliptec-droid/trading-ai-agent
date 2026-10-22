"""Backtest cronológico, orientado por eventos, através da MESMA conta virtual da operação.

Para cada vela i, por ordem:
  1. ordens decididas no fecho de i−1 executam na ABERTURA de i (compra no ask, venda no bid,
     slippage e comissão);
  2. stops e alvos dentro da vela i (gap na abertura sai à abertura; stop e alvo na mesma vela
     contam como stop);
  3. limite temporal no fecho de i;
  4. avaliação ao preço de fecho (equity com o resultado não realizado) e limites diários;
  5. decisão no FECHO de i, só com features até i e com o estado da conta nesse instante.
A curva de equity em i depende só das velas até i: nunca há lucros ou perdas futuros no passado
(há testes que alteram o futuro e verificam que o passado não muda).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from trading_agent.brokers.base import Order, Side
from trading_agent.execution.instruments import InstrumentSpec
from trading_agent.execution.paper import PaperAccount
from trading_agent.risk.engine import PortfolioState, Proposal, RiskEngine


@dataclass
class MarketCosts:
    """Mantido por compatibilidade: custo ida e volta em fração do preço."""

    fee_bps: float
    slippage_bps: float
    default_spread_bps: float = 0.0

    def round_trip_pct(self, spread_bps: float | None) -> float:
        s = self.default_spread_bps if spread_bps is None or np.isnan(spread_bps) else spread_bps
        return (s + 2 * self.fee_bps + 2 * self.slippage_bps) / 1e4


@dataclass
class BacktestConfig:
    spec: InstrumentSpec
    horizon_bars: int
    tp_mult: float
    sl_mult: float
    initial_capital: float = 10_000.0
    currency: str | None = None           # moeda da conta; por omissão a de cotação
    bar: pd.Timedelta = field(default_factory=lambda: pd.Timedelta(hours=1))
    fx_rate: pd.Series | None = None      # taxa conta→cotação (ex.: EUR/USD) conhecida em cada instante


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series
    vetoes: dict
    decisions: int
    account: PaperAccount


def run_backtest(bars: pd.DataFrame, features: pd.DataFrame, signals: pd.DataFrame, risk: RiskEngine,
                 cfg: BacktestConfig) -> BacktestResult:
    """`bars`: OHLC (+ `spread` em preço, se houver). `signals`: colunas `side` (1, −1, 0) e `prob`,
    indexadas pela vela em cujo FECHO se decide. `features`: pelo menos `atr_pct` (e `spread_bps`)."""
    spec = cfg.spec
    ccy = cfg.currency or spec.quote_currency
    acc = PaperAccount({spec.symbol: spec}, ccy, cfg.initial_capital)
    start = signals.index.min()
    b = bars.loc[bars.index >= start]
    o, h, lo, c = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    sp_series = b["spread"] if "spread" in b.columns else pd.Series(np.nan, index=b.index)
    sp = sp_series.to_numpy(float)
    times = b.index
    sig = signals.reindex(times)
    side_arr = sig["side"].fillna(0).to_numpy(int)
    prob_arr = sig["prob"].fillna(0.0).to_numpy(float)
    f = features.reindex(times)
    atr_pct = f["atr_pct"].to_numpy(float)
    spread_bps = f["spread_bps"].to_numpy(float) if "spread_bps" in f.columns else np.full(len(times), np.nan)
    fx = cfg.fx_rate.reindex(times, method="ffill") if cfg.fx_rate is not None else None
    quote = spec.quote_currency
    vetoes: dict[str, int] = {}
    equity = np.empty(len(times))
    decisions = 0
    for i, ts in enumerate(times):
        t_close = ts + cfg.bar
        if fx is not None and not np.isnan(fx.iloc[i]):
            acc.fx.set_rate(ccy, quote, float(fx.iloc[i]))
        spread_px = sp[i] if not np.isnan(sp[i]) else c[i] * spec.default_spread_bps / 1e4
        acc.on_bar(spec.symbol, ts, t_close, o[i], h[i], lo[i], c[i], spread_px, spec.price_basis)
        eq = acc.mark(t_close)
        equity[i] = eq
        s = side_arr[i]
        if s == 0 or spec.symbol in acc.positions_ or acc.pending or np.isnan(atr_pct[i]):
            continue
        decisions += 1
        sbps = spread_bps[i] if not np.isnan(spread_bps[i]) else spec.default_spread_bps
        cost = spec.round_trip_cost_pct(sbps)
        prop = Proposal(spec.symbol, s, float(prob_arr[i]), cfg.tp_mult * atr_pct[i], cfg.sl_mult * atr_pct[i], cost,
                        float(sbps), float(atr_pct[i]))
        st = PortfolioState(eq, acc.peak_equity, acc.day_start_equity, len(acc.positions_),
                            acc.exposure_by_symbol(), available_equity=acc.available(),
                            bar_move_atr=float((h[i] - lo[i]) / (atr_pct[i] * c[i])) if atr_pct[i] > 0 else 0.0)
        dec = risk.evaluate(prop, st)
        if not dec.trade:
            for r in dec.reasons:
                k = r.split(" ")[0]
                vetoes[k] = vetoes.get(k, 0) + 1
            continue
        notional_quote = acc.to_quote(dec.size_fraction * eq, spec.symbol)
        qty = notional_quote / c[i]
        atr_px = atr_pct[i] * c[i]
        order = Order(spec.symbol, Side.BUY if s == 1 else Side.SELL, qty, f"bt-{ts.isoformat()}",
                      max_bars=cfg.horizon_bars, sl_distance=cfg.sl_mult * atr_px, tp_distance=cfg.tp_mult * atr_px,
                      meta={"signal_time": ts.isoformat(), "prob": float(prob_arr[i]), "edge_bps": dec.expected_edge_bps,
                            "size_fraction": dec.size_fraction, "equity_before": eq})
        r = acc.queue_entry(order)
        if r.order.status.value == "rejected":
            k = r.order.reason.split(" ")[0]
            vetoes[k] = vetoes.get(k, 0) + 1
    # Posição aberta no fim dos dados: fecha ao último fecho (o resultado conta, não se esconde).
    if spec.symbol in acc.positions_:
        last = len(times) - 1
        spread_px = sp[last] if not np.isnan(sp[last]) else c[last] * spec.default_spread_bps / 1e4
        level = c[last] if spec.price_basis == "bid" else c[last] - spread_px / 2
        pos = acc.positions_[spec.symbol]
        level = level if pos.side == 1 else level + spread_px
        acc._close_at_level(spec.symbol, level, spread_px, times[-1] + cfg.bar, "fim_dos_dados")
        equity[-1] = acc.mark(times[-1] + cfg.bar)
    acc.pending.clear()
    trades = pd.DataFrame(acc.trades)
    if not trades.empty:
        trades["signal_time"] = trades["meta"].map(lambda m: m.get("signal_time"))
        trades["equity_before"] = trades["meta"].map(lambda m: m.get("equity_before"))
        trades["equity_ret"] = trades["pnl_account"] / trades["equity_before"]
        trades["prob"] = trades["meta"].map(lambda m: m.get("prob"))
        for col in ("entry_time", "exit_time", "signal_time"):
            trades[col] = pd.to_datetime(trades[col], utc=True)
    eq_series = pd.Series(equity, index=times + cfg.bar, name="equity")
    return BacktestResult(trades, eq_series, vetoes, decisions, acc)
