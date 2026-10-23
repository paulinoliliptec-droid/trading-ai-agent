"""Hipótese 4 (pré-registo em docs/h4-carry-funding-preregisto.md): carry de funding neutro ao preço.

Uso: python scripts/run_h4.py      (precisa de data/raw/derivados_BTCUSD_1h.parquet: scripts/fetch_derivatives.py)
Grava reports/h4/resultado.json e reports/h4/resultado.md.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import requests

from trading_agent.backtesting.metrics import max_drawdown
from trading_agent.backtesting.uncertainty import bootstrap_mean_ci
from trading_agent.config import ROOT
from trading_agent.data.derivatives import fetch_funding
from trading_agent.data.store import DATA_DIR, load_candles
from trading_agent.research.carry import daily_table, simulate

CENARIOS = {"principal": (25 + 4) + (5 + 2), "barato": (10 + 2) + (2 + 1)}   # bps por lado, soma das duas pernas
ESTRATEGIAS = ("sempre", "condicional")
DEV_FRAC = 2 / 3
REFERENCIA_ANUAL = 0.04


def funding_events() -> pd.Series:
    path = DATA_DIR / "raw" / "funding_BTCUSDT_8h.parquet"
    if path.exists():
        return pd.read_parquet(path)["funding"]
    h = pd.read_parquet(DATA_DIR / "raw" / "derivados_BTCUSD_1h.parquet")
    s = requests.Session()
    f = fetch_funding(h.index.min(), h.index.max() + pd.Timedelta(hours=1), s)
    f.to_frame().to_parquet(path)
    return f


def metricas(r: pd.DataFrame) -> dict:
    x = r["liquido"].to_numpy()
    eq = pd.Series(np.cumprod(1 + x))
    ci = bootstrap_mean_ci(x, n_boot=2000, mean_block=20.0)
    return {"dias": len(x), "dias_em_posicao": int(r["pos"].sum()), "entradas": int((np.diff(np.concatenate([[0], r["pos"]])) > 0).sum()),
            "retorno_anual_pct": float(x.mean() * 365 * 100), "retorno_total_pct": float((eq.iloc[-1] - 1) * 100),
            "ic95_diario_bps": [ci.get("ic_inf", np.nan) * 1e4, ci.get("ic_sup", np.nan) * 1e4],
            "max_drawdown_pct": float(max_drawdown(eq) * 100),
            "carry_anual_pct": float(r["carry"].mean() * 365 / 1.5 * 100), "base_anual_pct": float(r["base"].mean() * 365 / 1.5 * 100),
            "custo_total_pct": float(r["custo"].sum() / 1.5 * 100)}


def main() -> None:
    h = pd.read_parquet(DATA_DIR / "raw" / "derivados_BTCUSD_1h.parquet")
    d = daily_table(funding_events(), h["premio"].dropna())
    k = int(len(d) * DEV_FRAC)
    per = {"desenvolvimento": d.index[:k], "teste_final": d.index[k:]}
    btc = load_candles("BTC/USD", "1h", "coinbase")["close"].resample("1D").last()
    out: dict = {"gerado_em": datetime.now(UTC).isoformat(), "preregisto": "docs/h4-carry-funding-preregisto.md",
                 "periodos": {p: [str(i.min().date()), str(i.max().date()), len(i)] for p, i in per.items()},
                 "custos_bps_por_lado": CENARIOS, "resultados": {}, "riscos": {}}
    for c, cost in CENARIOS.items():
        for s in ESTRATEGIAS:
            out["resultados"][f"{s}|{c}"] = {p: metricas(simulate(d.loc[i], s, cost)) for p, i in per.items()}
            print(s, c, {p: round(v["retorno_anual_pct"], 2) for p, v in out["resultados"][f"{s}|{c}"].items()}, flush=True)
    for p, i in per.items():
        dd = d.loc[i]
        out["riscos"][p] = {"dias_funding_negativo_pct": float((dd["funding"] < 0).mean() * 100),
                            "pior_variacao_diaria_premio_bps": float(dd["d_premio"].abs().max() * 1e4),
                            "maior_subida_btc_30d_pct": float((btc.loc[i.min():i.max()].pct_change(30).max()) * 100),
                            "funding_medio_anual_pct": float(dd["funding"].mean() * 365 * 100)}
    esc = max(ESTRATEGIAS, key=lambda s: out["resultados"][f"{s}|principal"]["desenvolvimento"]["retorno_anual_pct"])
    r = out["resultados"][f"{esc}|principal"]
    crit = {"1_dev_ic95_diario_acima_de_zero": bool(r["desenvolvimento"]["ic95_diario_bps"][0] > 0),
            "2_final_retorno_anual_positivo": r["teste_final"]["retorno_anual_pct"] > 0,
            "3_final_supera_4pct": r["teste_final"]["retorno_anual_pct"] > REFERENCIA_ANUAL * 100}
    out.update({"escolhida": esc, "criterios": crit, "hipotese_confirmada": all(crit.values())})
    dest = ROOT / "reports" / "h4"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "resultado.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (dest / "resultado.md").write_text(render(out))
    print("escolhida:", esc, crit, "→", "CONFIRMADA" if out["hipotese_confirmada"] else "NÃO confirmada")


def render(o: dict) -> str:
    L = [f"# Hipótese 4: carry de funding (gerado {o['gerado_em'][:16]} UTC)", "", f"Pré-registo: `{o['preregisto']}`.", "",
         "Períodos: " + "; ".join(f"{p} {v[0]} a {v[1]} ({v[2]} dias)" for p, v in o["periodos"].items()) + ".",
         "Retornos sobre o capital (nocional + 50% de margem), líquidos de custos e da variação da base.", "",
         "| Estratégia | Custos | Período | Retorno anual % | IC95% diário (bps) | Total % | Máx. DD % | Carry %/ano | Base %/ano | Custos % | Dias em posição | Entradas |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in o["resultados"].items():
        s, c = k.split("|")
        for p, m in v.items():
            L.append(f"| {s} | {c} ({o['custos_bps_por_lado'][c]} bps) | {p} | {m['retorno_anual_pct']:.2f} | "
                     f"[{m['ic95_diario_bps'][0]:+.2f}; {m['ic95_diario_bps'][1]:+.2f}] | {m['retorno_total_pct']:.2f} | {m['max_drawdown_pct']:.2f} | "
                     f"{m['carry_anual_pct']:.2f} | {m['base_anual_pct']:.2f} | {m['custo_total_pct']:.2f} | {m['dias_em_posicao']} | {m['entradas']} |")
    L += ["", "## Riscos observados", "", "| Período | Funding médio %/ano (nocional) | Dias com funding negativo % | Pior Δ diário do prémio (bps) | Maior subida do BTC em 30 dias % |",
          "|---|---|---|---|---|"]
    for p, r in o["riscos"].items():
        L.append(f"| {p} | {r['funding_medio_anual_pct']:.2f} | {r['dias_funding_negativo_pct']:.1f} | {r['pior_variacao_diaria_premio_bps']:.1f} | {r['maior_subida_btc_30d_pct']:.1f} |")
    L += ["", f"**Escolhida no desenvolvimento (cenário principal):** {o['escolhida']}.", "", "| Critério pré-registado | Cumprido |", "|---|---|"]
    L += [f"| {k} | {'sim' if v else 'não'} |" for k, v in o["criterios"].items()]
    L += ["", f"**Hipótese {'CONFIRMADA' if o['hipotese_confirmada'] else 'NÃO confirmada'}.**", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
