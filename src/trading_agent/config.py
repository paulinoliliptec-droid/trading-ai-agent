"""Configuração central.

Os segredos (tokens de corretoras, Telegram, MongoDB) vêm SEMPRE de variáveis de ambiente
ou do Secret Manager, nunca de ficheiros no repositório. O comércio real está desligado por
construção: `live_trading_enabled` não é lido do ambiente nesta fase e é sempre False.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "default.toml"


class Secrets(BaseSettings):
    """Credenciais lidas do ambiente (`.env` local ou Secret Manager na GCP)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    oanda_api_token: SecretStr | None = None
    oanda_account_id: str | None = None
    oanda_environment: str = "practice"
    telegram_bot_token: SecretStr | None = None
    telegram_allowed_chat_ids: str = ""  # lista separada por vírgulas
    mongodb_uri: SecretStr | None = None
    api_admin_token: SecretStr | None = None

    def allowed_chat_ids(self) -> set[int]:
        return {int(x) for x in self.telegram_allowed_chat_ids.split(",") if x.strip().lstrip("-").isdigit()}


@dataclass(frozen=True)
class RiskLimits:
    max_spread_bps: float
    max_atr_pct: float
    max_exposure_per_asset_pct: float
    max_open_positions: int
    max_loss_per_trade_pct: float
    max_daily_loss_pct: float
    max_drawdown_pct: float
    min_probability: float
    min_expected_edge_bps: float


@dataclass(frozen=True)
class AppConfig:
    raw: dict = field(repr=False)
    risk: RiskLimits = None  # type: ignore[assignment]

    # Fase atual: só simulação. Não há caminho de configuração que ligue ordens reais.
    live_trading_enabled: bool = False

    def market(self, symbol: str) -> dict:
        return self.raw["markets"][symbol]


def load_config(path: Path | str = DEFAULT_CONFIG) -> AppConfig:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return AppConfig(raw=raw, risk=RiskLimits(**raw["risk"]))
