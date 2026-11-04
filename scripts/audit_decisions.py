"""Auditoria retrospetiva das decisões registadas: oportunidades rejeitadas que teriam dado lucro?

Uso:
  python scripts/audit_decisions.py --inicio 2026-10-22 --fim 2026-11-03T19:00 [--decisoes ficheiro.json]

Lê `trading_agent.decisions` (só `find`; nada é escrito no Atlas), os preços horários da Coinbase (a fonte do
modelo) e o modelo versionado (SHA-256 verificado; só inferência, para confirmar a probabilidade registada).
Grava em reports/auditoria/: um CSV com todas as decisões, um JSON com os agregados e os preços usados
(a leitura dos resultados fica em reports/auditoria/RESUMO.md, escrita à mão). Não altera o modelo, os limites de risco nem a operação.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from trading_agent.agent.worker import LOOKBACK_BARS
from trading_agent.config import ROOT, Secrets, load_config
from trading_agent.models.registry import ModelRegistry
from trading_agent.monitoring.audit import (
    PROB_LABELS,
    RESOLVIDO,
    carregar_decisoes,
    custo_extra,
    ic95,
    precos,
    sequencia_executavel,
    tabela,
)

H = pd.Timedelta(hours=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", default="2026-10-22")
    ap.add_argument("--fim", default="2026-11-03T19:00")
    ap.add_argument("--symbol", default="BTC/USD")
    ap.add_argument("--decisoes", help="JSON exportado (em vez do Atlas)")
    ap.add_argument("--limite-alternativo", type=float, default=0.30)
    args = ap.parse_args()
    sec, cfg = Secrets(), load_config()
    agora = datetime.now(UTC).replace(second=0, microsecond=0)
    dec = carregar_decisoes(sec, args.symbol, args.inicio, args.fim, args.decisoes)
    if not dec:
        raise SystemExit("sem decisões na janela")
    modelos = sorted({d["model_id"] for d in dec})
    reg = ModelRegistry()
    pol = {m: reg.load(m) for m in modelos}                   # (policy, meta), SHA-256 verificado
    inst = cfg.instrument(args.symbol)
    extra_cost = custo_extra(inst)
    t0 = pd.Timestamp(dec[0]["bar_time"])
    bars = precos(args.symbol, t0, agora)
    lim_atual = cfg.risk.min_probability
    lim_alt = args.limite_alternativo

    df = tabela(dec, bars, pol, extra_cost, lim_alt)
    col_alt = f"aprovaria_{lim_alt:.2f}"
    res = df[df["resultado"].isin(RESOLVIDO)]
    h24 = df[df["subiu_24h"].notna()]

    def stats(x: pd.DataFrame) -> dict:
        rx = x[x["resultado"].isin(RESOLVIDO)]
        hx = x[x["subiu_24h"].notna()]
        liq = rx["ret_liquido_bps"].astype(float)
        return {"n": len(x), "resolvidas": len(rx), "pendentes": int((x["resultado"] == "pendente").sum()),
                "tp": int((rx["resultado"] == "tp").sum()), "sl": int((rx["resultado"] == "sl").sum()),
                "tempo": int((rx["resultado"] == "tempo").sum()),
                "tempo_positivo_liq": int(((rx["resultado"] == "tempo") & (liq > 0)).sum()),
                "rentaveis_liq": int((liq > 0).sum()), "ret_liq_medio_bps": float(liq.mean()) if len(rx) else None,
                "ic95_liq_bps": ic95(list(liq)), "h24_avaliadas": len(hx), "subiu_24h": int(hx["subiu_24h"].sum()),
                "h24_rentavel_liq": int((hx["ret_24h_liquido_bps"] > 0).sum()),
                "prob_media": float(x["prob"].mean()) if x["prob"].notna().any() else None,
                "freq_tp": float((rx["resultado"] == "tp").mean()) if len(rx) else None,
                "exp_ret_medio_bps": float(rx["exp_ret_bruto_bps"].mean()) if len(rx) else None,
                "ret_bruto_medio_bps": float(rx["ret_bruto_bps"].mean()) if len(rx) else None}

    def carteira(mask: pd.Series) -> dict:
        s = sequencia_executavel(df, mask)
        if s.empty:
            return {"operacoes": 0}
        fech = s[s["resultado"].isin(RESOLVIDO)]
        L = cfg.risk
        eq = 1.0
        for _, r in fech.iterrows():
            sl_mult = float(pol[r["model_id"]][1]["sl_mult"])
            size = L.max_loss_per_trade_pct / (sl_mult * r["atr_pct"] + r["custo_bps"] / 1e4)
            size = min(size, L.max_exposure_per_asset_pct * inst.max_leverage, inst.max_leverage)
            eq *= 1 + size * r["ret_liquido_bps"] / 1e4
        return {"operacoes": len(s), "fechadas": len(fech), "aberta": int(len(s) - len(fech)),
                "tp": int((fech["resultado"] == "tp").sum()), "sl": int((fech["resultado"] == "sl").sum()),
                "tempo": int((fech["resultado"] == "tempo").sum()), "rentaveis_liq": int((fech["ret_liquido_bps"] > 0).sum()),
                "soma_ret_liq_bps_sem_sobreposicao": float(fech["ret_liquido_bps"].sum()),
                "resultado_capital_pct": (eq - 1) * 100, "entradas": [str(x) for x in s["entrada_ts"]],
                "resultados": list(s["resultado"]), "liq_bps": [None if pd.isna(v) else round(float(v), 1) for v in s["ret_liquido_bps"]]}

    # calibração: prob registada vs frequência de TP antes do SL (o alvo que o modelo estima)
    cal = []
    for lab in PROB_LABELS:
        x = res[res["faixa_prob"] == lab]
        if len(x):
            cal.append({"faixa": lab, "n": len(x), "prob_media": float(x["prob"].mean()), "freq_tp": float((x["resultado"] == "tp").mean()),
                        "exp_ret_bps": float(x["exp_ret_bruto_bps"].mean()), "ret_bruto_bps": float(x["ret_bruto_bps"].mean())})
    p = res["prob"].astype(float).clip(1e-6, 1 - 1e-6)
    y = (res["resultado"] == "tp").astype(float)
    base = float(y.mean()) if len(y) else np.nan
    out = {
        "gerado_em": agora.isoformat(), "janela": [args.inicio, args.fim], "simbolo": args.symbol, "modelos": modelos,
        "metadados_modelo": {m: {k: pol[m][1][k] for k in ("horizon_bars", "tp_mult", "sl_mult", "status", "sha256")} for m in modelos},
        "ultima_vela_fechada": str(bars.index[-1]), "velas_em_falta_no_periodo": int(
            len(pd.date_range(t0, bars.index[-1], freq=H)) - len(bars.loc[t0:])),
        "limite_atual": lim_atual, "limite_alternativo": lim_alt,
        "decisoes": len(df), "aprovadas": int(df["aprovado"].sum()),
        "prob_reproduzida_max_dif": float((df["prob"] - df["prob_recalculada"]).abs().max()),
        "prob_reproduzida_mediana_dif": float((df["prob"] - df["prob_recalculada"]).abs().median()),
        "estados": df["resultado"].value_counts().to_dict(), "ambiguas_tp_sl": int(df["tp_e_sl_mesma_vela"].sum()),
        "todas": stats(df),
        "por_faixa": {lab: stats(df[df["faixa_prob"] == lab]) for lab in PROB_LABELS if (df["faixa_prob"] == lab).any()},
        "calibracao": cal,
        "brier": float(((p - y) ** 2).mean()) if len(y) else None, "brier_climatologia": float(((base - y) ** 2).mean()) if len(y) else None,
        "logloss": float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()) if len(y) else None,
        "motivos": df["motivos"].str.split(r" \| ").explode().str.replace(r"[-+]?\d+(\.\d+)?", "#", regex=True).value_counts().to_dict(),
        "contrafactual": {"prob_ge_alt": int((df["prob"] >= lim_alt).sum()), "aprovaria_alt": int(df[col_alt].sum()),
                          "prob_ge_alt_bloqueadas_por": df[(df["prob"] >= lim_alt) & ~df[col_alt]]["outros_vetos"].str.replace(
                              r"[-+]?\d+(\.\d+)?", "#", regex=True).value_counts().to_dict(),
                          "sinais_alt": stats(df[df[col_alt]]), "carteira_alt": carteira(df[col_alt]),
                          "sinais_prob_ge_alt_ignorando_expectativa": stats(df[df["prob"] >= lim_alt]),
                          "carteira_prob_ge_alt_ignorando_expectativa": carteira(df["prob"] >= lim_alt),
                          "carteira_atual": carteira(df["aprovado"]),
                          "carteira_todas_as_compras": carteira(pd.Series(True, index=df.index))},
        "custo_bps": {"min": float(df["custo_bps"].min()), "max": float(df["custo_bps"].max())},
        "atr_pct": {"mediana": float(df["atr_pct"].median()), "min": float(df["atr_pct"].min()), "max": float(df["atr_pct"].max())},
        "custo_sobre_tp_mediana": float((df["custo_bps"] / 1e4 / (2 * df["atr_pct"])).median()),
        "btc": {"abertura_periodo": float(bars.loc[t0:, "open"].iloc[0]), "ultimo_fecho": float(bars["close"].iloc[-1])},
        "subiu_24h_total": int(h24["subiu_24h"].sum()), "h24_avaliadas": len(h24),
    }
    d_out = ROOT / "reports" / "auditoria"
    d_out.mkdir(parents=True, exist_ok=True)
    tag = f"{pd.Timestamp(args.inicio):%Y%m%d}_{pd.Timestamp(args.fim):%Y%m%dT%H%M}"
    df.to_csv(d_out / f"decisoes_{tag}.csv", index=False, float_format="%.6g")
    bars.loc[t0 - H * LOOKBACK_BARS:].to_csv(d_out / f"precos_coinbase_{tag}.csv", float_format="%.2f")
    (d_out / f"agregados_{tag}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: out[k] for k in ("decisoes", "aprovadas", "estados", "todas", "prob_reproduzida_max_dif")}, indent=1,
                     ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
