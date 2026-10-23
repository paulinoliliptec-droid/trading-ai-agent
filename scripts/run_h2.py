"""Hipótese 2 (pré-registo em docs/h2-derivados-preregisto.md): v3 = v2 + derivados e fluxo, regras da fase 2.

Uso: python scripts/run_h2.py      (precisa de data/raw/derivados_BTCUSD_1h.parquet: scripts/fetch_derivatives.py)
Grava reports/h2/resultado.json e reports/h2/resultado.md. Não grava modelos nem aprova nada.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime

from trading_agent.config import ROOT, AppConfig, load_config
from trading_agent.research.pipeline import ExperimentSpec, run_experiment

SPECS = [ExperimentSpec("BTC/USD", "coinbase", "1h", 24, 2.0, 1.0, "v3"),
         ExperimentSpec("BTC/USD", "coinbase", "1h", 24, 1.0, 1.0, "v3"),
         ExperimentSpec("BTC/USD", "coinbase", "4h", 12, 2.0, 1.0, "v3"),
         ExperimentSpec("BTC/USD", "coinbase", "4h", 12, 1.0, 1.0, "v3")]
MIN_TRADES = 30


def sem_custos(cfg: AppConfig, symbol: str) -> AppConfig:
    raw = json.loads(json.dumps(cfg.raw))
    for k in ("fee_bps", "slippage_bps", "spread_bps"):
        raw["markets"][symbol][k] = 0.0
    return dataclasses.replace(cfg, raw=raw)


def resumo(rep: dict) -> dict:
    b = rep["modelos"]["B_xgboost"]
    out = {"qualificado_no_desenvolvimento": b["qualificado_no_desenvolvimento"]}
    for p in ("desenvolvimento", "teste_final"):
        m = b.get(p) or {}
        cl = m.get("classificacao_lado_principal") or {}
        out[p] = {"operacoes": m.get("operacoes"), "bruto_bps": m.get("expectativa_bruta_bps"),
                  "liquido_bps": m.get("expectativa_bps_por_operacao"),
                  "ic95_liquido_bps": [(m.get("ic95_expectativa_liquida_bps") or {}).get(x) for x in ("ic_inf", "ic_sup")],
                  "ic95_bruto_bps": [(m.get("ic95_expectativa_bruta_bps") or {}).get(x) for x in ("ic_inf", "ic_sup")],
                  "retorno_pct": m.get("retorno_liquido_pct"), "auc": cl.get("roc_auc"), "brier_skill": cl.get("brier_skill")}
    out["periodos"] = rep["periodos"]
    return out


def main() -> None:
    cfg = load_config()
    zero = sem_custos(cfg, "BTC/USD")
    res: dict = {"gerado_em": datetime.now(UTC).isoformat(), "preregisto": "docs/h2-derivados-preregisto.md",
                 "experiencias": {}, "diagnostico_custo_zero": {}}
    for spec in SPECS:
        rep, _ = run_experiment(spec, cfg, ("B",), log=lambda *_: None)
        res["experiencias"][spec.name] = resumo(rep)
        print(spec.name, {p: (res["experiencias"][spec.name][p]["operacoes"], res["experiencias"][spec.name][p]["liquido_bps"])
                          for p in ("desenvolvimento", "teste_final")}, flush=True)
        for fs in ("v3", "v2"):   # diagnóstico: só previsão, sem custos; não seleciona nada
            s0 = dataclasses.replace(spec, feature_set=fs)
            r0, _ = run_experiment(s0, zero, ("B",), log=lambda *_: None)
            res["diagnostico_custo_zero"][s0.name] = resumo(r0)
            d = res["diagnostico_custo_zero"][s0.name]["desenvolvimento"]
            print("  custo zero", s0.name, d["operacoes"], d["bruto_bps"], d["ic95_bruto_bps"], "auc", d["auc"], flush=True)

    qual = {k: v for k, v in res["experiencias"].items() if v["qualificado_no_desenvolvimento"]}
    escolhida = max(qual, key=lambda k: qual[k]["desenvolvimento"]["liquido_bps"]) if qual else None
    final = res["experiencias"][escolhida]["teste_final"]["liquido_bps"] if escolhida else None
    res.update({"qualificadas": list(qual), "escolhida": escolhida,
                "hipotese_confirmada": bool(escolhida and final is not None and final > 0 and
                                            (res["experiencias"][escolhida]["teste_final"]["operacoes"] or 0) > 0)})
    dest = ROOT / "reports" / "h2"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "resultado.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    (dest / "resultado.md").write_text(render(res))
    print("qualificadas:", list(qual), "| escolhida:", escolhida, "| confirmada:", res["hipotese_confirmada"])


def render(r: dict) -> str:
    def f(x, nd=1):
        return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))

    def ic(v):
        return "—" if not v or v[0] is None else f"[{v[0]:+.1f}; {v[1]:+.1f}]"

    L = [f"# Hipótese 2: resultados (gerado {r['gerado_em'][:16]} UTC)", "", f"Pré-registo: `{r['preregisto']}`.", "",
         "## Experiências pré-registadas (custos reais, modelo B, features v3)", "",
         "| Experiência | Período | Operações | Bruto bps | Líquido bps | IC95% líquido | Retorno % | AUC | Qualifica |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in r["experiencias"].items():
        for p in ("desenvolvimento", "teste_final"):
            m = v[p]
            L.append(f"| {k} | {p} | {f(m['operacoes'])} | {f(m['bruto_bps'])} | {f(m['liquido_bps'])} | {ic(m['ic95_liquido_bps'])} | "
                     f"{f(m['retorno_pct'], 2)} | {f(m['auc'], 3)} | {('sim' if v['qualificado_no_desenvolvimento'] else 'não') if p == 'desenvolvimento' else ''} |")
    L += ["", f"**Qualificadas:** {', '.join(r['qualificadas']) or 'nenhuma'}. **Escolhida:** {r['escolhida'] or '—'}. "
          f"**Hipótese {'CONFIRMADA' if r['hipotese_confirmada'] else 'NÃO confirmada'}.**", "",
          "## Diagnóstico com custo zero (informativo): a informação nova melhora a previsão?", "",
          "| Experiência | Features | Operações (dev) | Bruto bps (dev) | IC95% bruto (dev) | AUC dev | Bruto bps (final) | AUC final |",
          "|---|---|---|---|---|---|---|---|"]
    for k, v in r["diagnostico_custo_zero"].items():
        d, t = v["desenvolvimento"], v["teste_final"]
        L.append(f"| {k.rsplit('_', 1)[0]} | {k.rsplit('_', 1)[1]} | {f(d['operacoes'])} | {f(d['bruto_bps'])} | {ic(d['ic95_bruto_bps'])} | "
                 f"{f(d['auc'], 3)} | {f(t['bruto_bps'])} | {f(t['auc'], 3)} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
