"""Uma experiência isolada (atalho para a pipeline da fase 2).

Uso: python scripts/run_research.py --symbol "BTC/USD" --source coinbase [--timeframe 1h] [--horizonte 24]
     [--tp 2] [--sl 1] [--features v2] [--sem-gru]
Para a grelha completa e a seleção pré-registada: scripts/run_experiments.py.
Para um ciclo de paper trading ao vivo (substitui o antigo paper_trade_once.py):
     python scripts/run_agent.py --symbol "BTC/USD" --ciclos 1
"""

from __future__ import annotations

import argparse
import json

from trading_agent.config import ROOT, load_config
from trading_agent.research.pipeline import ExperimentSpec, run_experiment


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC/USD")
    ap.add_argument("--source", default="coinbase")
    ap.add_argument("--timeframe", default="1h", choices=["15m", "1h", "4h", "1d"])
    ap.add_argument("--horizonte", type=int, default=24)
    ap.add_argument("--tp", type=float, default=2.0)
    ap.add_argument("--sl", type=float, default=1.0)
    ap.add_argument("--features", default="v2", choices=["v1", "v2"])
    ap.add_argument("--sem-gru", action="store_true")
    args = ap.parse_args()
    spec = ExperimentSpec(args.symbol, args.source, args.timeframe, args.horizonte, args.tp, args.sl, args.features)
    rep, _ = run_experiment(spec, load_config(), ("A", "B") if args.sem_gru else ("A", "B", "C", "D"))
    out = ROOT / "reports" / "fase2" / f"{spec.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str))
    for k, v in rep["modelos"].items():
        d = v.get("desenvolvimento", {})
        print(k, {x: d.get(x) for x in ("operacoes", "expectativa_bruta_bps", "custo_medio_bps", "expectativa_bps_por_operacao")})
    print("relatório:", out)


if __name__ == "__main__":
    main()
