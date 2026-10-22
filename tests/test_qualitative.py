"""Componente qualitativa: nada publicado depois da decisão pode entrar nela."""

from __future__ import annotations

import pandas as pd

from trading_agent.features.qualitative import Event, events_frame, qualitative_features


def test_so_entra_o_que_ja_foi_publicado():
    idx = pd.date_range("2026-03-01", periods=72, freq="1h", tz="UTC")
    ev = events_frame([
        # reunião agendada a 01/03 00:00 para 02/03 18:00, resultado publicado às 18:30
        Event(pd.Timestamp("2026-03-01 00:00", tz="UTC"), pd.Timestamp("2026-03-02 18:00", tz="UTC"), "banco_central", 3),
        Event(pd.Timestamp("2026-03-02 18:30", tz="UTC"), pd.Timestamp("2026-03-02 18:00", tz="UTC"), "banco_central", 3, value=0.25),
    ])
    f = qualitative_features(idx, ev)
    # 24 h antes da reunião o agendamento já é conhecido
    assert f.loc["2026-03-01 19:00", "evento_alto_impacto_proximo"].item() == 1
    assert f.loc["2026-03-01 17:00", "evento_alto_impacto_proximo"].item() == 0
    # o resultado (surpresa) NÃO entra às 18:00, só depois de publicado às 18:30
    assert f.loc["2026-03-02 18:00", "surpresa_recente"].item() == 0.0
    assert f.loc["2026-03-02 19:00", "surpresa_recente"].item() == 0.25


def test_mudar_eventos_futuros_nao_muda_o_passado():
    idx = pd.date_range("2026-03-01", periods=48, freq="1h", tz="UTC")
    base = [Event(pd.Timestamp("2026-03-01 05:00", tz="UTC"), pd.Timestamp("2026-03-01 05:00", tz="UTC"), "inflacao", 2, 0.1)]
    extra = base + [Event(pd.Timestamp("2026-03-02 10:00", tz="UTC"), pd.Timestamp("2026-03-02 12:00", tz="UTC"), "emprego", 3, 9.0)]
    a = qualitative_features(idx, events_frame(base))
    b = qualitative_features(idx, events_frame(extra))
    corte = pd.Timestamp("2026-03-02 09:00", tz="UTC")
    pd.testing.assert_frame_equal(a[a.index <= corte], b[b.index <= corte])
