"""Agente autónomo de paper trading: ciclo persistente, recuperável e idempotente.

Cada ciclo:
  1. recebe preços (velas recentes e cotação atual) da MESMA fonte usada no treino;
  2. gere as posições abertas com a cotação (stop, alvo, limite temporal, restos de ordens parciais);
  3. identifica a última vela FECHADA e mede a idade dos dados;
  4. se essa vela ainda não foi processada (reclamação atómica no estado partilhado), calcula as
     features, faz a inferência com o modelo versionado (sem treinar), submete a proposta ao risco;
  5. se aprovado e o modelo estiver aprovado, executa a ordem simulada com um id determinístico
     (o mesmo depois de um reinício: nunca duplica);
  6. regista decisões, ordens, operações, posições, equity e eventos; notifica; grava o estado.
Falhas: cada erro conta; ao fim de N seguidas o risco deixa de abrir posições, e o ciclo continua
a tentar com espera crescente. O kill switch (estado partilhado) bloqueia entradas mesmo que o
modelo ou a fonte de dados falhem; `/stop` fecha também as posições abertas.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from trading_agent.brokers.base import MarketDataSource, Order, OrderStatus, Quote, Side, ensure_simulated
from trading_agent.config import AppConfig
from trading_agent.data.quality import clean_ohlcv
from trading_agent.data.resample import resample_ohlcv
from trading_agent.execution.instruments import FxConverter
from trading_agent.execution.paper import PaperAccount, reconcile
from trading_agent.models.registry import TrainedPolicy
from trading_agent.notifications.telegram import Event, TelegramNotifier
from trading_agent.persistence.repository import Repository
from trading_agent.persistence.state import StateStore
from trading_agent.risk.engine import Decision, PortfolioState, Proposal, RiskEngine
from trading_agent.risk.kill_switch import KillSwitch

log = logging.getLogger(__name__)
BAR = {"15m": timedelta(minutes=15), "1h": timedelta(hours=1), "4h": timedelta(hours=4), "1d": timedelta(days=1)}
LOOKBACK_BARS = 260           # o suficiente para as janelas mais longas das features (168) com folga
MAX_QUOTE_AGE = timedelta(minutes=2)


@dataclass
class WorkerConfig:
    tenant_id: str = "default"
    mode: str = "observacao"          # «paper» abre posições simuladas; «observacao» só regista decisões
    notify_rejected: bool = True
    interval_s: float = 60.0
    max_backoff_s: float = 900.0


@dataclass
class AgentWorker:
    cfg: AppConfig
    policy: TrainedPolicy
    model_meta: dict
    data: MarketDataSource
    store: StateStore
    repo: Repository
    kill: KillSwitch
    notifier: TelegramNotifier
    wcfg: WorkerConfig = field(default_factory=WorkerConfig)
    fx_source: Callable[[], float] | None = None    # taxa conta→cotação (ex.: EUR/USD) quando as moedas diferem
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.symbol = self.policy.symbol
        self.inst = self.cfg.instrument(self.symbol)
        self.bar = BAR[self.policy.timeframe]
        self.risk = RiskEngine(self.cfg.risk, self.kill, self.inst.max_leverage)
        acc = self.cfg.account
        self.key = f"account:{self.wcfg.tenant_id}:{self.symbol}"
        st = self.store.get(self.key)
        self.account = (PaperAccount.from_state(st, {self.symbol: self.inst}) if st
                        else PaperAccount({self.symbol: self.inst}, acc["currency"], float(acc["initial_capital"]), FxConverter()))
        ensure_simulated(self.account)
        if self.wcfg.mode == "paper" and self.model_meta.get("status") != "aprovado":
            log.warning("modelo %s não aprovado (%s): o agente corre em observação", self.model_meta.get("model_id"),
                        self.model_meta.get("status"))
            self.wcfg.mode = "observacao"
        self.errors = int((self.store.get(f"health:{self.wcfg.tenant_id}:{self.symbol}") or {}).get("consecutive_errors", 0))
        self.extra_cost = (2 * self.inst.fee_bps + 2 * self.inst.slippage_bps
                           + (0 if self.inst.price_basis == "bid" else self.inst.default_spread_bps)) / 1e4

    # ---------- utilitários ----------
    def _event(self, level: str, kind: str, msg: str, **extra) -> None:
        self.repo.insert("events", self.wcfg.tenant_id, {"level": level, "kind": kind, "symbol": self.symbol, "message": msg, **extra})

    def _save(self) -> None:
        self.store.put(self.key, self.account.to_state())
        self.store.put(f"health:{self.wcfg.tenant_id}:{self.symbol}", {"consecutive_errors": self.errors,
                                                                       "last_cycle": self.clock().isoformat()})

    def _record_trades(self, trades: list[dict]) -> None:
        for t in trades:
            self.repo.insert("trades", self.wcfg.tenant_id, {**t, "model_id": self.model_meta.get("model_id")})
            self.notifier.notify(Event.CLOSED, f"{t['symbol']} {'comprado' if t['side'] == 1 else 'vendido'} fechado por "
                                               f"{t['reason']}: {t['pnl_account']:+.2f} {self.account.currency} "
                                               f"({t['net_ret'] * 1e4:+.1f} bps líquidos)")

    def start(self) -> None:
        self._event("info", "arranque", f"agente iniciado em modo {self.wcfg.mode}", model_id=self.model_meta.get("model_id"))
        self.notifier.notify(Event.STARTED, f"{self.symbol} · modelo {self.model_meta.get('model_id')} "
                                            f"({self.model_meta.get('status')}) · modo {self.wcfg.mode}")

    # ---------- um ciclo ----------
    def cycle(self) -> dict:
        now = self.clock()
        try:
            if self.fx_source is not None:
                self.account.fx.set_rate(self.account.currency, self.inst.quote_currency, self.fx_source())
            q = self.data.quote(self.symbol)
            base_tf = "15m" if self.policy.timeframe == "15m" else "1h"  # 4 h e 1 d: reamostrar como no treino
            raw = self.data.historical(self.symbol, base_tf, now - self.bar * LOOKBACK_BARS, now)
        except Exception as e:  # noqa: BLE001 - qualquer falha da fonte conta como falha de API
            self.errors += 1
            self._event("error", "falha_api", f"{type(e).__name__}: {e}"[:300], consecutive=self.errors)
            if self.errors == self.cfg.risk.max_consecutive_api_errors:
                self.notifier.notify(Event.TECH_FAILURE, f"{self.symbol}: {self.errors} falhas seguidas da fonte de dados. "
                                                         "Sem novas entradas até recuperar.")
            self._save()
            return {"estado": "falha_api", "erros_seguidos": self.errors}
        if self.errors:
            self._event("info", "recuperado", f"fonte de dados recuperada depois de {self.errors} falhas")
        self.errors = 0
        out: dict = {"estado": "ok"}

        # 2) posições abertas: stop, alvo, tempo (com a cotação, em qualquer ciclo)
        quote_age = now - q.timestamp
        if quote_age <= MAX_QUOTE_AGE:
            self._record_trades(self.account.on_quote(q, now))
        stop_req = self.store.get(f"command:{self.wcfg.tenant_id}:close_all")
        if stop_req and not stop_req.get("done"):
            for sym in list(self.account.positions_):
                r = self.account.close_position(sym, q, now, "stop_manual")
                if r and r.closed_trade:
                    self._record_trades([r.closed_trade])
            self.store.put(f"command:{self.wcfg.tenant_id}:close_all", {**stop_req, "done": True, "done_at": now.isoformat()})

        # 3) última vela fechada e idade dos dados
        hours = "forex" if self.inst.asset_class == "forex" else "24/7"
        bars, _ = clean_ohlcv(raw, "15min" if base_tf == "15m" else "1h", hours)
        base_bar = BAR[base_tf]
        bars = bars[bars.index + base_bar <= now]          # só velas de base fechadas
        bars = resample_ohlcv(bars, self.policy.timeframe, self.inst.asset_class)
        bars = bars[bars.index + self.bar <= now]          # e só velas agregadas completas
        if bars.empty:
            self._save()
            return {"estado": "sem_velas_fechadas"}
        last = bars.index[-1]
        age_bars = (now - (last + self.bar)) / self.bar
        bar_id = f"bar:{self.wcfg.tenant_id}:{self.symbol}:{self.policy.timeframe}:{last.isoformat()}"
        eq = self.account.mark(now)
        self._risk_alerts(eq)
        if not self.store.claim(bar_id, {"at": now.isoformat()}):
            self._save()
            return {**out, "estado": "vela_ja_processada", "vela": last.isoformat()}

        # 4) features e inferência (o modelo já está treinado)
        feats = self.policy.features(bars, self.extra_cost)
        row = feats.iloc[-1]
        prop_model = self.policy.decide(row)
        atr_pct = float(row.get("atr_pct", np.nan))
        sbps = float(row["spread_bps"]) if "spread_bps" in row and not pd.isna(row["spread_bps"]) else q.spread_bps
        cost = self.inst.round_trip_cost_pct(sbps)
        side = int(prop_model["side"])
        exp = prop_model["exp_ret"] if side else None
        prop = Proposal(self.symbol, side, float(prop_model["prob"] or 0.0), self.policy.tp_mult * atr_pct,
                        self.policy.sl_mult * atr_pct, cost, sbps, atr_pct, exp)
        state = PortfolioState(eq, self.account.peak_equity, self.account.day_start_equity, len(self.account.positions_),
                               self.account.exposure_by_symbol(), venue_available=quote_age <= MAX_QUOTE_AGE,
                               available_equity=self.account.available(), data_age_bars=float(age_bars),
                               consecutive_api_errors=self.errors,
                               bar_move_atr=float((bars["high"].iloc[-1] - bars["low"].iloc[-1]) / (atr_pct * bars["close"].iloc[-1]))
                               if atr_pct and atr_pct > 0 else 0.0)
        dec = self.risk.evaluate(prop, state)
        if dec.trade and self.symbol in self.account.positions_:
            dec = Decision(False, 0, 0.0, dec.expected_edge_bps, ["já existe posição neste instrumento"])
        decision_id = f"{self.wcfg.tenant_id}:{self.symbol}:{self.policy.timeframe}:{last.isoformat()}"
        doc = {"decision_id": decision_id, "symbol": self.symbol, "bar_time": last.isoformat(), "model_id": self.model_meta.get("model_id"),
               "modo": self.wcfg.mode, "proposta": {k: v for k, v in prop_model.items() if k != "por_lado"},
               "por_lado": prop_model.get("por_lado"), "custo_bps": cost * 1e4, "aprovado": dec.trade,
               "expectativa_bps": dec.expected_edge_bps, "tamanho": dec.size_fraction, "motivos": dec.reasons,
               "idade_dados_velas": float(age_bars)}
        self.repo.insert("decisions", self.wcfg.tenant_id, doc, unique_key="decision_id")
        if not dec.trade:
            self.repo.insert("risk_events", self.wcfg.tenant_id, {"kind": "veto", "symbol": self.symbol, "decision_id": decision_id,
                                                                  "reasons": dec.reasons})
        if dec.trade or (side and self.wcfg.notify_rejected):
            self.notifier.notify(Event.SIGNAL_APPROVED if dec.trade else Event.SIGNAL_REJECTED,
                                 f"{self.symbol} {'comprar' if side == 1 else 'vender'} · prob {prop.probability:.3f} · "
                                 f"expectativa {dec.expected_edge_bps:+.1f} bps · {'; '.join(dec.reasons)}")
        out.update({"vela": last.isoformat(), "decisao": dec.reasons, "aprovado": dec.trade})

        # 5) execução simulada (só com modelo aprovado)
        if dec.trade and self.wcfg.mode == "paper":
            notional_q = self.account.to_quote(dec.size_fraction * eq, self.symbol)
            qty = notional_q / q.mid
            atr_px = atr_pct * q.mid
            order = Order(self.symbol, Side.BUY if side == 1 else Side.SELL, qty, decision_id,
                          stop_loss=q.mid - side * self.policy.sl_mult * atr_px, take_profit=q.mid + side * self.policy.tp_mult * atr_px,
                          expires_at=now + self.bar * self.policy.horizon_bars, tenant_id=self.wcfg.tenant_id,
                          meta={"decision_id": decision_id, "prob": prop.probability, "edge_bps": dec.expected_edge_bps})
            r = self.account.submit(order, q, now)
            self.repo.insert("orders", self.wcfg.tenant_id, {"client_order_id": order.client_order_id, "symbol": self.symbol,
                                                             "side": str(order.side), "quantity": order.quantity,
                                                             "status": str(r.order.status), "reason": r.order.reason,
                                                             "fill_price": r.fill.price if r.fill else None, "duplicate": r.duplicate},
                             unique_key="client_order_id")
            if r.fill:
                self.notifier.notify(Event.OPENED, f"{self.symbol} {order.side} {r.fill.quantity:g} a {r.fill.price:.5f} "
                                                   f"(SL {order.stop_loss:.5f}, TP {order.take_profit:.5f})")
            elif r.order.status == OrderStatus.REJECTED:
                self._event("warning", "ordem_rejeitada", r.order.reason)
            out["ordem"] = str(r.order.status)

        # 6) estado, equity e posições
        diffs = reconcile({s: p.side * p.qty for s, p in self.account.positions_.items()}, self.account)
        if diffs:
            self._event("error", "reconciliacao", "; ".join(diffs))
        self.repo.insert("equity", self.wcfg.tenant_id, {"symbol": self.symbol, **self.account.summary()})
        for s, p in self.account.positions_.items():
            self.repo.insert("positions", self.wcfg.tenant_id, {"symbol": s, "side": p.side, "qty": p.qty, "entry_price": p.entry_price,
                                                                "stop_loss": p.stop_loss, "take_profit": p.take_profit,
                                                                "unrealized": self.account.unrealized(s)})
        self._reports(now)
        self._save()
        return out

    def _risk_alerts(self, eq: float) -> None:
        L = self.cfg.risk
        day = self.account.day
        dd = eq / self.account.peak_equity - 1 if self.account.peak_equity else 0.0
        dl = eq / self.account.day_start_equity - 1 if self.account.day_start_equity else 0.0
        if dl <= -L.max_daily_loss_pct and self.store.claim(f"alert:daily:{self.wcfg.tenant_id}:{self.symbol}:{day}"):
            self.notifier.notify(Event.DAILY_LIMIT, f"{self.symbol}: {dl * 100:.2f}% hoje. Sem novas entradas até amanhã (UTC).")
            self.repo.insert("risk_events", self.wcfg.tenant_id, {"kind": "limite_diario", "symbol": self.symbol, "value": dl})
        if dd <= -L.max_drawdown_pct / 2 and self.store.claim(f"alert:dd50:{self.wcfg.tenant_id}:{self.symbol}:{day}"):
            self.notifier.notify(Event.DRAWDOWN, f"{self.symbol}: drawdown {dd * 100:.2f}% (limite {L.max_drawdown_pct * 100:.0f}%).")
            self.repo.insert("risk_events", self.wcfg.tenant_id, {"kind": "drawdown", "symbol": self.symbol, "value": dd})

    def _reports(self, now: datetime) -> None:
        y = (now - timedelta(days=1)).date().isoformat()
        if self.store.claim(f"report:daily:{self.wcfg.tenant_id}:{self.symbol}:{y}"):
            s = self.account.summary()
            self.notifier.notify(Event.DAILY, f"{self.symbol} · equity {s['equity']:.2f} {s['moeda']} · realizado "
                                              f"{s['resultado_realizado']:+.2f} · aberto {s['resultado_nao_realizado']:+.2f} · "
                                              f"operações fechadas {s['operacoes_fechadas']}")
        wk = now.isocalendar()
        if now.weekday() == 0 and self.store.claim(f"report:weekly:{self.wcfg.tenant_id}:{self.symbol}:{wk.year}-{wk.week}"):
            trades = [t for t in self.account.trades if t["exit_time"] >= (now - timedelta(days=7)).isoformat()]
            pnl = sum(t["pnl_account"] for t in trades)
            self.notifier.notify(Event.WEEKLY, f"{self.symbol} · 7 dias: {len(trades)} operações, {pnl:+.2f} {self.account.currency} · "
                                               f"equity {self.account.equity():.2f}")

    # ---------- ciclo contínuo ----------
    def run_forever(self, max_cycles: int | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        self.start()
        n, backoff = 0, self.wcfg.interval_s
        while max_cycles is None or n < max_cycles:
            n += 1
            try:
                r = self.cycle()
                backoff = self.wcfg.interval_s if r.get("estado") != "falha_api" else min(backoff * 2, self.wcfg.max_backoff_s)
                log.info("ciclo %s: %s", n, r)
            except Exception as e:  # noqa: BLE001 - um erro inesperado não pode matar o agente
                log.exception("erro no ciclo")
                self._event("error", "erro_ciclo", f"{type(e).__name__}: {e}"[:300])
                self.notifier.notify(Event.TECH_FAILURE, f"{self.symbol}: erro no ciclo ({type(e).__name__}). O agente continua.")
                backoff = min(backoff * 2, self.wcfg.max_backoff_s)
            sleep(backoff)


def quote_from_bars(symbol: str, bars: pd.DataFrame, spread_bps: float, now: datetime) -> Quote:
    """Cotação aproximada a partir da última vela (para fontes sem cotação, como em testes)."""
    c = float(bars["close"].iloc[-1])
    h = c * spread_bps / 2e4
    return Quote(symbol, c - h, c + h, now, "velas")
