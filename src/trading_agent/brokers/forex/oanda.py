"""OANDA v20 (REST), ambiente Practice por omissão.

Só leitura nesta fase: velas e preços. A submissão de ordens à OANDA NÃO está implementada;
as ordens vão para o `PaperBroker`. Precisa de `OANDA_API_TOKEN` e `OANDA_ACCOUNT_ID` de uma
conta Practice (demo). Disponibilidade para residentes em Portugal: confirmar com a OANDA
Europe (ver docs/brokers.md).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import requests

from trading_agent.brokers.base import MarketDataSource, Quote

_HOSTS = {"practice": "https://api-fxpractice.oanda.com", "live": "https://api-fxtrade.oanda.com"}
_GRAN = {"1m": "M1", "5m": "M5", "15m": "M15", "1h": "H1", "4h": "H4", "1d": "D"}


class OandaMarketData(MarketDataSource):
    name = "oanda"

    def __init__(self, token: str, account_id: str, environment: str = "practice", session: requests.Session | None = None):
        if environment != "practice":
            # Ler preços do ambiente live não envia ordens, mas mantém-se Practice até haver decisão explícita.
            raise ValueError("Nesta fase só o ambiente Practice da OANDA é permitido.")
        self.base = _HOSTS[environment]
        self.account_id = account_id
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Accept-Datetime-Format": "RFC3339"})

    @staticmethod
    def instrument(symbol: str) -> str:
        return symbol.replace("/", "_")

    def historical(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        r = self.session.get(
            f"{self.base}/v3/instruments/{self.instrument(symbol)}/candles",
            params={"granularity": _GRAN[timeframe], "price": "BA", "from": start.isoformat(), "to": end.isoformat()},
            timeout=20,
        )
        r.raise_for_status()
        rows = []
        for c in r.json().get("candles", []):
            if not c.get("complete"):
                continue
            b, a = c["bid"], c["ask"]
            rows.append({
                "timestamp": c["time"], "open": float(b["o"]), "high": float(b["h"]), "low": float(b["l"]),
                "close": float(b["c"]), "volume": float(c["volume"]), "spread": float(a["c"]) - float(b["c"]),
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df.index = pd.to_datetime(df.pop("timestamp"), utc=True)
        return df

    def quote(self, symbol: str) -> Quote:
        r = self.session.get(
            f"{self.base}/v3/accounts/{self.account_id}/pricing", params={"instruments": self.instrument(symbol)}, timeout=10
        )
        r.raise_for_status()
        p = r.json()["prices"][0]
        return Quote(symbol, float(p["bids"][0]["price"]), float(p["asks"][0]["price"]),
                     pd.Timestamp(p["time"]).tz_convert("UTC").to_pydatetime(), self.name)
