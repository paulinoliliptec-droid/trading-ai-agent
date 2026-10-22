"""Verifica, com preços reais recolhidos, se 100 € chegam para negociar cada mercado ATIVO
respeitando o risco por operação (stop = 1 ATR horário mediano do último ano).

Uso: python scripts/capital_check.py [--capital 100]
Os mercados desativados são listados com a razão; não se inventam preços para eles.
"""

from __future__ import annotations

import argparse
import json

from trading_agent.config import load_config
from trading_agent.data.store import load_candles
from trading_agent.execution.instruments import capital_sufficiency
from trading_agent.features.build import atr

SOURCES = {"BTC/USD": "coinbase", "EUR/USD": "dukascopy"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capital", type=float, default=100.0)
    args = ap.parse_args()
    cfg = load_config()
    eurusd = load_candles("EUR/USD", "1h", "dukascopy")["close"].iloc[-1]
    out = {}
    for sym in cfg.raw["markets"]:
        spec = cfg.instrument(sym)
        if not spec.enabled or sym not in SOURCES:
            out[sym] = {"ativo": False, "razao": spec.disabled_reason or "sem fonte de dados configurada"}
            continue
        df = load_candles(sym, "1h", SOURCES[sym])
        last_year = df.iloc[-24 * 365:]
        stop = float((atr(last_year) / last_year["close"]).median())
        fx = eurusd if cfg.account["currency"] == "EUR" and spec.quote_currency == "USD" else 1.0
        r = capital_sufficiency(spec, args.capital, float(df["close"].iloc[-1]), stop, cfg.risk.max_loss_per_trade_pct, fx,
                                cfg.risk.max_exposure_per_asset_pct)
        out[sym] = {"ativo": True, "stop_1atr_pct": round(stop * 100, 4), "preco": float(df["close"].iloc[-1]), **r}
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
