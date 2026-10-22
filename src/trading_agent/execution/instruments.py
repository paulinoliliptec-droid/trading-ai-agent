"""Especificação de cada instrumento e conversão cambial explícita.

Cada mercado tem as suas regras: quantidade mínima, passo, alavancagem máxima, se permite
vender a descoberto, custos e base dos preços (bid ou médio). A conta pode estar em EUR e o
instrumento cotado em USD: a conversão faz-se SEMPRE com uma taxa conhecida no instante, e
falha se a taxa não existir (nunca se presume 1:1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    asset_class: str
    base_currency: str
    quote_currency: str
    min_qty: float
    qty_step: float
    max_leverage: float = 1.0
    allow_short: bool = False
    fee_bps: float = 0.0          # por lado, sobre o nocional
    slippage_bps: float = 0.0     # por lado, contra nós
    default_spread_bps: float = 0.0
    price_basis: str = "mid"      # «bid» (Dukascopy) ou «mid» (velas de negócios)
    enabled: bool = True
    disabled_reason: str = ""

    @classmethod
    def from_config(cls, symbol: str, m: dict) -> InstrumentSpec:
        base, quote = symbol.split("/") if "/" in symbol else (symbol, "USD")
        return cls(
            symbol=symbol, asset_class=m["asset_class"], base_currency=m.get("base_currency", base),
            quote_currency=m.get("quote_currency", quote), min_qty=float(m.get("min_qty", 0.0)),
            qty_step=float(m.get("qty_step", 1e-8)), max_leverage=float(m.get("max_leverage", 1.0)),
            allow_short=bool(m.get("allow_short", False)), fee_bps=float(m.get("fee_bps", 0.0)),
            slippage_bps=float(m.get("slippage_bps", 0.0)), default_spread_bps=float(m.get("spread_bps", 0.0)),
            price_basis=m.get("price_basis", "mid"), enabled=bool(m.get("enabled", True)),
            disabled_reason=m.get("disabled_reason", ""),
        )

    def round_qty(self, qty: float) -> float:
        """Arredonda PARA BAIXO ao passo negociável (nunca se arredonda para cima o risco)."""
        if self.qty_step <= 0:
            return qty
        steps = math.floor(qty / self.qty_step + 1e-9)
        return round(steps * self.qty_step, 12)

    def round_trip_cost_pct(self, spread_bps: float | None = None) -> float:
        s = self.default_spread_bps if spread_bps is None or math.isnan(spread_bps) else spread_bps
        return (s + 2 * self.fee_bps + 2 * self.slippage_bps) / 1e4


@dataclass
class FxConverter:
    """Taxas de câmbio conhecidas no instante. `rates[("EUR","USD")] = 1.08` quer dizer 1 EUR = 1,08 USD."""

    rates: dict[tuple[str, str], float] = field(default_factory=dict)

    def set_rate(self, base: str, quote: str, rate: float) -> None:
        if not rate or rate <= 0 or math.isnan(rate):
            raise ValueError(f"taxa inválida {base}/{quote}: {rate}")
        self.rates[(base, quote)] = float(rate)

    def convert(self, amount: float, from_ccy: str, to_ccy: str) -> float:
        if from_ccy == to_ccy:
            return amount
        if (from_ccy, to_ccy) in self.rates:
            return amount * self.rates[(from_ccy, to_ccy)]
        if (to_ccy, from_ccy) in self.rates:
            return amount / self.rates[(to_ccy, from_ccy)]
        raise LookupError(f"sem taxa de câmbio {from_ccy}→{to_ccy}: a conversão não é presumida")


def capital_sufficiency(spec: InstrumentSpec, capital: float, price: float, stop_pct: float,
                        max_loss_pct: float, fx_to_quote: float = 1.0) -> dict:
    """Diz se um capital chega para negociar o instrumento respeitando o risco por operação.

    `capital` na moeda da conta; `fx_to_quote` converte-a para a moeda de cotação. Compara o
    nocional que o risco permite com o nocional da quantidade mínima negociável.
    """
    risk_budget = capital * max_loss_pct * fx_to_quote
    notional_allowed = risk_budget / stop_pct if stop_pct > 0 else 0.0
    notional_allowed = min(notional_allowed, capital * fx_to_quote * spec.max_leverage)
    min_notional = spec.min_qty * price
    loss_at_min = min_notional * stop_pct / fx_to_quote
    return {
        "simbolo": spec.symbol,
        "capital": capital,
        "nocional_permitido_pelo_risco": round(notional_allowed, 4),
        "nocional_da_quantidade_minima": round(min_notional, 4),
        "perda_no_stop_com_quantidade_minima": round(loss_at_min, 4),
        "perda_no_stop_pct_capital_com_quantidade_minima": round(loss_at_min / capital * 100, 3) if capital else None,
        "suficiente": notional_allowed >= min_notional and spec.enabled,
        "nota": spec.disabled_reason if not spec.enabled else "",
    }
