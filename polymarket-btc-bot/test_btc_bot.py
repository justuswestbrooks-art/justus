import math
import random
import unittest
from datetime import datetime, timezone

import btc_bot as b


class ModelTests(unittest.TestCase):
    def test_at_target_is_coin_flip(self):
        self.assertAlmostEqual(b.prob_above(100_000, 100_000, 5e-4, 30), 0.5)

    def test_above_target_favours_up_and_tightens_with_time(self):
        early = b.prob_above(100_100, 100_000, 5e-4, 50)
        late = b.prob_above(100_100, 100_000, 5e-4, 2)
        self.assertGreater(early, 0.5)
        self.assertGreater(late, early)

    def test_expired(self):
        self.assertEqual(b.prob_above(99_999, 100_000, 5e-4, 0), 0.0)
        self.assertEqual(b.prob_above(100_000, 100_000, 5e-4, 0), 1.0)

    def test_ewma_vol_recovers_true_vol(self):
        rng = random.Random(1)
        px, closes = 100_000.0, []
        for _ in range(2000):
            px *= math.exp(rng.gauss(0, 8e-4))
            closes.append(px)
        self.assertAlmostEqual(b.ewma_vol(closes), 8e-4, delta=2.5e-4)


class PolymarketTests(unittest.TestCase):
    def test_hourly_slug_uses_eastern_time(self):
        start = datetime(2026, 10, 5, 19, 0, tzinfo=timezone.utc)  # 3pm EDT
        self.assertEqual(b.updown_slug("1h", start), "bitcoin-up-or-down-october-5-3pm-et")
        noon = datetime(2026, 12, 1, 17, 0, tzinfo=timezone.utc)   # 12pm EST
        self.assertEqual(b.updown_slug("1h", noon), "bitcoin-up-or-down-december-1-12pm-et")

    def test_15m_slug_and_window(self):
        now = datetime(2026, 10, 5, 19, 7, 30, tzinfo=timezone.utc)
        start, end = b.window_for("15m", now)
        self.assertEqual((start.minute, end.minute), (0, 15))
        self.assertEqual(b.updown_slug("15m", start), f"btc-updown-15m-{int(start.timestamp())}")

    def test_slug_from_url(self):
        self.assertEqual(b.slug_from_url("https://polymarket.com/event/btc-updown-15m-1759690800?tid=1"),
                         "btc-updown-15m-1759690800")
        self.assertEqual(b.slug_from_url("btc-updown-5m-1"), "btc-updown-5m-1")

    def test_parse_strike(self):
        self.assertEqual(b.parse_strike({"groupItemTitle": "112,000"}), 112_000)
        self.assertEqual(b.parse_strike({"question": "Will Bitcoin be above $118,500 on October 5?"}), 118_500)
        self.assertEqual(b.parse_strike({"question": "Bitcoin above 120k on October 5?"}), 120_000)
        self.assertIsNone(b.parse_strike({"question": "Up or down on October 5?"}))

    def test_decide(self):
        sig = b.Signal("x", 100_000, 100_200, 5, 5e-4, 0.9, {"Up": 0.70, "Down": 0.31}, "Up", "Down")
        action, edge = b.decide(sig, 0.05, 0.0)
        self.assertTrue(action.startswith("BUY UP"))
        self.assertAlmostEqual(edge, 0.20)
        sig.quotes = {"Up": 0.88, "Down": 0.13}
        self.assertTrue(b.decide(sig, 0.05, 0.0)[0].startswith("NO EDGE"))


class BacktestTests(unittest.TestCase):
    def test_random_walk_is_calibrated(self):
        rng = random.Random(7)
        px, candles = 100_000.0, []
        for i in range(60 * 24 * 10):
            o = px
            px *= math.exp(rng.gauss(0, 6e-4))
            candles.append(b.Candle(1_700_000_000 // 3600 * 3600 + i * 60, o, px))
        res = b.backtest(candles)
        self.assertGreater(res["n"], 500)
        self.assertLess(res["brier"], 0.20)  # far better than a coin flip on a true random walk


if __name__ == "__main__":
    unittest.main()
