"""Coinbase Exchange: candles públicos (sem conta) para o histórico de BTC/USD.

Endpoint público `GET /products/{id}/candles`, no máximo 300 velas por pedido; pagina-se
por janelas de tempo. Formato de cada vela: [time, low, high, open, close, volume].
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pandas as pd
import requests

from trading_agent.brokers.base import MarketDataSource, Quote

_GRANULARITY = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}
_PRODUCT = {"BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD"}


class CoinbaseMarketData(MarketDataSource):
    name = "coinbase"
    base_url = "https://api.exchange.coinbase.com"

    def __init__(self, session: requests.Session | None = None, pause_s: float = 0.15):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "trading-ai-agent/0.1")
        self.pause_s = pause_s

    def historical(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        gran = _GRANULARITY[timeframe]
        product = _PRODUCT[symbol]
        step = timedelta(seconds=gran * 300)
        rows: list[list[float]] = []
        cursor = start
        while cursor < end:
            stop = min(cursor + step, end)
            r = self.session.get(
                f"{self.base_url}/products/{product}/candles",
                params={"granularity": gran, "start": cursor.isoformat(), "end": stop.isoformat()},
                timeout=20,
            )
            if r.status_code == 429:
                time.sleep(2)
                continue
            r.raise_for_status()
            rows.extend(r.json())
            cursor = stop
            time.sleep(self.pause_s)
        df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
        if df.empty:
            return df
        df.index = pd.to_datetime(df.pop("time"), unit="s", utc=True)
        return df[["open", "high", "low", "close", "volume"]].astype(float).sort_index()

    def quote(self, symbol: str) -> Quote:
        r = self.session.get(f"{self.base_url}/products/{_PRODUCT[symbol]}/ticker", timeout=10)
        r.raise_for_status()
        d = r.json()
        return Quote(symbol, float(d["bid"]), float(d["ask"]), datetime.now(UTC), self.name)
