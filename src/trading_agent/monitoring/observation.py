"""Relatório do período de observação: o que o agente decidiu e o que o mercado fez a seguir.

Só lê registos (decisões, vetos, eventos, equity, operações) e preços posteriores; não treina nem aprova
nada. A qualidade preditiva é medida fora da amostra por construção: cada decisão foi tomada com a vela
fechada e o modelo já gravado, e compara-se com o movimento das `horizon` velas SEGUINTES.

Limite assumido: o resultado compara o retorno no fim do horizonte, não a ordem em que as barreiras
(TP/SL) seriam tocadas; serve para ver se a direção proposta acerta mais do que o acaso depois de custos.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Avaliacao:
    n_decisoes: int = 0
    n_sinais: int = 0                       # decisões com lado proposto (≠ 0)
    n_aprovados: int = 0
    n_rejeitados: int = 0
    motivos_veto: Counter = field(default_factory=Counter)
    n_avaliados: int = 0                    # sinais com horizonte já decorrido e preços disponíveis
    acertos: int = 0
    ret_bruto_bps: list[float] = field(default_factory=list)
    ret_liquido_bps: list[float] = field(default_factory=list)
    brier: list[float] = field(default_factory=list)

    @property
    def taxa_acerto(self) -> float | None:
        return self.acertos / self.n_avaliados if self.n_avaliados else None

    def resumo(self) -> dict:
        def media(xs):
            return sum(xs) / len(xs) if xs else None

        def ic95(xs):
            if len(xs) < 2:
                return None
            m = media(xs)
            sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
            h = 1.96 * sd / math.sqrt(len(xs))
            return (m - h, m + h)

        return {"decisoes": self.n_decisoes, "sinais": self.n_sinais, "aprovados": self.n_aprovados,
                "rejeitados": self.n_rejeitados, "motivos_veto": dict(self.motivos_veto.most_common(8)),
                "avaliados": self.n_avaliados, "taxa_acerto": self.taxa_acerto,
                "ret_bruto_medio_bps": media(self.ret_bruto_bps), "ret_liquido_medio_bps": media(self.ret_liquido_bps),
                "ic95_liquido_bps": ic95(self.ret_liquido_bps), "brier": media(self.brier)}


def avaliar(decisoes: list[dict], precos: pd.Series, bar: pd.Timedelta, horizon: int) -> Avaliacao:
    """`precos`: fechos indexados pela hora de ABERTURA da vela (UTC), no timeframe do modelo."""
    a = Avaliacao()
    for d in decisoes:
        a.n_decisoes += 1
        prop = d.get("proposta") or {}
        side = int(prop.get("side") or 0)
        if d.get("aprovado"):
            a.n_aprovados += 1
        else:
            a.n_rejeitados += 1
            for m in d.get("motivos") or []:
                a.motivos_veto[re.sub(r"[-+]?\d+(\.\d+)?", "#", m)] += 1   # agrupa sem os valores
        if not side:
            continue
        a.n_sinais += 1
        t0 = pd.Timestamp(d["bar_time"])
        t1 = t0 + bar * horizon
        if t0 not in precos.index or t1 not in precos.index:
            continue                                       # horizonte ainda a decorrer ou vela em falta
        bruto = side * (precos[t1] / precos[t0] - 1) * 1e4
        liquido = bruto - float(d.get("custo_bps") or 0.0)
        a.n_avaliados += 1
        a.acertos += int(bruto > 0)
        a.ret_bruto_bps.append(bruto)
        a.ret_liquido_bps.append(liquido)
        if prop.get("prob") is not None:
            a.brier.append((float(prop["prob"]) - float(liquido > 0)) ** 2)
    return a


def contagem_eventos(eventos: list[dict]) -> dict:
    return {"por_nivel": dict(Counter(e.get("level") for e in eventos)),
            "erros": dict(Counter(e.get("kind") for e in eventos if e.get("level") in ("error", "critical")).most_common(10))}
