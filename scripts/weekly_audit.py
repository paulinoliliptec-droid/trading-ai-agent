"""Auditoria semanal no Telegram: a «nota» do robô e a saúde da operação.

Uso:
  python scripts/weekly_audit.py            # envia para o Telegram e guarda o resumo em `trading_agent.audits`
  python scripts/weekly_audit.py --seco     # só imprime a mensagem (não envia nem grava)

Corre na VM uma vez por semana (systemd `trading-audit.timer`). Lê as decisões e os eventos do Atlas, os preços da
Coinbase e o modelo versionado (SHA-256 verificado, só inferência). A única escrita é o resumo da semana na coleção
`audits` (um documento por semana; repetir a mesma semana não duplica). Não altera o modelo, o risco nem a operação.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

import pandas as pd

from trading_agent.config import Secrets, load_config
from trading_agent.models.registry import ModelRegistry
from trading_agent.monitoring.audit import carregar_decisoes, custo_extra, precos, tabela
from trading_agent.monitoring.weekly import mensagem, nota, saude

H = pd.Timedelta(hours=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC/USD")
    ap.add_argument("--inicio", default="2026-10-22", help="primeira decisão do acumulado")
    ap.add_argument("--dias", type=int, default=7)
    ap.add_argument("--seco", action="store_true", help="só imprime; não envia nem grava")
    args = ap.parse_args()
    sec, cfg = Secrets(), load_config()
    if not sec.mongodb_uri:
        raise SystemExit("Falta MONGODB_URI.")
    agora = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)

    ultima = pd.Timestamp(agora) - H                         # última vela fechada
    dec_todas = carregar_decisoes(sec, args.symbol, args.inicio, ultima)
    if not dec_todas:
        raise SystemExit("sem decisões")
    modelos = sorted({d["model_id"] for d in dec_todas})
    reg = ModelRegistry()
    pol = {m: reg.load(m) for m in modelos}
    horizonte = max(int(pol[m][1]["horizon_bars"]) for m in modelos)
    fim = ultima - H * horizonte                             # decisões com o horizonte completo
    ini = fim - pd.Timedelta(days=args.dias) + H
    dec = [d for d in dec_todas if pd.Timestamp(d["bar_time"]) <= fim]
    if not dec:
        raise SystemExit("ainda sem decisões com o horizonte completo")

    bars = precos(args.symbol, pd.Timestamp(dec[0]["bar_time"]), agora)
    df = tabela(dec, bars, pol, custo_extra(cfg.instrument(args.symbol)))
    semana_df = df[df["bar_time"] >= ini]
    semana, acum = nota(semana_df), nota(df)

    from trading_agent.persistence.repository import MongoRepository

    repo = MongoRepository.from_uri(sec.mongodb_uri.get_secret_value())
    eventos = repo.find("events", sec.tenant_id, {"ts": {"$gte": ini.isoformat()}}, limit=1000)
    s = saude(dec, eventos, max(ini, pd.Timestamp(dec[0]["bar_time"])), fim)
    anteriores = repo.find("audits", sec.tenant_id, {"symbol": args.symbol}, limit=8)
    historico = [a.get("semana", {}).get("auc") for a in reversed(anteriores) if a.get("fim") != fim.isoformat()]
    w = bars.loc[ini:fim]
    btc = (float(w["open"].iloc[0]), float(w["close"].iloc[-1])) if len(w) else None

    texto = mensagem(args.symbol, ini, fim, semana, acum, s, btc, historico)
    print(texto)
    if args.seco:
        return

    audit_id = f"{args.symbol}:{fim.isoformat()}"
    repo.ensure_indexes()
    novo = repo.insert("audits", sec.tenant_id, {
        "audit_id": audit_id, "symbol": args.symbol, "inicio": ini.isoformat(), "fim": fim.isoformat(),
        "modelos": modelos, "semana": semana, "acumulado": acum,
        "saude": {"esperadas": s.esperadas, "registadas": s.registadas, "erros": s.erros, "recuperados": s.recuperados},
        "btc": btc,
    }, unique_key="audit_id")
    if not novo:
        print(f"(semana {audit_id} já auditada: não volto a enviar)")
        return

    from trading_agent.notifications.telegram import Event, TelegramNotifier

    tg = TelegramNotifier(sec.telegram_bot_token.get_secret_value() if sec.telegram_bot_token else None,
                          sec.allowed_chat_ids())
    tg.notify(Event.WEEKLY, texto)


if __name__ == "__main__":
    main()
