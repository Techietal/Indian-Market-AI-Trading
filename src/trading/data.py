"""Load daily OHLCV price files.

One CSV per symbol, named ``<SYMBOL>.csv``, with header
``Date,Open,High,Low,Close,Volume`` and ISO dates (YYYY-MM-DD), oldest first.
``scripts/fetch_prices.py`` writes files in this format.
"""
import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class Bar:
    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def _price(text: str) -> Decimal:
    value = Decimal(text).quantize(Decimal("0.01"))
    if not value.is_finite() or value <= 0:
        raise ValueError(f"Bad price {text!r}")
    return value


def load_csv(path: Path) -> list[Bar]:
    bars: list[Bar] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                bar = Bar(
                    day=date.fromisoformat(row["Date"][:10]),
                    open=_price(row["Open"]),
                    high=_price(row["High"]),
                    low=_price(row["Low"]),
                    close=_price(row["Close"]),
                    volume=int(float(row.get("Volume") or 0)),
                )
            except (ValueError, ArithmeticError, KeyError, TypeError):
                continue  # skip blank/holiday/corrupt rows
            if bars and bar.day <= bars[-1].day:
                continue  # drop duplicates / out-of-order rows
            bars.append(bar)
    if not bars:
        raise ValueError(f"No usable rows in {path}")
    return bars


def load_dir(folder: Path, symbols: list[str]) -> dict[str, list[Bar]]:
    data = {}
    for symbol in symbols:
        path = Path(folder) / f"{symbol}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}; run scripts/fetch_prices.py first")
        data[symbol] = load_csv(path)
    return data
