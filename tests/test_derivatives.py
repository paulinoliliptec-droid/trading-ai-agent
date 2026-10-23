"""Hipótese 2: os dados de derivados ficam alinhados ao fecho da vela e as features não veem o futuro."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading_agent.data.derivatives import derivative_features, hourly_table, resample_hourly


def _fontes(n: int = 24 * 40, seed: int = 3):
    rng = np.random.default_rng(seed)
    hours = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    funding = pd.Series(rng.normal(1e-4, 5e-5, n // 8), index=hours[::8][: n // 8])          # publicado às 00, 08, 16
    premium = pd.Series(rng.normal(0, 3e-4, n), index=hours)
    vol = rng.uniform(100, 200, n)
    taker = pd.DataFrame({"spot_volume": vol, "taker_buy": vol * rng.uniform(0.4, 0.6, n)}, index=hours)
    oi = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.01, n))) * 1e4, index=hours)              # instantâneo no início da hora
    return hours, funding, premium, taker, oi


def test_alinhamento_ao_fecho_da_vela():
    hours, funding, premium, taker, oi = _fontes()
    h = hourly_table(funding, premium, taker, oi, hours)
    # a vela das 07:00 fecha às 08:00: o funding publicado às 08:00 já é conhecido, o das 16:00 ainda não
    assert h.loc[hours[7], "funding"] == funding.loc[hours[8]]
    assert h.loc[hours[6], "funding"] == funding.loc[hours[0]]
    # OI: o instantâneo do fecho (hora seguinte), nunca um posterior
    assert h.loc[hours[5], "oi"] == oi.loc[hours[6]]
    assert h.loc[hours[5], "premio"] == premium.loc[hours[5]]


def test_features_nao_usam_o_futuro():
    hours, funding, premium, taker, oi = _fontes()
    corte = hours[600]
    base = derivative_features(hourly_table(funding, premium, taker, oi, hours), 1)

    def mexe(x):
        x = x.copy()
        x[x.index > corte] = x[x.index > corte] * 5
        return x

    h2 = hourly_table(mexe(funding), mexe(premium), taker.mul(np.where(taker.index > corte, 3.0, 1.0), axis=0), mexe(oi), hours)
    f2 = derivative_features(h2, 1)
    # até à vela que fecha em `corte` (abertura corte − 1h), nada pode mudar
    ate = base.index[base.index < corte]
    pd.testing.assert_frame_equal(base.loc[ate], f2.loc[ate])


def test_reamostragem_4h_usa_o_ultimo_valor_e_soma_o_fluxo():
    hours, funding, premium, taker, oi = _fontes()
    h = hourly_table(funding, premium, taker, oi, hours)
    h4 = resample_hourly(h, "4h")
    b = hours[4]
    assert h4.loc[b, "oi"] == h.loc[hours[7], "oi"] and h4.loc[b, "premio"] == h.loc[hours[7], "premio"]
    assert np.isclose(h4.loc[b, "taker_buy"], h.loc[hours[4]:hours[7], "taker_buy"].sum())
    f = derivative_features(h4, 4)
    assert {"funding_z_30d", "oi_var_24h", "taker_desequilibrio_24h"} <= set(f.columns)
