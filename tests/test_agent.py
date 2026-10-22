"""Agente persistente: ciclo, reinício sem duplicados, dados desatualizados, falhas e kill switch.

Dados SINTÉTICOS (fixture `candles`), só para testar o comportamento do ciclo.
"""

from __future__ import annotations

import multiprocessing as mp
from datetime import timedelta

import pandas as pd
import pytest

from trading_agent.agent.worker import AgentWorker, WorkerConfig, quote_from_bars
from trading_agent.brokers.base import MarketDataSource
from trading_agent.config import load_config
from trading_agent.models.registry import TrainedPolicy
from trading_agent.notifications.telegram import Event, TelegramCommands, TelegramNotifier, default_handlers
from trading_agent.persistence.repository import MongoRepository, SqliteRepository
from trading_agent.persistence.state import MongoStateStore, SqliteStateStore
from trading_agent.risk.kill_switch import KillSwitch


class FakeSource(MarketDataSource):
    name = "falsa"

    def __init__(self, bars: pd.DataFrame, clock, falhas: int = 0):
        self.bars, self.clock, self.falhas = bars, clock, falhas

    def historical(self, symbol, timeframe, start, end):
        if self.falhas > 0:
            self.falhas -= 1
            raise ConnectionError("fonte em baixo")
        b = self.bars
        return b[(b.index >= start) & (b.index <= end)]

    def quote(self, symbol):
        if self.falhas > 0:
            self.falhas -= 1
            raise ConnectionError("fonte em baixo")
        now = self.clock()
        fechadas = self.bars[self.bars.index + pd.Timedelta(hours=1) <= now]
        return quote_from_bars(symbol, fechadas, 0.5, now)


class PoliticaFixa(TrainedPolicy):
    """Política de teste: propõe sempre comprar com retorno esperado alto (não aprende nada)."""

    def decide(self, row):
        return {"side": 1, "prob": 0.7, "exp_ret": 0.01, "por_lado": {1: {"prob": 0.7, "exp_ret": 0.01}}}


class Relogio:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def mundo(candles, tmp_path):
    cfg = load_config()
    bars = candles.drop(columns="spread")
    relogio = Relogio(bars.index[300] + timedelta(hours=1, minutes=1))
    pol = PoliticaFixa("EUR/USD", "1h", 24, 2.0, 1.0, "v1", ["atr_pct"], (1, -1))
    ctx = dict(cfg=cfg, policy=pol, data=FakeSource(bars, relogio), store=SqliteStateStore(tmp_path / "state.db"),
               repo=SqliteRepository(tmp_path / "op.db"), kill=KillSwitch(None, store=None),
               notifier=TelegramNotifier(None, {1}), clock=relogio, fx_source=lambda: 1.10)
    ctx["kill"] = KillSwitch(None, store=ctx["store"])
    return ctx, relogio, bars


def novo(ctx, status="aprovado", modo="paper"):
    return AgentWorker(model_meta={"model_id": "teste", "status": status}, wcfg=WorkerConfig(mode=modo), **ctx)


def test_ciclo_abre_posicao_e_reinicio_nao_duplica(mundo):
    ctx, relogio, _ = mundo
    w = novo(ctx)
    r = w.cycle()
    assert r["aprovado"] and r["ordem"] == "filled", r
    assert len(w.account.positions_) == 1
    # reinício no mesmo instante: a mesma vela não volta a ser processada e não há segunda ordem
    w2 = novo(ctx)
    assert w2.account.summary() == w.account.summary()
    r2 = w2.cycle()
    assert r2["estado"] == "vela_ja_processada"
    assert len(ctx["repo"].find("orders", "default")) == 1
    assert len(w2.account.fills) == 1


def test_posicao_e_gerida_depois_do_reinicio(mundo):
    ctx, relogio, bars = mundo
    w = novo(ctx)
    w.cycle()
    for _ in range(1, 30):
        relogio.t += timedelta(hours=1)
        w = novo(ctx)  # reinício a cada hora
        w.cycle()
        if not w.account.positions_ and w.account.trades:
            break
    assert w.account.trades, "a posição fechou (stop, alvo ou tempo) depois de reinícios"
    assert w.account.trades[0]["reason"] in ("sl", "tp", "tempo")
    assert len(ctx["repo"].find("trades", "default")) >= 1


def test_dados_desatualizados_nao_abrem_posicao(mundo):
    ctx, relogio, bars = mundo
    ctx["data"].bars = bars[bars.index <= relogio.t - timedelta(hours=6)]
    w = novo(ctx)
    r = w.cycle()
    assert not r["aprovado"] and any("desatualizados" in m for m in r["decisao"])


def test_falhas_de_api_contam_e_o_agente_recupera(mundo):
    ctx, relogio, _ = mundo
    ctx["data"].falhas = 3
    w = novo(ctx)
    assert w.cycle()["estado"] == "falha_api"
    assert w.cycle()["estado"] == "falha_api"
    w = novo(ctx)  # o contador sobrevive ao reinício
    assert w.errors == 2
    assert w.cycle()["estado"] == "falha_api" and w.errors == 3
    assert any(Event.TECH_FAILURE.value in m for _, m in w.notifier.sent)
    assert w.cycle()["estado"] == "ok" and w.errors == 0


def test_erro_inesperado_nao_mata_o_agente(mundo):
    ctx, relogio, _ = mundo
    w = novo(ctx)
    chamadas = []
    original = w.cycle

    def ciclo():
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RuntimeError("erro inesperado")
        return original()

    w.cycle = ciclo
    w.run_forever(max_cycles=2, sleep=lambda s: None)
    assert len(chamadas) == 2 and len(w.account.positions_) == 1


def test_modelo_nao_aprovado_so_observa(mundo):
    ctx, *_ = mundo
    w = novo(ctx, status="rejeitado")
    r = w.cycle()
    assert w.wcfg.mode == "observacao" and r["aprovado"] and "ordem" not in r
    assert not w.account.positions_ and ctx["repo"].find("decisions", "default")


def _acionar(path):
    KillSwitch(None, store=SqliteStateStore(path)).engage("telegram", "/pause noutro processo")


def test_kill_switch_partilhado_entre_processos(mundo, tmp_path):
    ctx, *_ = mundo
    p = mp.get_context("spawn").Process(target=_acionar, args=(tmp_path / "state.db",))
    p.start()
    p.join(30)
    assert p.exitcode == 0
    w = novo(ctx)
    r = w.cycle()
    assert not r["aprovado"] and any("kill switch" in m for m in r["decisao"])


def test_stop_do_telegram_fecha_posicoes_e_bloqueia(mundo):
    ctx, relogio, _ = mundo
    w = novo(ctx)
    w.cycle()
    assert w.account.positions_
    cmds = TelegramCommands({42}, default_handlers(ctx["kill"], lambda: "ok", lambda: "c", lambda: "d", store=ctx["store"]))
    assert "Parado" in cmds.handle(42, "/stop")
    relogio.t += timedelta(minutes=5)
    w = novo(ctx)
    w.cycle()
    assert not w.account.positions_ and w.account.trades[-1]["reason"] == "stop_manual"
    relogio.t += timedelta(hours=1)
    r = w.cycle()
    assert not r["aprovado"]


def test_kill_switch_falha_fechada_se_estado_ilegivel():
    class Partido:
        def get(self, k):
            raise ConnectionError("Atlas inacessível")

    assert KillSwitch(None, store=Partido()).is_engaged()


def test_mongo_estado_e_repositorio_com_mongomock():
    mongomock = pytest.importorskip("mongomock")
    db = mongomock.MongoClient()["t"]
    st = MongoStateStore(db)
    assert st.claim("bar:x") and not st.claim("bar:x")
    st.put("kill_switch", {"engaged": True})
    assert KillSwitch(None, store=st).is_engaged()
    repo = MongoRepository(db)
    repo.ensure_indexes()
    assert repo.insert("orders", "t1", {"client_order_id": "a"}, unique_key="client_order_id")
    assert not repo.insert("orders", "t1", {"client_order_id": "a"}, unique_key="client_order_id")
    assert repo.find("orders", "t2") == [] and len(repo.find("orders", "t1")) == 1
    with pytest.raises(ValueError):
        repo.insert("orders", "", {"client_order_id": "b"})
