"""Features v2 sem fuga, reamostragem honesta, aprovação fixa e integridade dos modelos."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.isotonic import IsotonicRegression

from trading_agent.data.resample import resample_ohlcv
from trading_agent.features.build import build_features_v2
from trading_agent.models.registry import ModelRegistry, TrainedPolicy, approval
from trading_agent.models.xgboost_model.model import XGBoostModel


def test_features_v2_nao_veem_o_futuro(candles):
    base = build_features_v2(candles, cost_pct=0.0001)
    t = 450
    fut = candles.copy()
    fut.iloc[t + 1 :, :4] *= 1.4
    fut.iloc[t + 1 :, 4] *= 5
    pd.testing.assert_frame_equal(base.iloc[: t + 1], build_features_v2(fut, cost_pct=0.0001).iloc[: t + 1])


def test_reamostragem_nao_inventa_velas(candles):
    df = candles.drop(candles.index[8:11])  # buraco de 3 horas dentro da 3.ª vela de 4 h
    r = resample_ohlcv(df, "4h", "crypto")
    assert pd.Timestamp("2025-01-06 08:00", tz="UTC") not in r.index  # só 1 de 4 horas: fica em falta
    v = r.loc["2025-01-06 00:00"]
    janela = candles.loc["2025-01-06 00:00":"2025-01-06 03:00"]
    assert v["open"] == janela["open"].iloc[0] and v["close"] == janela["close"].iloc[-1]
    assert v["high"] == janela["high"].max() and v["low"] == janela["low"].min()


def test_aprovacao_exige_desenvolvimento_e_teste_final():
    assert approval(True, 3.0, 40)[0] == "aprovado"
    assert approval(False, 30.0, 40)[0] == "rejeitado", "bom no teste final mas não qualificado: rejeitado"
    assert approval(True, -1.0, 40)[0] == "rejeitado"
    assert approval(True, None, 0)[0] == "rejeitado"


def test_registo_versiona_e_deteta_alteracoes(tmp_path):
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(400, 3)), columns=["a", "b", "c"])
    y = pd.Series((X["a"] + rng.normal(scale=0.5, size=400) > 0).astype(int))
    m = XGBoostModel({"n_estimators": 20}).fit(X[:300], y[:300], X[300:], y[300:])
    emap = IsotonicRegression(out_of_bounds="clip").fit(m.predict_proba(X[300:]), y[300:] * 0.01)
    pol = TrainedPolicy("BTC/USD", "1h", 24, 2.0, 1.0, "v2", ["a", "b", "c"], (1,), {1: m}, {1: emap})
    reg = ModelRegistry(tmp_path)
    mid = reg.save(pol, {"status": "rejeitado"})
    carregada, meta = reg.load(mid)
    assert meta["status"] == "rejeitado" and reg.latest("BTC/USD", "aprovado") is None
    d = carregada.decide(X.iloc[0])
    assert d["side"] == 1 and 0 <= d["prob"] <= 1
    assert carregada.decide(pd.Series({"a": np.nan, "b": 0, "c": 0}))["side"] == 0
    (tmp_path / mid / "policy.joblib").write_bytes(b"adulterado")
    with pytest.raises(ValueError, match="SHA-256"):
        reg.load(mid)
