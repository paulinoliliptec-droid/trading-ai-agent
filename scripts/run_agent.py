"""Agente autónomo de paper trading (serviço persistente).

Uso: python scripts/run_agent.py --symbol "BTC/USD" [--model-id ID] [--modo paper|observacao] [--intervalo 60]

Carrega o modelo versionado mais recente do símbolo (aprovado, se houver; senão o mais recente,
que corre em OBSERVAÇÃO). Nunca treina. Estado em MongoDB Atlas se houver `MONGODB_URI`, senão
em data/state.db e data/operacao.db. Telegram em modo seco sem `TELEGRAM_BOT_TOKEN`.
"""

from __future__ import annotations

import argparse
import logging

from trading_agent.agent.worker import AgentWorker, WorkerConfig
from trading_agent.brokers.crypto.coinbase import CoinbaseMarketData
from trading_agent.brokers.crypto.kraken import KrakenMarketData
from trading_agent.config import Secrets, load_config
from trading_agent.models.registry import ModelRegistry
from trading_agent.monitoring.logging_setup import setup_logging
from trading_agent.notifications.telegram import TelegramNotifier
from trading_agent.persistence.repository import default_repository
from trading_agent.persistence.state import default_store
from trading_agent.risk.kill_switch import KillSwitch

log = logging.getLogger("agente")


def data_source(symbol: str, sec: Secrets):
    if symbol == "BTC/USD":
        return CoinbaseMarketData()  # a mesma fonte do treino
    if symbol == "EUR/USD":
        if not sec.oanda_api_token:
            raise SystemExit("EUR/USD ao vivo exige OANDA Practice (OANDA_API_TOKEN). A Dukascopy não serve preço em "
                             "tempo real e a Kraken EUR/USD é outro mercado: não se misturam fontes sem reconciliação.")
        from trading_agent.brokers.forex.oanda import OandaMarketData

        return OandaMarketData(sec.oanda_api_token.get_secret_value(), sec.oanda_account_id, sec.oanda_environment)
    raise SystemExit(f"sem fonte ao vivo para {symbol}")


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC/USD")
    ap.add_argument("--model-id")
    ap.add_argument("--modo", choices=["paper", "observacao"], default="observacao")
    ap.add_argument("--intervalo", type=float, default=60.0)
    ap.add_argument("--ciclos", type=int, default=None, help="número de ciclos (por omissão, contínuo)")
    args = ap.parse_args()
    if "/" not in args.symbol:  # «BTCUSD» (nomes de serviços systemd) → «BTC/USD»
        args.symbol = f"{args.symbol[:3]}/{args.symbol[3:]}"
    cfg, sec = load_config(), Secrets()
    reg = ModelRegistry()
    model_id = args.model_id or reg.latest(args.symbol, "aprovado") or reg.latest(args.symbol)
    if not model_id:
        raise SystemExit(f"Não há modelo treinado para {args.symbol}: correr scripts/train_model.py primeiro.")
    policy, meta = reg.load(model_id)
    store, repo = default_store(), default_repository()
    repo.insert("model_versions", sec.tenant_id, {k: meta[k] for k in ("model_id", "symbol", "timeframe", "status", "created_at", "sha256")},
                unique_key="model_id")
    fx = None
    if cfg.account["currency"] != cfg.instrument(args.symbol).quote_currency:
        kr = KrakenMarketData()
        fx = lambda: kr.quote("EUR/USD").mid  # noqa: E731 - taxa de conversão da conta (não é o mercado negociado)
    worker = AgentWorker(cfg, policy, meta, data_source(args.symbol, sec), store, repo, KillSwitch(store=store),
                         TelegramNotifier(sec.telegram_bot_token.get_secret_value() if sec.telegram_bot_token else None,
                                          sec.allowed_chat_ids() or {0}),
                         WorkerConfig(tenant_id=sec.tenant_id, mode=args.modo, interval_s=args.intervalo), fx_source=fx)
    worker.run_forever(max_cycles=args.ciclos)


if __name__ == "__main__":
    main()
