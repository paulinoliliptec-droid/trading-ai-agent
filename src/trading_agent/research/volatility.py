"""Hipótese 3: previsão da volatilidade diária e dimensionamento por volatilidade-alvo.

Pré-registo em docs/h3-volatilidade-preregisto.md (critérios fixos antes de correr). Tudo aqui é causal: a
previsão para o dia t+1 só usa velas até ao fim do dia t e modelos ajustados com alvos já conhecidos.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from trading_agent.backtesting.metrics import max_drawdown
from trading_agent.backtesting.uncertainty import stationary_bootstrap_indices

FORECASTERS = ("EWMA", "HAR", "XGB")


@dataclass(frozen=True)
class VolSpec:
    symbol: str
    week: int = 7            # janelas do HAR: 7/30 dias no BTC (24/7), 5/22 no EUR/USD (dias úteis)
    month: int = 30
    min_train_days: int = 365
    refit_every: int = 30
    min_hours: int = 20      # horas mínimas para um dia contar
    ewma_lambda: float = 0.94


def daily_table(hourly: pd.DataFrame, spec: VolSpec) -> pd.DataFrame:
    """Uma linha por dia UTC: RV e as features que só usam esse dia e os anteriores."""
    r = np.log(hourly["close"]).diff()
    day = hourly.index.floor("D")
    g = pd.DataFrame({"r": r, "r2": r ** 2, "neg2": (r.clip(upper=0)) ** 2, "high": hourly["high"], "low": hourly["low"],
                      "close": hourly["close"], "volume": hourly["volume"], "hour": hourly.index.hour}, index=hourly.index)
    g["last6"] = np.where(g["hour"] >= 18, g["r2"], 0.0)
    d = g.groupby(day).agg(n=("r", "count"), rv2=("r2", "sum"), neg2=("neg2", "sum"), last6=("last6", "sum"),
                           high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum"))
    d = d[d["n"] >= spec.min_hours].copy()
    d["rv"] = np.sqrt(d["rv2"])
    d["ret"] = np.log(d["close"]).diff()                       # dia a dia entre dias válidos consecutivos
    lrv = np.log(d["rv"])
    d["x_d"] = lrv
    d["x_w"] = 0.5 * np.log(d["rv2"].rolling(spec.week).mean())
    d["x_m"] = 0.5 * np.log(d["rv2"].rolling(spec.month).mean())
    d["x_last6"] = 0.5 * np.log(d["last6"] * 24 / 6 + 1e-12)
    d["x_neg"] = 0.5 * np.log(d["neg2"] + 1e-12)
    d["x_absret"] = np.log(d["ret"].abs() + 1e-6)
    d["x_range"] = np.log((d["high"] - d["low"]) / d["close"] + 1e-6)
    d["x_volz"] = np.log(d["volume"] + 1) - np.log(d["volume"] + 1).rolling(spec.month).mean()
    d["y"] = lrv.shift(-1)                                     # alvo: log RV do dia seguinte
    d["rv_next"] = d["rv"].shift(-1)
    d["ret_next"] = d["ret"].shift(-1)
    return d.dropna(subset=["x_m", "x_volz"])


HAR_COLS = ["x_d", "x_w", "x_m"]
XGB_COLS = HAR_COLS + ["x_last6", "x_neg", "x_absret", "x_range", "x_volz"]


def _fit_har(tr: pd.DataFrame):
    X = np.column_stack([np.ones(len(tr)), tr[HAR_COLS].to_numpy()])
    beta, *_ = np.linalg.lstsq(X, tr["y"].to_numpy(), rcond=None)
    resid = tr["y"].to_numpy() - X @ beta
    return beta, float(np.mean(np.exp(2 * resid)))             # smearing para passar de log RV a variância


def forecasts(d: pd.DataFrame, spec: VolSpec, seed: int = 0) -> pd.DataFrame:
    """Previsões fora da amostra da VARIÂNCIA do dia seguinte (colunas EWMA, HAR, XGB), a partir do dia
    `min_train_days`. Reajuste a cada `refit_every` dias com as linhas cujo alvo já é conhecido."""
    n = len(d)
    out = pd.DataFrame(index=d.index[spec.min_train_days:], columns=list(FORECASTERS), dtype=float)
    # EWMA: recursivo, causal por construção
    ew = np.empty(n)
    ew[0] = d["rv2"].iloc[: spec.week].mean()
    for i in range(1, n):
        ew[i] = spec.ewma_lambda * ew[i - 1] + (1 - spec.ewma_lambda) * d["rv2"].iloc[i]
    out["EWMA"] = ew[spec.min_train_days:]
    for start in range(spec.min_train_days, n, spec.refit_every):
        tr = d.iloc[: start - 1].dropna(subset=["y"])          # o alvo da linha start-1 é o próprio dia start: fora
        blk = d.iloc[start: start + spec.refit_every]
        beta, smear = _fit_har(tr)
        Xb = np.column_stack([np.ones(len(blk)), blk[HAR_COLS].to_numpy()])
        out.loc[blk.index, "HAR"] = np.exp(2 * (Xb @ beta)) * smear
        m = XGBRegressor(n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
                         min_child_weight=10, random_state=seed, n_jobs=2)
        m.fit(tr[XGB_COLS], tr["y"])
        res = tr["y"].to_numpy() - m.predict(tr[XGB_COLS])
        out.loc[blk.index, "XGB"] = np.exp(2 * m.predict(blk[XGB_COLS])) * float(np.mean(np.exp(2 * res)))
    return out


def qlike(rv2: np.ndarray, h: np.ndarray) -> np.ndarray:
    x = rv2 / h
    return x - np.log(x) - 1


def paired_ci(a: np.ndarray, b: np.ndarray, stat, n_boot: int = 2000, block: float = 20.0, seed: int = 42) -> dict:
    """IC95% de stat(a) - stat(b) com bootstrap estacionário EMPARELHADO (os mesmos dias nas duas séries)."""
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for k in range(n_boot):
        i = stationary_bootstrap_indices(len(a), block, rng)
        diffs[k] = stat(a[i]) - stat(b[i])
    lo, hi = np.quantile(diffs, [0.025, 0.975])
    return {"dif": float(stat(a) - stat(b)), "ic_inf": float(lo), "ic_sup": float(hi), "prob_positiva": float((diffs > 0).mean())}


def forecast_quality(d: pd.DataFrame, fc: pd.DataFrame, idx: pd.Index) -> dict:
    rv2 = d.loc[idx, "rv_next"].to_numpy() ** 2
    y = d.loc[idx, "y"].to_numpy()
    ok = ~np.isnan(rv2) & (rv2 > 0)
    res = {}
    base = qlike(rv2[ok], fc.loc[idx, "HAR"].to_numpy()[ok])
    for f in FORECASTERS:
        h = fc.loc[idx, f].to_numpy()[ok]
        ql = qlike(rv2[ok], h)
        res[f] = {"qlike": float(ql.mean()), "mse_log": float(np.mean((y[ok] - 0.5 * np.log(h)) ** 2)),
                  "r2_log": float(1 - np.mean((y[ok] - 0.5 * np.log(h)) ** 2) / np.var(y[ok])),
                  "qlike_menos_HAR": None if f == "HAR" else paired_ci(ql, base, np.mean, block=10.0)}
    res["dias"] = int(ok.sum())
    return res


def sharpe(r: np.ndarray, ppy: int = 365) -> float:
    s = r.std(ddof=1)
    return float(r.mean() / s * np.sqrt(ppy)) if s > 0 else 0.0


def vol_target_returns(d: pd.DataFrame, var_fc: pd.Series, target_ann: float, cost_bps: float, band: float = 0.10,
                       ppy: int = 365) -> pd.DataFrame:
    """Retornos diários líquidos: peso decidido no fecho do dia t (com a previsão para t+1) aplicado a t+1."""
    tgt = target_ann / np.sqrt(ppy)
    w_raw = np.minimum(1.0, tgt / np.sqrt(var_fc.to_numpy()))
    w = np.empty_like(w_raw)
    prev = 0.0
    for i, x in enumerate(w_raw):
        prev = x if abs(x - prev) >= band or i == 0 else prev
        w[i] = prev
    turnover = np.abs(np.diff(np.concatenate([[0.0], w])))
    ret = d.loc[var_fc.index, "ret_next"].to_numpy()
    simple = np.expm1(ret)
    net = w * simple - turnover * cost_bps / 1e4
    return pd.DataFrame({"w": w, "turnover": turnover, "gross": w * simple, "net": net, "asset": simple}, index=var_fc.index)


def perf(r: np.ndarray, ppy: int = 365) -> dict:
    eq = pd.Series(np.cumprod(1 + r))
    return {"retorno_total_pct": float((eq.iloc[-1] - 1) * 100), "vol_anual_pct": float(r.std(ddof=1) * np.sqrt(ppy) * 100),
            "sharpe": sharpe(r, ppy), "max_drawdown_pct": float(max_drawdown(eq) * 100)}
