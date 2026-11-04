import numpy as np
import pandas as pd

from trading_agent.monitoring.audit import aprovaria, barreiras, faixa, outros_vetos, recalcular, sequencia_executavel


def _bars(n=40, start="2026-10-01", price=100.0):
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"open": price, "high": price + 0.5, "low": price - 0.5, "close": price, "volume": 1.0}, index=idx)


def test_entrada_na_abertura_seguinte_e_tp():
    b = _bars()
    t = b.index[5]
    b.loc[b.index[6], "open"] = 100.2
    b.loc[b.index[9], "high"] = 100.2 + 2 * 1.0 + 0.01
    r = barreiras(b, t, atr=1.0, horizon=24, tp_mult=2, sl_mult=1)
    assert r.entrada_ts == b.index[6] and r.entrada == 100.2
    assert r.resultado == "tp" and r.saida_ts == b.index[9] and r.velas_observadas == 4
    assert abs(r.ret_bruto - 2 / 100.2) < 1e-12


def test_tp_e_sl_na_mesma_vela_conta_como_sl():
    b = _bars()
    t = b.index[5]
    b.loc[b.index[7], ["high", "low"]] = [103.0, 98.0]
    r = barreiras(b, t, atr=1.0, horizon=24, tp_mult=2, sl_mult=1)
    assert r.resultado == "sl" and r.ambigua and abs(r.saida - 99.0) < 1e-12


def test_saida_por_tempo_e_pendente():
    b = _bars(n=40)
    r = barreiras(b, b.index[5], atr=1.0, horizon=24, tp_mult=2, sl_mult=1)
    assert r.resultado == "tempo" and r.saida_ts == b.index[29] and r.fecho_24h == 100.0
    p = barreiras(b, b.index[30], atr=1.0, horizon=24, tp_mult=2, sl_mult=1)
    assert p.resultado == "pendente" and p.ret_bruto is None and p.fecho_24h is None


def test_atr_nao_usa_velas_futuras():
    rng = np.random.default_rng(0)
    b = _bars(n=300)
    b["close"] = 100 + rng.normal(0, 1, 300).cumsum()
    b["open"] = b["close"].shift(1).fillna(100)
    b["high"] = b[["open", "close"]].max(axis=1) + 0.3
    b["low"] = b[["open", "close"]].min(axis=1) - 0.3
    t = b.index[270]
    a = recalcular(b, t, 260, 0.0054)["atr"]
    b2 = b.copy()
    b2.loc[b.index[271]:, ["high", "low", "close"]] *= 3
    assert recalcular(b2, t, 260, 0.0054)["atr"] == a


def test_contrafactual_so_muda_o_limite():
    m = ["probabilidade 0.320 < 0.4"]
    assert outros_vetos(m) == [] and aprovaria(0.32, m, 0.30)
    m2 = ["probabilidade 0.320 < 0.4", "expectativa -5.00 bps < 1.0 bps depois de custos"]
    assert not aprovaria(0.32, m2, 0.30)
    assert not aprovaria(0.29, m, 0.30)
    assert faixa(0.35) == "0,30–0,40" and faixa(0.05) == "<0,10" and faixa(0.4) == "≥0,40"


def test_sequencia_sem_sobreposicao():
    ts = pd.date_range("2026-10-01", periods=4, freq="1h", tz="UTC")
    df = pd.DataFrame({"bar_time": ts, "entrada_ts": ts + pd.Timedelta(hours=1),
                       "saida_ts": [ts[0] + pd.Timedelta(hours=3), ts[1], ts[3] + pd.Timedelta(hours=5), pd.NaT],
                       "resultado": ["sl", "tp", "tempo", "tempo"]})
    s = sequencia_executavel(df, pd.Series(True, index=df.index))
    # a 1.ª sai às 03:00 → a 2.ª e a 3.ª (entradas 02:00 e 03:00) ficam de fora; a 4.ª entra às 04:00
    assert list(s["bar_time"]) == [ts[0], ts[3]]
