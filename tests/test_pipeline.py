"""Pipeline de investigação de ponta a ponta em dados SINTÉTICOS (passeio aleatório: não há vantagem a encontrar)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_agent.config import load_config
from trading_agent.research.pipeline import ExperimentSpec, run_experiment


def _passeio(n=3000, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = 1.10 * np.exp(np.cumsum(rng.normal(0, 0.001, n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * (1 + rng.uniform(0, 5e-4, n)),
                         "low": np.minimum(o, c) * (1 - rng.uniform(0, 5e-4, n)), "close": c,
                         "volume": rng.uniform(100, 1000, n), "spread": 0.00008}, index=idx)


def test_pipeline_separa_desenvolvimento_e_teste_final_e_nao_inventa_vantagem():
    bars = _passeio()
    spec = ExperimentSpec("EUR/USD", "sintetico", "1h", 12, 1.0, 1.0)
    rep, raw = run_experiment(spec, load_config(), ("A", "B"), n_splits=4, dev_splits=3, log=lambda *_: None, bars=bars)
    dev, fin = raw["periods"]["desenvolvimento"], raw["periods"]["teste_final"]
    assert len(dev) and len(fin) and dev.max() < fin.min(), "o teste final vem depois do desenvolvimento"
    b = rep["modelos"]["B_xgboost"]
    assert "desenvolvimento" in b and "teste_final" in b
    # Num passeio aleatório nenhuma configuração deve qualificar (IC95% inferior > 0)
    assert not b["qualificado_no_desenvolvimento"]
    auc = b["desenvolvimento"]["classificacao_lado_principal"]["roc_auc"]
    assert 0.4 < auc < 0.6
    assert rep["diagnostico_custos"]["custo_ida_volta_bps"] > 0
