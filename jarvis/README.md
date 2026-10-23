# Jarvis

A Claude-powered business partner with one job: grow your profit. It doesn't just run tools. It follows a playbook, keeps score in dollars per hour, chases your follow-ups, and remembers what worked.

## The plan

The fastest way to fail at side hustles is to start five at once. Jarvis works in two stages.

**Stage 1: cash now.** Stay here until you make $2,000+/month or have 10+ website clients.

1. **Websites for landscapers (the main engine).** Jarvis finds local landscapers on Google Maps that have good reviews and no website, and builds each one a demo site with their name on it. You show it to the owner. The offer is **$499 to launch + $49/month** for hosting, updates and Google Business Profile tune-ups. Ten clients is about $500/month in recurring revenue before you find another lead.
2. **Flipping (pays for gas and tools).** Paste a Marketplace listing and Jarvis checks *sold* prices, works out profit after fees and gives you a max offer and a message to send. It only says "buy" at $75+ profit or 50%+ ROI. Lawn equipment pairs well with the landscaper lane.

**Stage 2: scale.** Once Stage 1 is steady:

3. **Shopify + trending products.** Small, cheap product tests. Each product gets about $100 in ads or 2 weeks to make a sale; Jarvis drops it if it doesn't, and puts more behind anything earning 2x its ad spend.
4. **YouTube.** Document the journey. That content brings in both website clients and buyers.

Jarvis will still help if you want to jump ahead, but it will tell you what it costs you.

## How it keeps you honest

- **Dollars per hour by lane.** Tell Jarvis what you made and how long it took. Flips log themselves when you mark them sold. It moves your time toward the lane that pays best per hour.
- **Follow-ups first.** Most website deals close on the 2nd–4th contact, not the first. When you log an outreach, Jarvis schedules the next follow-up (2, then 4, then 7 days later) and puts it at the top of each morning's plan with the exact text to send.
- **Experiments and lessons.** Every change you try gets logged. When the results are in, Jarvis saves a one-line lesson and reads all its lessons at the start of every session, so it never repeats a mistake.

## Setup

```bash
cd jarvis
pip install -r requirements.txt
cp .env.example .env       # then fill in your keys
python jarvis.py           # chat
python jarvis.py daily     # morning: scoreboard, follow-ups due, today's top 5 actions
python jarvis.py weekly    # Sunday: what made money, what to cut, next week's experiments
```

Keys (only the first one is required; each lane switches on when you add its key):

- `ANTHROPIC_API_KEY`: get it from [console.anthropic.com](https://console.anthropic.com).
- `GOOGLE_PLACES_API_KEY`: in Google Cloud, enable **Places API (New)** and create a key. Each search costs a few cents.
- `SHOPIFY_STORE` + `SHOPIFY_ADMIN_TOKEN`: in Shopify admin, go to Settings → Apps → Develop apps, create an app with the `read_orders` scope and copy its Admin API token.
- `YOUTUBE_API_KEY` + `YOUTUBE_CHANNEL_ID`: in Google Cloud, enable **YouTube Data API v3** and create a key. Your channel ID (it starts with `UC`) is under YouTube Settings → Advanced.

## Your first week

```
My goal is $3,000/month. I live in <your city>.
Find 20 landscapers without websites near me and build demo sites for the 5 best.
Give me the call script and the follow-up text for Green Edge Lawn.
I called Green Edge, left a voicemail, then texted the demo link.
Here's a listing: Husqvarna 54" zero-turn, $900, needs a belt. Worth it?
Sold the mower for $1,650. Paid $850, spent $40 on the belt, about 5 hours total.
Green Edge said yes: $499 now, $49 a month. Took about 3 hours.
```

The pricing, profit thresholds and stage targets are in `SYSTEM` at the top of `jarvis.py`. Change them as you learn your market. The follow-up schedule is `FOLLOWUP_DAYS` in `tools.py`.

Demo sites are saved to `jarvis/sites/<business>/index.html`. You can host one for free on Netlify Drop or Cloudflare Pages and text the owner the link. Jarvis's memory lives in `jarvis/data/jarvis.db`. Both folders are git-ignored.

## What it won't do

- **It won't message people for you.** Facebook has no API for Marketplace messages, and bots that send them get accounts banned. Spam would also burn the local reputation this business runs on. Jarvis writes every message and you hit send.
- **It won't upload YouTube videos or change your Shopify store.** For now it only reads data. Uploading needs OAuth, and changing the store needs write scopes. They're good next steps for Stage 2.

## Tests

```bash
python -m unittest discover -s tests
```

The tests run offline, without any API keys.
