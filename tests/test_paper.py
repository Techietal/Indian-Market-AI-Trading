from decimal import Decimal
import pytest
from trading.paper import PaperBroker, Order, RiskRejected
from trading.ai import AISettings


def test_buy_and_sell():
    b = PaperBroker()
    b.execute(Order("TEST", "BUY", 10, Decimal("100")))
    assert b.cash == Decimal("98999.000")
    b.execute(Order("TEST", "SELL", 10, Decimal("110")))
    assert b.positions == {}
    assert b.cash == Decimal("100097.900")


def test_no_short():
    with pytest.raises(RiskRejected):
        PaperBroker().execute(Order("TEST", "SELL", 1, Decimal("100")))


def test_position_limit_no_partial_write():
    b = PaperBroker()
    with pytest.raises(RiskRejected):
        b.execute(Order("TEST", "BUY", 60, Decimal("100")))
    assert (b.cash, b.positions, b.marks, b.fills) == (Decimal("100000"), {}, {}, [])


def test_invalid_quantity():
    with pytest.raises(RiskRejected):
        PaperBroker().execute(Order("TEST", "BUY", 0, Decimal("100")))


def test_ai_allowlist():
    with pytest.raises(ValueError):
        AISettings().endpoint()
    assert "deepseek.com" in AISettings("deepseek", "test-model", "dummy").endpoint()
    with pytest.raises(ValueError):
        AISettings("other", "test-model", "dummy").endpoint()
