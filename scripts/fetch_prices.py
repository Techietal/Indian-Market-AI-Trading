"""Download daily NSE prices from Yahoo Finance into data/prices/<SYMBOL>.csv.

Usage:
    python scripts/fetch_prices.py                 # default 20 stocks + NIFTYBEES
    python scripts/fetch_prices.py --start 2012-01-01 --symbols INFY.NS TCS.NS

Requires the research extra:  pip install -e ".[research]"

Prices are adjusted for splits and dividends (auto_adjust=True). Yahoo data is
unofficial and free; spot-check a few values against NSE before trusting results.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trading.backtest import DEFAULT_BENCHMARK, DEFAULT_SYMBOLS  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS + [DEFAULT_BENCHMARK])
    p.add_argument("--start", default="2014-01-01",
                   help="first date to download; keep ~1 year before your backtest start")
    p.add_argument("--out", default="data/prices")
    a = p.parse_args()

    try:
        import yfinance as yf
    except ImportError:
        print('yfinance is not installed. Run: pip install -e ".[research]"')
        return 1

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    failed = []
    for sym in a.symbols:
        try:
            df = yf.Ticker(sym).history(start=a.start, interval="1d", auto_adjust=True)
        except Exception as exc:  # network errors, rate limits
            print(f"{sym:16} FAILED: {exc}")
            failed.append(sym)
            continue
        if df is None or df.empty:
            print(f"{sym:16} FAILED: no data returned")
            failed.append(sym)
            continue
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        df.index = df.index.strftime("%Y-%m-%d")
        df.index.name = "Date"
        df.round(2).to_csv(out / f"{sym}.csv")
        print(f"{sym:16} {len(df):5d} days  {df.index[0]} to {df.index[-1]}")
        time.sleep(1)  # be polite to the free endpoint
    if failed:
        print(f"\n{len(failed)} symbol(s) failed: {' '.join(failed)}. Re-run later to retry.")
        return 1
    print(f"\nSaved {len(a.symbols)} files to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
