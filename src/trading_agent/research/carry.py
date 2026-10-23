"""Hipótese 4: carry de funding neutro ao preço (comprado no spot, vendido no perpétuo). Pré-registo em
docs/h4-carry-funding-preregisto.md. Não prevê nada: mede um retorno estrutural, líquido de custos e da base.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ONE_MS = pd.Timedelta(milliseconds=1)
MARGIN = 0.5            # margem do perpétuo em fração do nocional; capital = nocional × (1 + MARGIN)
ENTER_ANN, EXIT_ANN = 0.10, 0.0


def daily_table(funding: pd.Series, premium: pd.Series) -> pd.DataFrame:
    """Por dia UTC: funding pago no dia (o evento das 00:00 fecha o período do dia ANTERIOR), prémio no fecho do
    dia e média do funding das últimas 72 h (9 eventos) anualizada, conhecida no fecho."""
    f = funding.sort_index()
    paid_day = (f.index - ONE_MS).floor("D")
    d = pd.DataFrame({"funding": f.groupby(paid_day).sum()})
    d["n_eventos"] = f.groupby(paid_day).count()
    d["premio"] = premium.sort_index().groupby((premium.index + pd.Timedelta(hours=1) - ONE_MS).floor("D")).last()
    d["funding_72h_anual"] = f.rolling(9).mean().groupby(paid_day).last() * 3 * 365
    d = d.dropna(subset=["premio"])
    d["d_premio"] = d["premio"].diff()
    return d.dropna(subset=["d_premio", "funding_72h_anual"])


def positions(d: pd.DataFrame, strategy: str) -> np.ndarray:
    """Exposição (0 ou 1) em cada dia; a decisão no fecho de t vale para t+1."""
    if strategy == "sempre":
        return np.ones(len(d))
    s, prev = np.zeros(len(d)), 0.0
    sig = d["funding_72h_anual"].to_numpy()
    for i in range(1, len(d)):
        x = sig[i - 1]
        prev = 1.0 if (prev == 0 and x > ENTER_ANN) else 0.0 if (prev == 1 and x < EXIT_ANN) else prev
        s[i] = prev
    return s


def simulate(d: pd.DataFrame, strategy: str, cost_bps_por_lado: float, margin: float = MARGIN,
             close_at_end: bool = True) -> pd.DataFrame:
    """Retorno diário sobre o capital. `cost_bps_por_lado`: custo de abrir (ou de fechar) as duas pernas."""
    s = positions(d, strategy)
    trade = np.abs(np.diff(np.concatenate([[0.0], s])))
    if close_at_end and s[-1] == 1:
        trade[-1] += 1.0          # o período acaba com a posição fechada: custo de saída no último dia
    carry = s * d["funding"].to_numpy()
    basis = -s * d["d_premio"].to_numpy()
    cost = trade * cost_bps_por_lado / 1e4
    per_notional = carry + basis - cost
    return pd.DataFrame({"pos": s, "carry": carry, "base": basis, "custo": cost,
                         "liquido": per_notional / (1 + margin)}, index=d.index)
