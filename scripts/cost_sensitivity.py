"""Diagnóstico (NÃO seleção): o XGBoost teria vantagem com custos mais baixos, ou não prevê de todo?

Repete as experiências v2 só com o modelo B, com os custos multiplicados por 0 e 0,5
(comissão, slippage e spread, incluindo o spread real das velas de Forex). Se nem com custo
zero a expectativa bruta fora da amostra for positiva com confiança, o problema é a previsão,
não a corretora. Resultados em reports/fase2/sensibilidade_custos.json.
"""

from __future__ import annotations

import dataclasses
import json

from trading_agent.config import ROOT, AppConfig, load_config
from trading_agent.research.pipeline import ExperimentSpec, load_bars, run_experiment

HORIZON = {"15m": 16, "1h": 24, "4h": 12, "1d": 10}
TF = {"BTC/USD": ("coinbase", ["1h", "4h", "1d"]), "EUR/USD": ("dukascopy", ["1h", "4h", "1d"])}


def scaled(cfg: AppConfig, symbol: str, k: float) -> AppConfig:
    raw = json.loads(json.dumps(cfg.raw))
    m = raw["markets"][symbol]
    for key in ("fee_bps", "slippage_bps", "spread_bps"):
        if key in m:
            m[key] = m[key] * k
    return dataclasses.replace(cfg, raw=raw)


def main() -> None:
    cfg = load_config()
    out = []
    for sym, (src, tfs) in TF.items():
        for tf in tfs:
            for tp, sl in ((2.0, 1.0), (1.0, 1.0)):
                spec = ExperimentSpec(sym, src, tf, HORIZON[tf], tp, sl)
                for k in (0.0, 0.5):
                    c = scaled(cfg, sym, k)
                    bars = load_bars(spec, c.market(sym)["asset_class"])
                    if "spread" in bars.columns:
                        bars = bars.assign(spread=bars["spread"] * k)
                    rep, _ = run_experiment(spec, c, ("B",), log=lambda *_: None, bars=bars)
                    b = rep["modelos"]["B_xgboost"]
                    for per in ("desenvolvimento", "teste_final"):
                        m = b.get(per) or {}
                        out.append({"experiencia": spec.name, "fator_custos": k, "periodo": per, "operacoes": m.get("operacoes"),
                                    "bruto_bps": m.get("expectativa_bruta_bps"), "custo_bps": m.get("custo_medio_bps"),
                                    "liquido_bps": m.get("expectativa_bps_por_operacao"),
                                    "ic95_bruto_bps": [(m.get("ic95_expectativa_bruta_bps") or {}).get(x) for x in ("ic_inf", "ic_sup")],
                                    "ic95_liquido_bps": [(m.get("ic95_expectativa_liquida_bps") or {}).get(x) for x in ("ic_inf", "ic_sup")],
                                    "retorno_pct": m.get("retorno_liquido_pct")})
                    print(spec.name, k, {p["periodo"]: (p["operacoes"], p["bruto_bps"], p["liquido_bps"]) for p in out[-2:]}, flush=True)
    (ROOT / "reports" / "fase2" / "sensibilidade_custos.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
