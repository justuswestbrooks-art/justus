#!/usr/bin/env python3
"""
Bitcoin direction predictor.

Pulls recent BTC/USD price history and combines a handful of standard
technical indicators (moving averages, RSI, MACD, momentum) into a single
up/down signal with a confidence score. Optionally projects that trend
toward a target you give: a price, a number of days out, or a date.

This is technical-analysis heuristics, not financial advice. Bitcoin is
highly volatile; no model here can reliably predict short-term price moves.

Usage:
    python3 predict.py
    python3 predict.py --target 100000
    python3 predict.py --target 30d
    python3 predict.py --target 2026-12-31
    python3 predict.py --days 90 --csv history.csv
"""

import argparse
import csv
import json
import math
import statistics
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

API_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"


def fetch_history(days: int):
    """Return a list of (datetime, price) tuples, oldest first, from CoinGecko."""
    url = f"{API_URL}?vs_currency=usd&days={days}&interval=daily"
    req = urllib.request.Request(url, headers={"User-Agent": "bitcoin-predictor/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    points = []
    for ts_ms, price in data["prices"]:
        points.append((datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc), float(price)))
    return points


def load_csv(path: str):
    """Load (datetime, price) pairs from a local CSV with 'date,price' columns."""
    points = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row:
                continue
            date_str, price_str = row[0], row[1]
            try:
                dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            except ValueError:
                dt = datetime.fromtimestamp(float(date_str), tz=timezone.utc)
            points.append((dt, float(price_str)))
    points.sort(key=lambda p: p[0])
    return points


def sma(values, window):
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def ema_series(values, window):
    if len(values) < window:
        return []
    k = 2 / (window + 1)
    out = [sum(values[:window]) / window]
    for v in values[window:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(values, window=14):
    if len(values) < window + 1:
        return None
    gains, losses = [], []
    for i in range(-window, 0):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(values, fast=12, slow=26, signal=9):
    if len(values) < slow + signal:
        return None, None
    ema_fast = ema_series(values, fast)
    ema_slow = ema_series(values, slow)
    offset = len(ema_fast) - len(ema_slow)
    macd_line = [f - s for f, s in zip(ema_fast[offset:], ema_slow)]
    if len(macd_line) < signal:
        return macd_line[-1], None
    signal_line = ema_series(macd_line, signal)
    return macd_line[-1], signal_line[-1]


def linear_trend(values):
    """Fit a line to log(price) vs day index; return (slope_per_day, intercept)."""
    n = len(values)
    xs = list(range(n))
    ys = [math.log(v) for v in values]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs) or 1e-9
    slope = num / den
    intercept = y_mean - slope * x_mean
    return slope, intercept


def daily_returns(values):
    return [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values))]


def build_signal(prices):
    """Score recent indicators into a single (label, confidence 0-100, details) result."""
    sma7 = sma(prices, 7)
    sma25 = sma(prices, 25)
    sma99 = sma(prices, min(99, len(prices) - 1)) if len(prices) > 30 else None
    rsi14 = rsi(prices, 14)
    macd_line, macd_signal = macd(prices)
    momentum_7d = (prices[-1] - prices[-8]) / prices[-8] * 100 if len(prices) > 8 else None

    score = 0.0
    weight_total = 0.0
    votes = []

    if sma7 is not None and sma25 is not None:
        w = 1.0
        weight_total += w
        if sma7 > sma25:
            score += w
            votes.append(f"SMA7 (${sma7:,.0f}) above SMA25 (${sma25:,.0f}) — bullish")
        else:
            score -= w
            votes.append(f"SMA7 (${sma7:,.0f}) below SMA25 (${sma25:,.0f}) — bearish")

    if sma25 is not None and sma99 is not None:
        w = 1.0
        weight_total += w
        if sma25 > sma99:
            score += w
            votes.append(f"SMA25 (${sma25:,.0f}) above SMA99 (${sma99:,.0f}) — bullish (golden cross zone)")
        else:
            score -= w
            votes.append(f"SMA25 (${sma25:,.0f}) below SMA99 (${sma99:,.0f}) — bearish (death cross zone)")

    if macd_line is not None and macd_signal is not None:
        w = 1.2
        weight_total += w
        if macd_line > macd_signal:
            score += w
            votes.append(f"MACD ({macd_line:.1f}) above signal ({macd_signal:.1f}) — bullish")
        else:
            score -= w
            votes.append(f"MACD ({macd_line:.1f}) below signal ({macd_signal:.1f}) — bearish")

    if rsi14 is not None:
        w = 0.8
        weight_total += w
        if rsi14 >= 70:
            score -= w
            votes.append(f"RSI14 ({rsi14:.0f}) overbought — bearish pressure")
        elif rsi14 <= 30:
            score += w
            votes.append(f"RSI14 ({rsi14:.0f}) oversold — bullish pressure")
        elif rsi14 > 50:
            score += w * 0.5
            votes.append(f"RSI14 ({rsi14:.0f}) above midline — mildly bullish")
        else:
            score -= w * 0.5
            votes.append(f"RSI14 ({rsi14:.0f}) below midline — mildly bearish")

    if momentum_7d is not None:
        w = 1.0
        weight_total += w
        if momentum_7d > 0:
            score += w
            votes.append(f"7-day momentum {momentum_7d:+.1f}% — bullish")
        else:
            score -= w
            votes.append(f"7-day momentum {momentum_7d:+.1f}% — bearish")

    normalized = score / weight_total if weight_total else 0.0
    confidence = round(min(abs(normalized), 1.0) * 100)
    if normalized > 0.15:
        label = "UP"
    elif normalized < -0.15:
        label = "DOWN"
    else:
        label = "NEUTRAL"
        confidence = max(confidence, 5)

    return label, confidence, votes


def parse_target(raw, now):
    """Return ('price', float) or ('date', datetime)."""
    raw = raw.strip().lower()
    if raw.endswith("d") and raw[:-1].replace(".", "", 1).isdigit():
        days = float(raw[:-1])
        return "date", now + timedelta(days=days)
    try:
        return "date", datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    cleaned = raw.replace(",", "").replace("$", "")
    return "price", float(cleaned)


def project_target(prices, dates, target_kind, target_value):
    current_price = prices[-1]
    slope, intercept = linear_trend(prices)
    returns = daily_returns(prices)
    daily_vol = statistics.pstdev(returns) if len(returns) > 1 else 0.0
    n = len(prices)

    if target_kind == "date":
        horizon_days = (target_value - dates[-1]).total_seconds() / 86400
        if horizon_days <= 0:
            print("Target date/offset must be in the future.", file=sys.stderr)
            sys.exit(1)
        projected_log = intercept + slope * (n - 1 + horizon_days)
        projected_price = math.exp(projected_log)
        direction = "UP" if projected_price > current_price else "DOWN"
        pct_change = (projected_price - current_price) / current_price * 100
        return {
            "horizon_days": horizon_days,
            "target_date": target_value,
            "projected_price": projected_price,
            "direction": direction,
            "pct_change": pct_change,
            "daily_vol_pct": daily_vol * 100,
        }

    target_price = target_value
    pct_needed = (target_price - current_price) / current_price * 100
    direction_needed = "UP" if target_price > current_price else "DOWN"
    trend_direction = "UP" if slope > 0 else "DOWN"
    aligned = trend_direction == direction_needed

    eta_days = None
    if slope != 0:
        try:
            log_ratio = math.log(target_price) - (intercept + slope * (n - 1))
            days_from_now = log_ratio / slope
            if days_from_now > 0:
                eta_days = days_from_now
        except ValueError:
            pass

    return {
        "target_price": target_price,
        "pct_needed": pct_needed,
        "direction_needed": direction_needed,
        "trend_direction": trend_direction,
        "aligned": aligned,
        "eta_days": eta_days,
        "daily_vol_pct": daily_vol * 100,
    }


def main():
    parser = argparse.ArgumentParser(description="Predict Bitcoin direction toward a target.")
    parser.add_argument("--target", help="A price ('100000'), a horizon ('30d'), or a date ('2026-12-31').")
    parser.add_argument("--days", type=int, default=180, help="Days of history to analyze (default 180).")
    parser.add_argument("--csv", help="Load offline history from a local CSV (date,price) instead of the API.")
    args = parser.parse_args()

    try:
        history = load_csv(args.csv) if args.csv else fetch_history(args.days)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"Could not fetch live BTC data ({e}).", file=sys.stderr)
        print("Retry later, or pass --csv <file> with local date,price history.", file=sys.stderr)
        sys.exit(1)

    if len(history) < 30:
        print("Not enough price history to analyze (need at least 30 data points).", file=sys.stderr)
        sys.exit(1)

    dates = [p[0] for p in history]
    prices = [p[1] for p in history]
    current_price = prices[-1]
    as_of = dates[-1]

    label, confidence, votes = build_signal(prices)

    print("=" * 60)
    print("BITCOIN DIRECTION SIGNAL")
    print("=" * 60)
    print(f"As of:          {as_of.strftime('%Y-%m-%d')}")
    print(f"Current price:  ${current_price:,.2f}")
    print(f"Signal:         {label}  ({confidence}% confidence)")
    print("-" * 60)
    print("Based on:")
    for v in votes:
        print(f"  - {v}")

    if args.target:
        try:
            kind, value = parse_target(args.target, as_of)
        except ValueError:
            print(f"\nCould not parse --target '{args.target}'. Use a price, 'Nd', or an ISO date.", file=sys.stderr)
            sys.exit(1)

        result = project_target(prices, dates, kind, value)
        print("-" * 60)
        print("TARGET PROJECTION")
        print(f"Recent daily volatility: {result['daily_vol_pct']:.2f}%")

        if kind == "date":
            print(f"Target date:     {result['target_date'].strftime('%Y-%m-%d')} ({result['horizon_days']:.0f} days out)")
            print(f"Trend-projected price: ${result['projected_price']:,.2f} ({result['pct_change']:+.1f}%)")
            print(f"Trend direction by then: {result['direction']}")
        else:
            print(f"Target price:    ${result['target_price']:,.2f} ({result['pct_needed']:+.1f}% from current)")
            print(f"Needs price to go: {result['direction_needed']}")
            print(f"Current trend is:  {result['trend_direction']}")
            if result["aligned"]:
                print("=> Current trend is moving TOWARD this target.")
            else:
                print("=> Current trend is moving AWAY from this target.")
            if result["eta_days"]:
                eta_date = as_of + timedelta(days=result["eta_days"])
                print(f"If the current trend holds, ETA ~{result['eta_days']:.0f} days ({eta_date.strftime('%Y-%m-%d')}).")
            else:
                print("ETA: trend does not point toward this target, so no ETA.")

    print("=" * 60)
    print("Not financial advice. Technical-analysis heuristics only —")
    print("crypto markets are highly volatile and can move against any trend.")


if __name__ == "__main__":
    main()
