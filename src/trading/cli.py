from decimal import Decimal
from .paper import Order, PaperBroker


def main() -> None:
    broker = PaperBroker()
    broker.execute(Order("SYNTHETIC", "BUY", 1, Decimal("100")))
    print("PAPER ONLY: virtual cash", broker.cash)
    print("PAPER ONLY: virtual equity", broker.equity)


if __name__ == "__main__":
    main()
