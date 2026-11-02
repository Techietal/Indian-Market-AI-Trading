"""Simulated broker for paper trading. Never talks to a real broker API.

Fills happen at the latest market price supplied through ``mark()``, adjusted
for slippage, never at a price the caller makes up. Orders can carry an
optional limit price; a fill worse than the limit is rejected.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .costs import CostBreakdown, DeliveryCostModel

PAISA = Decimal("0.01")


class RiskRejected(ValueError):
    pass


@dataclass(frozen=True)
class Order:
    symbol: str
    side: str
    quantity: int
    limit_price: Decimal | None = None


@dataclass(frozen=True)
class Fill:
    order: Order
    price: Decimal
    gross: Decimal
    costs: CostBreakdown


@dataclass(frozen=True)
class RiskLimits:
    max_position_fraction: Decimal = Decimal("0.05")
    max_exposure_fraction: Decimal = Decimal("0.50")
    max_positions: int = 10
    daily_loss_fraction: Decimal = Decimal("0.02")  # block new buys after this drawdown


@dataclass
class PaperBroker:
    cash: Decimal = Decimal("100000")
    limits: RiskLimits = field(default_factory=RiskLimits)
    costs: DeliveryCostModel = field(default_factory=DeliveryCostModel)
    slippage: Decimal = Decimal("0.0005")  # 0.05% against us on every fill
    positions: dict[str, int] = field(default_factory=dict)
    marks: dict[str, Decimal] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)
    day_start_equity: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.cash, Decimal) or self.cash <= 0:
            raise ValueError("Starting cash must be a positive Decimal")
        if not isinstance(self.slippage, Decimal) or not 0 <= self.slippage < 1:
            raise ValueError("Slippage must be a Decimal in [0, 1)")
        if self.day_start_equity is None:
            self.day_start_equity = self.cash

    @property
    def equity(self) -> Decimal:
        return self.cash + sum(n * self.marks[s] for s, n in self.positions.items())

    def mark(self, symbol: str, price: Decimal) -> None:
        """Record the latest market price for a symbol (from the data feed)."""
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("Invalid symbol")
        if not isinstance(price, Decimal) or not price.is_finite() or price <= 0:
            raise ValueError("Price must be a positive Decimal")
        self.marks[symbol] = price

    def start_day(self) -> None:
        """Call once at market open to reset the daily loss circuit breaker."""
        self.day_start_equity = self.equity

    def execute(self, order: Order) -> Fill:
        self._validate(order)
        market = self.marks.get(order.symbol)
        if market is None:
            raise RiskRejected("No market price for symbol; call mark() first")

        adjust = 1 + self.slippage if order.side == "BUY" else 1 - self.slippage
        price = (market * adjust).quantize(PAISA, rounding=ROUND_HALF_UP)
        if order.limit_price is not None:
            if order.side == "BUY" and price > order.limit_price:
                raise RiskRejected("Fill price above buy limit")
            if order.side == "SELL" and price < order.limit_price:
                raise RiskRejected("Fill price below sell limit")

        gross = price * order.quantity
        costs = self.costs.charges(order.side, gross)
        owned = self.positions.get(order.symbol, 0)
        equity = self.equity

        if order.side == "BUY":
            if equity < self.day_start_equity * (1 - self.limits.daily_loss_fraction):
                raise RiskRejected("Daily loss limit reached; no new buys today")
            if gross + costs.total > self.cash:
                raise RiskRejected("Insufficient virtual cash including charges")
            if (owned + order.quantity) * price > equity * self.limits.max_position_fraction:
                raise RiskRejected("Per-stock allocation limit")
            if owned == 0 and len(self.positions) >= self.limits.max_positions:
                raise RiskRejected("Maximum position count")
            exposure = sum(n * self.marks[s] for s, n in self.positions.items())
            if exposure + gross > equity * self.limits.max_exposure_fraction:
                raise RiskRejected("Portfolio exposure limit")
            self.cash -= gross + costs.total
            new_quantity = owned + order.quantity
        else:
            if owned < order.quantity:
                raise RiskRejected("Short selling is disabled")
            self.cash += gross - costs.total
            new_quantity = owned - order.quantity

        if new_quantity:
            self.positions[order.symbol] = new_quantity
        else:
            self.positions.pop(order.symbol, None)
        fill = Fill(order, price, gross, costs)
        self.fills.append(fill)
        return fill

    @staticmethod
    def _validate(order: Order) -> None:
        if not isinstance(order.symbol, str) or not order.symbol:
            raise RiskRejected("Invalid symbol")
        if order.side not in ("BUY", "SELL"):
            raise RiskRejected("Side must be BUY or SELL")
        if type(order.quantity) is not int or order.quantity <= 0:
            raise RiskRejected("Quantity must be a positive whole number")
        lp = order.limit_price
        if lp is not None and (not isinstance(lp, Decimal) or not lp.is_finite() or lp <= 0):
            raise RiskRejected("Limit price must be a positive Decimal")
