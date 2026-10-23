"""Generates a one-page, mobile-first website for a local service business (no build step)."""

import html
import os
import re
import urllib.parse

SITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sites")

# Simple line icons (24x24, stroke = currentColor), picked by keywords in each service title.
ICONS = {
    "mow": '<path d="M3 20h18"/><path d="M5 20v-3m3 3v-5m3 5v-3m3 3v-6m3 6v-3m3 3v-4"/>',
    "tree": '<path d="M12 22v-6"/><path d="M12 16c-4 0-7-2.5-7-6a5 5 0 0 1 4-4.9A4 4 0 0 1 12 2a4 4 0 0 1 3 3.1A5 5 0 0 1 19 10c0 3.5-3 6-7 6Z"/>',
    "palm": '<path d="M12 22c0-6 1-10 2-13"/><path d="M14 9c-2-3-6-4-9-2 3 0 6 1 9 2Zm0 0c1-3 4-5 8-4-3 1-6 2-8 4Zm0 0c-3 0-6 2-7 5 2-2 5-4 7-5Zm0 0c3 0 6 2 7 5-2-2-5-4-7-5Z"/>',
    "flower": '<circle cx="12" cy="9" r="2.5"/><path d="M12 6.5V3m0 9v10m2.5-13H18M6 9h3.5M12 22c0-4 3-6 6-6-1 3-3 6-6 6Zm0 0c0-4-3-6-6-6 1 3 3 6 6 6Z"/>',
    "building": '<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h1m4 0h1M9 11h1m4 0h1M9 15h1m4 0h1M10 21v-3h4v3"/>',
    "trim": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M8.6 7.6 20 18M8.6 16.4 20 6"/>',
    "clean": '<path d="M3 21h18"/><path d="M7 21l3-9h4l3 9"/><path d="M12 12V3"/>',
    "truck": '<path d="M3 6h11v10H3zM14 9h4l3 3v4h-7"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
    "water": '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11Z"/>',
    "tractor": '<circle cx="7" cy="17" r="4"/><circle cx="18" cy="18" r="2.5"/><path d="M7 13V6h6l2 7h4v5M11 6v7"/>',
    "leaf": '<path d="M5 19c0-9 6-15 15-15 0 9-6 15-15 15Z"/><path d="M5 19 14 10"/>',
}
ICON_KEYWORDS = [
    ("palm", "palm"), ("tree", "tree"), ("hedge", "trim"), ("shrub", "trim"), ("trim", "trim"),
    ("edg", "trim"), ("mow", "mow"), ("lawn", "mow"), ("weed", "mow"), ("commercial", "building"),
    ("hoa", "building"), ("clean", "clean"), ("debris", "clean"), ("junk", "truck"), ("haul", "truck"),
    ("trash", "truck"), ("irrigat", "water"), ("sprinkler", "water"), ("pressure", "water"),
    ("solar", "building"), ("tractor", "tractor"), ("skid", "tractor"), ("mulch", "flower"),
    ("forestry", "tractor"), ("landscap", "flower"), ("sod", "flower"), ("plant", "flower"),
]

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} | {niche} in {city}</title>
<meta name="description" content="{tagline}">
<meta name="theme-color" content="{dark}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --brand: {color}; --dark: {dark}; --tint: {tint}; --sun: #f5a524;
    --ink: #14201a; --muted: #56635c; --bg: #f6f8f4; --card: #fff; --line: #e1e7df;
    --radius: 18px; --shadow: 0 1px 2px rgba(20,32,26,.06), 0 8px 24px rgba(20,32,26,.06);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{ font: 400 17px/1.6 Inter, system-ui, sans-serif; color: var(--ink); background: var(--bg);
         padding-bottom: 76px; -webkit-font-smoothing: antialiased; }}
  h1, h2, h3, .logo {{ font-family: "Bricolage Grotesque", Inter, system-ui, sans-serif; line-height: 1.1; }}
  a {{ color: inherit; text-decoration: none; }}
  svg.i {{ width: 24px; height: 24px; fill: none; stroke: currentColor; stroke-width: 1.8;
          stroke-linecap: round; stroke-linejoin: round; flex: none; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 0 20px; }}

  /* Header */
  header {{ position: sticky; top: 0; z-index: 10; background: rgba(255,255,255,.92);
           backdrop-filter: blur(10px); border-bottom: 1px solid var(--line); }}
  header .wrap {{ display: flex; align-items: center; justify-content: space-between; height: 64px; gap: 12px; }}
  .logo {{ display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 1.1rem; min-width: 0; }}
  .logo span {{ font-size: .98rem; line-height: 1.15; display: -webkit-box; -webkit-line-clamp: 2;
               -webkit-box-orient: vertical; overflow: hidden; }}
  .mark {{ width: 36px; height: 36px; border-radius: 10px; background: var(--brand); color: #fff;
          display: grid; place-items: center; flex: none; }}
  .btn {{ display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 48px;
         padding: 0 22px; border-radius: 999px; font-weight: 600; white-space: nowrap;
         transition: transform .15s ease, box-shadow .15s ease; }}
  .btn:active {{ transform: scale(.97); }}
  .btn-brand {{ background: var(--brand); color: #fff; }}
  .btn-sun {{ background: var(--sun); color: #1d1405; box-shadow: 0 6px 20px rgba(245,165,36,.35); }}
  .btn-light {{ background: rgba(255,255,255,.12); color: #fff; border: 1.5px solid rgba(255,255,255,.5); }}
  header .btn {{ min-height: 42px; padding: 0 16px; font-size: .95rem; }}

  /* Hero */
  .hero {{ position: relative; overflow: hidden; color: #fff;
          background: radial-gradient(120% 90% at 85% 0%, var(--brand) 0%, var(--dark) 60%); }}
  .hero .wrap {{ position: relative; z-index: 2; padding-top: 64px; padding-bottom: 170px; }}
  .eyebrow {{ display: inline-flex; align-items: center; gap: 8px; font-size: .85rem; font-weight: 600;
             letter-spacing: .04em; text-transform: uppercase; background: rgba(255,255,255,.12);
             border: 1px solid rgba(255,255,255,.2); padding: 6px 14px; border-radius: 999px; margin-bottom: 20px; }}
  .hero h1 {{ font-size: clamp(2.3rem, 7vw, 4rem); font-weight: 800; max-width: 760px; margin-bottom: 18px;
             letter-spacing: -.02em; }}
  .hero h1 em {{ font-style: normal; color: var(--sun); }}
  .hero p.lead {{ font-size: 1.15rem; max-width: 600px; opacity: .9; margin-bottom: 28px; }}
  .ctas {{ display: flex; flex-wrap: wrap; gap: 12px; }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 10px 22px; margin-top: 28px; font-size: .95rem; opacity: .95; }}
  .chips span {{ display: inline-flex; align-items: center; gap: 8px; }}
  .chips svg.i {{ width: 20px; height: 20px; color: var(--sun); }}
  .stars {{ color: var(--sun); letter-spacing: 2px; }}
  .sun {{ position: absolute; right: 8%; bottom: 105px; width: 84px; height: 84px; border-radius: 50%; z-index: 1;
         background: var(--sun); opacity: .9; box-shadow: 0 0 60px 20px rgba(245,165,36,.35); }}
  .scene {{ position: absolute; left: 0; right: 0; bottom: -1px; width: 100%; height: 190px; z-index: 1; }}

  /* Sections */
  section {{ padding: 72px 0; }}
  .kicker {{ color: var(--brand); font-weight: 600; font-size: .9rem; letter-spacing: .06em;
            text-transform: uppercase; margin-bottom: 10px; }}
  h2 {{ font-size: clamp(1.8rem, 4.5vw, 2.6rem); font-weight: 800; letter-spacing: -.01em; margin-bottom: 14px; }}
  .sub {{ color: var(--muted); max-width: 620px; margin-bottom: 36px; }}
  .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }}
  .card {{ background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
          padding: 26px; box-shadow: var(--shadow); }}
  .card .ic {{ width: 52px; height: 52px; border-radius: 14px; background: var(--tint); color: var(--brand);
              display: grid; place-items: center; margin-bottom: 18px; }}
  .card .ic svg.i {{ width: 28px; height: 28px; }}
  .card h3 {{ font-size: 1.25rem; margin-bottom: 6px; }}
  .card p {{ color: var(--muted); }}

  .steps {{ counter-reset: s; }}
  .step {{ position: relative; padding-left: 64px; }}
  .step::before {{ counter-increment: s; content: counter(s); position: absolute; left: 0; top: 0;
                  width: 46px; height: 46px; border-radius: 50%; background: var(--brand); color: #fff;
                  display: grid; place-items: center; font: 800 1.2rem "Bricolage Grotesque", sans-serif; }}
  .step h3 {{ font-size: 1.2rem; margin: 8px 0 4px; }}
  .step p {{ color: var(--muted); }}
  .alt {{ background: #fff; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }}

  .areas {{ display: flex; flex-wrap: wrap; gap: 10px; }}
  .areas span {{ display: inline-flex; align-items: center; gap: 6px; background: var(--card);
                border: 1px solid var(--line); border-radius: 999px; padding: 10px 16px; font-weight: 500; }}
  .areas svg.i {{ width: 18px; height: 18px; color: var(--brand); }}

  .band {{ background: var(--dark); color: #fff; border-radius: 28px; padding: 48px 28px; text-align: center;
          position: relative; overflow: hidden; }}
  .band::after {{ content: ""; position: absolute; inset: auto -20% -60% -20%; height: 120%;
                 background: radial-gradient(closest-side, rgba(255,255,255,.08), transparent); }}
  .band h2 {{ color: #fff; }}
  .band p {{ opacity: .85; margin: 0 auto 26px; max-width: 520px; }}
  .band .ctas {{ justify-content: center; position: relative; z-index: 1; }}

  footer {{ padding: 36px 0 28px; color: var(--muted); font-size: .92rem; text-align: center; }}

  /* Sticky mobile action bar */
  .bar {{ position: fixed; left: 0; right: 0; bottom: 0; z-index: 20; display: flex; gap: 10px; padding: 10px 12px;
         background: rgba(255,255,255,.96); backdrop-filter: blur(10px); border-top: 1px solid var(--line); }}
  .bar .btn {{ flex: 1; min-height: 52px; }}
  @media (min-width: 760px) {{
    body {{ padding-bottom: 0; }}
    .bar {{ display: none; }}
    .hero .wrap {{ padding-top: 96px; padding-bottom: 210px; }}
  }}
</style>
</head>
<body>
<header><div class="wrap">
  <a class="logo" href="#"><span class="mark"><svg class="i" viewBox="0 0 24 24">{logo_icon}</svg></span><span>{name}</span></a>
  {header_btn}
</div></header>

<div class="hero">
  <div class="wrap">
    <div class="eyebrow">{eyebrow}</div>
    <h1>{tagline}</h1>
    <p class="lead">{about}</p>
    <div class="ctas">{hero_ctas}</div>
    <div class="chips">{chips}</div>
  </div>
  <div class="sun" aria-hidden="true"></div>
  <svg class="scene" viewBox="0 0 1440 190" preserveAspectRatio="none" aria-hidden="true">
    <path d="M0 120 C 220 60 420 70 640 110 S 1060 60 1440 100 V190 H0Z" fill="#fff" opacity=".07"/>
    <path d="M0 150 C 260 100 520 120 760 140 S 1180 110 1440 135 V190 H0Z" fill="#fff" opacity=".1"/>
    <path d="M0 170 C 300 140 600 160 900 165 S 1260 150 1440 160 V190 H0Z" fill="#f6f8f4"/>
  </svg>
</div>

<section id="services"><div class="wrap">
  <p class="kicker">What we do</p>
  <h2>Services in {city}</h2>
  <p class="sub">{services_sub}</p>
  <div class="grid">{services}</div>
</div></section>

<section class="alt"><div class="wrap">
  <p class="kicker">How it works</p>
  <h2>Getting started is easy</h2>
  <p class="sub">No forms, no runaround. Reach out and we'll take it from there.</p>
  <div class="grid steps">
    <div class="step"><h3>Call or text us</h3><p>Tell us what your yard or property needs.</p></div>
    <div class="step"><h3>Get your free quote</h3><p>Clear, upfront pricing with no surprises.</p></div>
    <div class="step"><h3>Enjoy the results</h3><p>We do the work and leave the place clean.</p></div>
  </div>
</div></section>

<section><div class="wrap">
  <p class="kicker">Service area</p>
  <h2>Proudly serving {city} and nearby</h2>
  <p class="sub">Not sure if we cover your street? Just send us a text.</p>
  <div class="areas">{areas}</div>
</div></section>

<section style="padding-top: 0"><div class="wrap">
  <div class="band" id="quote">
    <h2>Ready for a better-looking yard?</h2>
    <p>Get a free quote today. We usually reply the same day.</p>
    <div class="ctas">{band_ctas}</div>
  </div>
</div></section>

<footer><div class="wrap">&copy; {name} &middot; {niche} in {city}{footer_phone}</div></footer>

{bar}
</body>
</html>
"""

CHECK = '<svg class="i" viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>'
PIN = '<svg class="i" viewBox="0 0 24 24"><path d="M12 22s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12Z"/><circle cx="12" cy="10" r="2.5"/></svg>'
PHONE = '<svg class="i" viewBox="0 0 24 24"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2Z"/></svg>'
CHAT = '<svg class="i" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z"/></svg>'


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "site"


def _mix(hex_color: str, other: tuple[int, int, int], amount: float) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(c + (o - c) * amount):02x}" for c, o in zip((r, g, b), other))


def _icon(title: str) -> str:
    t = title.lower()
    key = next((icon for word, icon in ICON_KEYWORDS if word in t), "leaf")
    return f'<svg class="i" viewBox="0 0 24 24">{ICONS[key]}</svg>'


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
    color: str = "#15803d",
    areas: list[str] | None = None,
) -> str:
    """Write sites/<slug>/index.html and return its path. services: [{"title", "description"}]."""
    e = html.escape
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        color = "#15803d"
    dark = _mix(color, (8, 16, 12), 0.6)
    tint = _mix(color, (255, 255, 255), 0.88)
    digits = re.sub(r"[^0-9]", "", phone)
    tel = ("+1" + digits) if len(digits) == 10 else ("+" + digits if digits else "")
    sms_body = urllib.parse.quote(f"Hi {name}, I'd like a free quote for ")
    call = f'<a class="btn btn-sun" href="tel:{tel}">{PHONE}Call {e(phone)}</a>' if tel else ""
    text = f'<a class="btn btn-light" href="sms:{tel}?&body={sms_body}">{CHAT}Text for a free quote</a>' if tel else ""
    if not tel:
        text = '<a class="btn btn-sun" href="#quote">Get a free quote</a>'

    chips = [f"<span>{CHECK}Free estimates</span>", f"<span>{CHECK}Locally owned</span>"]
    if rating and review_count:
        chips.insert(0, f'<span><span class="stars">&#9733;&#9733;&#9733;&#9733;&#9733;</span>'
                        f'{rating:.1f} from {int(review_count)} Google reviews</span>')
    else:
        chips.append(f"<span>{CHECK}Fast replies</span>")

    cards = "".join(
        f'<div class="card"><div class="ic">{_icon(s.get("title", ""))}</div>'
        f'<h3>{e(s.get("title", ""))}</h3><p>{e(s.get("description", ""))}</p></div>'
        for s in services
    )
    area_list = areas or [city]
    page = PAGE.format(
        name=e(name),
        city=e(city),
        niche=e(niche),
        tagline=e(tagline),
        about=e(about),
        color=color,
        dark=dark,
        tint=tint,
        logo_icon=ICONS["leaf"],
        eyebrow=f"{PIN} {e(niche)} &middot; {e(city)}",
        header_btn=(f'<a class="btn btn-brand" href="tel:{tel}">{PHONE}Call</a>' if tel else ""),
        hero_ctas=call + text,
        chips="".join(chips),
        services_sub=f"From routine upkeep to bigger projects, {e(name)} has you covered.",
        services=cards,
        areas="".join(f"<span>{PIN}{e(a)}</span>" for a in area_list),
        band_ctas=(call + text) if tel else "",
        footer_phone=(f" &middot; {e(phone)}" if phone else ""),
        bar=(f'<nav class="bar"><a class="btn btn-brand" href="tel:{tel}">{PHONE}Call</a>'
             f'<a class="btn btn-sun" href="sms:{tel}?&body={sms_body}">{CHAT}Text us</a></nav>' if tel else ""),
    )
    out_dir = os.path.join(SITES_DIR, slugify(f"{name}-{city}"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path
