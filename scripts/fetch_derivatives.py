"""Descarrega os dados da hipótese 2 (funding, prémio, open interest, taker buy) para o período das velas da
Coinbase e grava data/raw/derivados_BTCUSD_1h.parquet com um manifesto de qualidade. Só leitura de APIs públicas.

Uso: python scripts/fetch_derivatives.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import requests

from trading_agent.data.derivatives import fetch_funding, fetch_open_interest, fetch_premium, fetch_taker, hourly_table
from trading_agent.data.store import DATA_DIR, load_candles


def main() -> None:
    hours = load_candles("BTC/USD", "1h", "coinbase").index
    start, end = hours.min(), hours.max() + (hours[1] - hours[0])
    s = requests.Session()
    s.headers["User-Agent"] = "trading-ai-agent/0.3"
    partes = {"funding": fetch_funding(start, end, s), "premio": fetch_premium(start, end, s),
              "taker": fetch_taker(start, end, s), "oi": fetch_open_interest(start, end, s)}
    for k, v in partes.items():
        print(k, len(v), v.index.min(), v.index.max(), flush=True)
    h = hourly_table(partes["funding"], partes["premio"], partes["taker"], partes["oi"], hours)
    path = DATA_DIR / "raw" / "derivados_BTCUSD_1h.parquet"
    h.to_parquet(path)
    falta = {c: round(float(h[c].isna().mean()), 5) for c in h.columns}
    manifest = {"fontes": {"funding": "Binance fapi/v1/fundingRate", "premio": "Binance fapi/v1/premiumIndexKlines",
                           "taker": "Binance api/v3/klines (spot BTCUSDT)", "oi": "Bybit v5/market/open-interest (linear)"},
                "alinhamento": "índice = abertura da vela horária da Coinbase; funding e OI conhecidos até ao fecho",
                "linhas": len(h), "inicio": str(h.index.min()), "fim": str(h.index.max()), "fracao_em_falta": falta,
                "observacoes_por_fonte": {k: len(v) for k, v in partes.items()},
                "recolhido_em": datetime.now(UTC).isoformat(), "sintetico": False}
    path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(json.dumps(manifest["fracao_em_falta"]))


if __name__ == "__main__":
    main()
