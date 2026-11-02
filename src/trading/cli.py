from decimal import Decimal

from .paper import Order, PaperBroker


def main() -> None:
    broker = PaperBroker()
    broker.mark("SYNTHETIC", Decimal("1000"))  # stand-in for a live market price
    buy = broker.execute(Order("SYNTHETIC", "BUY", 4))
    print("PAPER ONLY - synthetic price, no market feed")
    print(f"Bought 4 @ {buy.price} | charges Rs {buy.costs.total}")
    broker.mark("SYNTHETIC", Decimal("1020"))
    sell = broker.execute(Order("SYNTHETIC", "SELL", 4))
    print(f"Sold   4 @ {sell.price} | charges Rs {sell.costs.total}")
    print(f"Virtual cash: Rs {broker.cash}  (started at Rs 100000)")


if __name__ == "__main__":
    main()
