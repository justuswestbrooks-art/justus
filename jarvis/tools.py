"""Tools Jarvis can call. Each returns a JSON string the model reads.

Nothing here sends a message to another person. Outreach (Marketplace sellers, business owners)
is drafted by Jarvis and sent by you.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from anthropic import beta_tool

import memory
from site_builder import build_site

# Approximate seller fees as (percent, fixed $). Platforms change these; verify before relying on them.
PLATFORM_FEES = {
    "facebook_local": (0.0, 0.0),
    "facebook_shipped": (0.10, 0.0),
    "ebay": (0.1325, 0.40),
    "mercari": (0.10, 0.50),
    "offerup_local": (0.0, 0.0),
    "poshmark": (0.20, 0.0),
    "shopify": (0.029, 0.30),
}


def _ok(data) -> str:
    return json.dumps(data, default=str)


def _http_json(url: str, method: str = "GET", headers: dict | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"HTTP {err.code} from {urllib.parse.urlparse(url).netloc}: "
                           f"{err.read().decode()[:500]}") from err


# ---------------------------------------------------------------- flipping

@beta_tool
def calc_flip(buy_price: float, sell_price: float, platform: str = "facebook_local",
              extra_costs: float = 0.0) -> str:
    """Calculate profit and ROI for flipping an item, after platform fees.

    Args:
        buy_price: What you would pay the seller.
        sell_price: Expected resale price.
        platform: One of facebook_local, facebook_shipped, ebay, mercari, offerup_local, poshmark, shopify.
        extra_costs: Gas, cleaning, repair parts, shipping you pay, etc.
    """
    pct, fixed = PLATFORM_FEES.get(platform, (0.0, 0.0))
    fees = sell_price * pct + fixed
    profit = sell_price - fees - buy_price - extra_costs
    cost = buy_price + extra_costs
    return _ok({
        "platform": platform,
        "fees": round(fees, 2),
        "profit": round(profit, 2),
        "roi_pct": round(profit / cost * 100, 1) if cost else None,
        "max_offer_for_50pct_roi": round((sell_price - fees - extra_costs * 1.5) / 1.5, 2),
        "note": "Fee rates are estimates; check the platform's current fees.",
    })


@beta_tool
def save_deal(title: str, asking_price: float, est_resale: float, url: str = "", notes: str = "") -> str:
    """Save a Marketplace listing worth pursuing to the deal tracker.

    Args:
        title: Item name, e.g. "Craftsman riding mower 42in".
        asking_price: Seller's asking price.
        est_resale: Realistic resale price based on sold comps.
        url: Listing URL if you have it.
        notes: Condition, seller info, comps used.
    """
    with memory.connect() as conn:
        cur = conn.execute(
            "INSERT INTO deals (title, url, asking_price, est_resale, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, url, asking_price, est_resale, notes, memory.now(), memory.now()),
        )
    return _ok({"deal_id": cur.lastrowid})


@beta_tool
def update_deal(deal_id: int, status: str, bought_price: float | None = None,
                sold_price: float | None = None, notes: str = "") -> str:
    """Update a deal as it moves through the pipeline.

    Args:
        deal_id: ID from save_deal or list_deals.
        status: watching, messaged, bought, listed, sold, or passed.
        bought_price: What was actually paid.
        sold_price: What it actually sold for.
        notes: Anything worth remembering (appended).
    """
    with memory.connect() as conn:
        conn.execute(
            "UPDATE deals SET status = ?, bought_price = COALESCE(?, bought_price), "
            "sold_price = COALESCE(?, sold_price), "
            "notes = TRIM(COALESCE(notes, '') || ' ' || ?), updated_at = ? WHERE id = ?",
            (status, bought_price, sold_price, notes, memory.now(), deal_id),
        )
        row = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
    return _ok(dict(row) if row else {"error": f"no deal {deal_id}"})


@beta_tool
def list_deals(status: str = "") -> str:
    """List tracked flip deals, optionally filtered by status.

    Args:
        status: Filter (watching, messaged, bought, listed, sold, passed); empty for all.
    """
    with memory.connect() as conn:
        q = "SELECT * FROM deals" + (" WHERE status = ?" if status else "") + " ORDER BY id DESC LIMIT 100"
        return _ok(memory.rows(conn.execute(q, (status,) if status else ())))


# ---------------------------------------------------------------- website leads

@beta_tool
def find_businesses_without_website(niche: str, location: str, max_results: int = 20) -> str:
    """Search Google Maps for local businesses and keep the ones with no website. Saves them as leads.

    Args:
        niche: Business type, e.g. "landscaping", "lawn care", "tree service".
        location: City and state, e.g. "Tulsa, OK".
        max_results: Up to 20.
    """
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not key:
        return _ok({"error": "GOOGLE_PLACES_API_KEY is not set. See jarvis/README.md."})
    fields = ["id", "displayName", "formattedAddress", "nationalPhoneNumber", "websiteUri",
              "rating", "userRatingCount", "googleMapsUri", "businessStatus"]
    data = _http_json(
        "https://places.googleapis.com/v1/places:searchText",
        method="POST",
        headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": ",".join(f"places.{f}" for f in fields)},
        body={"textQuery": f"{niche} in {location}", "pageSize": min(max_results, 20)},
    )
    found = []
    with memory.connect() as conn:
        for p in data.get("places", []):
            if p.get("websiteUri") or p.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
                continue
            lead = {
                "place_id": p["id"],
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "niche": niche,
                "address": p.get("formattedAddress", ""),
                "phone": p.get("nationalPhoneNumber", ""),
                "rating": p.get("rating"),
                "review_count": p.get("userRatingCount"),
                "maps_url": p.get("googleMapsUri", ""),
            }
            conn.execute(
                "INSERT OR IGNORE INTO leads (place_id, name, niche, address, phone, rating, review_count, "
                "maps_url, created_at, updated_at) VALUES (:place_id, :name, :niche, :address, :phone, "
                ":rating, :review_count, :maps_url, :ts, :ts)",
                {**lead, "ts": memory.now()},
            )
            lead["lead_id"] = conn.execute(
                "SELECT id FROM leads WHERE place_id = ?", (p["id"],)
            ).fetchone()[0]
            found.append(lead)
    return _ok({"searched": len(data.get("places", [])), "no_website": found})


@beta_tool
def list_leads(status: str = "") -> str:
    """List website leads, optionally filtered by status.

    Args:
        status: new, site_built, contacted, replied, won, lost; empty for all.
    """
    with memory.connect() as conn:
        q = "SELECT * FROM leads" + (" WHERE status = ?" if status else "") + " ORDER BY id DESC LIMIT 100"
        return _ok(memory.rows(conn.execute(q, (status,) if status else ())))


@beta_tool
def update_lead(lead_id: int, status: str, notes: str = "") -> str:
    """Update a lead's status after outreach.

    Args:
        lead_id: Lead ID.
        status: new, site_built, contacted, replied, won, or lost.
        notes: What happened (appended).
    """
    with memory.connect() as conn:
        conn.execute(
            "UPDATE leads SET status = ?, notes = TRIM(COALESCE(notes, '') || ' ' || ?), updated_at = ? "
            "WHERE id = ?",
            (status, notes, memory.now(), lead_id),
        )
    return _ok({"lead_id": lead_id, "status": status})


@beta_tool
def build_business_website(name: str, city: str, services: list[dict], tagline: str, about: str,
                           phone: str = "", niche: str = "Landscaping", lead_id: int | None = None,
                           color: str = "#2f6b3f") -> str:
    """Generate a one-page demo website for a local business, to show the owner when pitching.

    Args:
        name: Business name.
        city: City they serve.
        services: 3-6 items, each {"title": ..., "description": ...}.
        tagline: Short headline, benefit-focused.
        about: One or two sentences about the business.
        phone: Business phone.
        niche: Business type, used in the page title.
        lead_id: Lead to attach the site to (fills rating/reviews and marks it site_built).
        color: Brand color as #RRGGBB.
    """
    rating = review_count = None
    if lead_id is not None:
        with memory.connect() as conn:
            row = conn.execute("SELECT rating, review_count FROM leads WHERE id = ?", (lead_id,)).fetchone()
            if row:
                rating, review_count = row["rating"], row["review_count"]
    path = build_site(name, city, services, tagline, about, phone, niche, rating, review_count, color)
    if lead_id is not None:
        with memory.connect() as conn:
            conn.execute(
                "UPDATE leads SET status = 'site_built', site_path = ?, updated_at = ? WHERE id = ?",
                (path, memory.now(), lead_id),
            )
    return _ok({"path": path})


# ---------------------------------------------------------------- shopify

@beta_tool
def shopify_sales_report(days: int = 30) -> str:
    """Pull recent Shopify orders and summarize revenue by product, so we can see what sells.

    Args:
        days: How many days back to look.
    """
    store = os.environ.get("SHOPIFY_STORE")
    token = os.environ.get("SHOPIFY_ADMIN_TOKEN")
    if not (store and token):
        return _ok({"error": "SHOPIFY_STORE and SHOPIFY_ADMIN_TOKEN are not set. See jarvis/README.md."})
    version = os.environ.get("SHOPIFY_API_VERSION", "2025-10")
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    query = """
    query($q: String!, $after: String) {
      orders(first: 100, after: $after, query: $q, sortKey: CREATED_AT, reverse: true) {
        pageInfo { hasNextPage endCursor }
        nodes {
          createdAt
          totalPriceSet { shopMoney { amount currencyCode } }
          lineItems(first: 50) { nodes { title quantity originalTotalSet { shopMoney { amount } } } }
        }
      }
    }"""
    url = f"https://{store.removesuffix('.myshopify.com')}.myshopify.com/admin/api/{version}/graphql.json"
    products: dict[str, dict] = {}
    orders = revenue = 0.0
    currency = ""
    after = None
    for _ in range(10):  # up to 1,000 orders
        data = _http_json(url, "POST", {"X-Shopify-Access-Token": token},
                          {"query": query, "variables": {"q": f"created_at:>={since}", "after": after}})
        if data.get("errors"):
            return _ok({"error": data["errors"]})
        page = data["data"]["orders"]
        for o in page["nodes"]:
            orders += 1
            money = o["totalPriceSet"]["shopMoney"]
            revenue += float(money["amount"])
            currency = money["currencyCode"]
            for li in o["lineItems"]["nodes"]:
                p = products.setdefault(li["title"], {"units": 0, "revenue": 0.0})
                p["units"] += li["quantity"]
                p["revenue"] += float(li["originalTotalSet"]["shopMoney"]["amount"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    ranked = sorted(products.items(), key=lambda kv: kv[1]["revenue"], reverse=True)
    return _ok({
        "days": days,
        "orders": int(orders),
        "revenue": round(revenue, 2),
        "currency": currency,
        "aov": round(revenue / orders, 2) if orders else 0,
        "products": [{"title": t, "units": v["units"], "revenue": round(v["revenue"], 2)} for t, v in ranked],
    })


# ---------------------------------------------------------------- youtube

@beta_tool
def youtube_channel_report(channel_id: str = "", max_videos: int = 15) -> str:
    """Get a YouTube channel's stats and its recent videos' views, likes and comments.

    Args:
        channel_id: Channel ID (starts with UC). Defaults to YOUTUBE_CHANNEL_ID.
        max_videos: How many recent uploads to include (max 50).
    """
    key = os.environ.get("YOUTUBE_API_KEY")
    channel_id = channel_id or os.environ.get("YOUTUBE_CHANNEL_ID", "")
    if not (key and channel_id):
        return _ok({"error": "YOUTUBE_API_KEY and a channel_id (or YOUTUBE_CHANNEL_ID) are required."})
    base = "https://www.googleapis.com/youtube/v3"
    ch = _http_json(f"{base}/channels?" + urllib.parse.urlencode(
        {"part": "snippet,statistics,contentDetails", "id": channel_id, "key": key}))
    if not ch.get("items"):
        return _ok({"error": f"channel {channel_id} not found"})
    item = ch["items"][0]
    uploads = item["contentDetails"]["relatedPlaylists"]["uploads"]
    pl = _http_json(f"{base}/playlistItems?" + urllib.parse.urlencode(
        {"part": "contentDetails", "playlistId": uploads, "maxResults": min(max_videos, 50), "key": key}))
    ids = ",".join(i["contentDetails"]["videoId"] for i in pl.get("items", []))
    videos = []
    if ids:
        vs = _http_json(f"{base}/videos?" + urllib.parse.urlencode(
            {"part": "snippet,statistics,contentDetails", "id": ids, "key": key}))
        for v in vs.get("items", []):
            s = v.get("statistics", {})
            videos.append({
                "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"],
                "duration": v["contentDetails"]["duration"],
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
            })
    return _ok({"channel": item["snippet"]["title"], "stats": item["statistics"], "recent_videos": videos})


# ---------------------------------------------------------------- learning loop

@beta_tool
def log_experiment(area: str, hypothesis: str, action: str) -> str:
    """Start tracking an experiment so we can learn whether it worked.

    Args:
        area: shopify, flips, websites, youtube, or products.
        hypothesis: What we expect, e.g. "Free shipping over $40 raises AOV".
        action: What is actually being changed and how we'll measure it.
    """
    with memory.connect() as conn:
        cur = conn.execute(
            "INSERT INTO experiments (area, hypothesis, action, created_at) VALUES (?, ?, ?, ?)",
            (area, hypothesis, action, memory.now()),
        )
    return _ok({"experiment_id": cur.lastrowid})


@beta_tool
def list_experiments(status: str = "running") -> str:
    """List experiments.

    Args:
        status: running, worked, failed; empty for all.
    """
    with memory.connect() as conn:
        q = "SELECT * FROM experiments" + (" WHERE status = ?" if status else "") + " ORDER BY id DESC"
        return _ok(memory.rows(conn.execute(q, (status,) if status else ())))


@beta_tool
def close_experiment(experiment_id: int, worked: bool, result: str, lesson: str) -> str:
    """Record an experiment's outcome and the lesson learned. Lessons are shown to Jarvis every session.

    Args:
        experiment_id: Experiment ID.
        worked: Whether the hypothesis held.
        result: The numbers / what actually happened.
        lesson: One sentence to remember next time.
    """
    with memory.connect() as conn:
        row = conn.execute("SELECT area FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        if not row:
            return _ok({"error": f"no experiment {experiment_id}"})
        conn.execute(
            "UPDATE experiments SET status = ?, result = ?, closed_at = ? WHERE id = ?",
            ("worked" if worked else "failed", result, memory.now(), experiment_id),
        )
        conn.execute(
            "INSERT INTO lessons (area, lesson, experiment_id, created_at) VALUES (?, ?, ?, ?)",
            (row["area"], lesson, experiment_id, memory.now()),
        )
    return _ok({"experiment_id": experiment_id, "status": "worked" if worked else "failed"})


@beta_tool
def record_lesson(area: str, lesson: str) -> str:
    """Save a lesson learned outside a formal experiment (e.g. "Sellers reply more to specific offers").

    Args:
        area: shopify, flips, websites, youtube, or products.
        lesson: One sentence to remember.
    """
    with memory.connect() as conn:
        conn.execute("INSERT INTO lessons (area, lesson, created_at) VALUES (?, ?, ?)",
                     (area, lesson, memory.now()))
    return _ok({"saved": True})


ALL_TOOLS = [
    calc_flip, save_deal, update_deal, list_deals,
    find_businesses_without_website, list_leads, update_lead, build_business_website,
    shopify_sales_report, youtube_channel_report,
    log_experiment, list_experiments, close_experiment, record_lesson,
]
