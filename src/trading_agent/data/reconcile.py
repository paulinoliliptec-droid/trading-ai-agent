"""Reconciliação entre duas fontes do mesmo instrumento antes de as usar em conjunto.

Exemplo: modelo treinado com velas da Dukascopy e agente ao vivo com a OANDA. Compara, no
período comum: diferença de preço de fecho (bps), spreads, correlação dos retornos e do volume.
Critério de compatibilidade (fixo): mediana da diferença de fecho ≤ `max_median_bps` e
correlação dos retornos ≥ `min_ret_corr`. O volume é reportado mas não decide (fontes diferentes
medem coisas diferentes: lotes, ticks), por isso features de volume relativas são preferíveis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compare_sources(a: pd.DataFrame, b: pd.DataFrame, max_median_bps: float = 1.0, min_ret_corr: float = 0.99) -> dict:
    idx = a.index.intersection(b.index)
    if len(idx) < 50:
        return {"velas_comuns": int(len(idx)), "compativel": False, "nota": "período comum curto demais"}
    ca, cb = a.loc[idx, "close"], b.loc[idx, "close"]
    diff = (ca / cb - 1).abs() * 1e4
    ra, rb = np.log(ca).diff().dropna(), np.log(cb).diff().dropna()
    out = {
        "velas_comuns": int(len(idx)),
        "dif_fecho_mediana_bps": round(float(diff.median()), 3),
        "dif_fecho_p99_bps": round(float(diff.quantile(0.99)), 3),
        "correlacao_retornos": round(float(ra.corr(rb)), 5),
        "correlacao_volume": round(float(a.loc[idx, "volume"].corr(b.loc[idx, "volume"])), 4),
    }
    for nome, df in (("a", a), ("b", b)):
        if "spread" in df.columns:
            out[f"spread_mediano_bps_{nome}"] = round(float((df.loc[idx, "spread"] / df.loc[idx, "close"]).median() * 1e4), 3)
    out["compativel"] = out["dif_fecho_mediana_bps"] <= max_median_bps and out["correlacao_retornos"] >= min_ret_corr
    return out
