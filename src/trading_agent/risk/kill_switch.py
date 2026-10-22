"""Kill switch independente: bloqueia a abertura de novas operações, já.

Independente do modelo e do motor: basta existir o ficheiro de bloqueio (ou a variável
`TRADING_KILL_SWITCH=1`) para nada novo abrir. Em produção o estado vive também no
MongoDB/Firestore, para o Telegram e a API o acionarem sem acesso ao disco do serviço.
Acionar é sempre permitido; desarmar fica registado.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from trading_agent.config import ROOT

DEFAULT_FILE = ROOT / "data" / "KILL_SWITCH"


class KillSwitch:
    def __init__(self, path: Path | str = DEFAULT_FILE):
        self.path = Path(path)

    def is_engaged(self) -> bool:
        return os.environ.get("TRADING_KILL_SWITCH", "0") == "1" or self.path.exists()

    def engage(self, by: str, reason: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"by": by, "reason": reason, "at": datetime.now(UTC).isoformat()}))

    def release(self, by: str) -> dict:
        info = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.path.unlink(missing_ok=True)
        return {"released_by": by, "at": datetime.now(UTC).isoformat(), "previous": info}
