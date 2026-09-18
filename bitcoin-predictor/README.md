# Bitcoin Direction Predictor

A small, dependency-free CLI that pulls recent BTC/USD price history and tells
you whether the trend looks UP or DOWN — optionally projected toward a target
price, a number of days out, or a specific date.

It combines standard technical indicators (SMA7/25/99, MACD, RSI14, 7-day
momentum) into one weighted signal, and fits a trend line to recent prices to
project where that trend points.

**This is technical-analysis heuristics, not financial advice.** Bitcoin is
highly volatile and no indicator-based model can reliably predict short-term
price moves. Use this as one input among many, not a trading signal on its own.

## Requirements

Python 3.x. No external packages — uses only the standard library.

## Usage

```bash
# Just the current signal
python3 predict.py

# Will it likely reach $150,000?
python3 predict.py --target 150000

# Where does the trend point 30 days out?
python3 predict.py --target 30d

# Where does the trend point by a specific date?
python3 predict.py --target 2026-12-31

# Analyze more/less history (default 180 days)
python3 predict.py --days 365

# Work offline from your own price history (CSV with 'date,price' columns)
python3 predict.py --csv history.csv --target 100000
```

By default, price history comes from the public CoinGecko API
(`/coins/bitcoin/market_chart`), so an internet connection is required unless
you pass `--csv`.

## How the signal is built

Each indicator casts a weighted vote toward UP or BEARISH:

- SMA7 vs SMA25, and SMA25 vs SMA99 (trend/crossover direction)
- MACD line vs its signal line
- RSI14 (overbought/oversold plus midline bias)
- 7-day price momentum

The votes are combined into a normalized score, mapped to `UP` / `DOWN` /
`NEUTRAL` with a confidence percentage.

## How target projection works

A straight line is fit to `log(price)` over time (so growth is modeled as
percentage-based, not linear-dollar). Depending on what you pass to
`--target`:

- **A price** (e.g. `100000`) — reports whether the current trend is moving
  toward or away from that price, and (if aligned) an ETA if the trend holds.
- **A horizon** (e.g. `30d`) or **a date** (e.g. `2026-12-31`) — projects the
  trend line forward to that point and reports the expected price and
  direction.

Recent daily volatility is reported alongside the projection as a reminder of
how much actual prices can deviate from a straight-line trend.
