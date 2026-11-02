# Running the backtest on EC2

The backtest compares a simple trend-following strategy on 20 large NSE stocks
against buying and holding NIFTYBEES (a Nifty 50 ETF), using real Indian
delivery charges. No API keys or broker account are needed.

## 1. Instance

Any small instance works; a full 10-year run takes about a second.

- `t3.micro` or `t3.small`, Ubuntu 24.04, Mumbai (`ap-south-1`)
- 8 GiB disk or more
- Outbound HTTPS allowed (the default security group allows it)

You can **stop the instance when you're done**; backtesting doesn't need it running 24/7.

## 2. One-time setup

Ubuntu 24.04 (ships Python 3.12):

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip
```

Amazon Linux 2023 (default Python is too old, install 3.11):

```bash
sudo dnf install -y git python3.11 python3.11-pip
# then use python3.11 instead of python3 in the next step
```

Get the code and install it:

```bash
git clone https://github.com/Techietal/Indian-Market-AI-Trading.git
cd Indian-Market-AI-Trading
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,research]"
pytest -q          # should say all tests passed
```

Each new SSH session: `cd Indian-Market-AI-Trading && source .venv/bin/activate`.

## 3. Download prices

```bash
python scripts/fetch_prices.py
```

This saves daily prices since 2014 for 21 symbols into `data/prices/` (git ignores
this folder). It takes about a minute.

If some symbols fail with a rate-limit error, Yahoo may be throttling AWS addresses.
Wait a few minutes and re-run. If it keeps failing, run the same script on your laptop
and copy the folder up:
`scp -r data/prices ubuntu@<EC2-IP>:~/Indian-Market-AI-Trading/data/`

## 4. Run the backtest

```bash
python -m trading.backtest
```

You'll get a table comparing the strategy with buy-and-hold: final value, yearly
return, worst fall from peak, charges paid, number of trades, and a one-line verdict.
Trades and the daily portfolio value are saved to `data/results/trades.csv` and
`data/results/equity.csv`.

Look at the trades in the terminal:

```bash
column -s, -t < data/results/trades.csv | less -S
```

## 5. Things to try

| Question | Command |
|---|---|
| Fairer comparison (allow fully invested, 10% per stock) | `python -m trading.backtest --max-position 0.10 --max-invested 1.0` |
| Recent years only | `python -m trading.backtest --start 2021-01-01` |
| A specific period, e.g. the 2020 crash | `python -m trading.backtest --start 2019-06-01 --end 2021-06-30` |
| Your own stock list | `python scripts/fetch_prices.py --symbols TATASTEEL.NS DLF.NS` then `python -m trading.backtest --symbols TATASTEEL.NS DLF.NS` |
| Bigger capital (₹20 brokerage hurts less) | `python -m trading.backtest --capital 500000` |

All options: `python -m trading.backtest --help`.

With the default limits the strategy holds at most 50% in stocks while the
benchmark is 100% invested, so in a rising market it will usually lag. Use the
"fairer comparison" row to compare like with like.

## 6. Reading the result honestly

- **Survivorship bias:** the default list is today's biggest companies. In 2016 nobody
  knew which ones would be on top in 2026, so results look better than reality.
- **Taxes are not included.** Short-term gains (held under a year) are taxed more
  than long-term ones, which hurts frequent trading most.
- **One good period proves little.** Check several start dates. If the strategy only
  wins in one window, it's probably luck.
- Yahoo data is free and unofficial. Spot-check a few prices against NSE.

If the strategy doesn't beat buy-and-hold after charges across several periods, that
is a useful result: it means a Nifty index fund is the better use of the money.
