from decimal import Decimal as D

import pytest

from trading.costs import DeliveryCostModel


def test_buy_charges_worked_example():
    # Rs 10,000 delivery buy on NSE via Upstox-style pricing
    c = DeliveryCostModel().charges("BUY", D("10000"))
    assert c.brokerage == D("20.00")
    assert c.stt == D("10.00")          # 0.1%
    assert c.exchange == D("0.31")      # 0.00307%
    assert c.sebi == D("0.01")          # Rs 10 / crore
    assert c.stamp_duty == D("1.50")    # 0.015% buy side
    assert c.dp == D("0.00")
    assert c.gst == D("3.66")           # 18% of (20 + 0.31 + 0.01)
    assert c.total == D("35.48")


def test_sell_charges_worked_example():
    c = DeliveryCostModel().charges("SELL", D("11000"))
    assert c.stt == D("11.00")
    assert c.stamp_duty == D("0.00")    # no stamp duty on sells
    assert c.dp == D("20.00")
    assert c.gst == D("7.26")           # 18% of (20 + 0.34 + 0.01 + 20)
    assert c.total == D("58.61")


def test_brokerage_never_exceeds_turnover():
    assert DeliveryCostModel().charges("BUY", D("5")).brokerage == D("5.00")


def test_zero_brokerage_broker():
    c = DeliveryCostModel(brokerage_per_order=D("0")).charges("BUY", D("10000"))
    assert c.brokerage == D("0.00")


@pytest.mark.parametrize("side,turnover", [("HOLD", D("100")), ("BUY", D("0"))])
def test_invalid_inputs(side, turnover):
    with pytest.raises(ValueError):
        DeliveryCostModel().charges(side, turnover)
