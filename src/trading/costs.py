"""Indian equity delivery (CNC) transaction costs.

Default rates are for NSE delivery trades via Upstox, taken from
https://upstox.com/brokerage-charges/ and cross-checked against
https://zerodha.com/charges (checked 2 Nov 2026). Rates change; review them
periodically and override via ``DeliveryCostModel(...)`` for another broker.

Simplifications:
- DP (depository) charge is applied per sell order. Real brokers charge it once
  per scrip per day, so several sells of one stock on one day are over-charged.
- STT is rounded to the paisa here; exchanges round STT to the nearest rupee.
- IPFT (Rs 0.01/crore) is ignored as negligible.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

PAISA = Decimal("0.01")
CRORE = Decimal("10000000")


def _r(x: Decimal) -> Decimal:
    return x.quantize(PAISA, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CostBreakdown:
    brokerage: Decimal
    stt: Decimal
    exchange: Decimal
    sebi: Decimal
    stamp_duty: Decimal
    dp: Decimal
    gst: Decimal

    @property
    def total(self) -> Decimal:
        return (self.brokerage + self.stt + self.exchange + self.sebi
                + self.stamp_duty + self.dp + self.gst)


@dataclass(frozen=True)
class DeliveryCostModel:
    brokerage_per_order: Decimal = Decimal("20")
    stt_rate: Decimal = Decimal("0.001")              # 0.1% on buy and sell
    exchange_rate: Decimal = Decimal("0.0000307")     # NSE 0.00307% from 1 Mar 2026
    sebi_per_crore: Decimal = Decimal("10")
    stamp_duty_rate: Decimal = Decimal("0.00015")     # 0.015%, buy side only
    dp_per_sell: Decimal = Decimal("20")              # plus GST, sell side only
    gst_rate: Decimal = Decimal("0.18")               # on brokerage, exchange, SEBI, DP

    def charges(self, side: str, turnover: Decimal) -> CostBreakdown:
        if side not in ("BUY", "SELL") or turnover <= 0:
            raise ValueError("Invalid side or turnover")
        brokerage = _r(min(self.brokerage_per_order, turnover))
        stt = _r(turnover * self.stt_rate)
        exchange = _r(turnover * self.exchange_rate)
        sebi = _r(turnover * self.sebi_per_crore / CRORE)
        stamp = _r(turnover * self.stamp_duty_rate) if side == "BUY" else Decimal("0.00")
        dp = _r(self.dp_per_sell) if side == "SELL" else Decimal("0.00")
        gst = _r((brokerage + exchange + sebi + dp) * self.gst_rate)
        return CostBreakdown(brokerage, stt, exchange, sebi, stamp, dp, gst)
