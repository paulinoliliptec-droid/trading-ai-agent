"""Pipeline de investigação: features → rótulos → walk-forward → modelos A/B/C → backtest → relatório.

Uso: python scripts/run_research.py --symbol "EUR/USD" --source dukascopy [--sem-gru]
Resultados em reports/{par}_{data}.json. Nada aqui é dado sintético: lê o Parquet recolhido.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from trading_agent.backtesting.engine import MarketCosts, run_backtest
from trading_agent.backtesting.metrics import classification_metrics, trading_metrics
from trading_agent.backtesting.splits import walk_forward
from trading_agent.config import ROOT, load_config
from trading_agent.data.store import dataset_path, load_candles
from trading_agent.features.build import atr, build_features, model_columns
from trading_agent.labels.triple_barrier import triple_barrier
from trading_agent.models.baseline.rules import rule_signals
from trading_agent.models.xgboost_model.model import XGBoostModel
from trading_agent.risk.engine import RiskEngine
from trading_agent.risk.kill_switch import KillSwitch

THRESHOLDS = [0.40, 0.45, 0.50, 0.55, 0.60]


def choose_threshold(p: np.ndarray, ret: np.ndarray, cost: float, min_trades: int = 30) -> float:
    """Limiar escolhido na VALIDAÇÃO: o que maximiza o retorno médio líquido, com um mínimo de operações."""
    best, best_thr = -np.inf, THRESHOLDS[-1]
    for thr in THRESHOLDS:
        m = p >= thr
        if m.sum() < min_trades:
            continue
        v = np.nanmean(ret[m]) - cost
        if v > best:
            best, best_thr = v, thr
    return best_thr


def sides_from_probs(p_long: pd.Series, p_short: pd.Series, thr: float) -> tuple[pd.Series, pd.Series]:
    side = np.where((p_long >= thr) & (p_long >= p_short), 1, np.where(p_short >= thr, -1, 0))
    prob = np.where(side == 1, p_long, np.where(side == -1, p_short, 0.0))
    return pd.Series(side, index=p_long.index), pd.Series(prob, index=p_long.index)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EUR/USD")
    ap.add_argument("--source", default="dukascopy")
    ap.add_argument("--sem-gru", action="store_true")
    args = ap.parse_args()
    cfg = load_config()
    R, mk = cfg.raw["research"], cfg.market(args.symbol)
    t0 = time.time()

    df = load_candles(args.symbol, "1h", args.source)
    manifest = json.loads(dataset_path(args.symbol, "1h", args.source).with_suffix(".manifest.json").read_text())
    feats = build_features(df, R["atr_window"])
    a = atr(df, R["atr_window"])
    bars = {s: triple_barrier(df, a, s, R["horizon_bars"], R["tp_atr_mult"], R["sl_atr_mult"]) for s in (1, -1)}
    cols = model_columns(feats)
    valid = feats[cols].notna().all(axis=1) & bars[1]["label"].notna() & bars[-1]["label"].notna()
    data = feats.loc[valid]
    yl, ys = bars[1]["label"][valid], bars[-1]["label"][valid]
    t1 = pd.concat([bars[1]["t1"], bars[-1]["t1"]], axis=1).max(axis=1)[valid]
    costs = MarketCosts(mk.get("fee_bps", 0.0), mk.get("slippage_bps", 0.0), mk.get("spread_bps", 0.0))
    cost_typ = costs.round_trip_pct(float(data["spread_bps"].median()) if "spread_bps" in data else None)
    ppy = 252 if mk["asset_class"] == "forex" else 365
    risk = RiskEngine(cfg.risk, KillSwitch(ROOT / "data" / "KILL_SWITCH_BACKTEST"), mk.get("max_leverage", 1.0))
    folds = walk_forward(t1, R["n_splits"], test_frac=0.5, val_frac=0.15, embargo=R["embargo_bars"])

    test_idx = np.concatenate([f.test for f in folds])
    test_times = data.index[test_idx]
    sides, probs = {}, {}
    rule = rule_signals(data)
    sides["A_regras"] = rule.iloc[test_idx]
    clf = {"B_xgboost": [], "C_gru": []}
    p_store = {k: {1: pd.Series(np.nan, index=data.index), -1: pd.Series(np.nan, index=data.index)} for k in clf}
    rule_prob = pd.Series(np.nan, index=data.index)
    thresholds = {k: [] for k in clf}
    importances = []

    for f in folds:
        fit_idx = np.concatenate([f.train, f.val])
        # A: probabilidade empírica da regra = taxa de TP-primeiro dos sinais da regra no treino.
        for s, y in ((1, yl), (-1, ys)):
            m = rule.iloc[fit_idx] == s
            rate = float(y.iloc[fit_idx][m.to_numpy()].mean()) if m.any() else 0.0
            rule_prob.iloc[f.test[(rule.iloc[f.test] == s).to_numpy()]] = rate
        # B: XGBoost por lado.
        thr_side = []
        for s, y in ((1, yl), (-1, ys)):
            Xtr, Xva, Xte = data[cols].iloc[f.train], data[cols].iloc[f.val], data[cols].iloc[f.test]
            mdl = XGBoostModel().fit(Xtr, y.iloc[f.train], Xva, y.iloc[f.val])
            p_store["B_xgboost"][s].iloc[f.test] = mdl.predict_proba(Xte)
            pv = mdl.predict_proba(Xva)
            thr_side.append(choose_threshold(pv, bars[s]["gross_ret"].loc[data.index[f.val]].to_numpy(), cost_typ))
            if s == 1:
                importances.append(mdl.importance())
        thresholds["B_xgboost"].append(max(thr_side))
        # C: GRU por lado.
        if not args.sem_gru:
            from trading_agent.models.neural_networks.gru import GRUModel
            thr_side = []
            for s, y in ((1, yl), (-1, ys)):
                g = GRUModel().fit(data[cols], y, f.train, f.val)
                pt, ok = g.predict_proba(f.test)
                p_store["C_gru"][s].iloc[ok] = pt
                pv, okv = g.predict_proba(f.val)
                thr_side.append(choose_threshold(pv, bars[s]["gross_ret"].loc[data.index[okv]].to_numpy(), cost_typ))
            thresholds["C_gru"].append(max(thr_side))
        print(f"fold {f.k}: treino={len(f.train)} validação={len(f.val)} teste={len(f.test)} ({time.time() - t0:.0f}s)", flush=True)

    probs["A_regras"] = rule_prob.iloc[test_idx].fillna(0.0)
    report_models = {}
    for k in ("B_xgboost", "C_gru"):
        if k == "C_gru" and args.sem_gru:
            continue
        s_all, p_all = [], []
        for f, thr in zip(folds, thresholds[k], strict=True):
            s_, p_ = sides_from_probs(p_store[k][1].iloc[f.test].fillna(0), p_store[k][-1].iloc[f.test].fillna(0), thr)
            s_all.append(s_)
            p_all.append(p_)
        sides[k], probs[k] = pd.concat(s_all), pd.concat(p_all)
        report_models[k] = {
            "limiares_por_fold": thresholds[k],
            "classificacao_teste_lado_comprado": classification_metrics(yl.iloc[test_idx].to_numpy(), p_store[k][1].iloc[test_idx].to_numpy(), float(np.median(thresholds[k]))),
            "classificacao_teste_lado_vendido": classification_metrics(ys.iloc[test_idx].to_numpy(), p_store[k][-1].iloc[test_idx].to_numpy(), float(np.median(thresholds[k]))),
        }

    results = {}
    for k in sides:
        trades, eq, vetoes = run_backtest(data.index, sides[k], probs[k], data, bars, costs, risk, args.symbol, R["tp_atr_mult"], R["sl_atr_mult"])
        results[k] = {**trading_metrics(trades, eq, ppy), "vetos_do_risco": vetoes, **report_models.get(k, {})}
    # Diagnóstico: as regras SEM os filtros de probabilidade e expectativa (os limites de carteira e o tamanho
    # mantêm-se). Mostra quanto custaria negociar a regra ingenuamente; não é uma estratégia proposta.
    permissivo = RiskEngine(dataclasses.replace(cfg.risk, min_probability=0.0, min_expected_edge_bps=-1e9),
                            KillSwitch(ROOT / "data" / "KILL_SWITCH_BACKTEST"), mk.get("max_leverage", 1.0))
    trades, eq, vetoes = run_backtest(data.index, sides["A_regras"], probs["A_regras"].clip(lower=0.5), data, bars, costs,
                                      permissivo, args.symbol, R["tp_atr_mult"], R["sl_atr_mult"])
    results["A_regras_sem_filtro_de_expectativa_diagnostico"] = {**trading_metrics(trades, eq, ppy), "vetos_do_risco": vetoes}
    results["nao_negociar"] = {"operacoes": 0, "retorno_liquido_pct": 0.0, "max_drawdown_pct": 0.0}
    c = df["close"].loc[test_times]
    results["comprar_e_manter_referencia"] = {"retorno_pct": round((c.iloc[-1] / c.iloc[0] - 1) * 100, 3),
                                             "max_drawdown_pct": round(float((c / c.cummax() - 1).min()) * 100, 3)}
    rep = {
        "gerado_em": datetime.now(UTC).isoformat(), "par": args.symbol, "fonte": args.source,
        "dados": {k: manifest[k] for k in ("rows", "start", "end", "quality", "synthetic")},
        "periodo_teste": [str(test_times.min()), str(test_times.max())], "amostras_validas": int(len(data)),
        "rotulagem": {"horizonte_velas": R["horizon_bars"], "tp_atr": R["tp_atr_mult"], "sl_atr": R["sl_atr_mult"],
                      "taxa_tp_comprado": round(float(yl.mean()), 4), "taxa_tp_vendido": round(float(ys.mean()), 4)},
        "custo_tipico_ida_volta_bps": round(cost_typ * 1e4, 3),
        "features": cols, "importancia_xgboost_fold0": dict(list(importances[0].items())[:10]) if importances else {},
        "resultados": results, "duracao_s": round(time.time() - t0, 1),
    }
    out = ROOT / "reports" / f"{args.symbol.replace('/', '')}_{datetime.now(UTC):%Y%m%d}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: {kk: v.get(kk) for kk in ("operacoes", "retorno_liquido_pct", "expectativa_bps_por_operacao", "profit_factor", "max_drawdown_pct", "sharpe_anualizado")} for k, v in results.items()}, indent=1, ensure_ascii=False, default=str))
    print("relatório:", out)


if __name__ == "__main__":
    main()
