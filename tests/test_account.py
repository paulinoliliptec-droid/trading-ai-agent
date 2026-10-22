"""Conta virtual: capital de 100 €, ordens, stops, execução parcial, idempotência e reinício."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from trading_agent.brokers.base import Order, OrderStatus, Quote, Side
from trading_agent.config import load_config
from trading_agent.execution.instruments import FxConverter, InstrumentSpec, capital_sufficiency
from trading_agent.execution.paper import PaperAccount, reconcile
from trading_agent.persistence.state import SqliteStateStore

T0 = datetime(2026, 1, 5, 10, tzinfo=UTC)


def q(symbol, bid, ask, t=T0):
    return Quote(symbol, bid, ask, t, "teste")


@pytest.fixture
def specs():
    cfg = load_config()
    return {s: cfg.instrument(s) for s in ("EUR/USD", "BTC/USD")}


@pytest.fixture
def conta(specs):
    fx = FxConverter()
    fx.set_rate("EUR", "USD", 1.10)
    return PaperAccount(specs, "EUR", 100.0, fx)


def test_100_euros_conversao_explicita_e_capital_disponivel(conta):
    assert conta.equity() == 100.0 and conta.available() == 100.0
    # BTC/USD à vista: compra de 0.0002 BTC a 70 000 USD = 14 USD = 12,73 EUR comprometidos por inteiro
    r = conta.submit(Order("BTC/USD", Side.BUY, 0.0002, "b1"), q("BTC/USD", 69_990, 70_000))
    assert r.order.status == OrderStatus.FILLED
    comprometido = 0.0002 * 69_990 / 1.10
    assert conta.used_margin() == pytest.approx(comprometido, rel=1e-6)
    taxa = 0.0002 * 70_000 * (1 + 2 / 1e4) * 25 / 1e4 / 1.10
    assert conta.cash == pytest.approx(100 - taxa)
    assert conta.available() == pytest.approx(conta.equity() - comprometido)


def test_sem_taxa_de_cambio_nao_se_presume(specs):
    conta = PaperAccount(specs, "EUR", 100.0)
    with pytest.raises(LookupError):
        conta.submit(Order("BTC/USD", Side.BUY, 0.0002, "b1"), q("BTC/USD", 69_990, 70_000))


def test_capital_insuficiente_e_quantidade_minima(conta):
    r = conta.submit(Order("BTC/USD", Side.BUY, 0.01, "grande"), q("BTC/USD", 69_990, 70_000))  # 700 USD > 100 €
    assert r.order.status == OrderStatus.REJECTED and "capital insuficiente" in r.order.reason
    r = conta.submit(Order("BTC/USD", Side.BUY, 0.00001, "pequena"), q("BTC/USD", 69_990, 70_000))
    assert r.order.status == OrderStatus.REJECTED and "mínimo" in r.order.reason
    assert conta.positions() == {}


def test_venda_a_descoberto_so_onde_e_permitida(conta):
    r = conta.submit(Order("BTC/USD", Side.SELL, 0.0002, "s1"), q("BTC/USD", 69_990, 70_000))
    assert r.order.status == OrderStatus.REJECTED and "descoberto" in r.order.reason
    r = conta.submit(Order("EUR/USD", Side.SELL, 500, "fx1"), q("EUR/USD", 1.0999, 1.1000))
    assert r.order.status == OrderStatus.FILLED
    assert conta.positions()["EUR/USD"].quantity == -500
    # Forex com alavancagem 30: 500 EUR de nocional comprometem ~16,7 EUR
    assert conta.used_margin() == pytest.approx(500 * 1.1000 / 1.0999 / 30, rel=1e-3)


def test_compra_e_venda_realizam_resultado_com_custos(conta):
    conta.submit(Order("EUR/USD", Side.BUY, 1000, "c1"), q("EUR/USD", 1.1000, 1.1001))
    r = conta.submit(Order("EUR/USD", Side.SELL, 1000, "c2", intent="close"), q("EUR/USD", 1.1050, 1.1051, T0 + timedelta(hours=1)))
    t = r.closed_trade
    assert t is not None and conta.positions() == {}
    assert t["pnl_quote"] == pytest.approx(1000 * (1.1050 * (1 - 0.2e-4) - 1.1001 * (1 + 0.2e-4)))
    assert t["net_ret"] < t["gross_ret"], "o custo (spread e slippage) entra"
    assert conta.equity() == pytest.approx(conta.cash)


def test_stop_alvo_e_tempo_ao_vivo(conta):
    conta.submit(Order("EUR/USD", Side.BUY, 1000, "a", stop_loss=1.0950, take_profit=1.1100,
                       expires_at=T0 + timedelta(hours=24)), q("EUR/USD", 1.1000, 1.1001))
    assert conta.on_quote(q("EUR/USD", 1.0990, 1.0991, T0 + timedelta(hours=1))) == []
    fechadas = conta.on_quote(q("EUR/USD", 1.0948, 1.0949, T0 + timedelta(hours=2)))
    assert len(fechadas) == 1 and fechadas[0]["reason"] == "sl"
    conta.submit(Order("EUR/USD", Side.BUY, 1000, "b", stop_loss=1.09, take_profit=1.12,
                       expires_at=T0 + timedelta(hours=5)), q("EUR/USD", 1.1000, 1.1001, T0 + timedelta(hours=3)))
    fechadas = conta.on_quote(q("EUR/USD", 1.1002, 1.1003, T0 + timedelta(hours=6)))
    assert fechadas[0]["reason"] == "tempo"


def test_stop_em_gap_sai_a_abertura_nao_ao_stop(specs):
    conta = PaperAccount(specs, "USD", 10_000.0)
    conta.marks["EUR/USD"] = (1.1000, 1.1001)
    conta.queue_entry(Order("EUR/USD", Side.BUY, 1000, "g", sl_distance=0.0010, tp_distance=0.0020, max_bars=24))
    t1 = T0 + timedelta(hours=1)
    conta.on_bar("EUR/USD", T0, t1, 1.1000, 1.1002, 1.0998, 1.1000, spread=0.0001, basis="bid")
    entrada = conta.positions_["EUR/USD"].entry_price
    # a vela seguinte ABRE 50 pips abaixo, muito para lá do stop (entrada − 10 pips)
    fechadas = conta.on_bar("EUR/USD", t1, t1 + timedelta(hours=1), 1.0950, 1.0960, 1.0940, 1.0955, spread=0.0001, basis="bid")
    assert fechadas[0]["reason"] == "sl_gap"
    assert fechadas[0]["exit_price"] == pytest.approx(1.0950 * (1 - 0.2e-4))
    assert fechadas[0]["exit_price"] < entrada - 0.0010


def test_stop_e_alvo_na_mesma_vela_conta_o_stop(specs):
    conta = PaperAccount(specs, "USD", 10_000.0)
    conta.marks["EUR/USD"] = (1.1000, 1.1001)
    conta.queue_entry(Order("EUR/USD", Side.BUY, 1000, "x", sl_distance=0.0010, tp_distance=0.0020, max_bars=24))
    f = conta.on_bar("EUR/USD", T0, T0 + timedelta(hours=1), 1.1000, 1.1040, 1.0960, 1.1000, spread=0.0001, basis="bid")
    assert f[0]["reason"] == "sl"


def test_execucao_parcial_e_resto_no_preco_seguinte(specs):
    conta = PaperAccount(specs, "USD", 10_000.0, liquidity={"EUR/USD": 400})
    r = conta.submit(Order("EUR/USD", Side.BUY, 1000, "p"), q("EUR/USD", 1.1000, 1.1001))
    assert r.order.status == OrderStatus.PARTIALLY_FILLED and r.order.filled_qty == 400
    assert conta.positions()["EUR/USD"].quantity == 400
    conta.on_quote(q("EUR/USD", 1.1002, 1.1003, T0 + timedelta(minutes=1)))
    conta.on_quote(q("EUR/USD", 1.1002, 1.1003, T0 + timedelta(minutes=2)))
    assert conta.positions()["EUR/USD"].quantity == 1000 and not conta.pending
    assert conta.orders["p"]["status"] == "filled"


def test_ordem_duplicada_nao_executa_duas_vezes(conta):
    o = lambda: Order("EUR/USD", Side.BUY, 1000, "mesma-ordem")  # noqa: E731
    r1 = conta.submit(o(), q("EUR/USD", 1.1000, 1.1001))
    r2 = conta.submit(o(), q("EUR/USD", 1.1000, 1.1001))
    assert r1.fill is not None and r2.duplicate and r2.fill is None
    assert conta.positions()["EUR/USD"].quantity == 1000 and len(conta.fills) == 1


def test_reinicio_com_posicao_aberta_preserva_tudo(tmp_path, conta, specs):
    store = SqliteStateStore(tmp_path / "state.db")
    conta.submit(Order("EUR/USD", Side.BUY, 1000, "r1", stop_loss=1.09, take_profit=1.12), q("EUR/USD", 1.1000, 1.1001))
    store.put("account:EUR/USD", conta.to_state())
    antes = conta.summary()
    # «reinício»: nova instância a partir do estado guardado
    nova = PaperAccount.from_state(store.get("account:EUR/USD"), specs)
    assert nova.summary() == antes
    assert reconcile({"EUR/USD": 1000}, nova) == []
    assert nova.submit(Order("EUR/USD", Side.BUY, 1000, "r1"), q("EUR/USD", 1.1, 1.1001)).duplicate
    fechadas = nova.on_quote(q("EUR/USD", 1.0899, 1.09, T0 + timedelta(hours=1)))
    assert fechadas and fechadas[0]["reason"] == "sl"


def test_suficiencia_de_capital_100_euros():
    cfg = load_config()
    btc, fx = cfg.instrument("BTC/USD"), cfg.instrument("EUR/USD")
    # BTC: stop de 1% e 0,5% de risco → 50 € de nocional permitidos; mínimo 0,00005 BTC a 70 000 = 3,5 USD
    r = capital_sufficiency(btc, 100, 70_000, 0.01, 0.005, fx_to_quote=1.10)
    assert r["suficiente"]
    # Forex numa corretora com micro-lote de 1000 unidades e stop de 0,2%: perda mínima > 0,5% do capital
    micro = InstrumentSpec("EUR/USD", "forex", "EUR", "USD", 1000, 1000, 30, True)
    r = capital_sufficiency(micro, 100, 1.10, 0.002, 0.005, fx_to_quote=1.10)
    assert not r["suficiente"] and r["perda_no_stop_pct_capital_com_quantidade_minima"] > 0.5
    assert capital_sufficiency(fx, 100, 1.10, 0.002, 0.005, fx_to_quote=1.10)["suficiente"]
