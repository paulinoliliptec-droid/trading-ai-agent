"""Armazenamento: séries temporais em Parquet (local ou gs://), operação em MongoDB (opcional).

Decisão (ver docs/adr/0002-armazenamento.md): candles, features e datasets de treino vão para
Parquet (barato, colunar, lido inteiro pelo treino). Sinais, ordens, operações, auditoria e
configuração por tenant vão para o MongoDB Atlas (documentos pequenos, consultas por tenant).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from trading_agent.config import ROOT

DATA_DIR = ROOT / "data"


def dataset_path(symbol: str, timeframe: str, source: str) -> Path:
    return DATA_DIR / "raw" / f"{source}_{symbol.replace('/', '')}_{timeframe}.parquet"


def save_candles(df: pd.DataFrame, symbol: str, timeframe: str, source: str, quality: dict | None = None) -> Path:
    path = dataset_path(symbol, timeframe, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    manifest = {
        "symbol": symbol, "timeframe": timeframe, "source": source, "rows": len(df),
        "start": str(df.index.min()), "end": str(df.index.max()),
        "collected_at": datetime.now(UTC).isoformat(), "quality": quality or {},
        "synthetic": False,
    }
    path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return path


def load_candles(symbol: str, timeframe: str, source: str) -> pd.DataFrame:
    return pd.read_parquet(dataset_path(symbol, timeframe, source))


class MongoRepository:
    """Registos operacionais por tenant. Todas as escritas levam `tenant_id` (isolamento)."""

    def __init__(self, uri: str, database: str = "trading_agent"):
        from pymongo import MongoClient  # import tardio: o MongoDB é opcional em desenvolvimento

        self.db = MongoClient(uri, appname="trading-ai-agent", serverSelectionTimeoutMS=5000)[database]

    def insert(self, collection: str, tenant_id: str, doc: dict) -> str:
        if not tenant_id:
            raise ValueError("tenant_id é obrigatório em todos os registos")
        res = self.db[collection].insert_one({**doc, "tenant_id": tenant_id, "created_at": datetime.now(UTC)})
        return str(res.inserted_id)

    def find(self, collection: str, tenant_id: str, query: dict | None = None, limit: int = 100) -> list[dict]:
        return list(self.db[collection].find({**(query or {}), "tenant_id": tenant_id}, limit=limit))
