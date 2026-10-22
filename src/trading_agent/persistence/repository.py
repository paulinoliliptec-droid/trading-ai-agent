"""Registos operacionais: decisões, ordens, operações, posições, equity, risco, eventos, modelos.

Mesmo contrato em duas implementações:
  · `MongoRepository` (MongoDB Atlas), para a operação contínua na cloud;
  · `SqliteRepository` (local), para desenvolvimento e quando o Atlas não está configurado.
Todos os documentos levam `tenant_id` (isolamento) e `ts` em UTC. As coleções e os índices
estão declarados aqui (`COLLECTIONS`) e são criados por `ensure_indexes()`.
"""

from __future__ import annotations

import abc
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

COLLECTIONS: dict[str, list[tuple[list[tuple[str, int]], dict]]] = {
    # coleção: [(campos do índice, opções)]
    "decisions": [([("tenant_id", 1), ("symbol", 1), ("bar_time", -1)], {}),
                  ([("tenant_id", 1), ("decision_id", 1)], {"unique": True})],
    "orders": [([("tenant_id", 1), ("client_order_id", 1)], {"unique": True}), ([("tenant_id", 1), ("ts", -1)], {})],
    "trades": [([("tenant_id", 1), ("symbol", 1), ("exit_time", -1)], {})],
    "positions": [([("tenant_id", 1), ("symbol", 1), ("ts", -1)], {})],
    "equity": [([("tenant_id", 1), ("ts", -1)], {})],
    "risk_events": [([("tenant_id", 1), ("ts", -1)], {}), ([("tenant_id", 1), ("kind", 1), ("ts", -1)], {})],
    "events": [([("tenant_id", 1), ("ts", -1)], {}), ([("tenant_id", 1), ("level", 1), ("ts", -1)], {})],
    "model_versions": [([("tenant_id", 1), ("model_id", 1)], {"unique": True}), ([("tenant_id", 1), ("symbol", 1), ("created_at", -1)], {})],
}


def _now() -> datetime:
    return datetime.now(UTC)


def _clean(doc: dict) -> dict:
    """Converte para tipos que o MongoDB/JSON aceitam (datas em ISO, numpy em float)."""
    return json.loads(json.dumps(doc, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else float(o)))


class Repository(abc.ABC):
    @abc.abstractmethod
    def insert(self, collection: str, tenant_id: str, doc: dict, unique_key: str | None = None) -> bool:
        """Insere. Com `unique_key`, um documento com o mesmo valor já existente é ignorado (False)."""

    @abc.abstractmethod
    def find(self, collection: str, tenant_id: str, query: dict | None = None, limit: int = 100,
             newest_first: bool = True) -> list[dict]: ...

    def ensure_indexes(self) -> None:  # noqa: B027 - opcional para implementações sem índices
        pass


def _check(collection: str, tenant_id: str) -> None:
    if collection not in COLLECTIONS:
        raise ValueError(f"coleção desconhecida: {collection}")
    if not tenant_id:
        raise ValueError("tenant_id é obrigatório em todos os registos")


class MongoRepository(Repository):
    def __init__(self, db):
        self.db = db

    @classmethod
    def from_uri(cls, uri: str, database: str = "trading_agent") -> MongoRepository:
        from pymongo import MongoClient  # import tardio: o MongoDB é opcional em desenvolvimento

        return cls(MongoClient(uri, appname="trading-ai-agent", serverSelectionTimeoutMS=5000)[database])

    def ensure_indexes(self) -> None:
        for name, idxs in COLLECTIONS.items():
            for keys, opts in idxs:
                self.db[name].create_index(keys, **opts)

    def insert(self, collection: str, tenant_id: str, doc: dict, unique_key: str | None = None) -> bool:
        from pymongo.errors import DuplicateKeyError

        _check(collection, tenant_id)
        d = {**_clean(doc), "tenant_id": tenant_id, "ts": doc.get("ts") or _now().isoformat()}
        if unique_key and self.db[collection].find_one({"tenant_id": tenant_id, unique_key: d[unique_key]}):
            return False
        try:
            self.db[collection].insert_one(d)
        except DuplicateKeyError:
            return False
        return True

    def find(self, collection: str, tenant_id: str, query: dict | None = None, limit: int = 100,
             newest_first: bool = True) -> list[dict]:
        _check(collection, tenant_id)
        cur = self.db[collection].find({**(query or {}), "tenant_id": tenant_id}, {"_id": 0})
        return list(cur.sort("ts", -1 if newest_first else 1).limit(limit))


class SqliteRepository(Repository):
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("CREATE TABLE IF NOT EXISTS docs (id INTEGER PRIMARY KEY, collection TEXT, tenant_id TEXT, "
                      "ts TEXT, ukey TEXT, doc TEXT)")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS u ON docs(collection, tenant_id, ukey) WHERE ukey IS NOT NULL")
            c.execute("CREATE INDEX IF NOT EXISTS t ON docs(collection, tenant_id, ts)")

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.execute("PRAGMA busy_timeout=30000")
        return c

    def insert(self, collection: str, tenant_id: str, doc: dict, unique_key: str | None = None) -> bool:
        _check(collection, tenant_id)
        d = {**_clean(doc), "tenant_id": tenant_id}
        d["ts"] = d.get("ts") or _now().isoformat()
        uk = f"{unique_key}={d[unique_key]}" if unique_key else None
        with self._lock, self._conn() as c:
            cur = c.execute("INSERT OR IGNORE INTO docs(collection,tenant_id,ts,ukey,doc) VALUES(?,?,?,?,?)",
                            (collection, tenant_id, d["ts"], uk, json.dumps(d)))
            return cur.rowcount == 1

    def find(self, collection: str, tenant_id: str, query: dict | None = None, limit: int = 100,
             newest_first: bool = True) -> list[dict]:
        _check(collection, tenant_id)
        with self._lock, self._conn() as c:
            rows = c.execute(f"SELECT doc FROM docs WHERE collection=? AND tenant_id=? ORDER BY ts {'DESC' if newest_first else 'ASC'}, id "
                             f"{'DESC' if newest_first else 'ASC'}", (collection, tenant_id)).fetchall()
        out = []
        for (raw,) in rows:
            d = json.loads(raw)
            if all(d.get(k) == v for k, v in (query or {}).items()):
                out.append(d)
                if len(out) >= limit:
                    break
        return out


def default_repository() -> Repository:
    """MongoDB Atlas se houver `MONGODB_URI`; senão SQLite local em data/operacao.db."""
    from trading_agent.config import ROOT, Secrets

    s = Secrets()
    if s.mongodb_uri:
        repo = MongoRepository.from_uri(s.mongodb_uri.get_secret_value())
        repo.ensure_indexes()
        return repo
    return SqliteRepository(ROOT / "data" / "operacao.db")
