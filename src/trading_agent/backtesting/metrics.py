"""Métricas de negociação e de classificação. A accuracy não entra: não prova rentabilidade."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, precision_score, recall_score, roc_auc_score


def trading_metrics(trades: pd.DataFrame, equity: pd.Series, periods_per_year: int) -> dict:
    n = len(trades)
    out = {"operacoes": n}
    if n == 0:
        return {**out, "retorno_liquido_pct": 0.0, "max_drawdown_pct": 0.0, "nota": "sem operações (equivale a não negociar)"}
    r = trades["net_ret"]
    wins, losses = r[r > 0], r[r <= 0]
    gross_win, gross_loss = trades.loc[r > 0, "equity_ret"].sum(), -trades.loc[r <= 0, "equity_ret"].sum()
    dd = (equity / equity.cummax() - 1).min()
    daily = equity.resample("1D").last().ffill().pct_change().dropna()
    sharpe = None
    if n >= 30 and daily.std() > 0:
        sharpe = float(daily.mean() / daily.std() * np.sqrt(periods_per_year))
    return {
        **out,
        "retorno_liquido_pct": round((equity.iloc[-1] / equity.iloc[0] - 1) * 100, 3),
        "taxa_acerto_pct": round(len(wins) / n * 100, 2),
        "ganho_medio_bps": round(wins.mean() * 1e4, 2) if len(wins) else 0.0,
        "perda_media_bps": round(losses.mean() * 1e4, 2) if len(losses) else 0.0,
        "expectativa_bps_por_operacao": round(r.mean() * 1e4, 3),
        "custo_medio_bps": round(trades["cost"].mean() * 1e4, 3),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else None,
        "max_drawdown_pct": round(float(dd) * 100, 3),
        "sharpe_anualizado": round(sharpe, 3) if sharpe is not None else "não calculado (menos de 30 operações)",
        "saidas": trades["barrier"].value_counts().to_dict(),
    }


def classification_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    ok = ~np.isnan(y) & ~np.isnan(p)
    y, p = y[ok].astype(int), p[ok]
    if len(np.unique(y)) < 2:
        return {"amostras": int(len(y)), "nota": "uma só classe no teste"}
    pred = (p >= threshold).astype(int)
    bins = pd.qcut(p, 5, duplicates="drop")
    calib = pd.DataFrame({"p": p, "y": y}).groupby(bins, observed=True).agg(prev=("p", "mean"), real=("y", "mean"), n=("y", "size"))
    return {
        "amostras": int(len(y)),
        "taxa_base": round(float(y.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "log_loss": round(float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))), 4),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "calibracao": [{"prevista": round(r.prev, 3), "observada": round(r.real, 3), "n": int(r.n)} for r in calib.itertuples()],
    }
