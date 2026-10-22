"""Interface abstracta das corretoras.

O motor só fala com `MarketDataSource` (dados) e `ExecutionVenue` (ordens). Trocar ou somar
uma plataforma (OANDA, Kraken, Coinbase, outra) é escrever um adaptador novo, sem tocar no
motor, nos modelos nem no risco.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    timestamp: datetime  # sempre UTC
    source: str

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread_bps(self) -> float:
        return (self.ask - self.bid) / self.mid * 1e4


@dataclass
class Order:
    symbol: str
    side: Side
    quantity: float
    client_order_id: str
    stop_loss: float | None = None
    take_profit: float | None = None
    tenant_id: str = "default"
    status: OrderStatus = OrderStatus.NEW
    reason: str = ""
    filled_qty: float = 0.0
    max_bars: int | None = None          # encerramento por limite temporal (em velas)
    expires_at: datetime | None = None   # encerramento por limite temporal (relógio)
    intent: str = "open"                 # «open» abre posição; «close» reduz/fecha
    sl_distance: float | None = None     # stop a esta distância do preço de EXECUÇÃO (quando o preço ainda não se sabe)
    tp_distance: float | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class Fill:
    client_order_id: str
    symbol: str
    side: Side
    quantity: float
    price: float
    fee: float
    timestamp: datetime


@dataclass
class Position:
    symbol: str
    quantity: float  # positivo = comprado, negativo = vendido
    avg_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: datetime | None = None
    meta: dict = field(default_factory=dict)


class LiveTradingDisabled(RuntimeError):
    """Levantada por qualquer tentativa de ordem real. Nesta fase só existe simulação."""


class MarketDataSource(abc.ABC):
    """Fonte de dados de mercado. Devolve candles OHLCV com índice UTC."""

    name: str

    @abc.abstractmethod
    def historical(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        """DataFrame com colunas OHLCV (e, quando a fonte tem, `spread`), índice DatetimeIndex UTC."""

    @abc.abstractmethod
    def quote(self, symbol: str) -> Quote:
        """Preço atual (bid/ask)."""


class ExecutionVenue(abc.ABC):
    """Onde as ordens são executadas. Nesta fase, só implementações simuladas."""

    is_simulated: bool = True

    @abc.abstractmethod
    def submit(self, order: Order, quote: Quote) -> Fill | None: ...

    @abc.abstractmethod
    def positions(self) -> dict[str, Position]: ...


def ensure_simulated(venue: ExecutionVenue) -> None:
    """Guarda única contra ordens reais: qualquer venue não simulado é recusado."""
    if not getattr(venue, "is_simulated", False):
        raise LiveTradingDisabled("Só é permitida execução simulada nesta fase do projeto.")
