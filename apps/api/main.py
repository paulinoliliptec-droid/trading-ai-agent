"""API (FastAPI): estado, desempenho dos relatórios, kill switch e painel.

Correr: uvicorn apps.api.main:app --port 8080
As rotas que mudam estado exigem `Authorization: Bearer <API_ADMIN_TOKEN>`.
"""

from __future__ import annotations

import hmac
import json
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

from trading_agent.config import ROOT, Secrets, load_config
from trading_agent.notifications.telegram import account_views
from trading_agent.persistence.repository import default_repository
from trading_agent.persistence.state import default_store
from trading_agent.risk.kill_switch import KillSwitch

app = FastAPI(title="Trading AI Agent", version="0.2.0", description="Só simulação. Nenhuma ordem real.")
_secrets = Secrets()
_store = default_store()            # o MESMO estado do worker e do bot do Telegram
_kill = KillSwitch(store=_store)


def admin(authorization: str = Header(default="")) -> None:
    token = _secrets.api_admin_token.get_secret_value() if _secrets.api_admin_token else ""
    given = authorization.removeprefix("Bearer ").strip()
    if not token or not hmac.compare_digest(token, given):
        raise HTTPException(status_code=401, detail="não autorizado")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/status")
def status() -> dict:
    cfg = load_config()
    contas = {k.split(":")[-1]: {kk: (v or {}).get(kk) for kk in ("currency", "cash", "peak_equity", "last_equity")}
              | {"posicoes": len((v or {}).get("positions", {})), "operacoes": len((v or {}).get("trades", []))}
              for k in _store.keys(f"account:{_secrets.tenant_id}:") for v in [_store.get(k)]}
    return {"modo": "simulação", "negociacao_real": cfg.live_trading_enabled, "kill_switch": _kill.is_engaged(),
            "mercados": list(cfg.raw["markets"].keys()), "contas": contas}


@app.get("/decisions")
def decisions(limit: int = 50) -> list[dict]:
    return default_repository().find("decisions", _secrets.tenant_id, limit=min(limit, 500))


@app.get("/portfolio")
def portfolio() -> dict:
    return {"texto": account_views(_store, _secrets.tenant_id)["portfolio"]()}


@app.get("/performance")
def performance() -> dict:
    out = {}
    for p in sorted((ROOT / "reports" / "fase2").glob("resumo_*.json")):
        d = json.loads(p.read_text())
        out[d["simbolo"]] = {k: d.get(k) for k in ("gerado_em", "criterio_selecao", "nenhum_qualificado", "escolhido",
                                                    "melhor_no_desenvolvimento", "simulacao_100_eur_risco_de_producao")}
    return out


@app.post("/killswitch/engage", dependencies=[Depends(admin)])
def engage() -> dict:
    _kill.engage("api", "pedido na API")
    return {"kill_switch": True}


@app.post("/killswitch/release", dependencies=[Depends(admin)])
def release() -> dict:
    return _kill.release("api")


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parents[1] / "dashboard" / "index.html")
