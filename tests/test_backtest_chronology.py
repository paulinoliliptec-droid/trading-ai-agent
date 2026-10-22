"""O backtest é cronológico: o futuro nunca muda o passado, e as execuções seguem a ordem real."""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from trading_agent.backtesting.engine import BacktestConfig, run_backtest
from trading_agent.backtesting.splits import walk_forward
from trading_agent.backtesting.uncertainty import bootstrap_mean_ci, monte_carlo_equity
from trading_agent.config import load_config
from trading_agent.features.build import atr, build_features
from trading_agent.labels.triple_barrier import triple_barrier
from trading_agent.risk.engine import RiskEngine
from trading_agent.risk.kill_switch import KillSwitch


def _risk(**kw):
    cfg = load_config()
    lim = dataclasses.replace(cfg.risk, min_probability=0.0, min_expected_edge_bps=-1e9, max_drawdown_pct=0.99,
                              max_daily_loss_pct=0.99, min_capital=0.0, **kw)
    return RiskEngine(lim, KillSwitch(None), 30)


def _run(candles, risk=None, sides=None, cfg=None):
    f = build_features(candles)
    idx = f.dropna().index
    sig = pd.DataFrame({"side": 1 if sides is None else sides.reindex(idx).fillna(0), "prob": 0.6}, index=idx)
    spec = load_config().instrument("EUR/USD")
    return run_backtest(candles, f, sig, risk or _risk(), cfg or BacktestConfig(spec, 24, 2.0, 1.0, 10_000.0))


def test_mudar_o_futuro_nao_muda_o_passado(candles):
    base = _run(candles)
    t = candles.index[450]
    futuro = candles.copy()
    futuro.loc[futuro.index > t, ["open", "high", "low", "close"]] *= 1.3
    alt = _run(futuro)
    corte = t + pd.Timedelta(hours=1)  # fecho da vela t
    pd.testing.assert_series_equal(base.equity[base.equity.index <= corte], alt.equity[alt.equity.index <= corte])
    # Operações fechadas ANTES do fecho de t (uma saída por gap na abertura de t+1 tem o mesmo instante
    # que o fecho de t e depende, legitimamente, do preço de t+1).
    fechadas = lambda r: r.trades[r.trades["exit_time"] < corte].reset_index(drop=True)  # noqa: E731
    pd.testing.assert_frame_equal(fechadas(base).drop(columns="meta"), fechadas(alt).drop(columns="meta"))


def test_entrada_na_abertura_seguinte_e_sem_sobreposicao(candles):
    r = _run(candles)
    tr = r.trades
    assert len(tr) > 3
    assert (tr["entry_time"] == tr["signal_time"] + pd.Timedelta(hours=1)).all(), "entra na abertura de t+1"
    prox_entrada = tr["entry_time"].iloc[1:].reset_index(drop=True)
    prox_sinal = tr["signal_time"].iloc[1:].reset_index(drop=True)
    saida_ant = tr["exit_time"].iloc[:-1].reset_index(drop=True)
    assert (prox_entrada >= saida_ant).all(), "uma posição de cada vez"
    assert (prox_sinal >= saida_ant - pd.Timedelta(hours=1)).all(), "só se decide depois de a anterior fechar"


def test_equity_marca_a_mercado_durante_a_operacao(candles):
    r = _run(candles)
    t = r.trades.iloc[0]
    durante = r.equity[(r.equity.index > t["entry_time"]) & (r.equity.index < t["exit_time"])]
    antes = r.equity[r.equity.index <= t["signal_time"] + pd.Timedelta(hours=1)].iloc[-1]
    if len(durante):
        assert durante.nunique() > 1 or durante.iloc[0] != antes, "o não realizado entra no equity"
    # e o resultado só aparece depois de a operação existir
    assert r.equity.loc[t["signal_time"] + pd.Timedelta(hours=1)] == pytest.approx(10_000.0)


def test_custos_em_todas_as_operacoes_e_decomposicao(candles):
    tr = _run(candles).trades
    assert (tr["cost_ret"] > 0).all()
    np.testing.assert_allclose(tr["gross_ret"] - tr["cost_ret"], tr["net_ret"], atol=1e-12)


def test_limite_diario_bloqueia_e_reinicia_no_dia_seguinte(candles):
    risk = _risk()
    risk.limits = dataclasses.replace(risk.limits, max_daily_loss_pct=0.0001)
    r = _run(candles, risk=risk)
    assert r.vetoes.get("limite", 0) > 0
    dias = r.trades["signal_time"].dt.date.value_counts()
    assert len(dias) > 1, "noutro dia volta a poder negociar"


def test_kill_switch_bloqueia_todas_as_entradas(candles, tmp_path):
    ks = KillSwitch(tmp_path / "KS")
    ks.engage("teste", "ensaio")
    risk = _risk()
    risk.kill_switch = ks
    r = _run(candles, risk=risk)
    assert r.trades.empty and r.vetoes.get("kill", 0) > 0


def test_tempo_fecha_ao_fim_do_horizonte(candles):
    spec = dataclasses.replace(load_config().instrument("EUR/USD"))
    r = _run(candles, cfg=BacktestConfig(spec, 3, 50.0, 50.0, 10_000.0))
    assert (r.trades["reason"].isin(["tempo", "fim_dos_dados"])).all()
    assert (r.trades.loc[r.trades["reason"] == "tempo", "bars_held"] == 3).all()


def test_sem_fuga_entre_treino_e_teste(candles):
    """Nenhuma amostra de treino/validação tem resultado (t1) dentro do teste, e há embargo."""
    lab = triple_barrier(candles, atr(candles), 1, horizon=24)
    t1 = lab["t1"].dropna()
    for f in walk_forward(t1, n_splits=3, test_frac=0.5, val_frac=0.15, calib_frac=0.15, embargo=24):
        ini = t1.index[f.test[0]]
        for parte in (f.train, f.val, f.calib):
            assert (t1.iloc[parte] < ini).all()
        assert f.train.max() < f.val.min() <= f.val.max() < f.calib.min() < f.test.min()
        assert f.test.min() - f.calib.max() > 24 and f.val.min() - f.train.max() > 1


def test_bootstrap_e_monte_carlo():
    rng = np.random.default_rng(1)
    ci = bootstrap_mean_ci(rng.normal(0.001, 0.01, 300))
    assert ci["ic_inf"] < ci["media"] < ci["ic_sup"]
    mc = monte_carlo_equity(pd.Series(rng.normal(0, 0.01, 200)))
    assert mc["drawdown_max_p05_pior"] <= mc["drawdown_max_p50"] <= 0
