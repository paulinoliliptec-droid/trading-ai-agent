"""Dados SINTÉTICOS só para testes unitários (marcados como tal). Nunca entram em relatórios."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def candles() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 600
    idx = pd.date_range("2025-01-06", periods=n, freq="1h", tz="UTC")
    close = 1.10 * np.exp(np.cumsum(rng.normal(0, 0.0008, n)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.0006, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.0006, n))
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                       "volume": rng.uniform(100, 1000, n), "spread": 0.00008}, index=idx)
    df.attrs["synthetic"] = True
    return df
