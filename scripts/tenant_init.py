"""Regista o tenant da operação pessoal (o único ativo nesta fase). Idempotente; não grava credenciais.

Uso: TENANT_ID=pessoal python scripts/tenant_init.py
O dono fica como OWNER, identificado pelo chat do Telegram autorizado. Negociação real e subscrição
ficam desligadas: o modelo de tenant recusa ligá-las nesta fase.
"""

from __future__ import annotations

from trading_agent.config import Secrets, load_config
from trading_agent.persistence.repository import default_repository
from trading_agent.tenants.models import Role, Tenant


def main() -> None:
    sec = Secrets()
    if sec.tenant_id == "default":
        raise SystemExit("Definir TENANT_ID (ex.: pessoal) antes de registar o tenant.")
    owners = {f"telegram:{c}": Role.OWNER for c in sorted(sec.allowed_chat_ids())}
    t = Tenant(sec.tenant_id, "Operação pessoal do dono", load_config().risk, members=owners)
    novo = default_repository().insert("tenants", t.tenant_id, t.to_doc(), unique_key="tenant_id")
    print(f"tenant {t.tenant_id}: {'registado' if novo else 'já existia'} · membros {len(owners)} · "
          f"negociação real {t.live_trading_allowed} · subscrição {t.subscription}")


if __name__ == "__main__":
    main()
