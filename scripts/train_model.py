"""Treina e grava a política (XGBoost) de uma experiência, com o estado de aprovação.

Uso: python scripts/train_model.py --experiencia BTCUSD_4h_h12_tp2_sl1_v2
     python scripts/train_model.py --escolhido BTC/USD   (a escolhida pelo resumo da fase 2, se houver)

A configuração e as métricas fora da amostra vêm do relatório da experiência (reports/fase2/).
O modelo final treina nos dados mais recentes: treino | validação | calibração, com embargo.
A inferência (worker) só carrega o artefacto: não volta a treinar.
"""

from __future__ import annotations

import argparse
import hashlib
import json

import numpy as np

from trading_agent.config import ROOT, load_config
from trading_agent.data.store import dataset_path
from trading_agent.models.registry import ModelRegistry, TrainedPolicy, approval
from trading_agent.models.xgboost_model.model import XGBoostModel
from trading_agent.research.pipeline import ExperimentSpec, _expected_ret_map, prepare

REPORTS = ROOT / "reports" / "fase2"


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--experiencia")
    g.add_argument("--escolhido", help="símbolo: usa a configuração escolhida no resumo da fase 2")
    args = ap.parse_args()
    if args.escolhido:
        resumo = json.loads((REPORTS / f"resumo_{args.escolhido.replace('/', '')}.json").read_text())
        if not resumo.get("escolhido"):
            raise SystemExit(f"Nenhuma configuração de {args.escolhido} qualificou no desenvolvimento: nada a treinar para operar.")
        args.experiencia = resumo["escolhido"]["experiencia"]
    rep = json.loads((REPORTS / f"{args.experiencia}.json").read_text())
    spec = ExperimentSpec(**rep["spec"])
    cfg = load_config()
    prep = prepare(spec, cfg)
    d, cols = prep.data, prep.cols
    n, emb = len(d), spec.horizon_bars
    n_cal = n_val = int(n * 0.15)
    tr = np.arange(0, n - n_val - n_cal - 2 * emb)
    va = np.arange(tr[-1] + 1 + emb, tr[-1] + 1 + emb + n_val)
    ca = np.arange(va[-1] + 1 + emb, n)
    t1 = prep.t1
    tr = tr[(t1.iloc[tr] < d.index[va[0]]).to_numpy()]
    va = va[(t1.iloc[va] < d.index[ca[0]]).to_numpy()]
    policy = TrainedPolicy(spec.symbol, spec.timeframe, spec.horizon_bars, spec.tp_mult, spec.sl_mult, spec.feature_set,
                           cols, prep.sides)
    for s in prep.sides:
        y = prep.labels[s]["label"].loc[d.index]
        r = prep.labels[s]["gross_ret"].loc[d.index]
        m = XGBoostModel().fit(d[cols].iloc[tr], y.iloc[tr], d[cols].iloc[va], y.iloc[va], d[cols].iloc[ca], y.iloc[ca])
        policy.models[s] = m
        policy.exp_maps[s] = _expected_ret_map(m.predict_proba(d[cols].iloc[ca]), r.iloc[ca].to_numpy())
    b = rep["modelos"]["B_xgboost"]
    hold = b.get("teste_final") or {}
    status, motivos = approval(b["qualificado_no_desenvolvimento"], hold.get("expectativa_bps_por_operacao"), hold.get("operacoes", 0))
    src_tf = "15m" if spec.timeframe == "15m" else "1h"
    data_file = dataset_path(spec.symbol, src_tf, spec.source)
    meta = {
        "experiencia": args.experiencia, "status": status, "motivos_estado": motivos,
        "treino": [str(d.index[tr[0]]), str(d.index[tr[-1]])], "validacao": [str(d.index[va[0]]), str(d.index[va[-1]])],
        "calibracao": [str(d.index[ca[0]]), str(d.index[ca[-1]])],
        "dados": {"ficheiro": data_file.name, "sha256": hashlib.sha256(data_file.read_bytes()).hexdigest(),
                  "manifesto": json.loads(data_file.with_suffix(".manifest.json").read_text())},
        "fora_da_amostra": {"desenvolvimento": b.get("desenvolvimento", {}).get("ic95_expectativa_liquida_bps"),
                            "teste_final_expectativa_bps": hold.get("expectativa_bps_por_operacao"),
                            "teste_final_operacoes": hold.get("operacoes")},
    }
    model_id = ModelRegistry().save(policy, meta)
    print(json.dumps({"model_id": model_id, "status": status, "motivos": motivos}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
