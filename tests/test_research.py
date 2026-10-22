from __future__ import annotations

import numpy as np
import pandas as pd

from trading_agent.backtesting.splits import walk_forward
from trading_agent.data.quality import clean_ohlcv
from trading_agent.features.build import atr, build_features
from trading_agent.labels.triple_barrier import triple_barrier


def test_features_nao_veem_o_futuro(candles):
    """Mudar os preços DEPOIS de t não pode mudar nenhuma feature até t."""
    base = build_features(candles)
    t = 400
    futuro = candles.copy()
    futuro.iloc[t + 1 :, :4] *= 1.5
    futuro.iloc[t + 1 :, 4] *= 3
    alterado = build_features(futuro)
    pd.testing.assert_frame_equal(base.iloc[: t + 1], alterado.iloc[: t + 1])


def test_triple_barrier_conservador_e_sem_rotulo_alem_dos_dados():
    idx = pd.date_range("2025-01-01", periods=6, freq="1h", tz="UTC")
    df = pd.DataFrame({"open": [100, 100, 100, 100, 100, 100], "high": [100, 100, 103, 100, 100, 100],
                       "low": [100, 100, 98, 100, 100, 100], "close": [100] * 6, "volume": [1] * 6}, index=idx, dtype=float)
    a = pd.Series(1.0, index=idx)
    lab = triple_barrier(df, a, side=1, horizon=3, tp_mult=2.0, sl_mult=1.0)
    # Na vela 2 tocam-se o TP (102) e o SL (99): conta como SL.
    assert lab["label"].iloc[0] == 0.0 and lab["barrier"].iloc[0] == "sl"
    assert lab["t1"].iloc[0] == idx[2]
    # Nas últimas velas o horizonte passa o fim dos dados: sem rótulo.
    assert lab["label"].iloc[-1:].isna().all()


def test_triple_barrier_vendido_ganha_quando_desce():
    idx = pd.date_range("2025-01-01", periods=5, freq="1h", tz="UTC")
    df = pd.DataFrame({"open": [100] * 5, "high": [100, 100, 100.5, 100, 100], "low": [100, 100, 97, 100, 100],
                       "close": [100] * 5, "volume": [1] * 5}, index=idx, dtype=float)
    lab = triple_barrier(df, pd.Series(1.0, index=idx), side=-1, horizon=3, tp_mult=2.0, sl_mult=1.0)
    assert lab["label"].iloc[0] == 1.0 and lab["gross_ret"].iloc[0] > 0


def test_walk_forward_com_purging(candles):
    a = atr(candles)
    lab = triple_barrier(candles, a, 1, horizon=24)
    t1 = lab["t1"].dropna()
    folds = walk_forward(t1, n_splits=3, test_frac=0.5, val_frac=0.15, embargo=24)
    for f in folds:
        inicio_teste = t1.index[f.test[0]]
        assert (t1.iloc[f.train] < t1.index[f.val[0]]).all(), "treino com resultados dentro da validação"
        assert (t1.iloc[f.val] < inicio_teste).all(), "validação com resultados dentro do teste"
        assert f.train.max() < f.val.min() < f.test.min()
        assert f.test.min() - f.val.max() >= 24, "falta o embargo"


def test_qualidade_utc_duplicados_e_velas_impossiveis(candles):
    df = candles.copy()
    df.index = df.index.tz_convert("Europe/Lisbon")
    df = pd.concat([df, df.iloc[[5]]])
    df.iloc[10, df.columns.get_loc("high")] = df.iloc[10]["low"] * 0.9
    df = df.drop(df.index[[20, 21]])
    out, rep = clean_ohlcv(df, "1h")
    assert str(out.index.tz) == "UTC" and out.index.is_monotonic_increasing
    assert rep.duplicates_removed == 1 and rep.invalid_bars_removed == 1 and rep.missing_bars == 3


def test_qualidade_forex_ignora_fim_de_semana():
    idx = pd.date_range("2025-01-03 20:00", "2025-01-05 23:00", freq="1h", tz="UTC")  # sexta a domingo
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    df = df[~((df.index.day_of_week == 5) | ((df.index.day_of_week == 4) & (df.index.hour >= 22)) | ((df.index.day_of_week == 6) & (df.index.hour < 22)))]
    _, rep = clean_ohlcv(df, "1h", market_hours="forex")
    assert rep.missing_bars == 0
    assert np.isclose(rep.missing_ratio, 0.0)
