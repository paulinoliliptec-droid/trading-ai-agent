"""Motor de decisão e risco: determinístico, separado dos modelos, e com a última palavra.

O modelo propõe (lado, probabilidade); o risco decide (negociar, com que tamanho, ou NÃO
negociar) e diz porquê. Nenhuma probabilidade, por mais alta, passa por cima de uma regra.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from trading_agent.config import RiskLimits
from trading_agent.risk.kill_switch import KillSwitch


@dataclass
class Proposal:
    symbol: str
    side: int                 # 1 comprado, -1 vendido, 0 nada
    probability: float        # probabilidade calibrada de o TP vir antes do SL
    tp_pct: float             # distância ao take-profit (fração do preço)
    sl_pct: float             # distância ao stop-loss (fração do preço)
    cost_pct: float           # custo estimado ida e volta (spread + comissões + slippage)
    spread_bps: float
    atr_pct: float


@dataclass
class PortfolioState:
    equity: float
    peak_equity: float
    day_start_equity: float
    open_positions: int
    exposure_by_symbol: dict[str, float] = field(default_factory=dict)  # fração do capital
    venue_available: bool = True


@dataclass
class Decision:
    trade: bool
    side: int
    size_fraction: float      # nocional / capital
    expected_edge_bps: float
    reasons: list[str]


def expected_edge(p: float, tp_pct: float, sl_pct: float, cost_pct: float) -> float:
    """Expectativa por operação (fração), aproximando a saída por tempo como neutra."""
    return p * tp_pct - (1 - p) * sl_pct - cost_pct


class RiskEngine:
    def __init__(self, limits: RiskLimits, kill_switch: KillSwitch, max_leverage: float = 1.0):
        self.limits = limits
        self.kill_switch = kill_switch
        self.max_leverage = max_leverage

    def evaluate(self, p: Proposal, s: PortfolioState) -> Decision:
        L = self.limits
        reasons: list[str] = []
        if self.kill_switch.is_engaged():
            reasons.append("kill switch acionado")
        if p.side == 0:
            reasons.append("sem sinal")
        if not s.venue_available:
            reasons.append("corretora indisponível")
        if p.probability < L.min_probability:
            reasons.append(f"probabilidade {p.probability:.3f} < {L.min_probability}")
        edge = expected_edge(p.probability, p.tp_pct, p.sl_pct, p.cost_pct)
        if edge * 1e4 < L.min_expected_edge_bps:
            reasons.append(f"expectativa {edge * 1e4:.2f} bps < {L.min_expected_edge_bps} bps depois de custos")
        if p.spread_bps > L.max_spread_bps:
            reasons.append(f"spread {p.spread_bps:.2f} bps > {L.max_spread_bps}")
        if p.atr_pct > L.max_atr_pct:
            reasons.append(f"volatilidade {p.atr_pct:.4f} > {L.max_atr_pct}")
        if s.open_positions >= L.max_open_positions:
            reasons.append("máximo de posições simultâneas")
        if s.day_start_equity > 0 and (s.equity / s.day_start_equity - 1) <= -L.max_daily_loss_pct:
            reasons.append("limite diário de perdas atingido")
        if s.peak_equity > 0 and (s.equity / s.peak_equity - 1) <= -L.max_drawdown_pct:
            reasons.append("drawdown máximo atingido")
        if p.sl_pct <= 0:
            reasons.append("stop-loss inválido")

        # Tamanho: perda no stop = max_loss_per_trade_pct do capital, com tectos de alavancagem e exposição.
        size = 0.0
        if p.sl_pct > 0:
            size = L.max_loss_per_trade_pct / (p.sl_pct + p.cost_pct)
        cap_exposure = L.max_exposure_per_asset_pct * self.max_leverage
        size = min(size, self.max_leverage, cap_exposure - s.exposure_by_symbol.get(p.symbol, 0.0))
        if size <= 0:
            reasons.append("sem margem de exposição para este ativo")
        trade = not reasons
        return Decision(trade, p.side if trade else 0, size if trade else 0.0, edge * 1e4, reasons or ["aprovado"])
