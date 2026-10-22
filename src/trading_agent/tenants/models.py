"""Modelo de tenant para a futura evolução SaaS (ver SAAS_ARCHITECTURE.md).

Cada tenant tem identidade, risco, conta de corretora e credenciais PRÓPRIAS. As credenciais
nunca ficam no registo do tenant: guarda-se só o NOME do segredo no Secret Manager. Nada
disto ativa negociação para terceiros: há um interruptor por tenant que nasce desligado e
que o código desta fase recusa ligar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from trading_agent.config import RiskLimits


class Role(StrEnum):
    OWNER = "owner"
    ANALYST = "analyst"
    VIEWER = "viewer"


PERMISSIONS = {
    Role.OWNER: {"read", "configure_risk", "pause", "resume", "manage_users"},
    Role.ANALYST: {"read", "pause"},
    Role.VIEWER: {"read"},
}


@dataclass
class BrokerAccountRef:
    broker: str                 # «oanda», «kraken», …
    environment: str            # «practice» nesta fase
    secret_name: str            # nome no Secret Manager, ex.: tenants/{id}/oanda-token


@dataclass
class Tenant:
    tenant_id: str
    name: str
    risk: RiskLimits
    brokers: list[BrokerAccountRef] = field(default_factory=list)
    members: dict[str, Role] = field(default_factory=dict)   # uid → papel
    live_trading_allowed: bool = False                       # exige validação jurídica/regulatória

    def can(self, uid: str, action: str) -> bool:
        role = self.members.get(uid)
        return role is not None and action in PERMISSIONS[role]

    def enable_live_trading(self) -> None:
        raise PermissionError("Negociação real para tenants exige validação jurídica e regulatória (CMVM, BdP, MiCA).")
