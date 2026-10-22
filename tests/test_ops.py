from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from trading_agent.config import load_config
from trading_agent.monitoring.logging_setup import redact
from trading_agent.notifications.telegram import Event, TelegramCommands, TelegramNotifier, default_handlers
from trading_agent.risk.kill_switch import KillSwitch
from trading_agent.tenants.models import Role, Tenant


def test_telegram_seco_sem_token():
    n = TelegramNotifier(token=None, chat_ids={123})
    n.notify(Event.OPENED, "EUR/USD comprado")
    assert n.dry_run and "[SIMULAÇÃO]" in n.sent[0][1] and n.sent[0][1].startswith("[TRADING AI]")


def test_telegram_comandos_so_de_chats_autorizados(tmp_path):
    ks = KillSwitch(tmp_path / "KS")
    cmds = TelegramCommands({42}, default_handlers(ks, lambda: "ok", lambda: "carteira", lambda: "desempenho"))
    assert cmds.handle(7, "/stop") == "Não autorizado." and not ks.is_engaged()
    assert "Pausado" in cmds.handle(42, "/pause") and ks.is_engaged()
    assert "Retomado" in cmds.handle(42, "/resume") and not ks.is_engaged()
    assert "Parado" in cmds.handle(42, "/stop@trading_bot") and ks.is_engaged()
    assert cmds.handle(42, "/status") == "ok"


def test_logs_mascaram_segredos():
    s = redact("url=https://api.telegram.org/bot123456:ABCdefGHIjklMNOpqrSTUvwx/send e mongodb+srv://u:p@c.mongodb.net/db Bearer abcdefghijklmnop")
    assert "ABCdef" not in s and "u:p@" not in s and "abcdefghijk" not in s


def test_tenant_isolado_e_sem_negociacao_real():
    t = Tenant("t1", "Escritório A", load_config().risk, members={"u1": Role.OWNER, "u2": Role.VIEWER})
    assert t.can("u1", "pause") and not t.can("u2", "pause") and not t.can("u3", "read")
    with pytest.raises(PermissionError):
        t.enable_live_trading()


def test_api_status_e_killswitch_exige_token(monkeypatch, tmp_path):
    import apps.api.main as api
    from trading_agent.persistence.state import SqliteStateStore

    st = SqliteStateStore(tmp_path / "state.db")
    monkeypatch.setattr(api, "_store", st)
    monkeypatch.setattr(api, "_kill", KillSwitch(None, store=st))
    c = TestClient(api.app)
    st = c.get("/status").json()
    assert st["modo"] == "simulação" and st["negociacao_real"] is False
    assert c.post("/killswitch/engage").status_code == 401
    assert c.post("/killswitch/engage", headers={"Authorization": "Bearer errado"}).status_code == 401
    from pydantic import SecretStr

    monkeypatch.setattr(api._secrets, "api_admin_token", SecretStr("token-de-teste-123"))
    assert c.post("/killswitch/engage", headers={"Authorization": "Bearer token-de-teste-123"}).status_code == 200
    # o worker, noutro processo, lê o mesmo estado
    assert KillSwitch(None, store=SqliteStateStore(tmp_path / "state.db")).is_engaged()
    assert c.get("/status").json()["kill_switch"] is True


def _bot(handler):
    import httpx

    from trading_agent.notifications.telegram import TelegramBot

    cmds = TelegramCommands({42}, {"/status": lambda: "ok"})
    return TelegramBot("t", cmds, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_bot_nao_arranca_com_webhook_de_outra_aplicacao():
    import httpx

    from trading_agent.notifications.telegram import BotConflict

    apagados = []

    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/deleteWebhook"):
            apagados.append(1)
            return httpx.Response(200, json={"ok": True, "result": True})
        return httpx.Response(200, json={"ok": True, "result": {"url": "https://outra.app/webhook"}})

    with pytest.raises(BotConflict):
        _bot(h).check_exclusive()
    assert not apagados
    _bot(h).check_exclusive(delete_webhook=True)   # só por decisão explícita
    assert apagados


def test_bot_sai_quando_outra_instancia_le_o_mesmo_bot():
    import httpx

    from trading_agent.notifications.telegram import BotConflict

    def h(req):
        return httpx.Response(409, json={"ok": False, "description": "Conflict: terminated by other getUpdates request"})

    with pytest.raises(BotConflict):
        _bot(h).poll_once()


def test_bot_responde_com_marca_trading_ai():
    import json

    import httpx

    enviados = []

    def h(req):
        if req.url.path.endswith("/getUpdates"):
            return httpx.Response(200, json={"ok": True, "result": [
                {"update_id": 1, "message": {"chat": {"id": 42}, "text": "/status"}}]})
        enviados.append(json.loads(req.content))
        return httpx.Response(200, json={"ok": True})

    assert _bot(h).poll_once() == 1
    assert enviados[0]["text"].startswith("[TRADING AI]") and enviados[0]["text"].endswith("ok")


def test_tenant_pessoal_guardavel_sem_credenciais():
    from trading_agent.tenants.models import BrokerAccountRef

    t = Tenant("pessoal", "Dono", load_config().risk, members={"telegram:42": Role.OWNER},
               brokers=[BrokerAccountRef("oanda", "practice", "tenants/pessoal/oanda-token")])
    d = t.to_doc()
    assert d["live_trading_allowed"] is False and d["subscription"] == "nenhuma"
    assert d["members"] == {"telegram:42": "owner"} and d["brokers"][0]["secret_name"].startswith("tenants/")


def test_comandos_do_telegram_respeitam_o_tenant(tmp_path):
    from trading_agent.persistence.state import SqliteStateStore

    st = SqliteStateStore(tmp_path / "s.db")
    ks = KillSwitch(None, store=st)
    cmds = TelegramCommands({42}, default_handlers(ks, lambda: "", lambda: "", lambda: "", store=st, tenant_id="pessoal"))
    cmds.handle(42, "/stop")
    assert st.get("command:pessoal:close_all")["done"] is False and st.get("command:default:close_all") is None


def test_observacao_compara_com_o_movimento_seguinte():
    import pandas as pd

    from trading_agent.monitoring.observation import avaliar

    idx = pd.date_range("2026-10-01", periods=6, freq="4h", tz="UTC")
    precos = pd.Series([100, 101, 102, 101, 100, 99], index=idx, dtype=float)
    dec = [{"bar_time": idx[0].isoformat(), "proposta": {"side": 1, "prob": 0.6}, "custo_bps": 50, "aprovado": False,
            "motivos": ["expectativa abaixo do mínimo (3.0 bps)"]},
           {"bar_time": idx[2].isoformat(), "proposta": {"side": -1, "prob": 0.7}, "custo_bps": 50, "aprovado": True},
           {"bar_time": idx[5].isoformat(), "proposta": {"side": 1, "prob": 0.5}, "custo_bps": 50},   # horizonte por decorrer
           {"bar_time": idx[1].isoformat(), "proposta": {"side": 0}}]
    r = avaliar(dec, precos, pd.Timedelta(hours=4), horizon=1).resumo()
    assert (r["decisoes"], r["sinais"], r["avaliados"], r["aprovados"]) == (4, 3, 2, 1)
    assert r["taxa_acerto"] == 1.0 and round(r["ret_bruto_medio_bps"], 1) == round((100 + 98.04) / 2, 1)
    assert r["ret_liquido_medio_bps"] < r["ret_bruto_medio_bps"]
    assert r["motivos_veto"] == {"expectativa abaixo do mínimo (# bps)": 1}


def test_notificacao_escapa_html():
    n = TelegramNotifier(token=None, chat_ids={1})
    n.notify(Event.SIGNAL_REJECTED, "probabilidade 0.177 < 0.4 & custo > 1")
    assert "0.177 &lt; 0.4 &amp; custo &gt; 1" in n.sent[0][1] and "<b>" in n.sent[0][1]
