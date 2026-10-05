# Polymarket BTC Up/Down Bot

Tells you whether Bitcoin is more likely to finish **above or below the target price** on a Polymarket market, and whether Polymarket's odds are mispriced against that estimate. It only reads data and never places trades. It uses Python 3.9+ and the standard library, with nothing to install.

## How it decides

1. Finds the live Polymarket market (hourly or 15m/5m "Bitcoin Up or Down", or any link you paste).
2. Target = BTC's price at the window open (Up/Down markets) or the strike (e.g. "above $118,000").
3. Measures BTC's recent volatility from 1-minute candles (Binance, falls back to Coinbase).
4. `P(up) = Φ( ln(price/target) / (vol · √minutes_left) )`: the chance the current gap survives the time left.
5. Compares with the Polymarket ask. If the model beats the price by `--min-edge` (default 5¢), it says `BUY UP` / `BUY DOWN`. Otherwise it says `NO EDGE`.

## Usage

```bash
python3 btc_bot.py                         # current hourly market
python3 btc_bot.py --market 15m            # current 15-minute market (also 5m)
python3 btc_bot.py --url https://polymarket.com/event/<slug>   # any BTC market link
python3 btc_bot.py --target 125000 --expiry 2026-10-05T20:00:00Z   # your own question
python3 btc_bot.py --market 15m --watch 20 # refresh every 20s
python3 btc_bot.py backtest --days 14 --market 15m   # check calibration on history
python -m unittest                         # tests
```

Example output:
```
  Target (price to beat): $99,075.87
  BTC now:                $99,126.97  (+$51.10)
  Time left:              5.7 min   (typical move ±$120, vol 5.1 bp/min)
  Model:      Up  66.5%   Down  33.5%
  Polymarket: Up  56.0%   Down  46.0%
  ==> BUY UP @ 0.56   edge +10.5%
```

## Honest caveats

- Nobody can reliably predict BTC's direction. Early in a window the model sits near 50/50. It becomes confident only once price has moved away from the target and little time is left, and that's when Polymarket usually prices it in too.
- Markets resolve on a specific feed (Binance BTCUSDT candles for hourly, Chainlink for 15m/5m). Small gaps between feeds matter when price is near the target.
- Use `--fee` for taker fees or slippage. Run `backtest` before risking real money.
