"""Pipeline de investigação da fase 2: experiências comparáveis, com regras fixadas ANTES dos resultados.

Desenho (pré-registado no código, não ajustado depois de ver números):
  · walk-forward com `n_splits` blocos de teste; cada bloco tem antes de si treino | validação |
    calibração, separados por embargo de `horizon` velas e com purging por `t1`;
  · os primeiros `dev_splits` blocos são o período de DESENVOLVIMENTO: é só aqui que se comparam
    configurações e modelos; os restantes são o TESTE FINAL, apenas reportado;
  · não se escolhe limiar de probabilidade: o motor de risco decide pela expectativa depois de
    custos, com o retorno bruto esperado estimado na CALIBRAÇÃO (fora do treino);
  · critério de seleção (fixo): ≥ 30 operações no desenvolvimento e limite inferior do intervalo
    de confiança (bootstrap por blocos, 95%) da expectativa líquida por operação acima de zero.
"""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from trading_agent.backtesting.engine import BacktestConfig, run_backtest
from trading_agent.backtesting.metrics import classification_metrics, max_drawdown, trading_metrics
from trading_agent.backtesting.splits import Fold, walk_forward
from trading_agent.backtesting.uncertainty import bootstrap_mean_ci, monte_carlo_equity
from trading_agent.config import AppConfig
from trading_agent.data.resample import resample_ohlcv
from trading_agent.data.store import load_candles
from trading_agent.execution.instruments import InstrumentSpec
from trading_agent.features.build import atr, build_features, build_features_v2, model_columns
from trading_agent.labels.triple_barrier import triple_barrier
from trading_agent.models.baseline.rules import rule_signals
from trading_agent.models.xgboost_model.model import XGBoostModel
from trading_agent.risk.engine import RiskEngine
from trading_agent.risk.kill_switch import KillSwitch

BAR = {"15m": pd.Timedelta(minutes=15), "1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4), "1d": pd.Timedelta(days=1)}
MIN_TRADES = 30


@dataclass(frozen=True)
class ExperimentSpec:
    symbol: str
    source: str
    timeframe: str
    horizon_bars: int
    tp_mult: float
    sl_mult: float
    feature_set: str = "v2"
    train_window: int | None = None     # None = janela crescente; N = só as últimas N velas de treino

    @property
    def name(self) -> str:
        w = f"_janela{self.train_window}" if self.train_window else ""
        return f"{self.symbol.replace('/', '')}_{self.timeframe}_h{self.horizon_bars}_tp{self.tp_mult:g}_sl{self.sl_mult:g}_{self.feature_set}{w}"


@dataclass
class Prepared:
    spec: ExperimentSpec
    inst: InstrumentSpec
    bars: pd.DataFrame
    feats: pd.DataFrame
    data: pd.DataFrame           # features válidas (linhas com rótulo)
    cols: list[str]
    labels: dict[int, pd.DataFrame]
    t1: pd.Series
    sides: tuple[int, ...]


def load_bars(spec: ExperimentSpec, asset_class: str) -> pd.DataFrame:
    if spec.timeframe == "15m":
        return load_candles(spec.symbol, "15m", spec.source)
    return resample_ohlcv(load_candles(spec.symbol, "1h", spec.source), spec.timeframe, asset_class)


def prepare(spec: ExperimentSpec, cfg: AppConfig, bars: pd.DataFrame | None = None) -> Prepared:
    m = cfg.market(spec.symbol)
    inst = cfg.instrument(spec.symbol)
    bars = load_bars(spec, m["asset_class"]) if bars is None else bars
    extra_cost = (2 * inst.fee_bps + 2 * inst.slippage_bps + (0 if "spread" in bars.columns else inst.default_spread_bps)) / 1e4
    feats = build_features_v2(bars, 14, extra_cost) if spec.feature_set == "v2" else build_features(bars, 14)
    a = atr(bars, 14)
    sides = (1, -1) if inst.allow_short else (1,)
    labels = {s: triple_barrier(bars, a, s, spec.horizon_bars, spec.tp_mult, spec.sl_mult) for s in (1, -1)}
    cols = model_columns(feats)
    valid = feats[cols].notna().all(axis=1)
    for s in sides:
        valid &= labels[s]["label"].notna()
    data = feats.loc[valid]
    t1 = pd.concat([labels[s]["t1"] for s in sides], axis=1).max(axis=1)[valid]
    return Prepared(spec, inst, bars, feats, data, cols, labels, t1, sides)


def _expected_ret_map(p_cal: np.ndarray, r_cal: np.ndarray) -> IsotonicRegression:
    """Retorno bruto esperado em função da probabilidade, estimado na calibração (monótono)."""
    ok = ~np.isnan(p_cal) & ~np.isnan(r_cal)
    return IsotonicRegression(out_of_bounds="clip", increasing=True).fit(p_cal[ok], r_cal[ok])


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


@dataclass
class ModelOutput:
    prob: dict[int, pd.Series] = field(default_factory=dict)       # probabilidade calibrada (teste)
    exp_ret: dict[int, pd.Series] = field(default_factory=dict)    # retorno bruto esperado (teste)
    fold_metrics: list[dict] = field(default_factory=list)
    cal_prob: dict[int, dict[int, np.ndarray]] = field(default_factory=dict)  # fold → lado → prob. na calibração


def run_models(prep: Prepared, folds: list[Fold], models: tuple[str, ...], log=print) -> dict[str, ModelOutput]:
    d, cols = prep.data, prep.cols
    X = d[cols]
    y = {s: prep.labels[s]["label"].loc[d.index] for s in prep.sides}
    gr = {s: prep.labels[s]["gross_ret"].loc[d.index] for s in prep.sides}
    out = {k: ModelOutput({s: pd.Series(np.nan, index=d.index) for s in prep.sides},
                          {s: pd.Series(np.nan, index=d.index) for s in prep.sides}) for k in models}
    rule = rule_signals(d) if "A" in models else None
    t0 = time.time()
    for f in folds:
        train = f.train[-prep.spec.train_window:] if prep.spec.train_window else f.train
        fit_all = np.concatenate([train, f.val, f.calib])
        for s in prep.sides:
            ys, rs = y[s], gr[s]
            if "A" in models:
                m = (rule.iloc[fit_all] == s).to_numpy()
                p = float(ys.iloc[fit_all][m].mean()) if m.any() else np.nan
                e = float(rs.iloc[fit_all][m].mean()) if m.any() else np.nan
                te = f.test[(rule.iloc[f.test] == s).to_numpy()]
                out["A"].prob[s].iloc[te] = p
                out["A"].exp_ret[s].iloc[te] = e
            if "B" in models:
                mdl = XGBoostModel().fit(X.iloc[train], ys.iloc[train], X.iloc[f.val], ys.iloc[f.val], X.iloc[f.calib], ys.iloc[f.calib])
                p_cal = mdl.predict_proba(X.iloc[f.calib])
                emap = _expected_ret_map(p_cal, rs.iloc[f.calib].to_numpy())
                p_te = mdl.predict_proba(X.iloc[f.test])
                out["B"].prob[s].iloc[f.test] = p_te
                out["B"].exp_ret[s].iloc[f.test] = emap.predict(p_te)
                out["B"].cal_prob.setdefault(f.k, {})[s] = p_cal
                auc_in = roc_auc_score(ys.iloc[train], mdl.predict_raw(X.iloc[train])) if ys.iloc[train].nunique() > 1 else np.nan
                cm = classification_metrics(ys.iloc[f.test].to_numpy(), p_te)
                out["B"].fold_metrics.append({"fold": f.k, "lado": s, "auc_treino": round(float(auc_in), 4),
                                              **{k: cm.get(k) for k in ("roc_auc", "brier_skill", "ece", "taxa_base")}})
            if "C" in models:
                from trading_agent.models.neural_networks.gru import GRUModel

                g = GRUModel().fit(X, ys, train, f.val, f.calib)
                p_cal, okc = g.predict_proba(f.calib)
                emap = _expected_ret_map(p_cal, rs.iloc[okc].to_numpy())
                p_te, ok = g.predict_proba(f.test)
                out["C"].prob[s].iloc[ok] = p_te
                out["C"].exp_ret[s].iloc[ok] = emap.predict(p_te)
                out["C"].cal_prob.setdefault(f.k, {})[s] = (p_cal, okc)
                cm = classification_metrics(ys.iloc[ok].to_numpy(), p_te)
                out["C"].fold_metrics.append({"fold": f.k, "lado": s, **{k: cm.get(k) for k in ("roc_auc", "brier_skill", "ece", "taxa_base")}})
            if "D" in models and "B" in models and "C" in models:
                # Ensemble por empilhamento (regressão logística) ajustado na calibração: só se aceita
                # se melhorar fora da amostra (avaliado como qualquer outro modelo).
                pb_cal = out["B"].cal_prob[f.k][s]
                pc_cal, okc = out["C"].cal_prob[f.k][s]
                pos = np.searchsorted(f.calib, okc)
                Z = np.c_[_logit(pb_cal[pos]), _logit(pc_cal)]
                yc = ys.iloc[okc].to_numpy()
                if len(np.unique(yc)) > 1:
                    st = LogisticRegression(C=1.0).fit(Z, yc)
                    pd_cal = st.predict_proba(Z)[:, 1]
                    emap = _expected_ret_map(pd_cal, rs.iloc[okc].to_numpy())
                    pb_te = out["B"].prob[s].iloc[f.test].to_numpy()
                    pc_te = out["C"].prob[s].iloc[f.test].to_numpy()
                    ok = ~np.isnan(pb_te) & ~np.isnan(pc_te)
                    p_te = st.predict_proba(np.c_[_logit(pb_te[ok]), _logit(pc_te[ok])])[:, 1]
                    out["D"].prob[s].iloc[f.test[ok]] = p_te
                    out["D"].exp_ret[s].iloc[f.test[ok]] = emap.predict(p_te)
        log(f"  fold {f.k}: treino={len(train)} val={len(f.val)} calib={len(f.calib)} teste={len(f.test)} ({time.time() - t0:.0f}s)")
    if "A" in models:
        out["A"].rule = rule  # type: ignore[attr-defined]
    return out


def signals(prep: Prepared, mo: ModelOutput, idx: pd.Index, rule: pd.Series | None = None) -> pd.DataFrame:
    """Lado com maior retorno esperado; o risco decide se compensa os custos."""
    if rule is not None:
        side = rule.loc[idx].where(rule.loc[idx].isin(prep.sides), 0)
        prob = pd.Series(np.nan, index=idx)
        exp = pd.Series(np.nan, index=idx)
        for s in prep.sides:
            m = side == s
            prob[m] = mo.prob[s].loc[idx][m]
            exp[m] = mo.exp_ret[s].loc[idx][m]
        side = side.where(exp.notna(), 0)
        return pd.DataFrame({"side": side.astype(int), "prob": prob.fillna(0), "exp_ret": exp})
    E = pd.concat({s: mo.exp_ret[s].loc[idx] for s in prep.sides}, axis=1)
    P = pd.concat({s: mo.prob[s].loc[idx] for s in prep.sides}, axis=1)
    best = E.idxmax(axis=1)
    side = best.fillna(0).astype(int)
    exp = E.max(axis=1)
    prob = pd.Series([P.at[t, s] if s else np.nan for t, s in zip(idx, side, strict=True)], index=idx)
    side = side.where(exp.notna(), 0)
    return pd.DataFrame({"side": side, "prob": prob.fillna(0), "exp_ret": exp})


def _periods(prep: Prepared, folds: list[Fold], dev_splits: int) -> dict[str, pd.Index]:
    d = prep.data.index
    dev = np.concatenate([f.test for f in folds[:dev_splits]])
    hold = np.concatenate([f.test for f in folds[dev_splits:]]) if len(folds) > dev_splits else np.array([], int)
    return {"desenvolvimento": d[dev], "teste_final": d[hold]}


def regime_table(trades: pd.DataFrame, feats: pd.DataFrame) -> dict:
    """Expectativa por regime (terços de volatilidade relativa e de eficiência/tendência), nas operações."""
    if trades.empty or "vol_rel_24_168" not in feats.columns:
        return {}
    f = feats.loc[trades["signal_time"]]
    out = {}
    for col, nome in (("vol_rel_24_168", "volatilidade_relativa"), ("efficiency_24", "tendencia_eficiencia")):
        edges = feats[col].quantile([1 / 3, 2 / 3]).to_numpy()  # terços na amostra toda (descritivo)
        b = np.digitize(f[col].to_numpy(), edges)
        tab = {}
        for k, nm in enumerate(("baixo", "medio", "alto")):
            m = b == k
            if m.any():
                tab[nm] = {"operacoes": int(m.sum()), "bruto_bps": round(float(trades["gross_ret"].to_numpy()[m].mean()) * 1e4, 2),
                           "liquido_bps": round(float(trades["net_ret"].to_numpy()[m].mean()) * 1e4, 2)}
        out[nome] = tab
    return out


def classification_by_regime(prep: Prepared, mo: ModelOutput, idx: pd.Index) -> dict:
    if "vol_rel_24_168" not in prep.feats.columns:
        return {}
    s = prep.sides[0]
    y = prep.labels[s]["label"].loc[idx]
    p = mo.prob[s].loc[idx]
    vr = prep.feats["vol_rel_24_168"].loc[idx]
    edges = prep.feats["vol_rel_24_168"].quantile([1 / 3, 2 / 3]).to_numpy()
    b = np.digitize(vr.to_numpy(), edges)
    out = {}
    for k, nm in enumerate(("baixo", "medio", "alto")):
        m = (b == k) & p.notna().to_numpy()
        if m.sum() > 50 and y[m].nunique() > 1:
            out[nm] = round(float(roc_auc_score(y[m], p[m])), 4)
    return {"auc_lado_principal_por_volatilidade": out}


def label_consistency(prep: Prepared, trades: pd.DataFrame) -> dict:
    """Confere a rotulagem com a execução simulada: a barreira do rótulo é a saída real da operação?"""
    if trades.empty:
        return {}
    ok = 0
    for t in trades.itertuples():
        lab = prep.labels[int(t.side)]["barrier"].get(t.signal_time)
        real = {"sl_gap": "sl"}.get(t.reason, t.reason)
        ok += int(lab == real)
    return {"operacoes": len(trades), "saida_igual_ao_rotulo_pct": round(ok / len(trades) * 100, 2)}


def research_risk(cfg: AppConfig, inst: InstrumentSpec) -> RiskEngine:
    """Risco da investigação: limites por operação e custos como em produção; drawdown global e perda
    diária desligados para medir o modelo no período TODO (em produção param a estratégia); probabilidade
    mínima desligada porque o filtro que conta é a expectativa depois de custos (com TP a 2×ATR a taxa de
    TP-primeiro ronda 25% e um mínimo fixo de 0,40 vetaria tudo antes de olhar para a expectativa)."""
    lim = dataclasses.replace(cfg.risk, max_drawdown_pct=0.99, max_daily_loss_pct=0.99, min_capital=0.0, min_probability=0.0)
    return RiskEngine(lim, KillSwitch(None), inst.max_leverage)


def evaluate_period(prep: Prepared, sig: pd.DataFrame, risk: RiskEngine, capital: float, ppy: int,
                    fx_rate: pd.Series | None = None, currency: str | None = None) -> tuple[dict, pd.DataFrame]:
    spec = prep.spec
    bars = prep.bars.loc[(prep.bars.index >= sig.index.min()) & (prep.bars.index <= sig.index.max() + BAR[spec.timeframe] * spec.horizon_bars)]
    res = run_backtest(bars, prep.feats, sig, risk, BacktestConfig(prep.inst, spec.horizon_bars, spec.tp_mult, spec.sl_mult,
                                                                    capital, currency, BAR[spec.timeframe], fx_rate))
    m = trading_metrics(res.trades, res.equity, ppy)
    m["vetos_do_risco"] = res.vetoes
    if not res.trades.empty:
        m["ic95_expectativa_liquida_bps"] = {k: (round(v * 1e4, 2) if isinstance(v, float) and k != "prob_media_positiva" else v)
                                             for k, v in bootstrap_mean_ci(res.trades["net_ret"].to_numpy()).items()}
        m["ic95_expectativa_bruta_bps"] = {k: (round(v * 1e4, 2) if isinstance(v, float) and k != "prob_media_positiva" else v)
                                           for k, v in bootstrap_mean_ci(res.trades["gross_ret"].to_numpy()).items()}
        daily = res.equity.resample("1D").last().dropna().pct_change().dropna()
        m["monte_carlo"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in monte_carlo_equity(daily).items()}
    return m, res.trades


def buy_and_hold(prep: Prepared, idx: pd.Index) -> dict:
    c = prep.bars["close"].loc[idx.min(): idx.max()]
    return {"retorno_pct": round(float(c.iloc[-1] / c.iloc[0] - 1) * 100, 3), "max_drawdown_pct": round(max_drawdown(c) * 100, 3)}


def run_experiment(spec: ExperimentSpec, cfg: AppConfig, models: tuple[str, ...] = ("A", "B", "C"), n_splits: int = 6,
                   dev_splits: int = 4, test_frac: float = 0.6, capital: float = 10_000.0, log=print) -> tuple[dict, dict]:
    t0 = time.time()
    prep = prepare(spec, cfg)
    ppy = 252 if prep.inst.asset_class == "forex" else 365
    folds = walk_forward(prep.t1, n_splits, test_frac, val_frac=0.15, calib_frac=0.15, embargo=spec.horizon_bars)
    log(f"{spec.name}: {len(prep.data)} amostras, modelos {models}")
    outs = run_models(prep, folds, models, log)
    periods = _periods(prep, folds, dev_splits)
    risk = research_risk(cfg, prep.inst)
    cost_typ = prep.inst.round_trip_cost_pct(float(prep.feats["spread_bps"].median()) if "spread_bps" in prep.feats else None)
    dev_idx = periods["desenvolvimento"]
    atr_med = float(prep.feats["atr_pct"].loc[dev_idx].median())
    s0 = prep.sides[0]
    rep: dict = {
        "experiencia": spec.name, "spec": dataclasses.asdict(spec), "amostras": len(prep.data), "features": prep.cols,
        "periodos": {k: [str(v.min()), str(v.max())] if len(v) else None for k, v in periods.items()},
        "diagnostico_custos": {
            "custo_ida_volta_bps": round(cost_typ * 1e4, 2), "atr_mediano_pct": round(atr_med * 100, 4),
            "custo_em_atr": round(cost_typ / atr_med, 3),
            "prob_ponto_morto_tp_primeiro": round((spec.sl_mult * atr_med + cost_typ) / ((spec.tp_mult + spec.sl_mult) * atr_med), 4),
            "taxa_tp_primeiro_observada": round(float(prep.labels[s0]["label"].loc[dev_idx].mean()), 4),
            "retorno_bruto_medio_rotulo_bps": round(float(prep.labels[s0]["gross_ret"].loc[dev_idx].mean()) * 1e4, 2),
        },
        "modelos": {},
    }
    raw = {"prep": prep, "outs": outs, "periods": periods, "trades": {}}
    for k, mo in outs.items():
        r: dict = {"classificacao_por_fold": mo.fold_metrics}
        rule = getattr(mo, "rule", None) if k == "A" else None
        for pname, idx in periods.items():
            if not len(idx):
                continue
            sig = signals(prep, mo, idx, rule)
            m, trades = evaluate_period(prep, sig, risk, capital, ppy)
            y = prep.labels[s0]["label"].loc[idx]
            m["classificacao_lado_principal"] = classification_metrics(y.to_numpy(), mo.prob[s0].loc[idx].to_numpy()) if k != "A" else None
            if pname == "desenvolvimento":
                m["regimes"] = regime_table(trades, prep.feats)
                if k != "A":
                    m.update(classification_by_regime(prep, mo, idx))
                m["consistencia_rotulo_execucao"] = label_consistency(prep, trades)
            r[pname] = m
            raw["trades"][(k, pname)] = trades
        ci = r.get("desenvolvimento", {}).get("ic95_expectativa_liquida_bps", {})
        r["qualificado_no_desenvolvimento"] = bool(r.get("desenvolvimento", {}).get("operacoes", 0) >= MIN_TRADES
                                                   and isinstance(ci.get("ic_inf"), float) and ci["ic_inf"] > 0)
        rep["modelos"][{"A": "A_regras", "B": "B_xgboost", "C": "C_gru", "D": "D_ensemble_BC"}[k]] = r
    rep["referencias"] = {p: {"nao_negociar": {"retorno_pct": 0.0}, "comprar_e_manter": buy_and_hold(prep, idx)}
                          for p, idx in periods.items() if len(idx)}
    rep["duracao_s"] = round(time.time() - t0, 1)
    return rep, raw
