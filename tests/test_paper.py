from decimal import Decimal as D

import pytest

from trading.paper import Order, PaperBroker, RiskLimits, RiskRejected


def broker(**kw) -> PaperBroker:
    kw.setdefault("slippage", D("0"))
    return PaperBroker(**kw)


def test_round_trip_with_real_charges():
    b = broker()
    b.mark("TEST", D("1000"))
    buy = b.execute(Order("TEST", "BUY", 4))
    assert buy.price == D("1000.00")
    assert b.cash == D("100000") - D("4000") - buy.costs.total
    b.mark("TEST", D("1100"))
    sell = b.execute(Order("TEST", "SELL", 4))
    assert b.positions == {}
    assert b.cash == D("100000") + D("400") - buy.costs.total - sell.costs.total


def test_small_gain_eaten_by_charges():
    # A 0.5% price gain on a Rs 4,000 trade is less than the round-trip charges.
    b = broker()
    b.mark("TEST", D("1000"))
    b.execute(Order("TEST", "BUY", 4))
    b.mark("TEST", D("1005"))
    b.execute(Order("TEST", "SELL", 4))
    assert b.cash < D("100000")


def test_fill_uses_market_price_not_caller_price():
    b = broker()
    b.mark("X", D("100"))
    b.execute(Order("X", "BUY", 10))
    b.mark("X", D("100"))
    fill = b.execute(Order("X", "SELL", 10, limit_price=D("1")))
    assert fill.price == D("100.00")  # limit is a floor, not the fill price


def test_slippage_moves_against_us():
    b = PaperBroker(slippage=D("0.001"))
    b.mark("X", D("1000"))
    assert b.execute(Order("X", "BUY", 1)).price == D("1001.00")
    assert b.execute(Order("X", "SELL", 1)).price == D("999.00")


def test_limit_prices_enforced():
    b = PaperBroker(slippage=D("0.001"))
    b.mark("X", D("1000"))
    with pytest.raises(RiskRejected, match="above buy limit"):
        b.execute(Order("X", "BUY", 1, limit_price=D("1000")))
    b.execute(Order("X", "BUY", 1, limit_price=D("1002")))
    with pytest.raises(RiskRejected, match="below sell limit"):
        b.execute(Order("X", "SELL", 1, limit_price=D("1000")))


def test_requires_market_price():
    with pytest.raises(RiskRejected, match="No market price"):
        broker().execute(Order("X", "BUY", 1))


def test_no_short_selling():
    b = broker()
    b.mark("X", D("100"))
    with pytest.raises(RiskRejected, match="Short selling"):
        b.execute(Order("X", "SELL", 1))


def test_rejection_leaves_state_untouched():
    b = broker()
    b.mark("X", D("100"))
    with pytest.raises(RiskRejected, match="Per-stock"):
        b.execute(Order("X", "BUY", 60))
    assert (b.cash, b.positions, b.fills) == (D("100000"), {}, [])


def test_position_count_limit():
    b = broker(limits=RiskLimits(max_positions=2))
    for s in ("A", "B", "C"):
        b.mark(s, D("100"))
    b.execute(Order("A", "BUY", 1))
    b.execute(Order("B", "BUY", 1))
    with pytest.raises(RiskRejected, match="position count"):
        b.execute(Order("C", "BUY", 1))


def test_exposure_limit():
    b = broker(limits=RiskLimits(max_position_fraction=D("1"), max_exposure_fraction=D("0.10")))
    b.mark("A", D("100"))
    b.execute(Order("A", "BUY", 90))
    with pytest.raises(RiskRejected, match="exposure"):
        b.execute(Order("A", "BUY", 20))


def test_daily_loss_circuit_breaker():
    b = broker(limits=RiskLimits(max_position_fraction=D("1"), max_exposure_fraction=D("1")))
    b.mark("A", D("1000"))
    b.execute(Order("A", "BUY", 50))       # Rs 50,000 position
    b.mark("A", D("940"))                  # -Rs 3,000 (~3% of equity)
    with pytest.raises(RiskRejected, match="Daily loss"):
        b.execute(Order("A", "BUY", 1))
    b.execute(Order("A", "SELL", 10))      # selling is still allowed
    b.start_day()
    b.execute(Order("A", "BUY", 1))        # new day, limit resets


def test_equity_tracks_marks():
    b = broker()
    b.mark("A", D("100"))
    b.execute(Order("A", "BUY", 10))
    before = b.equity
    b.mark("A", D("50"))
    assert b.equity == before - D("500")


@pytest.mark.parametrize("order", [
    Order("X", "BUY", 0),
    Order("X", "BUY", 1.5),
    Order("X", "BUY", True),
    Order("X", "HOLD", 1),
    Order("", "BUY", 1),
    Order("X", "BUY", 1, limit_price=100.0),
    Order("X", "BUY", 1, limit_price=D("NaN")),
])
def test_invalid_orders_rejected_cleanly(order):
    b = broker()
    b.mark("X", D("100"))
    with pytest.raises(RiskRejected):
        b.execute(order)


@pytest.mark.parametrize("price", [100.0, D("0"), D("-1"), D("Infinity")])
def test_invalid_marks_rejected(price):
    with pytest.raises(ValueError):
        broker().mark("X", price)
