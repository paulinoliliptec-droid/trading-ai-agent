"""Hipótese 2: dados de derivados e de fluxo de ordens (pré-registo em docs/h2-derivados-preregisto.md).

Coletores públicos, sem conta: funding e prémio do perpétuo (Binance), open interest (Bybit) e volume
comprador agressivo do spot (Binance). Tudo é alinhado à hora de ABERTURA das velas horárias da Coinbase,
com valores conhecidos até ao FECHO dessa vela (abertura + 1 h), para que as features sejam causais.
"""

from __future__ import annotations

import time
from datetime import datetime

import numpy as np
import pandas as pd
import requests

H = pd.Timedelta(hours=1)
_MS = 1000


def _ms(t: datetime | pd.Timestamp) -> int:
    return int(pd.Timestamp(t).timestamp() * _MS)


def _get(s: requests.Session, url: str, params: dict) -> list | dict:
    for tentativa in range(5):
        r = s.get(url, params=params, timeout=30)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 * (tentativa + 1))
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    return []


def fetch_funding(start, end, s: requests.Session) -> pd.Series:
    """Funding do BTCUSDT (Binance), indexado pelo instante em que passa a ser conhecido."""
    rows, cur = [], _ms(start)
    while cur < _ms(end):
        page = _get(s, "https://fapi.binance.com/fapi/v1/fundingRate",
                    {"symbol": "BTCUSDT", "startTime": cur, "endTime": _ms(end), "limit": 1000})
        if not page:
            break
        rows += page
        cur = page[-1]["fundingTime"] + 1
    df = pd.DataFrame(rows)
    return pd.Series(df["fundingRate"].astype(float).to_numpy(),
                     index=pd.to_datetime(df["fundingTime"], unit="ms", utc=True), name="funding")


def _binance_klines(url: str, symbol: str, start, end, s: requests.Session, limit: int) -> pd.DataFrame:
    rows, cur = [], _ms(start)
    while cur < _ms(end):
        page = _get(s, url, {"symbol": symbol, "interval": "1h", "startTime": cur, "endTime": _ms(end), "limit": limit})
        if not page:
            break
        rows += page
        cur = page[-1][0] + 3600 * _MS
    df = pd.DataFrame(rows).iloc[:, :11]
    df.columns = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote", "trades", "taker_base", "taker_quote"]
    df.index = pd.to_datetime(df.pop("open_time"), unit="ms", utc=True)
    return df.astype(float)


def fetch_premium(start, end, s: requests.Session) -> pd.Series:
    """Prémio do perpétuo sobre o índice (Binance), velas de 1 h; o fecho é o valor no fim da hora."""
    df = _binance_klines("https://fapi.binance.com/fapi/v1/premiumIndexKlines", "BTCUSDT", start, end, s, 1500)
    return df["close"].rename("premio")


def fetch_taker(start, end, s: requests.Session) -> pd.DataFrame:
    """Volume total e comprador agressivo do BTCUSDT spot (Binance), velas de 1 h."""
    df = _binance_klines("https://api.binance.com/api/v3/klines", "BTCUSDT", start, end, s, 1000)
    return df[["volume", "taker_base"]].rename(columns={"volume": "spot_volume", "taker_base": "taker_buy"})


def fetch_open_interest(start, end, s: requests.Session) -> pd.Series:
    """Open interest do BTCUSDT linear (Bybit), instantâneos de hora a hora."""
    rows, cur_end, start_ms = [], _ms(end), _ms(start)
    while cur_end > start_ms:
        win_start = max(start_ms, cur_end - 200 * 3600 * _MS)
        d = _get(s, "https://api.bybit.com/v5/market/open-interest",
                 {"category": "linear", "symbol": "BTCUSDT", "intervalTime": "1h", "startTime": win_start,
                  "endTime": cur_end, "limit": 200})
        page = (d.get("result") or {}).get("list") or []
        rows += page
        cur_end = win_start - 1
        time.sleep(0.05)
    df = pd.DataFrame(rows).drop_duplicates("timestamp")
    return pd.Series(df["openInterest"].astype(float).to_numpy(),
                     index=pd.to_datetime(df["timestamp"].astype("int64"), unit="ms", utc=True), name="oi").sort_index()


def hourly_table(funding: pd.Series, premium: pd.Series, taker: pd.DataFrame, oi: pd.Series,
                 hours: pd.DatetimeIndex) -> pd.DataFrame:
    """Uma linha por vela horária (indexada pela ABERTURA) com o que se sabe no FECHO dessa vela."""
    close_t = hours + H
    out = pd.DataFrame(index=hours)
    out["funding"] = funding.sort_index().reindex(close_t, method="ffill").to_numpy()
    out["oi"] = oi.sort_index().reindex(close_t, method="ffill").to_numpy()
    out["premio"] = premium.reindex(hours).to_numpy()
    tk = taker.reindex(hours)
    out["spot_volume"] = tk["spot_volume"].to_numpy()
    out["taker_buy"] = tk["taker_buy"].to_numpy()
    return out


def resample_hourly(h: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if timeframe == "1h":
        return h
    g = h.resample(timeframe, label="left", closed="left")
    return pd.DataFrame({"funding": g["funding"].last(), "oi": g["oi"].last(), "premio": g["premio"].last(),
                         "spot_volume": g["spot_volume"].sum(min_count=1), "taker_buy": g["taker_buy"].sum(min_count=1)})


def derivative_features(h: pd.DataFrame, bar_hours: int) -> pd.DataFrame:
    """Features `v3` (só janelas que acabam em t). `bar_hours` converte janelas em horas para velas."""
    def n(hours: int) -> int:
        return max(1, hours // bar_hours)

    f = pd.DataFrame(index=h.index)
    fr, pr = h["funding"], h["premio"]
    f["funding"] = fr
    f["funding_media_72h"] = fr.rolling(n(72), min_periods=n(72)).mean()
    f["funding_z_30d"] = (fr - fr.rolling(n(720), min_periods=n(240)).mean()) / fr.rolling(n(720), min_periods=n(240)).std().replace(0, np.nan)
    f["premio"] = pr
    f["premio_media_24h"] = pr.rolling(n(24), min_periods=n(24)).mean()
    f["premio_z_30d"] = (pr - pr.rolling(n(720), min_periods=n(240)).mean()) / pr.rolling(n(720), min_periods=n(240)).std().replace(0, np.nan)
    vol = h["spot_volume"].replace(0, np.nan)
    f["taker_desequilibrio"] = 2 * h["taker_buy"] / vol - 1
    f["taker_desequilibrio_24h"] = 2 * h["taker_buy"].rolling(n(24), min_periods=n(24)).sum() / vol.rolling(n(24), min_periods=n(24)).sum() - 1
    loi = np.log(h["oi"])
    f["oi_var_4h"] = loi.diff(n(4)) if bar_hours < 4 else loi.diff(1)
    f["oi_var_24h"] = loi.diff(n(24))
    f["oi_z_30d"] = (loi - loi.rolling(n(720), min_periods=n(240)).mean()) / loi.rolling(n(720), min_periods=n(240)).std().replace(0, np.nan)
    return f
