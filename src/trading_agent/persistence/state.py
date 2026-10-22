"""Estado partilhado entre processos: kill switch, conta virtual e idempotência.

Duas implementações com o mesmo contrato:
  · `SqliteStateStore`: local, segura entre vários processos da mesma máquina (WAL e
    transações), para desenvolvimento e para uma VM única;
  · `MongoStateStore`: MongoDB Atlas, partilhada entre serviços separados (worker, API,
    bot do Telegram) em máquinas diferentes.

`claim(chave)` é atómico: só o primeiro a reclamar uma chave recebe True. É assim que um
reinício não volta a processar a mesma vela nem a submeter a mesma ordem.
"""

from __future__ import annotations

import abc
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat()


class StateStore(abc.ABC):
    @abc.abstractmethod
    def get(self, key: str) -> dict | None: ...

    @abc.abstractmethod
    def put(self, key: str, value: dict) -> None: ...

    @abc.abstractmethod
    def delete(self, key: str) -> None: ...

    @abc.abstractmethod
    def claim(self, key: str, info: dict | None = None) -> bool:
        """Insere a chave se ainda não existir. True só para quem a criou."""

    @abc.abstractmethod
    def keys(self, prefix: str) -> list[str]: ...


class SqliteStateStore(StateStore):
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.execute("PRAGMA busy_timeout=30000")
        return c

    def get(self, key: str) -> dict | None:
        with self._lock, self._conn() as c:
            row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, value: dict) -> None:
        data = json.dumps(value, default=str)
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO kv(key,value,updated_at) VALUES(?,?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                      (key, data, _now()))

    def delete(self, key: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM kv WHERE key=?", (key,))

    def claim(self, key: str, info: dict | None = None) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute("INSERT OR IGNORE INTO kv(key,value,updated_at) VALUES(?,?,?)",
                            (key, json.dumps(info or {}, default=str), _now()))
            return cur.rowcount == 1

    def keys(self, prefix: str) -> list[str]:
        with self._lock, self._conn() as c:
            rows = c.execute("SELECT key FROM kv WHERE key LIKE ? ORDER BY key", (prefix.replace("%", r"\%") + "%",)).fetchall()
        return [r[0] for r in rows]


class MongoStateStore(StateStore):
    """Coleção `state` com `_id` = chave. `claim` usa a unicidade do `_id`."""

    def __init__(self, db, collection: str = "state"):
        self.col = db[collection]

    @classmethod
    def from_uri(cls, uri: str, database: str = "trading_agent") -> MongoStateStore:
        from pymongo import MongoClient

        return cls(MongoClient(uri, appname="trading-ai-agent", serverSelectionTimeoutMS=5000)[database])

    def get(self, key: str) -> dict | None:
        d = self.col.find_one({"_id": key})
        return d["value"] if d else None

    def put(self, key: str, value: dict) -> None:
        self.col.replace_one({"_id": key}, {"_id": key, "value": json.loads(json.dumps(value, default=str)),
                                             "updated_at": _now()}, upsert=True)

    def delete(self, key: str) -> None:
        self.col.delete_one({"_id": key})

    def claim(self, key: str, info: dict | None = None) -> bool:
        from pymongo.errors import DuplicateKeyError

        try:
            self.col.insert_one({"_id": key, "value": json.loads(json.dumps(info or {}, default=str)), "updated_at": _now()})
            return True
        except DuplicateKeyError:
            return False

    def keys(self, prefix: str) -> list[str]:
        import re

        return [d["_id"] for d in self.col.find({"_id": {"$regex": "^" + re.escape(prefix)}}, {"_id": 1}).sort("_id", 1)]


def default_store() -> StateStore:
    """MongoDB se houver `MONGODB_URI`; senão SQLite local em data/state.db."""
    from trading_agent.config import ROOT, Secrets

    s = Secrets()
    if s.mongodb_uri:
        return MongoStateStore.from_uri(s.mongodb_uri.get_secret_value())
    return SqliteStateStore(ROOT / "data" / "state.db")
