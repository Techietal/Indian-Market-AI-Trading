import math
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from trading.backtest import Result, main, run_buy_and_hold, run_strategy
from trading.data import Bar, load_csv
from trading.paper import RiskLimits

START = date(2020, 1, 1)


def make_bars(closes, start=START):
    bars, day = [], start
    for c in closes:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        p = D(str(round(c, 2)))
        bars.append(Bar(day, p, p, p, p, 1000))
        day += timedelta(days=1)
    return bars


def write_csv(path, bars):
    lines = ["Date,Open,High,Low,Close,Volume"]
    lines += [f"{b.day},{b.open},{b.high},{b.low},{b.close},{b.volume}" for b in bars]
    path.write_text("\n".join(lines) + "\n")


def test_load_csv_skips_bad_and_duplicate_rows(tmp_path):
    f = tmp_path / "X.csv"
    f.write_text("Date,Open,High,Low,Close,Volume\n"
                 "2024-01-01,10,11,9,10.5,100\n"
                 "2024-01-01,10,11,9,10.5,100\n"
                 "2024-01-02,,,,,\n"
                 "2024-01-03,10,11,9,-1,100\n"
                 "2024-01-04,10.123,11,9,10.456,100\n")
    bars = load_csv(f)
    assert [b.day.day for b in bars] == [1, 4]
    assert bars[1].close == D("10.46")


def test_uptrend_gets_bought_and_downtrend_sold():
    up = [100 * 1.002 ** i for i in range(300)]
    down = [up[-1] * 0.99 ** i for i in range(1, 80)]
    log = []
    res = run_strategy({"UP": make_bars(up + down)}, START, None, D("100000"),
                       RiskLimits(), log)
    sides = [t["side"] for t in log]
    assert sides[0] == "BUY" and "SELL" in sides
    assert res.round_trips == 1


def test_no_lookahead_trades_use_previous_close():
    # Flat for 250 days (no signal), then a jump. The signal can only be seen
    # after the jump day's close, so the first buy must be the day after.
    closes = [100.0] * 250 + [100.0 + i for i in range(1, 40)]
    bars = make_bars(closes)
    log = []
    run_strategy({"J": bars}, START, None, D("100000"), RiskLimits(), log)
    first_buy = date.fromisoformat(log[0]["date"])
    jump_day = bars[250].day
    assert first_buy > jump_day
    buy_bar = next(b for b in bars if b.day == first_buy)
    assert D(log[0]["price"]) >= buy_bar.open  # filled at that day's open + slippage


def test_position_size_respects_limits():
    up = [100 * 1.002 ** i for i in range(300)]
    data = {f"S{k}": make_bars(up) for k in range(15)}
    res = run_strategy(data, START, None, D("100000"), RiskLimits())
    assert res.trades <= 10  # max 10 positions, no exits in a pure uptrend


def test_buy_and_hold_and_stats():
    bars = make_bars([100, 110, 99, 120])
    res = run_buy_and_hold(bars, START, None, D("100000"), "IDX")
    s = res.stats()
    assert s["end_value"] > s["start_value"]
    assert s["max_drawdown"] == pytest.approx(99 / 110 - 1, abs=0.01)


def test_stats_flat_curve():
    r = Result("x", [(date(2020, 1, 1), D("100")), (date(2021, 1, 1), D("100"))],
               D("0"), 0, 0, 0, 0, 0)
    s = r.stats()
    assert s["cagr"] == 0 and s["max_drawdown"] == 0 and not math.isnan(s["volatility"])


def test_cli_end_to_end(tmp_path, capsys):
    prices = tmp_path / "prices"
    prices.mkdir()
    up = [100 * 1.001 ** i for i in range(400)]
    for sym in ("A", "B"):
        write_csv(prices / f"{sym}.csv", make_bars(up))
    write_csv(prices / "IDX.csv", make_bars(up))
    out = tmp_path / "results"
    main(["--data", str(prices), "--symbols", "A", "B", "--benchmark", "IDX",
          "--start", "2020-11-01", "--out", str(out)])
    text = capsys.readouterr().out
    assert "Verdict" in text and "Buy & hold IDX" in text
    assert (out / "equity.csv").exists() and (out / "trades.csv").exists()


def test_missing_file_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="fetch_prices"):
        main(["--data", str(tmp_path), "--symbols", "NOPE"])
