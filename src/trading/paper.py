from dataclasses import dataclass
from decimal import Decimal


class RiskRejected(ValueError):
    pass


@dataclass(frozen=True)
class Order:
    symbol: str
    side: str
    quantity: int
    price: Decimal


class PaperBroker:
    """Synthetic fills; never interacts with a broker API."""

    def __init__(self, cash: Decimal = Decimal("100000"),
                 fee_rate: Decimal = Decimal("0.001")):
        if cash <= 0 or fee_rate < 0:
            raise ValueError("Invalid settings")
        self.cash = cash
        self.fee_rate = fee_rate
        self.positions: dict[str, int] = {}
        self.marks: dict[str, Decimal] = {}
        self.fills: list[Order] = []

    @property
    def equity(self) -> Decimal:
        return self.cash + sum(n * self.marks[s] for s, n in self.positions.items())

    def execute(self, order: Order) -> None:
        if not order.symbol or order.side not in ("BUY", "SELL"):
            raise RiskRejected("Invalid order type")
        if order.quantity <= 0 or order.price <= 0:
            raise RiskRejected("Invalid quantity/price")
        marks = {**self.marks, order.symbol: order.price}
        equity = self.cash + sum(n * marks[s] for s, n in self.positions.items())
        gross = order.price * order.quantity
        fee = gross * self.fee_rate
        owned = self.positions.get(order.symbol, 0)
        if order.side == "BUY":
            if gross + fee > self.cash:
                raise RiskRejected("Insufficient virtual cash")
            if (owned + order.quantity) * order.price > equity * Decimal("0.05"):
                raise RiskRejected("Per-stock allocation limit")
            if owned == 0 and len(self.positions) >= 10:
                raise RiskRejected("Maximum position count")
            exposure = sum(n * marks[s] for s, n in self.positions.items())
            if exposure + gross > equity * Decimal("0.50"):
                raise RiskRejected("Portfolio exposure limit")
            new_cash, new_quantity = self.cash - gross - fee, owned + order.quantity
        else:
            if owned < order.quantity:
                raise RiskRejected("Short selling is disabled")
            new_cash, new_quantity = self.cash + gross - fee, owned - order.quantity
        self.cash = new_cash
        self.marks = marks
        if new_quantity:
            self.positions[order.symbol] = new_quantity
        else:
            self.positions.pop(order.symbol, None)
        self.fills.append(order)
