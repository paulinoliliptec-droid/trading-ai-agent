"""Auditoria retrospetiva das decisões: o que teria acontecido a cada compra rejeitada (ou aprovada).

Só leitura e sem reajuste: nenhum parâmetro do modelo ou do risco é escolhido a partir dos resultados.
Para cada decisão registada (vela t, decisão no fecho de t):
  · ATR(14) e features recalculados só com as velas FECHADAS até t, na mesma janela que o worker usa
    (LOOKBACK_BARS velas), o que permite também confirmar que a probabilidade guardada se reproduz;
  · compra hipotética na ABERTURA de t+1; TP = entrada + tp_mult × ATR(t), SL = entrada − sl_mult × ATR(t),
    limite temporal no fecho de t+horizon (as mesmas regras de `labels.triple_barrier`);
  · TP e SL na mesma vela: não se sabe a ordem, conta como SL (conservador) e fica assinalado;
  · custo = `custo_bps` registado na decisão (o custo que o risco usou nesse momento).

Estados: «tp», «sl», «tempo» (resolvido); «pendente» se o horizonte ainda não acabou e nenhuma barreira
foi tocada; «sem_dados» se faltam velas. «Subiu em 24 h» exige o horizonte completo.

As operações hipotéticas sobrepõem-se (uma por hora, cada uma com 24 h): não são somadas como carteira.
`sequencia_executavel` aplica a regra real do worker (uma posição por instrumento) para obter a sequência
que poderia de facto ter sido executada, sem sobreposição.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from trading_agent.features.build import build_features_v2

PROB_BINS = [0.0, 0.10, 0.20, 0.30, 0.40, 1.0]
PROB_LABELS = ["<0,10", "0,10–0,20", "0,20–0,30", "0,30–0,40", "≥0,40"]
HORA = pd.Timedelta(hours=1)
_PROB_REASON = re.compile(r"^probabilidade [\d.]+ < [\d.]+$")
RESOLVIDO = ("tp", "sl", "tempo")


@dataclass
class Barreiras:
    entrada_ts: pd.Timestamp | None
    entrada: float | None
    tp: float | None
    sl: float | None
    resultado: str                     # tp | sl | tempo | pendente | sem_dados
    saida_ts: pd.Timestamp | None
    saida: float | None
    ret_bruto: float | None            # fração; None se pendente
    ambigua: bool                      # TP e SL na mesma vela (contada como SL)
    velas_observadas: int
    fecho_24h: float | None            # fecho da vela t+horizon (None se o horizonte não acabou)
    max_favoravel: float | None        # maior subida (fração) até agora/ao fim do horizonte
    max_adversa: float | None          # maior queda (fração)
    ret_marcado: float | None          # retorno até à última vela fechada (pendentes: valor provisório)


def janela_causal(bars: pd.DataFrame, t: pd.Timestamp, lookback: int) -> pd.DataFrame:
    """Velas que o worker tinha no fecho de t: as `lookback - 1` fechadas que acabam em t (inclusive)."""
    w = bars.loc[:t]
    return w.iloc[-(lookback - 1):]


def barreiras(bars: pd.DataFrame, t: pd.Timestamp, atr: float, horizon: int, tp_mult: float, sl_mult: float,
              bar: pd.Timedelta = HORA) -> Barreiras:
    """Simula a compra na abertura de t+1. `bars` só pode conter velas FECHADAS."""
    nada = Barreiras(None, None, None, None, "sem_dados", None, None, None, False, 0, None, None, None, None)
    t1 = t + bar
    if t1 > bars.index[-1] and atr > 0:      # a vela de entrada ainda não fechou
        return Barreiras(t1, None, None, None, "pendente", None, None, None, False, 0, None, None, None, None)
    if t1 not in bars.index or not (atr > 0):
        return nada
    fim = t + bar * horizon
    fut = bars.loc[t1:fim]
    entrada = float(bars.at[t1, "open"])
    tp, sl = entrada + tp_mult * atr, entrada - sl_mult * atr
    hi, lo = fut["high"].to_numpy(float), fut["low"].to_numpy(float)
    mfe = float(hi.max() / entrada - 1)
    mae = float(lo.min() / entrada - 1)
    marcado = float(fut["close"].iloc[-1] / entrada - 1)
    completo = bars.index[-1] >= fim          # o horizonte já acabou (velas em falta no meio não o impedem)
    fecho = float(fut["close"].iloc[-1]) if completo else None
    for i, (ts, h, lw) in enumerate(zip(fut.index, hi, lo, strict=True)):
        hit_sl, hit_tp = lw <= sl, h >= tp
        if hit_sl or hit_tp:
            kind = "sl" if hit_sl else "tp"
            px = sl if hit_sl else tp
            return Barreiras(t1, entrada, tp, sl, kind, ts, px, px / entrada - 1, bool(hit_sl and hit_tp), i + 1,
                             fecho, mfe, mae, marcado)
    if completo:
        return Barreiras(t1, entrada, tp, sl, "tempo", fut.index[-1], fecho, fecho / entrada - 1, False, len(fut),
                         fecho, mfe, mae, marcado)
    return Barreiras(t1, entrada, tp, sl, "pendente", None, None, None, False, len(fut), None, mfe, mae, marcado)


def recalcular(bars: pd.DataFrame, t: pd.Timestamp, lookback: int, extra_cost: float, policy=None) -> dict:
    """ATR e (se houver `policy`) a proposta do modelo, só com dados até t."""
    w = janela_causal(bars, t, lookback)
    if w.empty or w.index[-1] != t:
        return {"atr_pct": np.nan, "atr": np.nan, "prob_recalc": np.nan}
    f = build_features_v2(w, 14, extra_cost)
    row = f.iloc[-1]
    out = {"atr_pct": float(row["atr_pct"]), "atr": float(row["atr_pct"] * w["close"].iloc[-1]), "prob_recalc": np.nan}
    if policy is not None:
        d = policy.decide(row)
        out["prob_recalc"] = float(d["prob"]) if d.get("prob") is not None else np.nan
    return out


def outros_vetos(motivos: list[str]) -> list[str]:
    """Motivos de veto que NÃO são o limite de probabilidade (para o contrafactual 0,40 → 0,30)."""
    return [m for m in motivos or [] if m != "aprovado" and not _PROB_REASON.match(m)]


def aprovaria(prob: float | None, motivos: list[str], limite: float) -> bool:
    """Decisão com o limite de probabilidade alterado e TODAS as outras regras como estavam registadas."""
    return prob is not None and prob >= limite and not outros_vetos(motivos)


def sequencia_executavel(df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    """Uma posição por instrumento (regra do worker): só entra se a anterior já saiu. Exclui pendentes."""
    rows, livre_desde = [], None
    for _, r in df[mask].sort_values("bar_time").iterrows():
        if livre_desde is not None and r["entrada_ts"] < livre_desde:
            continue
        if r["resultado"] not in ("tp", "sl", "tempo"):
            rows.append(r)
            break                       # posição ainda aberta: nada depois dela pode entrar
        rows.append(r)
        livre_desde = r["saida_ts"] + pd.Timedelta(hours=1)  # saída a meio/fim da vela: próxima vela livre
    return pd.DataFrame(rows)


def ic95(xs) -> tuple[float, float] | None:
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    h = 1.96 * sd / math.sqrt(len(xs))
    return (m - h, m + h)


def faixa(prob: float | None) -> str:
    if prob is None or (isinstance(prob, float) and math.isnan(prob)):
        return "sem prob."
    return str(pd.cut([prob], PROB_BINS, labels=PROB_LABELS, right=False)[0])


def custo_extra(inst) -> float:
    """Custo de ida e volta (fração) que o worker passa às features: comissões, slippage e spread se não for bid."""
    return (2 * inst.fee_bps + 2 * inst.slippage_bps + (0 if inst.price_basis == "bid" else inst.default_spread_bps)) / 1e4


def carregar_decisoes(sec, symbol: str, inicio, fim, ficheiro: str | None = None) -> list[dict]:
    """Decisões do Atlas (só `find`) ou de um JSON exportado, na janela [inicio, fim], sem duplicados."""
    if ficheiro:
        import json

        docs = json.loads(open(ficheiro).read())
    else:
        from trading_agent.persistence.repository import MongoRepository

        repo = MongoRepository.from_uri(sec.mongodb_uri.get_secret_value())   # sem ensure_indexes: só leitura
        docs = list(repo.db["decisions"].find({"tenant_id": sec.tenant_id, "symbol": symbol}, {"_id": 0}))
    ini, fim = pd.Timestamp(inicio), pd.Timestamp(fim)
    ini = ini if ini.tzinfo else ini.tz_localize("UTC")
    fim = fim if fim.tzinfo else fim.tz_localize("UTC")
    docs = [d for d in docs if ini <= pd.Timestamp(d["bar_time"]) <= fim]
    unicos = {d["decision_id"]: d for d in sorted(docs, key=lambda d: d["ts"])}  # o índice único já o garante
    return sorted(unicos.values(), key=lambda d: d["bar_time"])


def precos(symbol: str, ini: pd.Timestamp, agora) -> pd.DataFrame:
    """Velas horárias FECHADAS da Coinbase (a fonte do modelo), com a janela de aquecimento antes de `ini`."""
    from trading_agent.agent.worker import LOOKBACK_BARS
    from trading_agent.brokers.crypto.coinbase import CoinbaseMarketData
    from trading_agent.data.quality import clean_ohlcv

    raw = CoinbaseMarketData().historical(symbol, "1h", (ini - HORA * (LOOKBACK_BARS + 10)).to_pydatetime(), agora)
    bars, _ = clean_ohlcv(raw, "1h", "24/7")
    return bars[bars.index + HORA <= agora]


def tabela(dec: list[dict], bars: pd.DataFrame, pol: dict, extra_cost: float, lim_alt: float = 0.30) -> pd.DataFrame:
    """Uma linha por decisão: probabilidade registada e recalculada, barreiras e resultado da compra hipotética.

    `pol` = {model_id: (policy, meta)} carregados do registo (SHA-256 verificado).
    """
    from trading_agent.agent.worker import LOOKBACK_BARS

    linhas = []
    for d in dec:
        policy, meta = pol[d["model_id"]]
        t = pd.Timestamp(d["bar_time"])
        r = recalcular(bars, t, LOOKBACK_BARS, extra_cost, policy)
        b = barreiras(bars, t, r["atr"], int(meta["horizon_bars"]), float(meta["tp_mult"]), float(meta["sl_mult"]))
        prop = d.get("proposta") or {}
        prob = prop.get("prob")
        custo = float(d.get("custo_bps") or 0.0)
        bruto = None if b.ret_bruto is None else b.ret_bruto * 1e4
        r24 = None if b.fecho_24h is None else (b.fecho_24h / b.entrada - 1) * 1e4
        linhas.append({
            "decision_id": d["decision_id"], "bar_time": t, "decidido_em": d.get("ts"), "model_id": d["model_id"],
            "modo": d.get("modo"), "lado": prop.get("side"), "prob": prob, "prob_recalculada": r["prob_recalc"],
            "exp_ret_bruto_bps": None if prop.get("exp_ret") is None else prop["exp_ret"] * 1e4,
            "custo_bps": custo, "expectativa_liquida_bps": d.get("expectativa_bps"), "aprovado": bool(d.get("aprovado")),
            "motivos": " | ".join(d.get("motivos") or []), "outros_vetos": " | ".join(outros_vetos(d.get("motivos"))),
            "faixa_prob": faixa(prob), f"aprovaria_{lim_alt:.2f}": aprovaria(prob, d.get("motivos"), lim_alt),
            "idade_dados_velas": d.get("idade_dados_velas"), "atr_pct": r["atr_pct"], "atr_usd": r["atr"],
            "entrada_ts": b.entrada_ts, "entrada": b.entrada, "take_profit": b.tp, "stop_loss": b.sl,
            "resultado": b.resultado, "tp_e_sl_mesma_vela": b.ambigua, "saida_ts": b.saida_ts, "saida": b.saida,
            "velas_observadas": b.velas_observadas,
            "ret_bruto_bps": bruto, "ret_liquido_bps": None if bruto is None else bruto - custo,
            "rentavel_liquido": None if bruto is None else bool(bruto - custo > 0),
            "fecho_24h": b.fecho_24h, "ret_24h_bps": r24, "subiu_24h": None if r24 is None else bool(r24 > 0),
            "ret_24h_liquido_bps": None if r24 is None else r24 - custo,
            "max_favoravel_bps": None if b.max_favoravel is None else b.max_favoravel * 1e4,
            "max_adverso_bps": None if b.max_adversa is None else b.max_adversa * 1e4,
            "ret_marcado_bps": None if b.ret_marcado is None else b.ret_marcado * 1e4,
        })
    return pd.DataFrame(linhas)
