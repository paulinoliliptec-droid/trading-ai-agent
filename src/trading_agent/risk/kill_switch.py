"""Kill switch independente: bloqueia a abertura de novas operações, já.

Independente do modelo e do motor de decisão. Três fontes, basta UMA para bloquear:
  · a variável `TRADING_KILL_SWITCH=1`;
  · o estado partilhado (`StateStore`: SQLite entre processos locais, MongoDB entre serviços),
    que o worker, a API e o Telegram leem e escrevem;
  · um ficheiro de bloqueio (compatibilidade e acionamento manual no servidor).
Falha fechada: se o estado partilhado não puder ser lido, considera-se ACIONADO.
Acionar é sempre permitido; desarmar fica registado com o estado anterior.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from trading_agent.config import ROOT
from trading_agent.persistence.state import StateStore

DEFAULT_FILE = ROOT / "data" / "KILL_SWITCH"
KEY = "kill_switch"
log = logging.getLogger(__name__)


class KillSwitch:
    def __init__(self, path: Path | str | None = DEFAULT_FILE, store: StateStore | None = None):
        self.path = Path(path) if path is not None else None
        self.store = store

    def is_engaged(self) -> bool:
        if os.environ.get("TRADING_KILL_SWITCH", "0") == "1":
            return True
        if self.path is not None and self.path.exists():
            return True
        if self.store is not None:
            try:
                st = self.store.get(KEY)
            except Exception as e:  # noqa: BLE001 - sem leitura do estado, não se abre nada
                log.error("kill switch ilegível (%s): considerado acionado", type(e).__name__)
                return True
            return bool(st and st.get("engaged"))
        return False

    def status(self) -> dict:
        st = None
        if self.store is not None:
            try:
                st = self.store.get(KEY)
            except Exception:  # noqa: BLE001
                st = {"erro": "estado ilegível"}
        return {"engaged": self.is_engaged(), "env": os.environ.get("TRADING_KILL_SWITCH", "0") == "1",
                "file": bool(self.path and self.path.exists()), "store": st}

    def engage(self, by: str, reason: str) -> None:
        info = {"engaged": True, "by": by, "reason": reason, "at": datetime.now(UTC).isoformat()}
        if self.store is not None:
            self.store.put(KEY, info)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(info))

    def release(self, by: str) -> dict:
        previous: dict = {}
        if self.store is not None:
            previous = self.store.get(KEY) or {}
            self.store.put(KEY, {"engaged": False, "released_by": by, "at": datetime.now(UTC).isoformat(), "previous": previous})
        if self.path is not None:
            if self.path.exists():
                previous = previous or json.loads(self.path.read_text() or "{}")
            self.path.unlink(missing_ok=True)
        return {"released_by": by, "at": datetime.now(UTC).isoformat(), "previous": previous}
