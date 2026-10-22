"""Modelo C: GRU sobre sequências das últimas `seq_len` velas de features.

Pequena de propósito (1 camada, 32 unidades, dropout): com dezenas de milhares de velas
horárias, redes maiores aprendem o ruído. Normalização com estatísticas SÓ do treino.
Early stopping e calibração na validação. Não se presume que bata o XGBoost: compara-se.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from sklearn.isotonic import IsotonicRegression
from torch import nn


class _Net(nn.Module):
    def __init__(self, n_features: int, hidden: int = 32, dropout: float = 0.2):
        super().__init__()
        self.gru = nn.GRU(n_features, hidden, batch_first=True)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        _, h = self.gru(x)
        return self.head(self.drop(h[-1])).squeeze(-1)


class GRUModel:
    def __init__(self, seq_len: int = 48, hidden: int = 32, epochs: int = 15, lr: float = 1e-3, batch: int = 256, seed: int = 42):
        self.seq_len, self.hidden, self.epochs, self.lr, self.batch, self.seed = seq_len, hidden, epochs, lr, batch, seed
        self.mean = self.std = None
        self.net: _Net | None = None
        self.calibrator: IsotonicRegression | None = None

    def _sequences(self, F: np.ndarray, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Sequência que ACABA na vela i (inclusive): só passado. Índices sem histórico suficiente saem."""
        ok = idx[idx >= self.seq_len - 1]
        X = np.stack([F[i - self.seq_len + 1 : i + 1] for i in ok]) if len(ok) else np.empty((0, self.seq_len, F.shape[1]))
        return X.astype(np.float32), ok

    def fit(self, F_all: pd.DataFrame, y_all: pd.Series, tr: np.ndarray, val: np.ndarray) -> GRUModel:
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        A = F_all.to_numpy(np.float64)
        self.mean, self.std = np.nanmean(A[tr], axis=0), np.nanstd(A[tr], axis=0) + 1e-9
        Z = np.nan_to_num((A - self.mean) / self.std)
        y = y_all.to_numpy(np.float32)
        Xtr, itr = self._sequences(Z, tr)
        Xva, iva = self._sequences(Z, val)
        self.net = _Net(Z.shape[1], self.hidden)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr, weight_decay=1e-4)
        loss_fn = nn.BCEWithLogitsLoss()
        best, best_state, paciencia = np.inf, None, 0
        xt, yt = torch.from_numpy(Xtr), torch.from_numpy(y[itr])
        xv, yv = torch.from_numpy(Xva), torch.from_numpy(y[iva])
        for _ in range(self.epochs):
            self.net.train()
            perm = torch.randperm(len(xt))
            for b in range(0, len(xt), self.batch):
                j = perm[b : b + self.batch]
                opt.zero_grad()
                loss = loss_fn(self.net(xt[j]), yt[j])
                loss.backward()
                opt.step()
            self.net.eval()
            with torch.no_grad():
                vl = loss_fn(self.net(xv), yv).item()
            if vl < best - 1e-4:
                best, best_state, paciencia = vl, {k: v.clone() for k, v in self.net.state_dict().items()}, 0
            else:
                paciencia += 1
                if paciencia >= 3:
                    break
        if best_state:
            self.net.load_state_dict(best_state)
        self._Z = Z
        raw = self._raw(iva)
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw, y[iva])
        return self

    def _raw(self, idx: np.ndarray) -> np.ndarray:
        X, _ = self._sequences(self._Z, idx)
        self.net.eval()
        with torch.no_grad():
            return torch.sigmoid(self.net(torch.from_numpy(X))).numpy()

    def predict_proba(self, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Devolve (probabilidades, índices válidos)."""
        ok = idx[idx >= self.seq_len - 1]
        raw = self._raw(ok)
        return (self.calibrator.predict(raw) if self.calibrator is not None else raw), ok
