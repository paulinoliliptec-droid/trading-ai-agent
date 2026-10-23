"""Hipótese 3: a previsão de volatilidade é causal, encontra persistência quando existe e não a inventa."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_agent.research.volatility import (
    VolSpec,
    daily_table,
    forecast_quality,
    forecasts,
    paired_ci,
    sharpe,
    vol_target_returns,
)

SPEC = VolSpec("X", min_train_days=120, refit_every=40)


def _hourly(n_days: int, clustered: bool, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = n_days * 24
    if clustered:   # log-volatilidade AR(1) diária persistente
        lv = np.zeros(n_days)
        for t in range(1, n_days):
            lv[t] = 0.95 * lv[t - 1] + 0.3 * rng.standard_normal()
        sig = 0.01 * np.exp(np.repeat(lv, 24))
    else:
        sig = np.full(n, 0.01)
    r = sig * rng.standard_normal(n)
    close = 100 * np.exp(np.cumsum(r))
    idx = pd.date_range("2022-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"open": close, "high": close * (1 + sig / 2), "low": close * (1 - sig / 2), "close": close,
                         "volume": rng.uniform(1, 2, n)}, index=idx)


def _oos(d, fc):
    return fc.index[d.loc[fc.index, "rv_next"].notna().to_numpy()]


def test_previsoes_nao_usam_o_futuro():
    h = _hourly(300, True)
    d = daily_table(h, SPEC)
    fc = forecasts(d, SPEC)
    corte = d.index[200]
    h2 = h.copy()
    h2.loc[h2.index >= corte + pd.Timedelta(days=1), ["close", "high", "low"]] *= 3.0   # muda tudo a partir de corte+1
    d2 = daily_table(h2, SPEC)
    fc2 = forecasts(d2, SPEC)
    antes = fc.index[fc.index < corte]
    pd.testing.assert_frame_equal(fc.loc[antes], fc2.loc[antes])


def test_encontra_persistencia_quando_existe():
    d = daily_table(_hourly(500, True), SPEC)
    fc = forecasts(d, SPEC)
    q = forecast_quality(d, fc, _oos(d, fc))
    assert q["HAR"]["r2_log"] > 0.3 and q["XGB"]["r2_log"] > 0.2


def test_nao_inventa_previsibilidade_nem_vantagem_sem_ela():
    d = daily_table(_hourly(500, False), SPEC)
    fc = forecasts(d, SPEC)
    idx = _oos(d, fc)
    assert forecast_quality(d, fc, idx)["HAR"]["r2_log"] < 0.05
    vt = vol_target_returns(d, fc.loc[idx, "HAR"], target_ann=0.10, cost_bps=0.0)
    ci = paired_ci(vt["net"].to_numpy(), vt["asset"].to_numpy(), sharpe, n_boot=300)
    assert ci["ic_inf"] < 0 < ci["ic_sup"]


def test_volatilidade_alvo_aplica_o_peso_ao_dia_seguinte_e_cobra_a_rotacao():
    d = daily_table(_hourly(200, True), SPEC)
    idx = d.index[150:155]
    var = pd.Series([1e-4, 4e-4, 4e-4, 1e-4, 1e-4], index=idx)
    vt = vol_target_returns(d, var, target_ann=0.01 * np.sqrt(365), cost_bps=10.0, band=0.1)
    assert np.allclose(vt["w"], [1.0, 0.5, 0.5, 1.0, 1.0])
    assert np.allclose(vt["turnover"], [1.0, 0.5, 0.0, 0.5, 0.0])
    assert np.allclose(vt["net"], vt["w"] * np.expm1(d.loc[idx, "ret_next"]) - vt["turnover"] * 10 / 1e4)
