"""Reamostragem de velas de 1 hora para 4 horas e 1 dia, sem inventar velas.

Uma vela agregada só existe se tiver pelo menos `min_fill` das velas de 1 hora esperadas;
as restantes ficam em falta (não se preenchem). Forex: o dia começa às 22:00 UTC (fecho de
Nova Iorque), para que a vela diária não misture duas sessões.
"""

from __future__ import annotations

import pandas as pd

RULE = {"4h": ("4h", 4), "1d": ("24h", 24)}


def resample_ohlcv(df: pd.DataFrame, timeframe: str, asset_class: str = "crypto", min_fill: float = 0.75) -> pd.DataFrame:
    if timeframe in ("1h", "15m"):
        return df
    rule, n = RULE[timeframe]
    offset = "22h" if (asset_class == "forex" and timeframe == "1d") else None
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    if "spread" in df.columns:
        agg["spread"] = "mean"
    g = df.resample(rule, offset=offset, label="left", closed="left")
    out = g.agg(agg)
    cnt = g["close"].count()
    expected = n if asset_class != "forex" or timeframe != "1d" else 24
    out = out[cnt >= max(1, int(expected * min_fill))]
    return out.dropna(subset=["open", "high", "low", "close"])
