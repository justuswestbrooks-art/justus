#!/usr/bin/env python3
"""
Polymarket BTC Up/Down signal bot.

Estimates the probability that Bitcoin finishes ABOVE the market's target
price ("price to beat") when a Polymarket market resolves, compares it with
the odds Polymarket is offering, and tells you UP / DOWN / NO EDGE.

Model: BTC is treated as a driftless random walk over the minutes left. Its
volatility is measured from recent 1-minute candles (EWMA). Then

    P(up) = Phi( ln(price_now / target) / (sigma_per_min * sqrt(minutes_left)) )

This does NOT predict the future. It prices how likely the current gap to the
target is to hold given how much BTC usually moves in the time left. Any edge
comes from Polymarket's odds lagging that math. Use `backtest` to check
calibration before trusting it with money.

Stdlib only. Read-only: it never places orders.

Usage:
    python3 btc_bot.py                      # current hourly Up/Down market
    python3 btc_bot.py --market 15m         # current 15-minute market
    python3 btc_bot.py --url https://polymarket.com/event/<slug>
    python3 btc_bot.py --target 125000 --expiry 2026-10-05T16:00:00Z
    python3 btc_bot.py --watch 30           # refresh every 30s
    python3 btc_bot.py backtest --days 7    # calibration check on history
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
BINANCE_HOSTS = ["https://data-api.binance.vision", "https://api.binance.com", "https://api.binance.us"]
COINBASE = "https://api.exchange.coinbase.com"
ET = ZoneInfo("America/New_York")
INTERVALS = {"5m": 300, "15m": 900, "1h": 3600}
UA = {"User-Agent": "polymarket-btc-bot/1.0"}


# ---------------------------------------------------------------- HTTP ----

def get_json(url: str, params: dict | None = None, timeout: float = 10):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


# ------------------------------------------------------- price data -------

@dataclass
class Candle:
    t: int        # open time, unix seconds
    open: float
    close: float


def binance_candles(start: int, end: int) -> list[Candle]:
    """1-minute BTCUSDT candles with open time in [start, end)."""
    last_err = None
    for host in BINANCE_HOSTS:
        try:
            out: list[Candle] = []
            cur = start
            symbol = "BTCUSDT"
            while cur < end:
                rows = get_json(f"{host}/api/v3/klines", {
                    "symbol": symbol, "interval": "1m",
                    "startTime": cur * 1000, "endTime": end * 1000 - 1, "limit": 1000,
                })
                if not rows:
                    break
                out += [Candle(int(r[0]) // 1000, float(r[1]), float(r[4])) for r in rows]
                cur = out[-1].t + 60
                if len(rows) < 1000:
                    break
            return out
        except (urllib.error.URLError, OSError, ValueError) as e:
            last_err = e
    raise RuntimeError(f"Binance unavailable: {last_err}")


def coinbase_candles(start: int, end: int) -> list[Candle]:
    out: list[Candle] = []
    cur = start
    while cur < end:
        chunk_end = min(end, cur + 300 * 60)
        rows = get_json(f"{COINBASE}/products/BTC-USD/candles", {
            "granularity": 60,
            "start": datetime.fromtimestamp(cur, timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(chunk_end, timezone.utc).isoformat(),
        })
        # [time, low, high, open, close, volume], newest first
        out += [Candle(int(r[0]), float(r[3]), float(r[4])) for r in rows if cur <= r[0] < chunk_end]
        cur = chunk_end
        time.sleep(0.15)  # Coinbase public rate limit
    out.sort(key=lambda c: c.t)
    return out


def get_candles(start: int, end: int) -> tuple[list[Candle], str]:
    try:
        return binance_candles(start, end), "Binance BTCUSDT"
    except RuntimeError:
        return coinbase_candles(start, end), "Coinbase BTC-USD"


def spot_price() -> tuple[float, str]:
    for host in BINANCE_HOSTS:
        try:
            return float(get_json(f"{host}/api/v3/ticker/price", {"symbol": "BTCUSDT"})["price"]), "Binance"
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            pass
    return float(get_json(f"{COINBASE}/products/BTC-USD/ticker")["price"]), "Coinbase"


# ------------------------------------------------------------ model -------

def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def ewma_vol(closes: list[float], lam: float = 0.97, floor: float = 2e-4) -> float:
    """Per-minute volatility of log returns (EWMA). Floor avoids overconfidence in dead markets."""
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:]) if a > 0 and b > 0]
    if len(rets) < 10:
        return max(floor, 6e-4)
    var = sum(r * r for r in rets[:20]) / 20
    for r in rets[20:]:
        var = lam * var + (1 - lam) * r * r
    return max(floor, math.sqrt(var))


def prob_above(price: float, target: float, sigma_min: float, minutes_left: float) -> float:
    """P(price at expiry >= target) under a driftless lognormal random walk."""
    if minutes_left <= 0:
        return 1.0 if price >= target else 0.0
    z = math.log(price / target) / (sigma_min * math.sqrt(minutes_left))
    return norm_cdf(z)


# ------------------------------------------------------- polymarket -------

def updown_slug(interval: str, start: datetime) -> str:
    if interval in ("5m", "15m"):
        return f"btc-updown-{interval}-{int(start.timestamp())}"
    et = start.astimezone(ET)
    hour = et.strftime("%I").lstrip("0") + et.strftime("%p").lower()
    return f"bitcoin-up-or-down-{et.strftime('%B').lower()}-{et.day}-{hour}-et"


def window_for(interval: str, now: datetime) -> tuple[datetime, datetime]:
    secs = INTERVALS[interval]
    start = int(now.timestamp()) // secs * secs
    s = datetime.fromtimestamp(start, timezone.utc)
    return s, s + timedelta(seconds=secs)


def slug_from_url(url_or_slug: str) -> str:
    path = urllib.parse.urlparse(url_or_slug).path or url_or_slug
    parts = [p for p in path.split("/") if p]
    return parts[-1] if parts else url_or_slug


def fetch_event(slug: str) -> dict | None:
    events = get_json(f"{GAMMA}/events", {"slug": slug})
    if events:
        return events[0]
    markets = get_json(f"{GAMMA}/markets", {"slug": slug})
    if markets:
        return {"title": markets[0].get("question"), "slug": slug, "markets": markets}
    return None


def _jlist(v):
    return json.loads(v) if isinstance(v, str) else (v or [])


def best_ask(token_id: str) -> float | None:
    try:
        book = get_json(f"{CLOB}/book", {"token_id": token_id})
        asks = [float(a["price"]) for a in book.get("asks", [])]
        return min(asks) if asks else None
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None


def market_quotes(m: dict) -> dict[str, float]:
    """Cost to buy each outcome now: CLOB best ask, falling back to Gamma's displayed price."""
    outcomes = _jlist(m.get("outcomes"))
    prices = [float(p) for p in _jlist(m.get("outcomePrices"))]
    tokens = _jlist(m.get("clobTokenIds"))
    quotes = {}
    for i, name in enumerate(outcomes):
        ask = best_ask(tokens[i]) if i < len(tokens) else None
        quotes[name] = ask if ask is not None else (prices[i] if i < len(prices) else float("nan"))
    return quotes


def parse_strike(m: dict) -> float | None:
    for text in (m.get("groupItemTitle"), m.get("question")):
        if not text:
            continue
        for hit in re.finditer(r"(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*([kK])?", text):
            val = float(hit.group(1).replace(",", "") + (hit.group(2) or ""))
            val *= 1000 if hit.group(3) else 1
            if val >= 1000:  # skip day numbers like "October 5"
                return val
    return None


def parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ----------------------------------------------------------- report -------

@dataclass
class Signal:
    label: str
    target: float
    price: float
    minutes_left: float
    sigma: float
    p_up: float
    quotes: dict[str, float]
    up_name: str
    down_name: str


def decide(sig: Signal, min_edge: float, fee: float) -> tuple[str, float]:
    up_cost = sig.quotes.get(sig.up_name, float("nan"))
    dn_cost = sig.quotes.get(sig.down_name, float("nan"))
    edge_up = sig.p_up - up_cost - fee if not math.isnan(up_cost) else float("-inf")
    edge_dn = (1 - sig.p_up) - dn_cost - fee if not math.isnan(dn_cost) else float("-inf")
    if max(edge_up, edge_dn) < min_edge:
        lean = sig.up_name.upper() if sig.p_up >= 0.5 else sig.down_name.upper()
        return f"NO EDGE (model leans {lean})", max(edge_up, edge_dn)
    if edge_up >= edge_dn:
        return f"BUY {sig.up_name.upper()} @ {up_cost:.2f}", edge_up
    return f"BUY {sig.down_name.upper()} @ {dn_cost:.2f}", edge_dn


def print_signal(sig: Signal, min_edge: float, fee: float) -> None:
    action, edge = decide(sig, min_edge, fee)
    gap = sig.price - sig.target
    one_sd = sig.price * sig.sigma * math.sqrt(max(sig.minutes_left, 0))
    print(f"\n{sig.label}")
    print(f"  Target (price to beat): ${sig.target:,.2f}")
    print(f"  BTC now:                ${sig.price:,.2f}  ({'+' if gap >= 0 else '-'}${abs(gap):,.2f})")
    print(f"  Time left:              {sig.minutes_left:.1f} min   "
          f"(typical move ±${one_sd:,.0f}, vol {sig.sigma * 1e4:.1f} bp/min)")
    print(f"  Model:      {sig.up_name} {sig.p_up:6.1%}   {sig.down_name} {1 - sig.p_up:6.1%}")
    q = "   ".join(f"{k} {v:6.1%}" if not math.isnan(v) else f"{k}   n/a" for k, v in sig.quotes.items())
    print(f"  Polymarket: {q}" if sig.quotes else "  Polymarket: (no market linked)")
    if sig.quotes:
        print(f"  ==> {action}   edge {edge:+.1%}")
    else:
        print(f"  ==> {'UP' if sig.p_up >= 0.5 else 'DOWN'} more likely ({max(sig.p_up, 1 - sig.p_up):.1%})")


def market_vol(now: int, lookback: int) -> tuple[float, list[Candle], str]:
    candles, src = get_candles(now - lookback * 60, now)
    return ewma_vol([c.close for c in candles]), candles, src


def run_once(args) -> None:
    now = datetime.now(timezone.utc)
    nowts = int(now.timestamp())
    price, psrc = spot_price()
    sigma, candles, csrc = market_vol(nowts, args.lookback)

    # Manual mode: any "above X by time T" question.
    if args.target is not None and not args.url:
        if not args.expiry:
            sys.exit("--target needs --expiry (e.g. 2026-10-05T16:00:00Z)")
        exp = parse_time(args.expiry)
        mins = (exp - now).total_seconds() / 60
        print_signal(Signal(f"BTC >= ${args.target:,.0f} at {exp:%Y-%m-%d %H:%M UTC}?", args.target, price,
                            mins, sigma, prob_above(price, args.target, sigma, mins), {}, "Up", "Down"),
                     args.min_edge, args.fee)
        return

    if args.url:
        slug = slug_from_url(args.url)
    else:
        start, _ = window_for(args.market, now)
        slug = updown_slug(args.market, start)

    event = fetch_event(slug)
    if not event:
        sys.exit(f"No Polymarket market found for slug '{slug}'. Paste the market link with --url.")
    print(f"{event.get('title')}   [{slug}]   price: {psrc}, candles: {csrc}")

    m15 = re.match(r"btc-updown-(5m|15m)-(\d+)$", slug)
    for m in event.get("markets", []):
        if m.get("closed"):
            continue
        end = parse_time(m.get("endDate")) or now
        quotes = market_quotes(m)
        names = list(quotes) or ["Up", "Down"]
        up_name, down_name = (names + ["Down"])[:2]

        if up_name.lower() == "up":
            # Up/Down: target is BTC's price at the start of the window.
            start = (datetime.fromtimestamp(int(m15.group(2)), timezone.utc) if m15
                     else parse_time(m.get("eventStartTime")) or end - timedelta(hours=1))
            st = int(start.timestamp())
            if args.target is not None:
                target = args.target
            elif st > nowts:
                print("  Window has not opened yet; target unknown.")
                continue
            else:
                opening = [c for c in candles if c.t == st] or get_candles(st, st + 60)[0]
                if not opening:
                    print("  Could not fetch the window's opening price; pass --target.")
                    continue
                target = opening[0].open
        else:
            target = args.target if args.target is not None else parse_strike(m)
            if target is None:
                continue
        mins = (end - now).total_seconds() / 60
        label = m.get("groupItemTitle") or m.get("question") or slug
        print_signal(Signal(label, target, price, mins, sigma, prob_above(price, target, sigma, mins),
                            quotes, up_name, down_name), args.min_edge, args.fee)


# --------------------------------------------------------- backtest -------

def backtest(candles: list[Candle], window_min: int = 60, checkpoints=(5, 15, 30, 45, 55),
             lookback: int = 120) -> dict:
    """Replay past windows: at each checkpoint, model P(close >= open) vs what happened."""
    by_t = {c.t: c for c in candles}
    if not candles:
        return {"n": 0}
    t0 = candles[0].t + lookback * 60
    t0 += (-t0) % (window_min * 60)
    rows = []  # (minutes_in, p, outcome)
    t = t0
    while t + window_min * 60 <= candles[-1].t + 60:
        first, last = by_t.get(t), by_t.get(t + (window_min - 1) * 60)
        if first and last:
            outcome = 1 if last.close >= first.open else 0
            for k in checkpoints:
                now = t + k * 60
                hist = [by_t[s].close for s in range(now - lookback * 60, now, 60) if s in by_t]
                cur = by_t.get(now - 60)
                if cur and len(hist) > 30:
                    p = prob_above(cur.close, first.open, ewma_vol(hist), window_min - k)
                    rows.append((k, p, outcome))
        t += window_min * 60
    if not rows:
        return {"n": 0}

    def brier(rs):
        return sum((p - o) ** 2 for _, p, o in rs) / len(rs)

    buckets = []
    for lo in [i / 10 for i in range(10)]:
        b = [r for r in rows if lo <= r[1] < lo + 0.1 or (lo == 0.9 and r[1] == 1.0)]
        if b:
            buckets.append((lo, len(b), sum(r[1] for r in b) / len(b), sum(r[2] for r in b) / len(b)))
    return {
        "n": len(rows),
        "brier": brier(rows),
        "by_checkpoint": {k: brier([r for r in rows if r[0] == k]) for k in checkpoints
                          if any(r[0] == k for r in rows)},
        "calibration": buckets,
    }


def run_backtest(args) -> None:
    end = int(time.time()) // 60 * 60
    start = end - args.days * 86400
    print(f"Downloading {args.days}d of 1-minute BTC candles...")
    candles, src = get_candles(start, end)
    win = INTERVALS[args.market] // 60
    cps = tuple(sorted({max(1, int(win * f)) for f in (0.1, 0.25, 0.5, 0.75, 0.9)}))
    res = backtest(candles, win, cps, args.lookback)
    if not res["n"]:
        sys.exit("Not enough data.")
    print(f"Source: {src}, {len(candles)} candles, {res['n']} predictions over {args.market} windows")
    print(f"Brier score: {res['brier']:.4f}   (coin flip = 0.2500, lower is better)")
    print("By minutes into window:")
    for k, b in res["by_checkpoint"].items():
        print(f"  {k:3d} min in: Brier {b:.4f}")
    print("Calibration (model said -> actually happened):")
    for lo, n, p, o in res["calibration"]:
        print(f"  {lo:.0%}-{lo + 0.1:.0%}: n={n:5d}  predicted {p:6.1%}  actual {o:6.1%}")


# -------------------------------------------------------------- CLI -------

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Polymarket BTC Up/Down signal bot (read-only).")
    ap.add_argument("command", nargs="?", default="signal", choices=["signal", "backtest"])
    ap.add_argument("--market", choices=list(INTERVALS), default="1h", help="Up/Down market length")
    ap.add_argument("--url", help="Polymarket event URL or slug (any BTC Up/Down or 'above $X' market)")
    ap.add_argument("--target", type=float, help="Override/specify the target price")
    ap.add_argument("--expiry", help="ISO time the --target question resolves (manual mode)")
    ap.add_argument("--min-edge", type=float, default=0.05, help="Min edge to recommend a side (default 0.05)")
    ap.add_argument("--fee", type=float, default=0.0, help="Per-share fee/slippage to subtract (e.g. 0.01)")
    ap.add_argument("--lookback", type=int, default=120, help="Minutes of history for volatility")
    ap.add_argument("--watch", type=int, help="Refresh every N seconds")
    ap.add_argument("--days", type=int, default=7, help="Backtest history length")
    args = ap.parse_args(argv)

    if args.command == "backtest":
        run_backtest(args)
        return
    while True:
        try:
            run_once(args)
        except (urllib.error.URLError, OSError, RuntimeError) as e:
            print(f"Network error: {e}", file=sys.stderr)
        if not args.watch:
            break
        time.sleep(args.watch)
        print("\n" + "-" * 60)


if __name__ == "__main__":
    main()
