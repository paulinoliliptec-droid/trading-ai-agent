"""Kraken pela CCXT: preços atuais e velas recentes (públicos, sem conta).

Limite conhecido: a API pública de OHLC da Kraken devolve só as últimas 720 velas por
intervalo (30 dias em velas de 1 hora). Para treino usa-se a Coinbase (cripto) e a
Dukascopy (Forex); a Kraken serve preços em tempo real e a reconciliação com o histórico.
A Kraken também cota EUR/USD (par ZEURZUSD): é um mercado de uma bolsa cripto, não o
interbancário, e é tratado como proxy de preço atual para o Forex enquanto não há OANDA.
"""

from __future__ import annotations

from datetime import UTC, datetime

import ccxt
import pandas as pd

from trading_agent.brokers.base import MarketDataSource, Quote


class KrakenMarketData(MarketDataSource):
    name = "kraken"

    def __init__(self, exchange: ccxt.Exchange | None = None):
        # Sem chaves: só endpoints públicos. Não se instancia nada com permissão de negociar.
        self.ex = exchange or ccxt.kraken({"enableRateLimit": True})

    def historical(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        since = int(start.timestamp() * 1000)
        rows = self.ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=720)
        df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
        if df.empty:
            return df
        df.index = pd.to_datetime(df.pop("time"), unit="ms", utc=True)
        return df[df.index <= pd.Timestamp(end)].astype(float)

    def quote(self, symbol: str) -> Quote:
        t = self.ex.fetch_ticker(symbol)
        ts = datetime.fromtimestamp(t["timestamp"] / 1000, UTC) if t.get("timestamp") else datetime.now(UTC)
        return Quote(symbol, float(t["bid"]), float(t["ask"]), ts, self.name)
