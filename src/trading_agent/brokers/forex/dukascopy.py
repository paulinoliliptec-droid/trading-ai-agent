"""Dukascopy: histórico Forex gratuito (sem conta), com bid E ask.

Ficheiros mensais de velas horárias, comprimidos em LZMA:
`https://datafeed.dukascopy.com/datafeed/{PAR}/{ANO}/{MÊS-1:02d}/{BID|ASK}_candles_hour_1.bi5`
(o mês conta a partir de 0). Cada vela tem 24 bytes big-endian: segundos desde o início do mês,
abertura, fecho, mínimo, máximo (inteiros, em 1e-5 para pares com 5 casas) e volume (float).

As horas com o mercado fechado vêm com volume 0 e preço parado: são removidas. O spread
real de cada hora é ask_close - bid_close. Uso: investigação. Confirmar os termos de
utilização da Dukascopy antes de qualquer uso comercial dos dados.
"""

from __future__ import annotations

import lzma
import struct
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from trading_agent.brokers.base import MarketDataSource, Quote
from trading_agent.config import ROOT

_POINT = {"EUR/USD": 1e5, "GBP/USD": 1e5, "USD/JPY": 1e3}


class DukascopyMarketData(MarketDataSource):
    name = "dukascopy"
    base_url = "https://datafeed.dukascopy.com/datafeed"

    def __init__(self, session: requests.Session | None = None, pause_s: float = 3.0, cache_dir: Path | None = None):
        self.cache_dir = cache_dir if cache_dir is not None else ROOT / "data" / "cache" / "dukascopy"
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "Mozilla/5.0 (trading-ai-agent research)")
        self.pause_s = pause_s

    def _month(self, symbol: str, year: int, month: int, side: str) -> pd.DataFrame:
        pair = symbol.replace("/", "")
        url = f"{self.base_url}/{pair}/{year}/{month - 1:02d}/{side}_candles_hour_1.bi5"
        cache = self.cache_dir / pair / f"{year}-{month:02d}_{side}.bi5" if self.cache_dir else None
        corrente = (year, month) == (datetime.now(UTC).year, datetime.now(UTC).month)
        if cache and cache.exists() and not corrente:
            content = cache.read_bytes()  # meses fechados não mudam: não se volta a pedir
        else:
            r = None
            for tentativa in range(8):
                try:
                    r = self.session.get(url, timeout=30)
                except requests.RequestException:
                    r = None  # ligação recusada ou expirada: esperar e repetir
                if r is not None and r.status_code not in (429, 503):
                    break
                time.sleep(min(120, 5 * 2**tentativa))  # o servidor limita a cadência: esperar e repetir
            if r is None:
                raise ConnectionError(f"Dukascopy sem resposta para {url}")
            if r.status_code == 404 or not r.content:
                return pd.DataFrame()
            r.raise_for_status()
            content = r.content
            if cache and not corrente:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(content)
            time.sleep(self.pause_s)
        raw = lzma.decompress(content)
        point = _POINT[symbol]
        base = datetime(year, month, 1, tzinfo=UTC)
        recs = [struct.unpack(">5if", raw[i : i + 24]) for i in range(0, len(raw) - len(raw) % 24, 24)]
        df = pd.DataFrame(recs, columns=["t", "open", "close", "low", "high", "volume"])
        df.index = pd.to_datetime(base) + pd.to_timedelta(df.pop("t"), unit="s")
        for c in ("open", "close", "low", "high"):
            df[c] = df[c] / point
        return df

    def historical(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        if timeframe != "1h":
            raise ValueError("Este adaptador implementa só velas de 1 hora.")
        frames = []
        for p in pd.period_range(start.strftime("%Y-%m"), end.strftime("%Y-%m"), freq="M"):
            bid = self._month(symbol, p.year, p.month, "BID")
            ask = self._month(symbol, p.year, p.month, "ASK")
            if bid.empty:
                continue
            m = bid.copy()
            m["spread"] = (ask["close"] - bid["close"]) if not ask.empty else float("nan")
            frames.append(m)
        if not frames:
            return pd.DataFrame()
        df = pd.concat(frames)
        df = df[df["volume"] > 0]  # mercado fechado: volume 0 e preço parado
        df = df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        return df[["open", "high", "low", "close", "volume", "spread"]].sort_index()

    def quote(self, symbol: str) -> Quote:  # pragma: no cover - a Dukascopy não serve preço em tempo real por esta via
        raise NotImplementedError("A Dukascopy serve histórico; o preço atual vem da OANDA ou da Kraken.")
