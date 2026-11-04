"""Auditoria semanal: a «nota» do robô, em linguagem simples, para o Telegram.

Só reporta; não escolhe nem altera nada (modelo, limites de risco, operação). Usa a mesma tabela da auditoria
retrospetiva (`audit.tabela`): cada decisão é avaliada como compra hipotética com as regras do `triple_barrier`.

Janelas: uma decisão só tem resultado depois do horizonte (24 velas), por isso a «semana» avaliada são as 7 × 24
decisões que acabam `horizonte` horas antes da última vela fechada. O «acumulado» vai da primeira decisão até ao
mesmo fim. As decisões mais recentes entram no relatório seguinte.

Regra fixa para a palavra «sinal» (definida antes de ver os resultados futuros, e não ajustada depois):
AUC acumulado ≥ 0,55 e pelo menos 90 dias de decisões. Abaixo disso, a mensagem diz que não há habilidade
demonstrada, mesmo que uma semana isolada corra bem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from trading_agent.monitoring.audit import RESOLVIDO

AUC_SINAL = 0.55
DIAS_SINAL = 90


def auc(y, p) -> float | None:
    """Área sob a curva ROC (Mann-Whitney com empates a meio). None se só houver uma classe."""
    s = pd.DataFrame({"y": list(y), "p": list(p)}).dropna()
    pos, neg = int((s["y"] == 1).sum()), int((s["y"] == 0).sum())
    if pos == 0 or neg == 0:
        return None
    r = s["p"].rank(method="average")
    return float((r[s["y"] == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


def nota(df: pd.DataFrame) -> dict:
    """Métricas de acerto das decisões já resolvidas (tp, sl ou tempo)."""
    r = df[df["resultado"].isin(RESOLVIDO)]
    out = {"decisoes": len(df), "resolvidas": len(r), "aprovadas": int(df["aprovado"].sum()) if len(df) else 0,
           "dias": int(pd.to_datetime(r["bar_time"]).dt.floor("D").nunique()) if len(r) else 0}
    if not len(r):
        return out
    y = (r["resultado"] == "tp").astype(int)
    liq = r["ret_liquido_bps"].astype(float)
    aprov = r[r["aprovado"]]
    rej = r[~r["aprovado"]]
    out.update({
        "tp": int(y.sum()),
        "rejeicoes": len(rej),
        "rejeicoes_certas": int((rej["ret_liquido_bps"] <= 0).sum()),
        "aprovadas_resolvidas": len(aprov),
        "aprovadas_certas": int((aprov["ret_liquido_bps"] > 0).sum()),
        "ret_liq_medio_bps": float(liq.mean()),
        "ret_bruto_medio_bps": float(r["ret_bruto_bps"].astype(float).mean()),
        "prob_media": float(r["prob"].astype(float).mean()),
        "freq_tp": float(y.mean()),
        "auc": auc(y, r["prob"].astype(float)),
        "spearman": _spearman(r["exp_ret_bruto_bps"], r["ret_bruto_bps"]),
    })
    return out


def _spearman(a: pd.Series, b: pd.Series) -> float | None:
    s = pd.DataFrame({"a": a.astype(float), "b": b.astype(float)}).dropna()
    if len(s) < 3 or s["a"].nunique() < 2 or s["b"].nunique() < 2:
        return None
    v = s["a"].rank().corr(s["b"].rank())
    return None if math.isnan(v) else float(v)


@dataclass
class Saude:
    esperadas: int          # uma decisão por vela fechada na janela
    registadas: int
    erros: int              # eventos de nível «error» (falhas de API, etc.)
    recuperados: int

    @property
    def em_falta(self) -> int:
        return max(self.esperadas - self.registadas, 0)


def saude(dec: list[dict], eventos: list[dict], ini: pd.Timestamp, fim: pd.Timestamp) -> Saude:
    horas = len(pd.date_range(ini, fim, freq="1h"))
    reg = len({d["bar_time"] for d in dec if ini <= pd.Timestamp(d["bar_time"]) <= fim})
    ev = [e for e in eventos if ini <= pd.Timestamp(e["ts"]) <= fim + pd.Timedelta(hours=1)]
    return Saude(horas, reg, sum(e.get("level") == "error" for e in ev), sum(e.get("kind") == "recuperado" for e in ev))


def veredicto(acum: dict) -> str:
    a, dias = acum.get("auc"), acum.get("dias", 0)
    if a is None:
        return "ainda sem decisões resolvidas suficientes para dar nota."
    if a >= AUC_SINAL and dias >= DIAS_SINAL:
        return (f"possível habilidade (nota ≥ {AUC_SINAL:.2f} em {dias} dias). Vale uma avaliação a sério antes de "
                "pensar em dinheiro real.")
    if a >= AUC_SINAL:
        return (f"nota boa, mas só {dias} dias (precisa de {DIAS_SINAL}). Pode ser sorte: continuar a observar.")
    return "o robô ainda não mostra habilidade para prever. A proteção (não comprar) continua a ser o certo."


def _pct(x: float | None, casas: int = 2) -> str:
    return "—" if x is None else f"{x / 100:+.{casas}f}%".replace(".", ",")


def _num(x: float | None, casas: int = 2) -> str:
    return "—" if x is None else f"{x:.{casas}f}".replace(".", ",")


def _taxa(a: int, b: int) -> str:
    return "—" if not b else f"{a}/{b} ({a / b:.0%})"


def _data(t: pd.Timestamp) -> str:
    return f"{t:%d/%m}"


def mensagem(simbolo: str, ini: pd.Timestamp, fim: pd.Timestamp, semana: dict, acum: dict, s: Saude,
             btc: tuple[float, float] | None, historico: list[float | None] | None = None) -> str:
    """Texto simples (sem HTML: o notificador escapa-o). `historico` = notas (AUC) das semanas anteriores."""
    linhas = [f"Auditoria semanal {simbolo} · {_data(ini)} → {_data(fim)}", ""]
    linhas.append("🤖 Funcionamento")
    ok = "✅" if s.em_falta == 0 else "⚠️"
    linhas.append(f"{ok} Decisões: {s.registadas}/{s.esperadas}" + (f" ({s.em_falta} em falta)" if s.em_falta else ""))
    perda = "nenhuma decisão perdida" if s.em_falta == 0 else f"{s.em_falta} decisões perdidas"
    linhas.append(f"Falhas de ligação: {s.erros} ({perda})")
    linhas.append(f"Compras feitas: {semana.get('aprovadas', 0)}")
    linhas.append("")
    linhas.append("🎯 Decisões da semana")
    if semana.get("resolvidas"):
        linhas.append(f"Não comprar estava certo: {_taxa(semana['rejeicoes_certas'], semana['rejeicoes'])}")
        if semana.get("aprovadas_resolvidas"):
            linhas.append(f"Compras com lucro: {_taxa(semana['aprovadas_certas'], semana['aprovadas_resolvidas'])}")
        linhas.append(f"Se comprasse sempre: {_pct(semana['ret_liq_medio_bps'])} por operação, depois de custos")
    else:
        linhas.append("Sem decisões resolvidas nesta semana.")
    linhas.append("")
    linhas.append("📊 Nota do robô (0,50 = moeda ao ar; 1,00 = perfeito)")
    linhas.append(f"Esta semana: {_num(semana.get('auc'))}")
    linhas.append(f"Desde o início ({acum.get('dias', 0)} dias): {_num(acum.get('auc'))}")
    prev = [h for h in (historico or []) if h is not None][-4:]
    if prev:
        linhas.append("Semanas anteriores: " + " · ".join(_num(h) for h in prev))
    linhas.append("")
    if btc:
        a, b = btc
        linhas.append(f"₿ {simbolo}: {a:,.0f} → {b:,.0f} ({(b / a - 1):+.1%})".replace(",", " ").replace(".", ","))
        linhas.append("")
    linhas.append("👉 " + veredicto(acum))
    return "\n".join(linhas)
