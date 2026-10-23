"""Generates a one-page, mobile-first website for a local service business (no build step)."""

import html
import os
import re

SITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites")

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} | {niche} in {city}</title>
<meta name="description" content="{tagline}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
  :root {{ --brand: {color}; --ink: #1c2321; --muted: #5b6662; --bg: #f7f8f5; --card: #ffffff; }}
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ font-family: Inter, system-ui, sans-serif; color: var(--ink); background: var(--bg); line-height: 1.6; }}
  a {{ color: inherit; }}
  .wrap {{ max-width: 1040px; margin: 0 auto; padding: 0 16px; }}
  header {{ background: var(--card); border-bottom: 1px solid #e3e6e1; position: sticky; top: 0; z-index: 2; }}
  header .wrap {{ display: flex; justify-content: space-between; align-items: center; height: 64px; }}
  .logo {{ font-weight: 800; font-size: 1.15rem; }}
  .btn {{ display: inline-block; background: var(--brand); color: #fff; text-decoration: none; font-weight: 600;
          padding: 12px 22px; border-radius: 10px; min-height: 44px; white-space: nowrap; }}
  .btn.ghost {{ background: transparent; color: var(--brand); border: 2px solid var(--brand); }}
  .hero {{ padding: 72px 0 56px; background: linear-gradient(160deg, var(--brand) 0%, #13261c 100%); color: #fff; }}
  .hero h1 {{ font-size: clamp(2rem, 5vw, 3.2rem); line-height: 1.15; margin-bottom: 16px; }}
  .hero p {{ font-size: 1.15rem; max-width: 620px; opacity: .92; margin-bottom: 28px; }}
  .hero .btn {{ background: #fff; color: var(--brand); margin-right: 10px; margin-bottom: 10px; }}
  .hero .btn.ghost {{ background: transparent; color: #fff; border-color: #fff; }}
  .trust {{ margin-top: 20px; font-size: .95rem; opacity: .9; }}
  section {{ padding: 56px 0; }}
  h2 {{ font-size: 1.8rem; margin-bottom: 24px; }}
  .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
  .card {{ background: var(--card); border: 1px solid #e3e6e1; border-radius: 14px; padding: 22px; }}
  .card h3 {{ font-size: 1.1rem; margin-bottom: 6px; }}
  .card p {{ color: var(--muted); }}
  .cta {{ background: var(--card); text-align: center; }}
  .cta p {{ color: var(--muted); margin-bottom: 20px; }}
  footer {{ padding: 28px 0; color: var(--muted); font-size: .9rem; text-align: center; }}
</style>
</head>
<body>
<header><div class="wrap">
  <span class="logo">{name}</span>
  {phone_btn_short}
</div></header>

<div class="hero"><div class="wrap">
  <h1>{tagline}</h1>
  <p>{about}</p>
  {phone_btn_hero}
  <a class="btn ghost" href="#quote">Get a free quote</a>
  {trust}
</div></div>

<section><div class="wrap">
  <h2>What we do</h2>
  <div class="grid">{services}</div>
</div></section>

<section class="cta" id="quote"><div class="wrap">
  <h2>Free estimates in {city}</h2>
  <p>Call or text and we'll get back to you the same day.</p>
  {phone_btn}
</div></section>

<footer><div class="wrap">&copy; {name} &middot; Serving {city} and surrounding areas</div></footer>
</body>
</html>
"""


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "site"


def build_site(
    name: str,
    city: str,
    services: list[dict],
    tagline: str,
    about: str,
    phone: str = "",
    niche: str = "Landscaping",
    rating: float | None = None,
    review_count: int | None = None,
    color: str = "#2f6b3f",
) -> str:
    """Write sites/<slug>/index.html and return its path. services: [{"title", "description"}]."""
    e = html.escape
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        color = "#2f6b3f"
    tel = re.sub(r"[^0-9+]", "", phone)
    phone_btn = f'<a class="btn" href="tel:{tel}">Call {e(phone)}</a>' if tel else ""
    phone_btn_short = f'<a class="btn" href="tel:{tel}">Call now</a>' if tel else ""
    trust = ""
    if rating and review_count:
        trust = f'<p class="trust">&#9733; {rating:.1f} from {int(review_count)} Google reviews</p>'
    cards = "".join(
        f'<div class="card"><h3>{e(s.get("title", ""))}</h3><p>{e(s.get("description", ""))}</p></div>'
        for s in services
    )
    page = PAGE.format(
        name=e(name),
        city=e(city),
        niche=e(niche),
        tagline=e(tagline),
        about=e(about),
        color=color,
        phone_btn=phone_btn,
        phone_btn_hero=phone_btn,
        phone_btn_short=phone_btn_short,
        trust=trust,
        services=cards,
    )
    out_dir = os.path.join(SITES_DIR, slugify(f"{name}-{city}"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path
