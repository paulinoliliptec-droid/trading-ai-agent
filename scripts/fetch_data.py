"""Recolhe o histórico real e guarda em Parquet com manifesto (fonte, período, qualidade).

Uso: python scripts/fetch_data.py [--eurusd-desde 2022-01-01] [--btc-desde 2023-01-01]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from trading_agent.brokers.crypto.coinbase import CoinbaseMarketData
from trading_agent.brokers.forex.dukascopy import DukascopyMarketData
from trading_agent.data.quality import clean_ohlcv
from trading_agent.data.store import save_candles


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eurusd-desde", default="2022-01-01")
    ap.add_argument("--btc-desde", default="2023-01-01")
    ap.add_argument("--so", choices=["EUR/USD", "BTC/USD"], default=None, help="recolher só um mercado")
    args = ap.parse_args()
    fim = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)

    jobs = [
        ("EUR/USD", DukascopyMarketData(), "forex", args.eurusd_desde),
        ("BTC/USD", CoinbaseMarketData(), "24/7", args.btc_desde),
    ]
    for symbol, src, hours, desde in jobs:
        if args.so and symbol != args.so:
            continue
        inicio = datetime.fromisoformat(desde).replace(tzinfo=UTC)
        print(f"[{src.name}] {symbol} {inicio:%Y-%m-%d} → {fim:%Y-%m-%d %H:%M}", flush=True)
        raw = src.historical(symbol, "1h", inicio, fim)
        df, rep = clean_ohlcv(raw, "1h", market_hours=hours)
        path = save_candles(df, symbol, "1h", src.name, rep.as_dict())
        print(json.dumps({"ficheiro": str(path), **rep.as_dict()}, ensure_ascii=False, indent=1), flush=True)


if __name__ == "__main__":
    main()
