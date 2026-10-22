"""Um ciclo de paper trading com dados ao vivo: preço atual → modelo → risco → ordem simulada.

Uso: python scripts/paper_trade_once.py --symbol "BTC/USD"
O modelo é treinado no histórico guardado (XGBoost, só o lado comprado e vendido); o preço e as
velas recentes vêm da Kraken (público). A ordem, se o risco a aprovar, vai para o PaperBroker.
Em produção isto corre em ciclo (Cloud Run com instância mínima 1, ou uma VM pequena).
"""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime, timedelta

import pandas as pd

from trading_agent.backtesting.engine import MarketCosts
from trading_agent.brokers.base import Order, Side, ensure_simulated
from trading_agent.brokers.crypto.kraken import KrakenMarketData
from trading_agent.config import ROOT, Secrets, load_config
from trading_agent.data.quality import clean_ohlcv
from trading_agent.data.store import load_candles
from trading_agent.execution.paper import PaperBroker, reconcile
from trading_agent.features.build import atr, build_features, model_columns
from trading_agent.labels.triple_barrier import triple_barrier
from trading_agent.models.xgboost_model.model import XGBoostModel
from trading_agent.monitoring.logging_setup import setup_logging
from trading_agent.notifications.telegram import Event, TelegramNotifier
from trading_agent.risk.engine import PortfolioState, Proposal, RiskEngine
from trading_agent.risk.kill_switch import KillSwitch

SOURCES = {"BTC/USD": "coinbase", "EUR/USD": "dukascopy"}


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC/USD")
    args = ap.parse_args()
    cfg, sec = load_config(), Secrets()
    R, mk = cfg.raw["research"], cfg.market(args.symbol)
    tg = TelegramNotifier(sec.telegram_bot_token.get_secret_value() if sec.telegram_bot_token else None, sec.allowed_chat_ids() or {0})
    broker = PaperBroker(fee_bps=mk.get("fee_bps", 0), slippage_bps=mk.get("slippage_bps", 0))
    ensure_simulated(broker)

    # 1) Modelo treinado no histórico guardado (os últimos 15% servem de validação/calibração).
    hist = load_candles(args.symbol, "1h", SOURCES[args.symbol])
    f = build_features(hist, R["atr_window"])
    cols = model_columns(f)
    a = atr(hist, R["atr_window"])
    models = {}
    for side in (1, -1):
        lab = triple_barrier(hist, a, side, R["horizon_bars"], R["tp_atr_mult"], R["sl_atr_mult"])
        ok = f[cols].notna().all(axis=1) & lab["label"].notna()
        X, y = f.loc[ok, cols], lab.loc[ok, "label"]
        cut = int(len(X) * 0.85) - R["embargo_bars"]
        models[side] = XGBoostModel().fit(X.iloc[:cut], y.iloc[:cut], X.iloc[cut + R["embargo_bars"]:], y.iloc[cut + R["embargo_bars"]:])

    # 2) Dados ao vivo: velas recentes e preço atual (Kraken, público).
    live = KrakenMarketData()
    now = datetime.now(UTC)
    recent, rep = clean_ohlcv(live.historical(args.symbol, "1h", now - timedelta(days=29), now), "1h")
    recent = recent.iloc[:-1]  # a última vela ainda não fechou
    q = live.quote(args.symbol)
    fr = build_features(recent, R["atr_window"]).iloc[-1]
    p_long, p_short = (float(models[s].predict_proba(pd.DataFrame([fr[cols]]))[0]) for s in (1, -1))
    side, prob = (1, p_long) if p_long >= p_short else (-1, p_short)
    costs = MarketCosts(mk.get("fee_bps", 0), mk.get("slippage_bps", 0), mk.get("spread_bps", 0))
    cost = costs.round_trip_pct(q.spread_bps)
    prop = Proposal(args.symbol, side, prob, R["tp_atr_mult"] * fr["atr_pct"], R["sl_atr_mult"] * fr["atr_pct"], cost, q.spread_bps, fr["atr_pct"])

    # 3) Risco decide; se aprovar, ordem simulada ao preço ao vivo.
    risk = RiskEngine(cfg.risk, KillSwitch(), mk.get("max_leverage", 1.0))
    capital = 10_000.0
    dec = risk.evaluate(prop, PortfolioState(capital, capital, capital, 0))
    print(f"{args.symbol} {q.timestamp:%Y-%m-%d %H:%M} UTC · bid {q.bid} ask {q.ask} (spread {q.spread_bps:.2f} bps) · "
          f"última vela fechada {recent.index[-1]:%H:%M} · P(TP primeiro) comprado {p_long:.3f} vendido {p_short:.3f}")
    print(f"decisão do risco: {'NEGOCIAR' if dec.trade else 'NÃO NEGOCIAR'} · expectativa {dec.expected_edge_bps:.1f} bps · {'; '.join(dec.reasons)}")
    if dec.trade:
        qty = capital * dec.size_fraction / q.mid
        order = Order(args.symbol, Side.BUY if side == 1 else Side.SELL, qty, f"paper-{uuid.uuid4().hex[:10]}",
                      stop_loss=q.mid * (1 - side * prop.sl_pct), take_profit=q.mid * (1 + side * prop.tp_pct))
        fill = broker.submit(order, q)
        tg.notify(Event.OPENED, f"{args.symbol} {order.side} {qty:.6f} a {fill.price:.5f} (SL {order.stop_loss:.5f}, TP {order.take_profit:.5f})")
        print("ordem simulada:", fill)
        print("reconciliação:", reconcile({args.symbol: qty * side}, broker) or "sem diferenças")
    else:
        tg.notify(Event.SIGNAL, f"{args.symbol}: sem operação ({'; '.join(dec.reasons)})")
    print("telegram:", "modo seco (sem token)" if tg.dry_run else "enviado")
    (ROOT / "reports").mkdir(exist_ok=True)


if __name__ == "__main__":
    main()
