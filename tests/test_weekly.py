import pandas as pd

from trading_agent.monitoring.weekly import DIAS_SINAL, Saude, auc, mensagem, nota, saude, veredicto


def _df(rows):
    base = {"aprovado": False, "exp_ret_bruto_bps": 0.0, "ret_bruto_bps": 0.0, "ret_liquido_bps": -54.0}
    out = []
    for i, r in enumerate(rows):
        out.append({**base, "bar_time": pd.Timestamp("2026-10-01", tz="UTC") + pd.Timedelta(hours=i), **r})
    return pd.DataFrame(out)


def test_auc_perfeito_aleatorio_e_empates():
    assert auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]) == 0.0
    assert auc([0, 1, 0, 1], [0.3, 0.3, 0.3, 0.3]) == 0.5           # o mesmo número para todos = moeda ao ar
    assert auc([1, 1], [0.2, 0.3]) is None                          # uma só classe: sem nota


def test_nota_conta_rejeicoes_certas_e_ignora_pendentes():
    df = _df([
        {"resultado": "tp", "prob": 0.4, "ret_liquido_bps": 100.0},
        {"resultado": "sl", "prob": 0.2, "ret_liquido_bps": -150.0},
        {"resultado": "tempo", "prob": 0.3, "ret_liquido_bps": -10.0},
        {"resultado": "pendente", "prob": 0.9, "ret_liquido_bps": None},
    ])
    n = nota(df)
    assert n["decisoes"] == 4 and n["resolvidas"] == 3 and n["tp"] == 1
    assert n["rejeicoes"] == 3 and n["rejeicoes_certas"] == 2
    assert n["auc"] == 1.0 and abs(n["ret_liq_medio_bps"] - (-20.0)) < 1e-9


def test_nota_sem_resolvidas():
    n = nota(_df([{"resultado": "pendente", "prob": 0.3}]))
    assert n["resolvidas"] == 0 and "auc" not in n


def test_saude_conta_horas_em_falta_e_erros():
    ini, fim = pd.Timestamp("2026-10-01T00:00", tz="UTC"), pd.Timestamp("2026-10-01T03:00", tz="UTC")
    dec = [{"bar_time": f"2026-10-01T0{h}:00:00+00:00"} for h in (0, 1, 3)]
    ev = [{"ts": "2026-10-01T01:05:00+00:00", "level": "error", "kind": "falha_api"},
          {"ts": "2026-10-01T01:07:00+00:00", "level": "info", "kind": "recuperado"},
          {"ts": "2026-09-30T10:00:00+00:00", "level": "error", "kind": "falha_api"}]   # fora da janela
    s = saude(dec, ev, ini, fim)
    assert (s.esperadas, s.registadas, s.em_falta, s.erros, s.recuperados) == (4, 3, 1, 1, 1)


def test_veredicto_exige_nota_e_dias():
    assert "não mostra habilidade" in veredicto({"auc": 0.50, "dias": 200})
    assert "Pode ser sorte" in veredicto({"auc": 0.60, "dias": 30})
    assert "possível habilidade" in veredicto({"auc": 0.60, "dias": DIAS_SINAL})
    assert "sem decisões" in veredicto({"dias": 0})


def test_mensagem_em_linguagem_simples():
    ini, fim = pd.Timestamp("2026-10-27T10:00", tz="UTC"), pd.Timestamp("2026-11-03T09:00", tz="UTC")
    semana = {"aprovadas": 0, "resolvidas": 168, "rejeicoes": 168, "rejeicoes_certas": 91,
              "aprovadas_resolvidas": 0, "ret_liq_medio_bps": -37.0, "auc": 0.59}
    txt = mensagem("BTC/USD", ini, fim, semana, {"auc": 0.50, "dias": 13}, Saude(168, 168, 15, 11),
                   (79817.0, 77004.0), [None, 0.48])
    assert "27/10 → 03/11" in txt and "168/168" in txt and "nenhuma decisão perdida" in txt
    assert "91/168 (54%)" in txt and "-0,37%" in txt and "Esta semana: 0,59" in txt
    assert "Semanas anteriores: 0,48" in txt and "-3,5%" in txt and "não mostra habilidade" in txt
    assert "<" not in txt                                            # o notificador escapa, mas não há HTML
