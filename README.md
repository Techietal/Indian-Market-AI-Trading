# Indian Market AI Trading

A research project for **paper trading** Indian equities (NSE/BSE): simulated orders with virtual money, deterministic risk rules, and optional AI classification of company news.

> **Paper only.** There is no code that can place a real order. No real money is involved, and nothing here is investment advice or a promise of returns.

## Status

Stage 1 (foundation). What exists today:

| Component | State |
|---|---|
| Simulated broker (`src/trading/paper.py`) | Working. Fills at the latest market price plus slippage; synthetic prices until a feed is connected |
| Indian delivery charges (`src/trading/costs.py`) | Working. Brokerage, STT, exchange, SEBI, stamp duty, DP, GST (Upstox rates, Nov 2026) |
| Risk rules: 5% per stock, 50% invested, 10 positions, 2% daily loss stop, no short selling | Working, configurable via `RiskLimits` |
| DeepSeek / GLM news classifier (`src/trading/ai.py`) | Written and unit-tested with mocks; not yet run against a live API |
| Backtest vs Nifty buy-and-hold (`src/trading/backtest.py`) | Working. See [`docs/backtest-on-ec2.md`](docs/backtest-on-ec2.md) |
| Unit tests + GitHub Actions CI | Working |
| Market data, news feeds, database, Telegram, EC2 deployment | Not started |

Known gaps are tracked in [`docs/implementation.md`](docs/implementation.md).

## Run it locally

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
python -m trading.cli
```

## Configuration and secrets

This repository is **public**. Copy `.env.example` to `.env` and fill it in on your own machine or server only. `.env` is ignored by git.

Never commit or paste into issues/logs: API keys, broker credentials or tokens, Telegram bot tokens or chat IDs, AWS keys, or real account holdings.

## Project layout

```
src/trading/
  paper.py   simulated broker + risk checks
  costs.py   Indian delivery-trade charges
  ai.py      optional DeepSeek/GLM news classifier (advisory only, never trades)
  cli.py     small demo
  data.py    loads daily price CSVs
  backtest.py  strategy vs buy-and-hold backtest
scripts/
  fetch_prices.py  downloads NSE daily prices (Yahoo Finance)
tests/       unit tests
docs/        implementation plan and roadmap
```

## Budget

Target running cost: ₹1,320/month (server ₹670, market data ₹0, AI ₹500, misc ₹150). Note the server figure was based on a $6 VPS; an EC2 `t3.small` in Mumbai running 24/7 will cost noticeably more. Check the AWS pricing calculator before launching.
