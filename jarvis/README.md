# Jarvis

A Claude-powered assistant that helps you make money in four ways:

| Lane | What Jarvis does | What you do |
|---|---|---|
| **Flipping** | Paste a Marketplace listing and Jarvis looks up sold prices, works out profit after fees, gives you a max offer and writes the message to the seller. It also tracks every deal from first look to sold. | Send the message and pick up the item |
| **Websites for landscapers** | Finds local landscapers on Google Maps that have no website, builds a demo one-page site for each and writes the pitch | Call or text the owner and show them the site |
| **Shopify + trending products** | Pulls your sales, shows what sells and what doesn't, and searches the web for trending products with signs of real demand | Decide what to list or cut |
| **YouTube** | Pulls your channel and video stats, finds what's working and suggests the next videos | Film and upload |

**How it learns:** when Jarvis suggests a change (a new product, a price test, a different seller message), it logs it as an *experiment*. Once you report results, it closes the experiment and saves a one-line *lesson*. Jarvis reads every saved lesson at the start of each session, so it stops repeating things that didn't work.

## Setup

```bash
cd jarvis
pip install -r requirements.txt
cp .env.example .env      # then fill in your keys
python jarvis.py          # chat
python jarvis.py daily    # daily briefing: what's working, trending products, top 5 actions
```

Keys (only the first one is required; each lane switches on when you add its key):

- `ANTHROPIC_API_KEY`: get it from [console.anthropic.com](https://console.anthropic.com).
- `GOOGLE_PLACES_API_KEY`: in Google Cloud, enable **Places API (New)** and create a key. Each search costs a few cents.
- `SHOPIFY_STORE` + `SHOPIFY_ADMIN_TOKEN`: in Shopify admin, go to Settings → Apps → Develop apps, create an app with the `read_orders` scope and copy its Admin API token.
- `YOUTUBE_API_KEY` + `YOUTUBE_CHANNEL_ID`: in Google Cloud, enable **YouTube Data API v3** and create a key. Your channel ID (it starts with `UC`) is under YouTube Settings → Advanced.

## Things to try

```
Here's a listing: Craftsman 42" riding mower, runs, $350, 30 min away. Worth it?
Find landscapers without websites in Tulsa, OK and build sites for the top 3.
How's my Shopify doing this month? What should I cut?
Find 5 trending products under $30 I could test on Shopify.
What's working on my YouTube channel? Give me my next 3 video ideas.
The free-shipping test ended: AOV went from $31 to $38. Close it out.
```

Demo sites are saved to `jarvis/sites/<business>/index.html`. Open one in a browser, or host it for free on Netlify Drop, GitHub Pages or Cloudflare Pages. Jarvis's memory lives in `jarvis/data/jarvis.db`. Both folders are git-ignored.

## What it won't do

- **It won't message people on Facebook for you.** Facebook has no API for Marketplace messages, and bots that send them break Facebook's rules and get accounts banned. Jarvis writes the messages and you send them yourself. That takes about 10 seconds per message and keeps your account safe.
- **It won't upload YouTube videos or change your Shopify store.** For now it only reads data. Uploading needs OAuth, and changing the store needs write scopes. Both are good next steps once you trust its advice.

## Tests

```bash
python -m unittest discover -s tests
```

The tests run offline, without any API keys.
