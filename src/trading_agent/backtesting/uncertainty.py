"""Incerteza das métricas: bootstrap por blocos, que respeita a dependência temporal.

Reamostrar operações uma a uma presume que são independentes; não são (regimes, volatilidade
agrupada). O bootstrap estacionário (Politis e Romano) reamostra BLOCOS de comprimento
aleatório, mantendo a autocorrelação de curto prazo. Serve para:
  · intervalo de confiança da expectativa líquida por operação;
  · distribuição do retorno total e do drawdown máximo (Monte Carlo sobre retornos diários).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def stationary_bootstrap_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    idx = np.empty(n, dtype=int)
    p = 1.0 / max(mean_block, 1.0)
    i = rng.integers(n)
    for k in range(n):
        idx[k] = i
        i = rng.integers(n) if rng.random() < p else (i + 1) % n
    return idx


def bootstrap_mean_ci(x: np.ndarray, n_boot: int = 2000, mean_block: float = 5.0, alpha: float = 0.05,
                      seed: int = 42) -> dict:
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 5:
        return {"n": int(len(x)), "nota": "amostra pequena demais para um intervalo"}
    rng = np.random.default_rng(seed)
    means = np.array([x[stationary_bootstrap_indices(len(x), mean_block, rng)].mean() for _ in range(n_boot)])
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return {"n": int(len(x)), "media": float(x.mean()), "ic_inf": float(lo), "ic_sup": float(hi),
            "prob_media_positiva": float((means > 0).mean())}


def monte_carlo_equity(daily_returns: pd.Series, n_paths: int = 2000, mean_block: float = 10.0, seed: int = 42) -> dict:
    r = daily_returns.dropna().to_numpy(float)
    if len(r) < 20:
        return {"n_dias": int(len(r)), "nota": "poucos dias para Monte Carlo"}
    rng = np.random.default_rng(seed)
    tot, dds = np.empty(n_paths), np.empty(n_paths)
    for k in range(n_paths):
        path = r[stationary_bootstrap_indices(len(r), mean_block, rng)]
        eq = np.cumprod(1 + path)
        tot[k] = eq[-1] - 1
        dds[k] = (eq / np.maximum.accumulate(eq) - 1).min()
    q = lambda a, v: float(np.quantile(a, v))  # noqa: E731
    return {
        "n_dias": int(len(r)), "caminhos": n_paths,
        "retorno_total_p05": q(tot, 0.05), "retorno_total_p50": q(tot, 0.5), "retorno_total_p95": q(tot, 0.95),
        "prob_retorno_positivo": float((tot > 0).mean()),
        "drawdown_max_p50": q(dds, 0.5), "drawdown_max_p05_pior": q(dds, 0.05),
    }
