"""Hipótese 3 (pré-registo em docs/h3-volatilidade-preregisto.md): previsão da volatilidade e volatilidade-alvo.

Uso: python scripts/run_vol_research.py
Grava reports/h3/resultado.json e reports/h3/resultado.md. Não grava modelos nem aprova nada.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from trading_agent.config import ROOT, load_config
from trading_agent.data.store import load_candles
from trading_agent.research.volatility import (
    FORECASTERS,
    VolSpec,
    daily_table,
    forecast_quality,
    forecasts,
    paired_ci,
    perf,
    sharpe,
    vol_target_returns,
)

TARGET_ANN = 0.40
DEV_FRAC = 2 / 3
MARKETS = {"BTC/USD": ("coinbase", VolSpec("BTC/USD")),
           "EUR/USD": ("dukascopy", VolSpec("EUR/USD", week=5, month=22, min_train_days=252))}


def split(idx: pd.Index) -> dict[str, pd.Index]:
    k = int(len(idx) * DEV_FRAC)
    return {"desenvolvimento": idx[:k], "teste_final": idx[k:]}


def main() -> None:
    cfg = load_config()
    out: dict = {"gerado_em": datetime.now(UTC).isoformat(), "preregisto": "docs/h3-volatilidade-preregisto.md",
                 "parte_A": {}, "parte_B": {}}
    tables = {}
    for sym, (src, spec) in MARKETS.items():
        d = daily_table(load_candles(sym, "1h", src), spec)
        fc = forecasts(d, spec)
        idx = fc.index[d.loc[fc.index, "rv_next"].notna().to_numpy()]
        per = split(idx)
        out["parte_A"][sym] = {"periodos": {k: [str(v.min().date()), str(v.max().date()), len(v)] for k, v in per.items()},
                               **{k: forecast_quality(d, fc, v) for k, v in per.items()}}
        tables[sym] = (d, fc, per)
        print(sym, {k: {f: round(out["parte_A"][sym][k][f]["qlike"], 4) for f in FORECASTERS} for k in per}, flush=True)

    # Parte B: só BTC/USD
    d, fc, per = tables["BTC/USD"]
    m = cfg.market("BTC/USD")
    cost = m["fee_bps"] + m["spread_bps"] + m["slippage_bps"]
    res: dict = {"volatilidade_alvo_anual": TARGET_ANN, "custo_bps_por_lado": cost, "previsores": {}}
    for f in FORECASTERS:
        r = {}
        for pname, idx in per.items():
            vt = vol_target_returns(d, fc.loc[idx, f], TARGET_ANN, cost)
            bh = vt["asset"].to_numpy()
            const = vt["w"].mean() * bh
            net = vt["net"].to_numpy()
            r[pname] = {"estrategia": perf(net), "comprar_e_manter": perf(bh), "exposicao_constante": perf(const),
                        "exposicao_media": float(vt["w"].mean()), "rotacao_anual": float(vt["turnover"].sum() / len(vt) * 365),
                        "custo_anual_pct": float(vt["turnover"].sum() * cost / 1e4 / len(vt) * 365 * 100),
                        "sharpe_menos_bh": paired_ci(net, bh, sharpe), "sharpe_menos_constante": paired_ci(net, const, sharpe)}
        res["previsores"][f] = r
        print(f, {p: (round(r[p]["estrategia"]["sharpe"], 3), round(r[p]["comprar_e_manter"]["sharpe"], 3)) for p in r}, flush=True)

    escolhido = max(FORECASTERS, key=lambda f: res["previsores"][f]["desenvolvimento"]["estrategia"]["sharpe"])
    e = res["previsores"][escolhido]
    crit = {"1_dev_ic95_sharpe_vs_bh_acima_de_zero": e["desenvolvimento"]["sharpe_menos_bh"]["ic_inf"] > 0,
            "2_final_sharpe_vs_bh_positivo": e["teste_final"]["sharpe_menos_bh"]["dif"] > 0,
            "3_dev_sharpe_vs_constante_positivo": e["desenvolvimento"]["sharpe_menos_constante"]["dif"] > 0}
    res.update({"escolhido_no_desenvolvimento": escolhido, "criterios": crit, "hipotese_confirmada": all(crit.values())})
    out["parte_B"] = res

    dest = ROOT / "reports" / "h3"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "resultado.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (dest / "resultado.md").write_text(render(out))
    print("escolhido:", escolhido, crit, "→ confirmada" if res["hipotese_confirmada"] else "→ NÃO confirmada")


def render(o: dict) -> str:
    def ci(x):
        return f"{x['dif']:+.3f} [{x['ic_inf']:+.3f}; {x['ic_sup']:+.3f}]"

    L = [f"# Hipótese 3: resultados (gerado {o['gerado_em'][:16]} UTC)", "", f"Pré-registo: `{o['preregisto']}`.", "",
         "## Parte A: qualidade da previsão do dia seguinte (QLIKE, menor é melhor)", ""]
    for sym, a in o["parte_A"].items():
        L += [f"### {sym}", "", "| Período | Dias | " + " | ".join(f"{f} QLIKE" for f in FORECASTERS) + " | R² log (HAR) | XGB − HAR (IC95%) | EWMA − HAR (IC95%) |",
              "|---|---|" + "---|" * (len(FORECASTERS) + 3)]
        for p in ("desenvolvimento", "teste_final"):
            q = a[p]
            L.append(f"| {p} ({a['periodos'][p][0]} a {a['periodos'][p][1]}) | {q['dias']} | "
                     + " | ".join(f"{q[f]['qlike']:.4f}" for f in FORECASTERS)
                     + f" | {q['HAR']['r2_log']:.3f} | {ci(q['XGB']['qlike_menos_HAR'])} | {ci(q['EWMA']['qlike_menos_HAR'])} |")
        L.append("")
    b = o["parte_B"]
    L += ["## Parte B: volatilidade-alvo no BTC/USD (líquido de custos)", "",
          f"Alvo {b['volatilidade_alvo_anual']:.0%} ao ano, custo {b['custo_bps_por_lado']:.0f} bps por unidade rodada, banda de 0,10.", "",
          "| Previsor | Período | Sharpe | Retorno % | Vol % | Máx. DD % | Exposição média | Custo %/ano | Sharpe − comprar e manter (IC95%) | Sharpe − exposição constante (IC95%) |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for f, r in b["previsores"].items():
        for p in ("desenvolvimento", "teste_final"):
            s = r[p]["estrategia"]
            L.append(f"| {f} | {p} | {s['sharpe']:.3f} | {s['retorno_total_pct']:.1f} | {s['vol_anual_pct']:.1f} | {s['max_drawdown_pct']:.1f} | "
                     f"{r[p]['exposicao_media']:.2f} | {r[p]['custo_anual_pct']:.2f} | {ci(r[p]['sharpe_menos_bh'])} | {ci(r[p]['sharpe_menos_constante'])} |")
    for p in ("desenvolvimento", "teste_final"):
        s = b["previsores"]["HAR"][p]["comprar_e_manter"]
        L.append(f"| comprar e manter | {p} | {s['sharpe']:.3f} | {s['retorno_total_pct']:.1f} | {s['vol_anual_pct']:.1f} | {s['max_drawdown_pct']:.1f} | 1.00 | 0 | | |")
    L += ["", f"**Escolhido no desenvolvimento:** {b['escolhido_no_desenvolvimento']}.", "", "| Critério pré-registado | Cumprido |", "|---|---|"]
    L += [f"| {k} | {'sim' if v else 'não'} |" for k, v in b["criterios"].items()]
    L += ["", f"**Hipótese {'CONFIRMADA' if b['hipotese_confirmada'] else 'NÃO confirmada'}.**", ""]
    return "\n".join(L)


if __name__ == "__main__":
    np.seterr(divide="ignore")
    main()
