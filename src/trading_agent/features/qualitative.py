"""Componente qualitativa (EXPERIMENTAL, desligada por omissão): eventos e dados macro com datas fiáveis.

Regra única: um evento só pode influenciar a decisão de t se foi PUBLICADO até t
(`published_at <= t`). Para eventos agendados (reuniões de bancos centrais, divulgações de
inflação), o que se sabe antes é o AGENDAMENTO, não o resultado: o agendamento entra como
«evento de alto impacto nas próximas N horas»; o resultado só entra depois de publicado.
Para dados macro revistos (PIB, emprego), usar a primeira publicação (vintage), nunca a série
revista de hoje.

Sem uma fonte com timestamps históricos de publicação, este módulo não é usado nas
experiências (ver docs/research-results-fase2.md). Está aqui, testado, para quando houver.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Event:
    published_at: pd.Timestamp     # quando a informação ficou disponível
    effective_at: pd.Timestamp     # quando o evento acontece (≥ published_at para eventos agendados)
    category: str                  # «banco_central», «inflacao», «emprego», «geopolitica», …
    importance: int                # 1 (baixa) a 3 (alta)
    value: float | None = None     # resultado (surpresa, por exemplo), só para eventos já ocorridos


def events_frame(events: list[Event]) -> pd.DataFrame:
    df = pd.DataFrame([e.__dict__ for e in events])
    if df.empty:
        return pd.DataFrame(columns=["published_at", "effective_at", "category", "importance", "value"])
    for c in ("published_at", "effective_at"):
        df[c] = pd.to_datetime(df[c], utc=True)
    if (df["effective_at"] < df["published_at"]).any() and df.loc[df["effective_at"] < df["published_at"], "value"].isna().any():
        raise ValueError("evento agendado com efeito antes da publicação: datas inconsistentes")
    return df.sort_values("published_at").reset_index(drop=True)


DAY = pd.Timedelta(hours=24)


def qualitative_features(index: pd.DatetimeIndex, events: pd.DataFrame, ahead: pd.Timedelta = DAY,
                         behind: pd.Timedelta = DAY) -> pd.DataFrame:
    """Para cada instante de decisão t (fecho da vela), só com eventos publicados até t:
      · `evento_alto_impacto_proximo`: há evento importante agendado (conhecido em t) nas próximas `ahead`;
      · `eventos_recentes`: número de eventos ocorridos e publicados nas últimas `behind`;
      · `surpresa_recente`: soma dos valores publicados nas últimas `behind`.
    """
    out = pd.DataFrame(index=index, data={"evento_alto_impacto_proximo": 0, "eventos_recentes": 0, "surpresa_recente": 0.0})
    if events.empty:
        return out
    pub = events["published_at"].to_numpy()
    eff = events["effective_at"].to_numpy()
    imp = events["importance"].to_numpy()
    val = events["value"].astype(float).fillna(0.0).to_numpy()
    for i, t in enumerate(index.to_numpy()):
        known = pub <= t
        if not known.any():
            continue
        prox = known & (eff > t) & (eff <= t + np.timedelta64(int(ahead.total_seconds()), "s")) & (imp >= 3)
        rec = known & (eff <= t) & (eff > t - np.timedelta64(int(behind.total_seconds()), "s"))
        out.iat[i, 0] = int(prox.any())
        out.iat[i, 1] = int(rec.sum())
        out.iat[i, 2] = float(val[rec].sum())
    return out
