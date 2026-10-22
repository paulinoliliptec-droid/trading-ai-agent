"""Features sem fuga de informação futura.

Regra: a feature da vela t usa só dados até ao FECHO de t (janelas que acabam em t). A
decisão é tomada no fecho de t e a entrada acontece na ABERTURA de t+1. Há um teste que muda
os preços futuros e confirma que nenhuma feature passada se altera.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def build_features(df: pd.DataFrame, atr_window: int = 14) -> pd.DataFrame:
    c = df["close"]
    logc = np.log(c)
    f = pd.DataFrame(index=df.index)
    for h in (1, 3, 6, 12, 24):
        f[f"ret_{h}"] = logc.diff(h)
    for w in (24, 72):
        f[f"vol_{w}"] = logc.diff().rolling(w, min_periods=w).std()
    f["rsi_14"] = rsi(c, 14)
    f["ema_12_48"] = ema(c, 12) / ema(c, 48) - 1
    f["close_ema_96"] = c / ema(c, 96) - 1
    f["atr_pct"] = atr(df, atr_window) / c
    f["mom_24"] = c / c.shift(24) - 1
    hi, lo = df["high"].rolling(24, min_periods=24).max(), df["low"].rolling(24, min_periods=24).min()
    f["range_pos_24"] = (c - lo) / (hi - lo).replace(0, np.nan)
    hour = df.index.hour
    f["hour_sin"], f["hour_cos"] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)
    f["dow"] = df.index.day_of_week
    vol = df["volume"].replace(0, np.nan)
    f["volume_z_72"] = (np.log(vol) - np.log(vol).rolling(72, min_periods=72).mean()) / np.log(vol).rolling(72, min_periods=72).std()
    if "spread" in df.columns:
        f["spread_bps"] = df["spread"] / c * 1e4
    return f


FEATURES_EXCLUDED_FROM_MODEL = {"dow"}  # usado em relatórios; fora do modelo para não aprender o calendário da amostra


def model_columns(f: pd.DataFrame) -> list[str]:
    return [c for c in f.columns if c not in FEATURES_EXCLUDED_FROM_MODEL]
