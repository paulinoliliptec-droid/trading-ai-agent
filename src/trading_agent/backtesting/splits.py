"""Validação walk-forward com purging e embargo, e com partes separadas para cada uso.

Janela de treino a crescer; cada bloco de teste vem DEPOIS de tudo o resto. Antes do teste:

    treino | embargo | validação | embargo | calibração | embargo | TESTE

  · treino: ajusta os pesos;
  · validação: early stopping e escolha do limiar de decisão;
  · calibração: ajusta a calibração das probabilidades (isotónica), em dados que nem o
    treino nem a escolha do limiar viram (com `calib_frac=0` a calibração usa a validação,
    como na fase 1);
  · teste: só se mede. Nada do teste escolhe parâmetros.
Purging: sai de cada parte qualquer amostra cujo resultado (`t1`) entra na parte seguinte.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Fold:
    k: int
    train: np.ndarray
    val: np.ndarray
    test: np.ndarray
    calib: np.ndarray = field(default_factory=lambda: np.array([], int))


def _purge(idx: np.ndarray, t1: pd.Series, boundary: pd.Timestamp) -> np.ndarray:
    if len(idx) == 0:
        return idx
    ends = t1.iloc[idx]
    return idx[(ends < boundary).to_numpy()]


def walk_forward(t1: pd.Series, n_splits: int = 5, test_frac: float = 0.5, val_frac: float = 0.15,
                 embargo: int = 24, calib_frac: float = 0.0) -> list[Fold]:
    """`test_frac` da amostra (a parte mais recente) divide-se em `n_splits` blocos de teste."""
    n = len(t1)
    if n < 10 * n_splits:
        raise ValueError(f"amostras válidas insuficientes para walk-forward: {n} (features ou rótulos todos em falta?)")
    first_test = int(n * (1 - test_frac))
    edges = np.linspace(first_test, n, n_splits + 1).astype(int)
    times = t1.index
    folds = []
    for k in range(n_splits):
        test = np.arange(edges[k], edges[k + 1])
        pool_end = max(edges[k] - embargo, 0)
        n_val, n_cal = int(pool_end * val_frac), int(pool_end * calib_frac)
        gaps = embargo * (int(n_val > 0) + int(n_cal > 0))
        n_train = max(pool_end - n_val - n_cal - gaps, 0)
        train = np.arange(0, n_train)
        pos = n_train + (embargo if n_val else 0)
        val = np.arange(pos, pos + n_val)
        pos = pos + n_val + (embargo if n_cal else 0)
        calib = np.arange(pos, pos + n_cal)
        parts = [p for p in (train, val, calib) if len(p)]
        nxt = [p for p in (val, calib) if len(p)] + [test]
        purged = [_purge(p, t1, times[q[0]]) for p, q in zip(parts, nxt, strict=False)]
        train = purged[0]
        val = purged[1] if n_val else np.array([], int)
        calib = purged[-1] if n_cal else np.array([], int)
        folds.append(Fold(k, train, val, test, calib))
    return folds
