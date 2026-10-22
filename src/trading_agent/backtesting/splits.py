"""Validação walk-forward com purging e embargo.

Janela de treino a crescer; cada bloco de teste vem DEPOIS do treino. Saem do treino as
amostras cujo resultado (`t1`) entra no período de validação/teste (purging), e há um
intervalo de `embargo` velas entre treino e teste. Dentro do treino, os últimos `val_frac`
servem de validação (calibração, limiar, early stopping), também com purging.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Fold:
    k: int
    train: np.ndarray
    val: np.ndarray
    test: np.ndarray


def _purge(idx: np.ndarray, t1: pd.Series, boundary: pd.Timestamp) -> np.ndarray:
    ends = t1.iloc[idx]
    return idx[(ends < boundary).to_numpy()]


def walk_forward(t1: pd.Series, n_splits: int = 5, test_frac: float = 0.5, val_frac: float = 0.15,
                 embargo: int = 24) -> list[Fold]:
    """`test_frac` da amostra (a parte mais recente) divide-se em `n_splits` blocos de teste."""
    n = len(t1)
    first_test = int(n * (1 - test_frac))
    edges = np.linspace(first_test, n, n_splits + 1).astype(int)
    times = t1.index
    folds = []
    for k in range(n_splits):
        test = np.arange(edges[k], edges[k + 1])
        train_end = max(edges[k] - embargo, 0)
        pool = np.arange(0, train_end)
        n_val = int(len(pool) * val_frac)
        val = pool[-n_val:] if n_val else np.array([], int)
        train = pool[:-n_val] if n_val else pool
        if len(val):
            train = _purge(train, t1, times[val[0]])
            val = _purge(val, t1, times[test[0]])
        else:
            train = _purge(train, t1, times[test[0]])
        folds.append(Fold(k, train, val, test))
    return folds
