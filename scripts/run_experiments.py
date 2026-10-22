"""Experiências da fase 2: horizontes, TP/SL, features e janelas, para BTC/USD e EUR/USD.

Uso: python scripts/run_experiments.py [--simbolos BTC/USD EUR/USD] [--sem-gru] [--rapido]
Escreve um JSON por experiência em reports/fase2/ e um resumo por mercado com a seleção feita
SÓ no período de desenvolvimento (critério fixo, ver research/pipeline.py). O teste final é
apenas reportado. Dados reais; nada sintético.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from datetime import UTC, datetime

from trading_agent.config import ROOT, load_config
from trading_agent.data.store import load_candles
from trading_agent.research.pipeline import ExperimentSpec, evaluate_period, run_experiment, signals

OUT = ROOT / "reports" / "fase2"
HORIZON = {"15m": 16, "1h": 24, "4h": 12, "1d": 10}   # 4 h, 1 dia, 2 dias, 2 semanas
TP_SL = [(2.0, 1.0), (1.0, 1.0)]                        # assimétrico (fase 1) e simétrico; grelha curta de propósito
SOURCE = {"BTC/USD": "coinbase", "EUR/USD": "dukascopy"}
TIMEFRAMES = {"BTC/USD": ["15m", "1h", "4h", "1d"], "EUR/USD": ["1h", "4h", "1d"]}  # EUR/USD sem 15m: ver docs


def grid(symbol: str) -> list[ExperimentSpec]:
    src = SOURCE[symbol]
    specs = [ExperimentSpec(symbol, src, tf, HORIZON[tf], tp, sl) for tf in TIMEFRAMES[symbol] for tp, sl in TP_SL]
    # Ablações na configuração da fase 1 (1 h, TP 2 / SL 1): features antigas e janela de treino de 1 ano
    specs.append(ExperimentSpec(symbol, src, "1h", 24, 2.0, 1.0, feature_set="v1"))
    specs.append(ExperimentSpec(symbol, src, "1h", 24, 2.0, 1.0, train_window=24 * 365 if symbol == "BTC/USD" else 24 * 260))
    return specs


def compact(m: dict | None) -> dict | None:
    if not m:
        return None
    keys = ("operacoes", "retorno_liquido_pct", "taxa_acerto_pct", "expectativa_bruta_bps", "custo_medio_bps",
            "expectativa_bps_por_operacao", "profit_factor", "max_drawdown_pct", "sharpe_anualizado")
    out = {k: m.get(k) for k in keys}
    ci = m.get("ic95_expectativa_liquida_bps") or {}
    out["ic95_liquida_bps"] = [ci.get("ic_inf"), ci.get("ic_sup")] if "ic_inf" in ci else None
    c = m.get("classificacao_lado_principal") or {}
    out["auc"] = c.get("roc_auc")
    out["brier_skill"] = c.get("brier_skill")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simbolos", nargs="+", default=["BTC/USD", "EUR/USD"])
    ap.add_argument("--sem-gru", action="store_true")
    ap.add_argument("--rapido", action="store_true", help="só 1 h e 4 h, sem ablações (verificação)")
    args = ap.parse_args()
    cfg = load_config()
    OUT.mkdir(parents=True, exist_ok=True)
    models = ("A", "B") if args.sem_gru else ("A", "B", "C", "D")
    eurusd = load_candles("EUR/USD", "1h", "dukascopy")
    fx_eurusd = (eurusd["close"] + eurusd["spread"] / 2).rename("EURUSD")  # preço médio, conhecido no fecho de cada vela
    for symbol in args.simbolos:
        specs = grid(symbol)
        if args.rapido:
            specs = [s for s in specs if s.timeframe in ("1h", "4h") and s.feature_set == "v2" and not s.train_window]
        linhas, raws = [], {}
        for spec in specs:
            t0 = time.time()
            rep, raw = run_experiment(spec, cfg, models)
            (OUT / f"{spec.name}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str))
            raws[spec.name] = raw
            for mk, r in rep["modelos"].items():
                linhas.append({"experiencia": spec.name, "modelo": mk, "qualificado": r["qualificado_no_desenvolvimento"],
                               "desenvolvimento": compact(r.get("desenvolvimento")), "teste_final": compact(r.get("teste_final"))})
            print(f"{spec.name} concluída em {time.time() - t0:.0f}s", flush=True)

        # Seleção pré-registada: só o desenvolvimento conta.
        qual = [x for x in linhas if x["qualificado"]]
        escolhido = max(qual, key=lambda x: x["desenvolvimento"]["expectativa_bps_por_operacao"]) if qual else None
        com_ops = [x for x in linhas if x["desenvolvimento"] and x["desenvolvimento"]["operacoes"] >= 30]
        melhor_dev = max(com_ops, key=lambda x: x["desenvolvimento"]["expectativa_bps_por_operacao"]) if com_ops else None

        # Simulação com 100 € (conta em EUR, conversão explícita) na configuração escolhida, ou na melhor do
        # desenvolvimento se nenhuma qualificar (para mostrar o efeito do capital pequeno, não para a usar).
        alvo = escolhido or melhor_dev
        sim100 = None
        if alvo:
            spec = next(s for s in specs if s.name == alvo["experiencia"])
            raw = raws[spec.name]
            prep, mo = raw["prep"], raw["outs"][alvo["modelo"][0]]
            rule = getattr(mo, "rule", None) if alvo["modelo"].startswith("A") else None
            risk_prod = __import__("trading_agent.risk.engine", fromlist=["RiskEngine"]).RiskEngine(
                dataclasses.replace(cfg.risk), __import__("trading_agent.risk.kill_switch", fromlist=["KillSwitch"]).KillSwitch(None),
                prep.inst.max_leverage)
            sim100 = {}
            for pname, idx in raw["periods"].items():
                if not len(idx):
                    continue
                sig = signals(prep, mo, idx, rule)
                m, _ = evaluate_period(prep, sig, risk_prod, 100.0, 252 if prep.inst.asset_class == "forex" else 365,
                                       fx_rate=fx_eurusd, currency="EUR")
                sim100[pname] = {**compact(m), "vetos_do_risco": m.get("vetos_do_risco")}
        resumo = {
            "gerado_em": datetime.now(UTC).isoformat(), "simbolo": symbol, "modelos": models,
            "n_configuracoes_x_modelos": len(linhas),
            "criterio_selecao": "desenvolvimento: >= 30 operações e IC95% inferior da expectativa líquida > 0 (bootstrap por blocos)",
            "escolhido": escolhido, "nenhum_qualificado": escolhido is None, "melhor_no_desenvolvimento": melhor_dev,
            "simulacao_100_eur_risco_de_producao": {"configuracao": alvo["experiencia"] + " / " + alvo["modelo"] if alvo else None,
                                                    "resultados": sim100},
            "tabela": linhas,
        }
        out = OUT / f"resumo_{symbol.replace('/', '')}.json"
        out.write_text(json.dumps(resumo, indent=1, ensure_ascii=False, default=str))
        print(json.dumps({k: resumo[k] for k in ("simbolo", "nenhum_qualificado", "escolhido", "melhor_no_desenvolvimento")},
                         indent=1, ensure_ascii=False, default=str), flush=True)
        print("resumo:", out, flush=True)



if __name__ == "__main__":
    main()
