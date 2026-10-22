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
    assert n.dry_run and "[SIMULAÇÃO]" in n.sent[0][1]


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
