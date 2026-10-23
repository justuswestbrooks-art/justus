"""Offline tests: no API keys or network needed."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["JARVIS_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import memory  # noqa: E402
import site_builder  # noqa: E402
import tools  # noqa: E402


def call(tool, **kwargs):
    return json.loads(tool.call(kwargs))


class FlipTests(unittest.TestCase):
    def test_local_flip_profit(self):
        r = call(tools.calc_flip, buy_price=100, sell_price=250, platform="facebook_local", extra_costs=20)
        self.assertEqual(r["profit"], 130)
        self.assertEqual(r["roi_pct"], 108.3)

    def test_max_offer_gives_50pct_roi(self):
        r = call(tools.calc_flip, buy_price=0, sell_price=300, platform="ebay", extra_costs=10)
        offer = r["max_offer_for_50pct_roi"]
        check = call(tools.calc_flip, buy_price=offer, sell_price=300, platform="ebay", extra_costs=10)
        self.assertAlmostEqual(check["roi_pct"], 50.0, delta=0.2)

    def test_deal_lifecycle_feeds_scoreboard(self):
        deal = call(tools.save_deal, title="Mower", asking_price=80, est_resale=200)["deal_id"]
        call(tools.update_deal, deal_id=deal, status="sold", bought_price=70, sold_price=190)
        self.assertGreaterEqual(memory.scoreboard()["flip_profit"], 120)


class LearningTests(unittest.TestCase):
    def test_closed_experiment_becomes_lesson(self):
        exp = call(tools.log_experiment, area="shopify", hypothesis="h", action="a")["experiment_id"]
        call(tools.close_experiment, experiment_id=exp, worked=False, result="no lift", lesson="Skip X")
        self.assertIn("Skip X", [l["lesson"] for l in memory.recent_lessons()])


class SiteTests(unittest.TestCase):
    def test_site_is_escaped_and_written(self):
        site_builder.SITES_DIR = tempfile.mkdtemp()
        r = call(tools.build_business_website, name="Green <Cuts>", city="Tulsa",
                 services=[{"title": "Mowing", "description": "Weekly"}],
                 tagline="Lawns done right", about="Family owned.", phone="(918) 555-0100")
        with open(r["path"]) as f:
            page = f.read()
        self.assertIn("Green &lt;Cuts&gt;", page)
        self.assertIn('href="tel:9185550100"', page)


class MissingKeyTests(unittest.TestCase):
    def test_integrations_explain_missing_config(self):
        for var in ("GOOGLE_PLACES_API_KEY", "SHOPIFY_STORE", "YOUTUBE_API_KEY"):
            os.environ.pop(var, None)
        self.assertIn("error", call(tools.find_businesses_without_website, niche="lawn", location="X"))
        self.assertIn("error", call(tools.shopify_sales_report))
        self.assertIn("error", call(tools.youtube_channel_report))


if __name__ == "__main__":
    unittest.main()
