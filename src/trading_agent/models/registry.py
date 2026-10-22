"""Modelos treinados e versionados, separados da inferência.

O treino produz uma `TrainedPolicy` (modelos por lado, colunas, horizonte, TP/SL, mapa de
retorno esperado) e grava-a com um identificador único e metadados: período de treino,
manifesto e hash dos dados, métricas fora da amostra e o ESTADO de aprovação.

Aprovação (regra fixa): `aprovado` só se a configuração qualificou no desenvolvimento (≥ 30
operações e IC95% inferior da expectativa líquida > 0) E o teste final, que não foi usado
para escolher, também tem expectativa líquida positiva. Bom desempenho no treino não conta.
O worker só abre posições simuladas com modelos aprovados; os outros correm em observação.

Integridade: o ficheiro do modelo tem o SHA-256 nos metadados e é verificado ao carregar
(o formato usa pickle: carregar só artefactos produzidos por este projeto).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from trading_agent.config import ROOT
from trading_agent.features.build import build_features, build_features_v2

DEFAULT_ROOT = ROOT / "models_artifacts"


@dataclass
class TrainedPolicy:
    symbol: str
    timeframe: str
    horizon_bars: int
    tp_mult: float
    sl_mult: float
    feature_set: str
    columns: list[str]
    sides: tuple[int, ...]
    models: dict = field(default_factory=dict)      # lado → modelo com predict_proba(DataFrame)
    exp_maps: dict = field(default_factory=dict)    # lado → IsotonicRegression (prob → retorno bruto esperado)
    kind: str = "B_xgboost"

    def features(self, bars: pd.DataFrame, extra_cost: float) -> pd.DataFrame:
        if self.feature_set == "v2":
            return build_features_v2(bars, 14, extra_cost)
        return build_features(bars, 14)

    def decide(self, row: pd.Series) -> dict:
        """Proposta para a vela (já fechada) com estas features: lado com maior retorno esperado."""
        x = pd.DataFrame([row[self.columns].astype(float)])
        if x.isna().any(axis=None):
            return {"side": 0, "prob": None, "exp_ret": None, "motivo": "features incompletas"}
        best = {"side": 0, "prob": None, "exp_ret": -np.inf}
        por_lado = {}
        for s in self.sides:
            p = float(self.models[s].predict_proba(x)[0])
            e = float(self.exp_maps[s].predict([p])[0])
            por_lado[s] = {"prob": p, "exp_ret": e}
            if e > best["exp_ret"]:
                best = {"side": s, "prob": p, "exp_ret": e}
        return {**best, "por_lado": por_lado}


def approval(qualified_dev: bool, holdout_net_bps: float | None, holdout_trades: int) -> tuple[str, list[str]]:
    reasons = []
    if not qualified_dev:
        reasons.append("não qualificou no desenvolvimento (IC95% da expectativa líquida não exclui zero ou < 30 operações)")
    if holdout_net_bps is None or holdout_trades == 0:
        reasons.append("sem operações no teste final")
    elif holdout_net_bps <= 0:
        reasons.append(f"teste final com expectativa líquida {holdout_net_bps:.2f} bps ≤ 0")
    return ("aprovado" if not reasons else "rejeitado"), reasons


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ModelRegistry:
    def __init__(self, root: Path | str = DEFAULT_ROOT):
        self.root = Path(root)

    def save(self, policy: TrainedPolicy, meta: dict) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        model_id = f"{policy.symbol.replace('/', '')}-{policy.timeframe}-{policy.kind}-{stamp}"
        d = self.root / model_id
        d.mkdir(parents=True, exist_ok=False)
        joblib.dump(policy, d / "policy.joblib")
        meta = {**meta, "model_id": model_id, "symbol": policy.symbol, "timeframe": policy.timeframe, "kind": policy.kind,
                "created_at": datetime.now(UTC).isoformat(), "sha256": _sha256(d / "policy.joblib"),
                "columns": policy.columns, "horizon_bars": policy.horizon_bars, "tp_mult": policy.tp_mult,
                "sl_mult": policy.sl_mult, "feature_set": policy.feature_set}
        (d / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=str))
        return model_id

    def meta(self, model_id: str) -> dict:
        return json.loads((self.root / model_id / "meta.json").read_text())

    def load(self, model_id: str) -> tuple[TrainedPolicy, dict]:
        meta = self.meta(model_id)
        path = self.root / model_id / "policy.joblib"
        if _sha256(path) != meta["sha256"]:
            raise ValueError(f"modelo {model_id} alterado depois de gravado (SHA-256 não confere)")
        return joblib.load(path), meta

    def list(self, symbol: str | None = None) -> list[dict]:
        if not self.root.exists():
            return []
        metas = [json.loads(p.read_text()) for p in sorted(self.root.glob("*/meta.json"))]
        return [m for m in metas if symbol is None or m["symbol"] == symbol]

    def latest(self, symbol: str, status: str | None = None) -> str | None:
        ms = [m for m in self.list(symbol) if status is None or m.get("status") == status]
        return max(ms, key=lambda m: m["created_at"])["model_id"] if ms else None
