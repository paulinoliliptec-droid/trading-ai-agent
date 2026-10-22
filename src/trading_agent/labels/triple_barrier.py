"""Rotulagem triple-barrier (López de Prado), com entrada na abertura da vela seguinte.

Para cada vela t (decisão no fecho de t):
  · entrada = abertura de t+1;
  · take-profit = entrada ± tp_mult × ATR(t); stop-loss = entrada ∓ sl_mult × ATR(t);
  · limite temporal = fecho de t+horizon.
Se o TP e o SL caem dentro da MESMA vela não se sabe qual veio primeiro: assume-se o SL
(conservador). O rótulo é 1 se o TP é tocado primeiro, 0 caso contrário. `t1` é o instante de
saída: serve para o purging (amostras cujo resultado se sobrepõe ao período de teste).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def triple_barrier(df: pd.DataFrame, atr_series: pd.Series, side: int, horizon: int = 24,
                   tp_mult: float = 2.0, sl_mult: float = 1.0) -> pd.DataFrame:
    if side not in (1, -1):
        raise ValueError("side é 1 (comprado) ou -1 (vendido)")
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    a = atr_series.to_numpy(float)
    n = len(df)
    label = np.full(n, np.nan)
    ret = np.full(n, np.nan)
    exit_idx = np.full(n, -1)
    barrier = np.empty(n, dtype=object)
    for t in range(n - 1):
        if np.isnan(a[t]):
            continue
        last = min(t + horizon, n - 1)
        if last <= t:
            continue
        entry = o[t + 1]
        tp = entry + side * tp_mult * a[t]
        sl = entry - side * sl_mult * a[t]
        out_px, out_j, kind = c[last], last, "tempo"
        for j in range(t + 1, last + 1):
            hit_sl = lo[j] <= sl if side == 1 else h[j] >= sl
            hit_tp = h[j] >= tp if side == 1 else lo[j] <= tp
            if hit_sl:  # inclui o caso TP e SL na mesma vela: conservador
                out_px, out_j, kind = sl, j, "sl"
                break
            if hit_tp:
                out_px, out_j, kind = tp, j, "tp"
                break
        if out_j == last and kind == "tempo" and t + horizon > n - 1:
            continue  # o horizonte passa o fim dos dados: resultado desconhecido, sem rótulo
        label[t] = 1.0 if kind == "tp" else 0.0
        ret[t] = side * (out_px / entry - 1)
        exit_idx[t] = out_j
        barrier[t] = kind
    out = pd.DataFrame({"label": label, "gross_ret": ret, "barrier": barrier}, index=df.index)
    valid = exit_idx >= 0
    t1 = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    t1[valid] = df.index[exit_idx[valid]]
    out["t1"] = t1
    out["entry_time"] = pd.Series(df.index, index=df.index).shift(-1)
    return out
