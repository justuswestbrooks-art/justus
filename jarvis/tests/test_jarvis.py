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

    def test_selling_a_deal_logs_profit_once(self):
        deal = call(tools.save_deal, title="Mower", asking_price=80, est_resale=200)["deal_id"]
        call(tools.update_deal, deal_id=deal, status="bought", bought_price=70)
        r = call(tools.update_deal, deal_id=deal, status="sold", sold_price=190, hours=3)
        self.assertEqual(r["logged_profit"], 120)
        call(tools.update_deal, deal_id=deal, status="sold", notes="buyer happy")  # no double count
        flips = [l for l in memory.lane_stats(30) if l["lane"] == "flips"][0]
        self.assertEqual(flips["profit"], 120)
        self.assertEqual(flips["per_hour"], 40)


class MoneyTests(unittest.TestCase):
    def test_lanes_ranked_by_dollars_per_hour(self):
        call(tools.log_result, lane="websites", profit=499, hours=5, recurring_monthly=49)
        call(tools.log_result, lane="youtube", profit=0, hours=4)
        call(tools.set_monthly_goal, amount=2000)
        board = call(tools.money_report)
        self.assertEqual(board["lanes"][0]["lane"], "websites")
        self.assertEqual(board["monthly_goal"], 2000)
        self.assertGreaterEqual(board["recurring_monthly_revenue"], 49)


class FollowupTests(unittest.TestCase):
    def test_cadence_then_stop(self):
        with memory.connect() as conn:
            lead = conn.execute("INSERT INTO leads (place_id, name) VALUES ('p1', 'Acme Lawn')").lastrowid
        days = []
        for _ in range(4):
            days.append(call(tools.mark_contacted, lead_id=lead, channel="text")["next_followup"])
        self.assertTrue(all(d.startswith("20") for d in days[:3]))
        self.assertIn("last touch", days[3])
        with memory.connect() as conn:  # make it due now
            conn.execute("UPDATE leads SET next_followup = '2000-01-01T00:00:00+00:00' WHERE id = ?", (lead,))
        self.assertEqual([l["id"] for l in call(tools.followups_due)], [lead])
        call(tools.update_lead, lead_id=lead, status="won")
        self.assertEqual(call(tools.followups_due), [])


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
        self.assertIn('href="tel:+19185550100"', page)


class MissingKeyTests(unittest.TestCase):
    def test_integrations_explain_missing_config(self):
        for var in ("GOOGLE_PLACES_API_KEY", "SHOPIFY_STORE", "YOUTUBE_API_KEY"):
            os.environ.pop(var, None)
        self.assertIn("error", call(tools.find_businesses_without_website, niche="lawn", location="X"))
        self.assertIn("error", call(tools.shopify_sales_report))
        self.assertIn("error", call(tools.youtube_channel_report))


if __name__ == "__main__":
    unittest.main()
