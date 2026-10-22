"""Modelo B: XGBoost, probabilidade de o take-profit vir antes do stop-loss.

Hiperparâmetros conservadores e FIXOS (árvores rasas, regularização), sem busca extensa:
a busca de parâmetros é a forma mais rápida de sobreajustar séries financeiras. Early stopping
e calibração isotónica usam a janela de validação, nunca o teste.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from xgboost import XGBClassifier

PARAMS = dict(
    n_estimators=400, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
    min_child_weight=20, reg_lambda=5.0, reg_alpha=1.0, objective="binary:logistic",
    eval_metric="logloss", early_stopping_rounds=40, tree_method="hist", n_jobs=4, random_state=42,
)


class XGBoostModel:
    def __init__(self, params: dict | None = None):
        self.params = {**PARAMS, **(params or {})}
        self.model: XGBClassifier | None = None
        self.calibrator: IsotonicRegression | None = None
        self.columns: list[str] = []

    def fit(self, X_tr: pd.DataFrame, y_tr: pd.Series, X_val: pd.DataFrame, y_val: pd.Series) -> XGBoostModel:
        self.columns = list(X_tr.columns)
        self.model = XGBClassifier(**self.params)
        self.model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
        raw = self.model.predict_proba(X_val)[:, 1]
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw, y_val)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.model.predict_proba(X[self.columns])[:, 1]
        return self.calibrator.predict(raw) if self.calibrator is not None else raw

    def importance(self) -> dict[str, float]:
        imp = self.model.get_booster().get_score(importance_type="gain")
        tot = sum(imp.values()) or 1.0
        return dict(sorted(((k, v / tot) for k, v in imp.items()), key=lambda kv: -kv[1]))
