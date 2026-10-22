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


def build_features_v2(df: pd.DataFrame, atr_window: int = 14, cost_pct: float | None = None) -> pd.DataFrame:
    """Features da fase 2: as da v1 mais regimes, volatilidade realizada, liquidez e custos.

    Todas usam janelas que acabam em t. `cost_pct` (custo ida e volta) permite a feature mais
    importante do diagnóstico: o custo em unidades do movimento esperado (ATR).
    """
    f = build_features(df, atr_window)
    c, h, lo, o = df["close"], df["high"], df["low"], df["open"]
    logc = np.log(c)
    r1 = logc.diff()
    hl = np.log(h / lo) ** 2
    co = np.log(c / o) ** 2
    # Volatilidade realizada (Parkinson e Garman-Klass) e volatilidade relativa (curta vs longa)
    f["vol_parkinson_24"] = np.sqrt(hl.rolling(24, min_periods=24).mean() / (4 * np.log(2)))
    f["vol_gk_24"] = np.sqrt((0.5 * hl - (2 * np.log(2) - 1) * co).clip(lower=0).rolling(24, min_periods=24).mean())
    vol_168 = r1.rolling(168, min_periods=168).std()
    f["vol_rel_24_168"] = f["vol_24"] / vol_168.replace(0, np.nan)
    # Regime de tendência e lateral: eficiência do movimento (1 = tendência limpa, 0 = vai e vem)
    path = r1.abs().rolling(24, min_periods=24).sum()
    f["efficiency_24"] = (logc.diff(24)).abs() / path.replace(0, np.nan)
    f["efficiency_72"] = (logc.diff(72)).abs() / r1.abs().rolling(72, min_periods=72).sum().replace(0, np.nan)
    a = atr(df, atr_window)
    f["trend_slope_48_atr"] = (ema(c, 48) - ema(c, 48).shift(12)) / a.replace(0, np.nan)
    f["range_compression_24"] = (h.rolling(24, min_periods=24).max() - lo.rolling(24, min_periods=24).min()) / a.replace(0, np.nan)
    # Momentum ajustado à volatilidade
    for k in (24, 72):
        f[f"mom_vol_adj_{k}"] = logc.diff(k) / (r1.rolling(k, min_periods=k).std() * np.sqrt(k)).replace(0, np.nan)
    # Volume e liquidez
    vol = df["volume"].replace(0, np.nan)
    lv = np.log(vol)
    f["volume_chg_24"] = lv - lv.rolling(24, min_periods=24).mean()
    dollar = (c * vol).replace(0, np.nan)
    f["amihud_24"] = np.log((r1.abs() / dollar).rolling(24, min_periods=24).mean() + 1e-18)
    # Custos: spread relativo ao seu histórico e custo em unidades de ATR
    if "spread_bps" in f.columns:
        sb = f["spread_bps"]
        f["spread_z_168"] = (sb - sb.rolling(168, min_periods=48).mean()) / sb.rolling(168, min_periods=48).std().replace(0, np.nan)
        cost_series = sb / 1e4 if cost_pct is None else sb / 1e4 + cost_pct
    else:
        cost_series = pd.Series(cost_pct if cost_pct is not None else np.nan, index=df.index)
    f["cost_to_atr"] = cost_series / f["atr_pct"].replace(0, np.nan)
    return f
