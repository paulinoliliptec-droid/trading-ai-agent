"""Cria as coleções e os índices no MongoDB Atlas (precisa de MONGODB_URI). Não grava dados."""

from __future__ import annotations

from trading_agent.config import Secrets
from trading_agent.persistence.repository import COLLECTIONS, MongoRepository


def main() -> None:
    s = Secrets()
    if not s.mongodb_uri:
        raise SystemExit("Falta MONGODB_URI (ver docs/mongodb.md). Nada foi feito.")
    repo = MongoRepository.from_uri(s.mongodb_uri.get_secret_value())
    repo.ensure_indexes()
    print("índices criados:", {k: len(v) for k, v in COLLECTIONS.items()})


if __name__ == "__main__":
    main()
