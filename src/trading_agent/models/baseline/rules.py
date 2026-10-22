"""Modelo A: baseline determinístico por regras (EMA, RSI, momentum, ATR).

Comprado quando a tendência curta está acima da longa, o momentum é positivo e o RSI está
entre 50 e 70 (força sem exaustão); vendido no espelho. Não aprende nada: é a régua com que
se medem os modelos que aprendem.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def rule_signals(features: pd.DataFrame) -> pd.Series:
    f = features
    long = (f["ema_12_48"] > 0) & (f["mom_24"] > 0) & f["rsi_14"].between(50, 70)
    short = (f["ema_12_48"] < 0) & (f["mom_24"] < 0) & f["rsi_14"].between(30, 50)
    sig = np.where(long, 1, np.where(short, -1, 0))
    return pd.Series(sig, index=f.index, name="signal")
