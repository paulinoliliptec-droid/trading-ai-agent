from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from trading_agent.backtesting.engine import BacktestConfig, run_backtest
from trading_agent.brokers.base import LiveTradingDisabled, Order, Quote, Side, ensure_simulated
from trading_agent.config import load_config
from trading_agent.execution.paper import PaperBroker, reconcile
from trading_agent.features.build import build_features
from trading_agent.risk.engine import PortfolioState, Proposal, RiskEngine, expected_edge
from trading_agent.risk.kill_switch import KillSwitch


@pytest.fixture
def risk(tmp_path):
    return RiskEngine(load_config().risk, KillSwitch(tmp_path / "KS"), max_leverage=30)


def boa_proposta(**kw):
    base = dict(symbol="EUR/USD", side=1, probability=0.6, tp_pct=0.004, sl_pct=0.002, cost_pct=0.0001, spread_bps=0.8, atr_pct=0.002)
    return Proposal(**{**base, **kw})


def estado(**kw):
    base = dict(equity=100.0, peak_equity=100.0, day_start_equity=100.0, open_positions=0)
    return PortfolioState(**{**base, **kw})


def test_aprova_e_dimensiona_pela_perda_no_stop(risk):
    d = risk.evaluate(boa_proposta(), estado())
    assert d.trade and d.side == 1
    # perda no stop ≈ 0,5% do capital
    assert abs(d.size_fraction * (0.002 + 0.0001) - 0.005) < 1e-9


@pytest.mark.parametrize("kw,motivo", [
    (dict(probability=0.2), "probabilidade"),
    (dict(spread_bps=10), "spread"),
    (dict(atr_pct=0.2), "volatilidade"),
    (dict(cost_pct=0.01), "expectativa"),
    (dict(side=0), "sem sinal"),
])
def test_veta_e_diz_porque(risk, kw, motivo):
    d = risk.evaluate(boa_proposta(**kw), estado())
    assert not d.trade and any(motivo in r for r in d.reasons)


def test_limites_de_carteira(risk):
    assert not risk.evaluate(boa_proposta(), estado(open_positions=2)).trade
    assert not risk.evaluate(boa_proposta(), estado(equity=97, day_start_equity=100, peak_equity=100)).trade
    assert not risk.evaluate(boa_proposta(), estado(equity=89, day_start_equity=89, peak_equity=100)).trade
    assert not risk.evaluate(boa_proposta(), PortfolioState(100, 100, 100, 0, venue_available=False)).trade


@pytest.mark.parametrize("kw,motivo", [
    (dict(equity=40, peak_equity=40, day_start_equity=40), "abaixo do mínimo"),
    (dict(data_age_bars=5), "desatualizados"),
    (dict(consecutive_api_errors=3), "falhas de API"),
    (dict(bar_move_atr=12), "anómala"),
    (dict(anomaly="spread negativo"), "anómala"),
])
def test_protecoes_operacionais(risk, kw, motivo):
    d = risk.evaluate(boa_proposta(), estado(**kw))
    assert not d.trade and any(motivo in r for r in d.reasons)


def test_tamanho_limitado_pelo_capital_disponivel(risk):
    livre = risk.evaluate(boa_proposta(), estado())
    preso = risk.evaluate(boa_proposta(), estado(available_equity=1.0))
    assert preso.trade and preso.size_fraction < livre.size_fraction
    assert preso.size_fraction * 100 <= 1.0 * 30 + 1e-9


def test_kill_switch_vence_qualquer_probabilidade(risk, monkeypatch):
    risk.kill_switch.engage("teste", "ensaio")
    assert not risk.evaluate(boa_proposta(probability=0.99), estado()).trade
    risk.kill_switch.release("teste")
    assert risk.evaluate(boa_proposta(), estado()).trade
    monkeypatch.setenv("TRADING_KILL_SWITCH", "1")
    assert not risk.evaluate(boa_proposta(), estado()).trade


def test_expectativa_desconta_custos():
    assert expected_edge(0.5, 0.004, 0.002, 0.0) > 0
    assert expected_edge(0.5, 0.004, 0.002, 0.002) < 0.001


def test_so_execucao_simulada():
    class Real:
        is_simulated = False
    with pytest.raises(LiveTradingDisabled):
        ensure_simulated(Real())
    ensure_simulated(PaperBroker())
    assert load_config().live_trading_enabled is False


def test_paper_broker_custos_e_reconciliacao():
    b = PaperBroker(fee_bps=10, slippage_bps=1)
    q = Quote("BTC/USD", 100.0, 100.2, datetime.now(UTC), "teste")
    f = b.submit(Order("BTC/USD", Side.BUY, 2.0, "o1"), q).fill
    assert f.price == pytest.approx(100.2 * 1.0001) and f.fee == pytest.approx(f.price * 2 * 0.001)
    assert reconcile({"BTC/USD": 2.0}, b) == []
    assert reconcile({"BTC/USD": 1.0}, b) == ["BTC/USD: motor=1.0 corretora=2.0"]
    b.submit(Order("BTC/USD", Side.SELL, 2.0, "o2"), q)
    assert b.positions() == {}
    assert b.realized_pnl < 0, "comprar no ask e vender no bid, com comissões, perde"


def test_backtest_custos_e_vetos(candles, tmp_path):
    f = build_features(candles)
    sig = pd.DataFrame({"side": 1, "prob": 0.7}, index=f.dropna().index)
    eng = RiskEngine(load_config().risk, KillSwitch(tmp_path / "KS"), 30)
    cfg = BacktestConfig(load_config().instrument("EUR/USD"), 24, 2.0, 1.0, 10_000.0)
    r = run_backtest(candles, f, sig, eng, cfg)
    assert len(r.trades) > 0
    assert (r.trades["net_ret"] < r.trades["gross_ret"]).all(), "os custos entram em todas as operações"
    KillSwitch(tmp_path / "KS").engage("t", "t")
    r2 = run_backtest(candles, f, sig, eng, cfg)
    assert r2.trades.empty and r2.vetoes.get("kill", 0) > 0
