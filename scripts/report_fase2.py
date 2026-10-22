"""Gera docs/research-results-fase2-tabelas.md a partir dos JSON em reports/fase2/ (sem transcrição manual)."""

from __future__ import annotations

import json

import numpy as np

from trading_agent.config import ROOT

R = ROOT / "reports" / "fase2"
MODELS = ("A_regras", "B_xgboost", "C_gru", "D_ensemble_BC")


def f(v, nd=2):
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.{nd}f}".replace(".", ",")
    return str(v)


def ci(m):
    c = (m or {}).get("ic95_expectativa_liquida_bps") or {}
    return f"[{f(c.get('ic_inf'), 1)}; {f(c.get('ic_sup'), 1)}]" if "ic_inf" in c else "–"


def main() -> None:
    L = ["# Resultados da fase 2: tabelas", "",
         "> Gerado por `scripts/report_fase2.py` a partir de `reports/fase2/*.json`. Valores em pontos base (bps) por operação,",
         "> depois de custos, salvo indicação. **Desenvolvimento** = períodos usados para comparar; **teste final** = só reportado.", ""]
    for sym in ("BTCUSD", "EURUSD"):
        exps = sorted(p for p in R.glob(f"{sym}_*.json"))
        if not exps:
            continue
        resumo = json.loads((R / f"resumo_{sym}.json").read_text()) if (R / f"resumo_{sym}.json").exists() else {}
        L += [f"## {sym[:3]}/{sym[3:]}", ""]
        L += ["### Custos face ao movimento esperado", "",
              "| Experiência | Custo ida e volta (bps) | ATR mediano (%) | Custo em ATR | Prob. ponto morto | TP-primeiro observado | Bruto médio do rótulo (bps) |",
              "|---|---|---|---|---|---|---|"]
        reps = [json.loads(p.read_text()) for p in exps]
        for r in reps:
            d = r["diagnostico_custos"]
            L.append(f"| {r['experiencia']} | {f(d['custo_ida_volta_bps'], 1)} | {f(d['atr_mediano_pct'], 3)} | {f(d['custo_em_atr'], 3)} | "
                     f"{f(d['prob_ponto_morto_tp_primeiro'], 3)} | {f(d['taxa_tp_primeiro_observada'], 3)} | {f(d['retorno_bruto_medio_rotulo_bps'], 1)} |")
        L += ["", "### Resultados por experiência e modelo", "",
              "| Experiência | Modelo | Ops (dev) | Bruto | Custo | Líquido | IC95% líquido | AUC | Brier skill | Qualifica | Ops (teste final) | Líquido (teste final) | Retorno teste final (%) |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in reps:
            for mk in MODELS:
                m = r["modelos"].get(mk)
                if not m:
                    continue
                dv, tf = m.get("desenvolvimento") or {}, m.get("teste_final") or {}
                c = dv.get("classificacao_lado_principal") or {}
                L.append(f"| {r['experiencia']} | {mk} | {dv.get('operacoes', 0)} | {f(dv.get('expectativa_bruta_bps'), 1)} | "
                         f"{f(dv.get('custo_medio_bps'), 1)} | {f(dv.get('expectativa_bps_por_operacao'), 1)} | {ci(dv)} | "
                         f"{f(c.get('roc_auc'), 3)} | {f(c.get('brier_skill'), 4)} | {'sim' if m['qualificado_no_desenvolvimento'] else 'não'} | "
                         f"{tf.get('operacoes', 0)} | {f(tf.get('expectativa_bps_por_operacao'), 1)} | {f(tf.get('retorno_liquido_pct'), 2)} |")
        L += ["", "### Referências (mesmos períodos; «não negociar» = 0%)", "",
              "| Intervalo | Período | Datas | Comprar e manter (%) | Max DD comprar e manter (%) |", "|---|---|---|---|---|"]
        vistos = set()
        for r in reps:
            tfr = r["spec"]["timeframe"]
            if tfr in vistos:
                continue
            vistos.add(tfr)
            for p, v in r["referencias"].items():
                datas = " a ".join(x[:10] for x in r["periodos"][p])
                L.append(f"| {tfr} | {p} | {datas} | {f(v['comprar_e_manter']['retorno_pct'])} | {f(v['comprar_e_manter']['max_drawdown_pct'])} |")
        L += ["", "### Estabilidade do XGBoost por fold (AUC no treino vs fora da amostra, Brier skill, ECE)", "",
              "| Experiência | AUC treino (média) | AUC fora (média) | AUC fora (mín–máx) | Brier skill (média) | ECE (média) |", "|---|---|---|---|---|---|"]
        for r in reps:
            fm = (r["modelos"].get("B_xgboost") or {}).get("classificacao_por_fold") or []
            if not fm:
                continue
            a_in = [x["auc_treino"] for x in fm if x.get("auc_treino") is not None]
            a_out = [x["roc_auc"] for x in fm if x.get("roc_auc") is not None]
            bs = [x["brier_skill"] for x in fm if x.get("brier_skill") is not None]
            ece = [x["ece"] for x in fm if x.get("ece") is not None]
            L.append(f"| {r['experiencia']} | {f(float(np.mean(a_in)), 3)} | {f(float(np.mean(a_out)), 3)} | "
                     f"{f(min(a_out), 3)}–{f(max(a_out), 3)} | {f(float(np.mean(bs)), 4)} | {f(float(np.mean(ece)), 4)} |")
        L += ["", "### Regimes (XGBoost, desenvolvimento): líquido em bps por terço", "",
              "| Experiência | Vol. rel. baixa | média | alta | Tendência baixa | média | alta | AUC por volatilidade (baixa/média/alta) |",
              "|---|---|---|---|---|---|---|---|"]
        for r in reps:
            dv = (r["modelos"].get("B_xgboost") or {}).get("desenvolvimento") or {}
            rg = dv.get("regimes") or {}
            if not rg:
                continue
            vr, tr = rg.get("volatilidade_relativa", {}), rg.get("tendencia_eficiencia", {})
            cell = lambda t, k: f"{f(t[k]['liquido_bps'], 1)} ({t[k]['operacoes']})" if k in t else "–"  # noqa: E731
            auc = dv.get("auc_lado_principal_por_volatilidade") or {}
            L.append(f"| {r['experiencia']} | {cell(vr, 'baixo')} | {cell(vr, 'medio')} | {cell(vr, 'alto')} | {cell(tr, 'baixo')} | "
                     f"{cell(tr, 'medio')} | {cell(tr, 'alto')} | {f(auc.get('baixo'), 3)}/{f(auc.get('medio'), 3)}/{f(auc.get('alto'), 3)} |")
        L += ["", "### Consistência entre rótulo e execução simulada (XGBoost, desenvolvimento)", "",
              "| Experiência | Operações | Saída igual à barreira do rótulo (%) |", "|---|---|---|"]
        for r in reps:
            c = ((r["modelos"].get("B_xgboost") or {}).get("desenvolvimento") or {}).get("consistencia_rotulo_execucao") or {}
            if c:
                L.append(f"| {r['experiencia']} | {c['operacoes']} | {f(c['saida_igual_ao_rotulo_pct'], 1)} |")
        if resumo:
            s = resumo.get("simulacao_100_eur_risco_de_producao") or {}
            L += ["", "### Seleção pré-registada e simulação com 100 €", "",
                  f"- Critério: {resumo['criterio_selecao']}.",
                  f"- Combinações avaliadas (configuração × modelo): {resumo['n_configuracoes_x_modelos']}.",
                  f"- Escolhida: **{(resumo.get('escolhido') or {}).get('experiencia', 'nenhuma')}"
                  f"{' / ' + resumo['escolhido']['modelo'] if resumo.get('escolhido') else ''}**.",
                  f"- Melhor no desenvolvimento (com ≥ 30 operações, qualificada ou não): "
                  f"{(resumo.get('melhor_no_desenvolvimento') or {}).get('experiencia', '–')} / "
                  f"{(resumo.get('melhor_no_desenvolvimento') or {}).get('modelo', '–')}.",
                  f"- Simulação com 100 € (conta em EUR, risco de produção): configuração {s.get('configuracao')}.", ""]
            for p, v in (s.get("resultados") or {}).items():
                L.append(f"  - {p}: {v.get('operacoes')} operações, retorno {f(v.get('retorno_liquido_pct'))}%, "
                         f"líquido {f(v.get('expectativa_bps_por_operacao'), 1)} bps/op, max DD {f(v.get('max_drawdown_pct'))}%, "
                         f"vetos {v.get('vetos_do_risco')}")
        L.append("")
    out = ROOT / "docs" / "research-results-fase2-tabelas.md"
    out.write_text("\n".join(L) + "\n")
    print(out)


if __name__ == "__main__":
    main()
