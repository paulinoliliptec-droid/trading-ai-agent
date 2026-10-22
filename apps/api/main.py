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
from trading_agent.risk.kill_switch import KillSwitch

app = FastAPI(title="Trading AI Agent", version="0.1.0", description="Só simulação. Nenhuma ordem real.")
_secrets = Secrets()
_kill = KillSwitch()


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
    return {"modo": "simulação", "negociacao_real": cfg.live_trading_enabled, "kill_switch": _kill.is_engaged(),
            "mercados": list(cfg.raw["markets"].keys())}


@app.get("/performance")
def performance() -> dict:
    reps = sorted((ROOT / "reports").glob("*.json"))
    out = {}
    for p in reps:
        d = json.loads(p.read_text())
        out[d["par"]] = {"gerado_em": d["gerado_em"], "periodo_teste": d["periodo_teste"], "resultados": d["resultados"]}
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
