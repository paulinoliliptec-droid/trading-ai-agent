"""Qualidade dos dados de mercado: UTC, duplicados, falhas e velas incoerentes."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from trading_agent.brokers.base import OHLCV_COLUMNS


def to_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    """Índice em UTC, ordenado. Um índice sem fuso é tratado como já estando em UTC."""
    out = df.copy()
    idx = pd.DatetimeIndex(out.index)
    out.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    out.index.name = "timestamp"
    return out.sort_index()


@dataclass
class QualityReport:
    rows: int
    start: str | None
    end: str | None
    duplicates_removed: int
    missing_bars: int
    missing_ratio: float
    invalid_bars_removed: int
    largest_gap: str | None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _expected_index(index: pd.DatetimeIndex, freq: str, market_hours: str) -> pd.DatetimeIndex:
    full = pd.date_range(index.min(), index.max(), freq=freq, tz="UTC")
    if market_hours == "forex":
        # FX à vista: fechado de sexta 22:00 UTC a domingo 22:00 UTC (aproximação; feriados ficam como «em falta»).
        dow, hour = full.day_of_week, full.hour
        closed = (dow == 5) | ((dow == 4) & (hour >= 22)) | ((dow == 6) & (hour < 22))
        full = full[~closed]
    return full


def clean_ohlcv(df: pd.DataFrame, freq: str = "1h", market_hours: str = "24/7") -> tuple[pd.DataFrame, QualityReport]:
    """Normaliza para UTC, tira duplicados e velas impossíveis, e mede as falhas.

    As falhas NÃO são preenchidas: inventar preços seria pior do que reconhecê-las. Quem treina
    vê a percentagem em falta e decide.
    """
    notes: list[str] = []
    out = to_utc_index(df)
    n0 = len(out)
    out = out[~out.index.duplicated(keep="last")]
    dups = n0 - len(out)

    ok = (
        (out["high"] >= out[["open", "close"]].max(axis=1))
        & (out["low"] <= out[["open", "close"]].min(axis=1))
        & (out[["open", "high", "low", "close"]] > 0).all(axis=1)
    )
    invalid = int((~ok).sum())
    out = out[ok]
    if invalid:
        notes.append(f"{invalid} velas com high/low incoerentes ou preços não positivos removidas")

    missing, ratio, largest = 0, 0.0, None
    if len(out) > 1:
        expected = _expected_index(out.index, freq, market_hours)
        missing_idx = expected.difference(out.index)
        missing = len(missing_idx)
        ratio = missing / max(len(expected), 1)
        gaps = out.index.to_series().diff().dropna()
        if len(gaps):
            largest = str(gaps.max())
    report = QualityReport(
        rows=len(out),
        start=str(out.index.min()) if len(out) else None,
        end=str(out.index.max()) if len(out) else None,
        duplicates_removed=dups,
        missing_bars=missing,
        missing_ratio=round(ratio, 5),
        invalid_bars_removed=invalid,
        largest_gap=largest,
        notes=notes,
    )
    cols = [c for c in out.columns if c in OHLCV_COLUMNS or c in ("spread",)]
    return out[cols], report
