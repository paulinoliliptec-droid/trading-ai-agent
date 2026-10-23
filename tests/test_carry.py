"""Hipótese 4: contabilidade do carry (funding no dia certo, base, custos, capital com margem, sinal causal)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_agent.research.carry import daily_table, positions, simulate


def _dados(dias: int = 30, rate: float = 1e-4, prem: float = 0.0):
    ev = pd.date_range("2024-01-01 00:00:00.001", periods=dias * 3, freq="8h", tz="UTC")
    funding = pd.Series(rate, index=ev)
    hours = pd.date_range("2024-01-01", periods=dias * 24, freq="h", tz="UTC")
    premium = pd.Series(prem, index=hours)
    return funding, premium


def test_evento_das_zero_horas_pertence_ao_dia_anterior():
    funding, premium = _dados()
    d = daily_table(funding, premium)
    # dia completo: eventos às 08:00 e 16:00 do próprio dia e às 00:00 do seguinte
    assert (d["n_eventos"].iloc[1:-1] == 3).all()
    assert np.isclose(d["funding"].iloc[5], 3e-4)


def test_funding_constante_sem_base_da_o_carry_menos_custos_sobre_o_capital():
    funding, premium = _dados(rate=1e-4)
    d = daily_table(funding, premium)
    r = simulate(d, "sempre", cost_bps_por_lado=10.0, margin=0.5)
    esperado = (len(d) * 3e-4 - 2 * 10 / 1e4) / 1.5
    assert np.isclose(r["liquido"].sum(), esperado)
    assert np.isclose(r["base"].abs().sum(), 0.0)


def test_subida_do_premio_custa_a_perna_vendida():
    funding, premium = _dados(rate=0.0)
    premium.iloc[24 * 10:] = 0.002          # o perpétuo fica 20 bps acima do índice a partir do dia 10
    d = daily_table(funding, premium)
    r = simulate(d, "sempre", 0.0, margin=0.0)
    assert np.isclose(r["liquido"].sum(), -0.002)


def test_condicional_so_entra_depois_de_o_sinal_ser_conhecido():
    funding, premium = _dados(dias=40, rate=-1e-4)
    funding.iloc[60:] = 3e-4                 # passa a ~33% ao ano a partir do dia 20
    d = daily_table(funding, premium)
    s = positions(d, "condicional")
    primeiro = d.index[np.argmax(s)]
    sinal_ok = d.index[np.argmax(d["funding_72h_anual"].to_numpy() > 0.10)]
    assert primeiro > sinal_ok and s[: list(d.index).index(sinal_ok) + 1].sum() == 0
