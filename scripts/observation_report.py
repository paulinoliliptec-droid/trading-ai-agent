"""Relatório do teste de observação (por omissão, os últimos 5 dias) a partir dos registos e de preços reais.

Uso: python scripts/observation_report.py [--dias 5] [--symbol BTC/USD]
Grava reports/observacao/relatorio_<data>.md e .json. Só leitura: não aprova modelos nem muda o risco.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta

import pandas as pd

from trading_agent.brokers.crypto.coinbase import CoinbaseMarketData
from trading_agent.config import ROOT, Secrets
from trading_agent.models.registry import ModelRegistry
from trading_agent.monitoring.observation import avaliar, contagem_eventos
from trading_agent.persistence.repository import MongoRepository, default_repository

BAR = {"1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4), "15m": pd.Timedelta(minutes=15), "1d": pd.Timedelta(days=1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=5)
    ap.add_argument("--symbol", default="BTC/USD")
    args = ap.parse_args()
    sec, repo = Secrets(), default_repository()
    fim = datetime.now(UTC)
    ini = fim - timedelta(days=args.dias)

    def janela(col: str) -> list[dict]:
        docs = repo.find(col, sec.tenant_id, limit=100_000, newest_first=False)
        return [d for d in docs if ini.isoformat() <= d["ts"] <= fim.isoformat() and d.get("symbol", args.symbol) == args.symbol]

    dec, eventos, equity, trades = janela("decisions"), janela("events"), janela("equity"), janela("trades")
    modelos = sorted({d.get("model_id") for d in dec if d.get("model_id")})
    meta = ModelRegistry().load(modelos[-1])[1] if modelos else {}
    tf, hz = meta.get("timeframe", "4h"), int(meta.get("horizon_bars", 1))
    bar = BAR[tf]
    precos = pd.Series(dtype=float)
    if dec:
        base_tf = "1h" if tf in ("4h", "1d") else tf
        raw = CoinbaseMarketData().historical(args.symbol, base_tf, ini - bar, fim)
        precos = raw["close"].resample(bar, label="left", closed="left").last().dropna() if base_tf != tf else raw["close"]
    av = avaliar(dec, precos, bar, hz)
    uso_mongo = None
    if isinstance(repo, MongoRepository):
        st = repo.db.command("dbstats")
        uso_mongo = {"dados_mb": round(st["dataSize"] / 2**20, 2), "armazenamento_mb": round(st["storageSize"] / 2**20, 2),
                     "indices_mb": round(st["indexSize"] / 2**20, 2), "limite_m0_mb": 512}
    r = {"gerado_em": fim.isoformat(), "tenant": sec.tenant_id, "simbolo": args.symbol, "janela": [ini.isoformat(), fim.isoformat()],
         "modelos": modelos, "timeframe": tf, "horizonte_velas": hz, "avaliacao": av.resumo(),
         "eventos": contagem_eventos(eventos), "operacoes_simuladas": len(trades),
         "resultado_simulado": sum(t.get("pnl_account", 0.0) for t in trades),
         "equity_inicio_fim": [equity[0].get("equity") if equity else None, equity[-1].get("equity") if equity else None],
         "custo_assumido_bps_medio": (sum(d.get("custo_bps") or 0 for d in dec) / len(dec)) if dec else None,
         "uso_mongodb": uso_mongo}
    out = ROOT / "reports" / "observacao"
    out.mkdir(parents=True, exist_ok=True)
    stamp = fim.strftime("%Y%m%d")
    (out / f"relatorio_{stamp}.json").write_text(json.dumps(r, indent=2, ensure_ascii=False, default=str))
    a = r["avaliacao"]

    def f(x, nd=1):
        return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))

    md = [f"# Relatório de observação · {args.symbol} · {stamp}", "",
          f"Janela: {ini:%Y-%m-%d %H:%M} → {fim:%Y-%m-%d %H:%M} UTC · tenant `{sec.tenant_id}` · modelos {', '.join(modelos) or '—'} "
          f"({tf}, horizonte {hz} velas). Só simulação.", "",
          "| Métrica | Valor |", "|---|---|",
          f"| Decisões registadas | {a['decisoes']} |", f"| Sinais (lado proposto) | {a['sinais']} |",
          f"| Aprovados / rejeitados pelo risco | {a['aprovados']} / {a['rejeitados']} |",
          f"| Sinais já avaliáveis | {a['avaliados']} |",
          f"| Taxa de acerto da direção | {f(a['taxa_acerto'], 3)} |",
          f"| Retorno bruto médio (bps) | {f(a['ret_bruto_medio_bps'])} |",
          f"| Retorno líquido médio (bps) | {f(a['ret_liquido_medio_bps'])} |",
          f"| IC95% do líquido (bps) | {f(a['ic95_liquido_bps'])} |",
          f"| Brier (prob. vs resultado líquido) | {f(a['brier'], 3)} |",
          f"| Custo médio assumido (bps, ida e volta) | {f(r['custo_assumido_bps_medio'])} |",
          f"| Operações simuladas / resultado | {r['operacoes_simuladas']} / {r['resultado_simulado']:+.2f} |",
          f"| Eventos por nível | {r['eventos']['por_nivel']} |", f"| Erros técnicos | {r['eventos']['erros'] or 'nenhum'} |",
          f"| MongoDB | {uso_mongo or 'SQLite local'} |", "",
          "## Motivos de veto mais frequentes", ""] + [f"- {k}: {v}" for k, v in a["motivos_veto"].items()] + [
          "", "## Leitura", "",
          "Com poucas dezenas de sinais, o intervalo de confiança é largo: este período verifica a operação "
          "(dados, decisões, persistência, alertas) e não prova vantagem. Nenhum modelo é aprovado com base nele."]
    (out / f"relatorio_{stamp}.md").write_text("\n".join(md) + "\n")
    print(out / f"relatorio_{stamp}.md")


if __name__ == "__main__":
    main()
