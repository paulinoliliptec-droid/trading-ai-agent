"""Métricas de negociação e de classificação. A accuracy não entra: não prova rentabilidade.

Separam-se três coisas que a fase 1 misturava: o movimento de mercado captado (`gross_ret`,
ao preço médio), o custo de execução (`cost_ret`: spread, slippage, comissões) e o resultado
líquido (`net_ret`). Assim vê-se se uma estratégia falha por não prever ou por pagar demais.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score


def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min()) if len(equity) else 0.0


def trading_metrics(trades: pd.DataFrame, equity: pd.Series, periods_per_year: int) -> dict:
    n = len(trades)
    out: dict = {"operacoes": n}
    dd = max_drawdown(equity)
    if n == 0:
        return {**out, "retorno_liquido_pct": 0.0, "max_drawdown_pct": round(dd * 100, 3),
                "nota": "sem operações (equivale a não negociar)"}
    r = trades["net_ret"]
    wins, losses = r[r > 0], r[r <= 0]
    pnl = trades["pnl_account"]
    gross_win, gross_loss = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    daily = equity.resample("1D").last().dropna().pct_change().dropna()
    sharpe = None
    if n >= 30 and daily.std() > 0:
        sharpe = float(daily.mean() / daily.std() * np.sqrt(periods_per_year))
    return {
        **out,
        "retorno_liquido_pct": round(float(equity.iloc[-1] / equity.iloc[0] - 1) * 100, 3) if len(equity) else 0.0,
        "taxa_acerto_pct": round(len(wins) / n * 100, 2),
        "ganho_medio_bps": round(float(wins.mean()) * 1e4, 2) if len(wins) else 0.0,
        "perda_media_bps": round(float(losses.mean()) * 1e4, 2) if len(losses) else 0.0,
        "expectativa_bruta_bps": round(float(trades["gross_ret"].mean()) * 1e4, 3),
        "custo_medio_bps": round(float(trades["cost_ret"].mean()) * 1e4, 3),
        "expectativa_bps_por_operacao": round(float(r.mean()) * 1e4, 3),
        "profit_factor": round(float(gross_win / gross_loss), 3) if gross_loss > 0 else None,
        "max_drawdown_pct": round(dd * 100, 3),
        "sharpe_anualizado": round(sharpe, 3) if sharpe is not None else "não calculado (menos de 30 operações)",
        "saidas": trades["reason"].value_counts().to_dict(),
        "duracao_media_velas": round(float(trades["bars_held"].mean()), 2),
    }


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 5) -> list[dict]:
    q = pd.qcut(p, bins, duplicates="drop")
    t = pd.DataFrame({"p": p, "y": y}).groupby(q, observed=True).agg(prev=("p", "mean"), real=("y", "mean"), n=("y", "size"))
    return [{"prevista": round(r.prev, 3), "observada": round(r.real, 3), "n": int(r.n)} for r in t.itertuples()]


def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    ece = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            ece += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(ece)


def classification_metrics(y: np.ndarray, p: np.ndarray, threshold: float | None = None) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    ok = ~np.isnan(y) & ~np.isnan(p)
    y, p = y[ok].astype(int), p[ok]
    if len(np.unique(y)) < 2:
        return {"amostras": int(len(y)), "nota": "uma só classe"}
    base_rate = float(y.mean())
    brier = float(brier_score_loss(y, p))
    out = {
        "amostras": int(len(y)),
        "taxa_base": round(base_rate, 4),
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "brier": round(brier, 5),
        # Brier skill: >0 só se bate prever sempre a taxa base
        "brier_skill": round(1 - brier / (base_rate * (1 - base_rate)), 5),
        "log_loss": round(float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))), 5),
        "ece": round(expected_calibration_error(y, p), 4),
        "calibracao": calibration_table(y, p),
    }
    if threshold is not None:
        m = p >= threshold
        out["limiar"] = threshold
        out["sinais_acima_do_limiar"] = int(m.sum())
        out["taxa_tp_acima_do_limiar"] = round(float(y[m].mean()), 4) if m.any() else None
    return out
