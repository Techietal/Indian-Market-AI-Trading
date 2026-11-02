"""Daily backtest of a trend-following strategy against a buy-and-hold benchmark.

Rules (long only, Indian delivery trades, real charges via PaperBroker):
- Signals use closing prices up to *yesterday*; orders fill at *today's open*
  plus slippage. Nothing from today is used before trading today.
- Enter when close > 50-day average > 200-day average. If more stocks qualify
  than free slots, prefer the strongest 6-month return.
- Exit when close falls below the 50-day average.
- Position size and limits come from RiskLimits (default 5% per stock, 50%
  invested, 10 positions, 2% daily loss stop).

Run: python -m trading.backtest --help
"""
import argparse
import csv
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from .data import Bar, load_dir
from .paper import Order, PaperBroker, RiskLimits, RiskRejected

FAST, SLOW, MOMENTUM = 50, 200, 126

DEFAULT_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "BAJFINANCE.NS", "NESTLEIND.NS", "ULTRACEMCO.NS", "HCLTECH.NS",
]
DEFAULT_BENCHMARK = "NIFTYBEES.NS"


class Series:
    """One symbol's bars with precomputed moving averages."""

    def __init__(self, bars: list[Bar]):
        self.bars = bars
        self.index = {b.day: i for i, b in enumerate(bars)}
        closes = [float(b.close) for b in bars]
        cum = [0.0]
        for c in closes:
            cum.append(cum[-1] + c)
        self.closes = closes
        self._cum = cum

    def sma(self, i: int, n: int) -> float | None:
        if i + 1 < n:
            return None
        return (self._cum[i + 1] - self._cum[i + 1 - n]) / n

    def momentum(self, i: int) -> float:
        return self.closes[i] / self.closes[i - MOMENTUM] - 1 if i >= MOMENTUM else 0.0

    def entry_signal(self, i: int) -> bool:
        fast, slow = self.sma(i, FAST), self.sma(i, SLOW)
        return fast is not None and slow is not None and self.closes[i] > fast > slow

    def exit_signal(self, i: int) -> bool:
        fast = self.sma(i, FAST)
        return fast is not None and self.closes[i] < fast


@dataclass
class Result:
    name: str
    curve: list[tuple[date, Decimal]]
    charges: Decimal
    trades: int
    round_trips: int
    wins: int
    rejected: int
    invested_days: int

    def stats(self) -> dict[str, float]:
        start, end = float(self.curve[0][1]), float(self.curve[-1][1])
        years = max((self.curve[-1][0] - self.curve[0][0]).days / 365.25, 1 / 365.25)
        peak, max_dd = start, 0.0
        for _, v in self.curve:
            v = float(v)
            peak = max(peak, v)
            max_dd = min(max_dd, v / peak - 1)
        rets = [float(b) / float(a) - 1 for (_, a), (_, b) in zip(self.curve, self.curve[1:])]
        mean = sum(rets) / len(rets) if rets else 0.0
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1) if len(rets) > 1 else 0.0
        vol = math.sqrt(var) * math.sqrt(252)
        cagr = (end / start) ** (1 / years) - 1
        return {
            "start_value": start, "end_value": end,
            "total_return": end / start - 1, "cagr": cagr, "max_drawdown": max_dd,
            "volatility": vol, "return_per_risk": cagr / vol if vol else 0.0,
        }


def _qty(budget: Decimal, price: Decimal) -> int:
    return int(budget // price) if price > 0 else 0


def run_strategy(data: dict[str, list[Bar]], start: date, end: date | None,
                 capital: Decimal, limits: RiskLimits,
                 trade_log: list[dict] | None = None) -> Result:
    series = {s: Series(b) for s, b in data.items()}
    days = sorted({b.day for bars in data.values() for b in bars
                   if b.day >= start and (end is None or b.day <= end)})
    if not days:
        raise ValueError("No trading days in the chosen date range")
    broker = PaperBroker(cash=capital, limits=limits)
    cost_basis: dict[str, Decimal] = {}
    curve, rejected, wins, round_trips, invested_days = [], 0, 0, 0, 0

    # Seed marks with the last close before the start so equity is defined.
    for sym, s in series.items():
        prior = [b for b in s.bars if b.day < days[0]]
        if prior:
            broker.mark(sym, prior[-1].close)

    def log(day, sym, side, fill, pnl=None):
        if trade_log is not None:
            trade_log.append({"date": day.isoformat(), "symbol": sym, "side": side,
                              "qty": fill.order.quantity, "price": str(fill.price),
                              "charges": str(fill.costs.total),
                              "pnl": "" if pnl is None else str(pnl)})

    for day in days:
        broker.start_day()
        today = {sym: s.index[day] for sym, s in series.items() if day in s.index}

        # 1. Exits, decided on yesterday's close.
        for sym in list(broker.positions):
            i = today.get(sym)
            if i is None or i == 0 or not series[sym].exit_signal(i - 1):
                continue
            broker.mark(sym, series[sym].bars[i].open)
            qty = broker.positions[sym]
            try:
                fill = broker.execute(Order(sym, "SELL", qty))
            except RiskRejected:
                rejected += 1
                continue
            pnl = fill.gross - fill.costs.total - cost_basis.pop(sym)
            round_trips += 1
            wins += pnl > 0
            log(day, sym, "SELL", fill, pnl)

        # 2. Entries, ranked by momentum, decided on yesterday's close.
        candidates = [
            (series[sym].momentum(i - 1), sym) for sym, i in today.items()
            if i > 0 and sym not in broker.positions and series[sym].entry_signal(i - 1)
        ]
        for _, sym in sorted(candidates, reverse=True):
            if len(broker.positions) >= limits.max_positions:
                break
            i = today[sym]
            open_price = series[sym].bars[i].open
            broker.mark(sym, open_price)
            fill_price = open_price * (1 + broker.slippage)
            equity = broker.equity
            exposure = sum(n * broker.marks[s] for s, n in broker.positions.items())
            budget = min(equity * limits.max_position_fraction,
                         equity * limits.max_exposure_fraction - exposure,
                         broker.cash - 100) * Decimal("0.99")
            qty = _qty(budget, fill_price)
            if qty < 1:
                continue
            try:
                fill = broker.execute(Order(sym, "BUY", qty))
            except RiskRejected:
                rejected += 1
                continue
            cost_basis[sym] = fill.gross + fill.costs.total
            log(day, sym, "BUY", fill)

        # 3. Mark to today's close.
        for sym, i in today.items():
            broker.mark(sym, series[sym].bars[i].close)
        invested_days += bool(broker.positions)
        curve.append((day, broker.equity))

    charges = sum((f.costs.total for f in broker.fills), Decimal("0"))
    return Result("Strategy", curve, charges, len(broker.fills), round_trips, wins,
                  rejected, invested_days)


def run_buy_and_hold(bars: list[Bar], start: date, end: date | None,
                     capital: Decimal, name: str) -> Result:
    bars = [b for b in bars if b.day >= start and (end is None or b.day <= end)]
    if not bars:
        raise ValueError(f"No benchmark data for {name} in range")
    all_in = RiskLimits(max_position_fraction=Decimal("1"), max_exposure_fraction=Decimal("1"),
                        max_positions=1, daily_loss_fraction=Decimal("1"))
    broker = PaperBroker(cash=capital, limits=all_in)
    broker.mark(name, bars[0].open)
    qty = _qty(capital * Decimal("0.995"), bars[0].open * (1 + broker.slippage))
    broker.execute(Order(name, "BUY", qty))
    curve = []
    for b in bars:
        broker.mark(name, b.close)
        curve.append((b.day, broker.equity))
    return Result(f"Buy & hold {name}", curve, broker.fills[0].costs.total, 1, 0, 0, 0,
                  len(bars))


def format_report(strategy: Result, benchmark: Result) -> str:
    s, b = strategy.stats(), benchmark.stats()
    pct = lambda x: f"{x * 100:8.2f}%"  # noqa: E731
    inr = lambda x: f"Rs {x:,.0f}"  # noqa: E731
    rows = [
        ("Period", f"{strategy.curve[0][0]} to {strategy.curve[-1][0]}", ""),
        ("Start value", inr(s["start_value"]), inr(b["start_value"])),
        ("End value", inr(s["end_value"]), inr(b["end_value"])),
        ("Total return", pct(s["total_return"]), pct(b["total_return"])),
        ("Yearly return (CAGR)", pct(s["cagr"]), pct(b["cagr"])),
        ("Worst fall from peak", pct(s["max_drawdown"]), pct(b["max_drawdown"])),
        ("Volatility (yearly)", pct(s["volatility"]), pct(b["volatility"])),
        ("Return per unit of risk", f"{s['return_per_risk']:9.2f}", f"{b['return_per_risk']:9.2f}"),
        ("Charges paid", inr(float(strategy.charges)), inr(float(benchmark.charges))),
        ("Orders", str(strategy.trades), str(benchmark.trades)),
    ]
    width = max(len(r[0]) for r in rows) + 2
    out = [f"{'':{width}}{'Strategy':>16}{benchmark.name:>28}"]
    out += [f"{a:{width}}{x:>16}{y:>28}" for a, x, y in rows[1:]]
    out.insert(0, f"Period: {rows[0][1]}")
    if strategy.round_trips:
        out.append(f"Closed trades: {strategy.round_trips}, profitable: "
                   f"{strategy.wins} ({strategy.wins / strategy.round_trips:.0%})")
    out.append(f"Days with any position: {strategy.invested_days / len(strategy.curve):.0%}")
    if strategy.rejected:
        out.append(f"Orders blocked by risk rules: {strategy.rejected}")
    verdict = "BEAT" if s["cagr"] > b["cagr"] else "DID NOT BEAT"
    out.append(f"\nVerdict: the strategy {verdict} buy-and-hold on yearly return.")
    out.append(
        "Caveats: the stock list is today's large caps chosen with hindsight (survivorship\n"
        "bias flatters the strategy); taxes on gains are not included; past results do not\n"
        "predict future returns."
    )
    return "\n".join(out)


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Backtest the trend strategy vs buy-and-hold.")
    p.add_argument("--data", default="data/prices", help="folder of <SYMBOL>.csv files")
    p.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    p.add_argument("--benchmark", default=DEFAULT_BENCHMARK)
    p.add_argument("--start", default="2016-01-01", type=date.fromisoformat)
    p.add_argument("--end", default=None, type=date.fromisoformat)
    p.add_argument("--capital", default="100000", type=Decimal)
    p.add_argument("--max-position", default="0.05", type=Decimal,
                   help="max fraction of equity in one stock (default 0.05)")
    p.add_argument("--max-invested", default="0.50", type=Decimal,
                   help="max fraction of equity invested overall (default 0.50)")
    p.add_argument("--max-positions", default=10, type=int)
    p.add_argument("--out", default="data/results", help="folder for trades/equity CSVs")
    a = p.parse_args(argv)

    data = load_dir(Path(a.data), a.symbols)
    bench = load_dir(Path(a.data), [a.benchmark])[a.benchmark]
    limits = RiskLimits(max_position_fraction=a.max_position,
                        max_exposure_fraction=a.max_invested, max_positions=a.max_positions)
    trades: list[dict] = []
    strat = run_strategy(data, a.start, a.end, a.capital, limits, trades)
    first_day = strat.curve[0][0]
    hold = run_buy_and_hold(bench, first_day, a.end, a.capital, a.benchmark)
    print(format_report(strat, hold))

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "trades.csv", trades)
    bench_by_day = dict(hold.curve)
    _write_csv(out / "equity.csv", [
        {"date": d.isoformat(), "strategy": str(v), "benchmark": str(bench_by_day.get(d, ""))}
        for d, v in strat.curve
    ])
    print(f"\nSaved {out / 'trades.csv'} and {out / 'equity.csv'}")


if __name__ == "__main__":
    main()
