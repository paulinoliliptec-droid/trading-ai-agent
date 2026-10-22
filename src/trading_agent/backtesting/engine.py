"""Backtest sem fuga de informação futura, com custos e com o motor de risco no caminho.

Uma posição de cada vez por ativo. Para cada vela t com proposta: o risco decide; se aprova,
entra-se na abertura de t+1 e sai-se pela barreira já calculada (TP, SL ou tempo). A vela
seguinte disponível para decidir é a de saída. O capital compõe com o tamanho que o risco deu.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from trading_agent.risk.engine import PortfolioState, Proposal, RiskEngine


@dataclass
class MarketCosts:
    fee_bps: float          # por lado
    slippage_bps: float     # por lado
    default_spread_bps: float = 0.0  # quando os dados não trazem spread

    def round_trip_pct(self, spread_bps: float | None) -> float:
        s = self.default_spread_bps if spread_bps is None or np.isnan(spread_bps) else spread_bps
        return (s + 2 * self.fee_bps + 2 * self.slippage_bps) / 1e4


def run_backtest(index: pd.DatetimeIndex, sides: pd.Series, probs: pd.Series, features: pd.DataFrame,
                 barriers: dict[int, pd.DataFrame], costs: MarketCosts, risk: RiskEngine, symbol: str,
                 tp_mult: float, sl_mult: float, start_equity: float = 1.0) -> tuple[pd.DataFrame, pd.Series, dict]:
    pos_of = {ts: i for i, ts in enumerate(index)}
    equity, peak, day_start, day = start_equity, start_equity, start_equity, None
    trades, curve = [], {}
    vetoes: dict[str, int] = {}
    next_free = index[0]
    for ts in sides.index:
        d = ts.date()
        if d != day:
            day, day_start = d, equity
        curve[ts] = equity
        side = int(sides.loc[ts])
        if side == 0 or ts < next_free:
            continue
        b = barriers[side].loc[ts]
        if pd.isna(b["gross_ret"]) or pd.isna(b["t1"]):
            continue
        f = features.loc[ts]
        spread_bps = float(f["spread_bps"]) if "spread_bps" in f and not pd.isna(f["spread_bps"]) else costs.default_spread_bps
        cost = costs.round_trip_pct(spread_bps)
        prop = Proposal(symbol, side, float(probs.loc[ts]), tp_mult * float(f["atr_pct"]), sl_mult * float(f["atr_pct"]),
                        cost, spread_bps, float(f["atr_pct"]))
        dec = risk.evaluate(prop, PortfolioState(equity, peak, day_start, 0))
        if not dec.trade:
            for r in dec.reasons:
                k = r.split(" ")[0]
                vetoes[k] = vetoes.get(k, 0) + 1
            continue
        net = float(b["gross_ret"]) - cost
        equity *= 1 + dec.size_fraction * net
        peak = max(peak, equity)
        trades.append({"entry_signal": ts, "exit_time": b["t1"], "side": side, "prob": prop.probability,
                       "size": dec.size_fraction, "gross_ret": float(b["gross_ret"]), "cost": cost, "net_ret": net,
                       "equity_ret": dec.size_fraction * net, "barrier": b["barrier"], "edge_bps": dec.expected_edge_bps})
        curve[b["t1"]] = equity
        i = pos_of.get(b["t1"])
        next_free = index[i] if i is not None else b["t1"]
    eq = pd.Series(curve).sort_index()
    eq = eq[~eq.index.duplicated(keep="last")]
    return pd.DataFrame(trades), eq, vetoes
