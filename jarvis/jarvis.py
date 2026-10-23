"""Jarvis: a money-making assistant for flipping, local-business websites, Shopify and YouTube.

Usage:
    python jarvis.py              # chat
    python jarvis.py daily        # morning briefing: follow-ups and today's plan
    python jarvis.py weekly       # weekly review: what to double down on and what to cut
    python jarvis.py "find landscapers without websites in Tulsa, OK"
"""

import json
import os
import sys

import anthropic


def load_env(path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")) -> None:
    """Read KEY=value lines from jarvis/.env into the environment (real env vars win)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

import memory  # noqa: E402  (reads JARVIS_DB from the environment)
from tools import ALL_TOOLS  # noqa: E402

MODEL = os.environ.get("JARVIS_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("JARVIS_EFFORT", "medium")

SYSTEM = """You are Jarvis, the user's business partner. Your one job is to grow the user's profit, \
and you think like a disciplined, successful operator, not a hype guru.

THE PLAYBOOK
Stage 1, cash now (until profit is steady at $2,000+/month or 10+ recurring website clients):
- Websites for local service businesses are the main engine. Landscapers with good reviews and no \
website are the best targets: they're busy and they get calls from Google. The offer is a free demo \
site already built with their name on it, then $499 to launch plus $49/month for hosting, updates and \
Google Business Profile tune-ups. Never pitch "do you want a website?". Show them their site. \
Recurring revenue is the real prize: one client at $49/month is worth about $600 a year.
- Flipping pays for gas and tools. Only take deals with $75+ profit or 50%+ ROI, based on SOLD comps, \
not asking prices. Best categories: lawn equipment, power tools, furniture, and items that are free \
or underpriced because of a move. Mowers and trimmers are a natural fit with the landscaping lane.
Stage 2, scale (only after Stage 1 is steady):
- Shopify: test new products cheaply. Kill a product after about $100 in ads or 2 weeks with no \
sales. Double down on anything with a 2x+ return on ad spend.
- YouTube: document the journey ("I build websites for landscapers", "flipping $1,000 in mowers"). \
The audience feeds both lanes.
If the user wants to jump ahead to Stage 2, say plainly what it costs them, then help anyway. It's \
their call.

OPERATING RULES
- Dollars per hour decides where time goes. Use money_report; recommend more time on the lane with \
the highest $/hr and less on the lowest. Ask for hours when the user reports a win, and log it with \
log_result (flips log themselves through update_deal).
- Follow-ups come before new leads. Most website deals close on touch 2-4. Always check \
followups_due, and log each outreach with mark_contacted.
- Every plan is concrete: who to contact, what to say (write the script), how many, by when.
- Volume beats perfection: 20 outreach touches a day beats one perfect site.
- Every change is an experiment. Log it with log_experiment and close it with a lesson when results \
are in. Read the lessons below before advising, and never repeat something that already failed.
- Use real data from tools or search, and label estimates as estimates.
- Be honest. Tell the user when an idea is bad, when a lane isn't paying, or when they're avoiding \
the uncomfortable work (usually picking up the phone).

LIMITS
- You never message people or publish anything yourself. You draft, the user sends. No spam, fake \
reviews, fake scarcity, misleading claims, or automation that breaks a platform's rules: those get \
accounts banned and burn the local reputation this business runs on.
- If no monthly goal is set, ask for one early and save it with set_monthly_goal.
- Be concise. Lead with the money and the next action."""


def build_system() -> list[dict]:
    lessons = memory.recent_lessons()
    lesson_text = "\n".join(f"- [{l['area']}] {l['lesson']}" for l in lessons) or "- (none yet)"
    state = (
        f"Scoreboard: {json.dumps(memory.scoreboard())}\n\nLessons learned so far (newest first):\n"
        f"{lesson_text}"
    )
    # The instructions are stable and cached; the scoreboard and lessons change between runs.
    return [
        {"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": state},
    ]


TOOLS = [*ALL_TOOLS, {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}]


def run_turn(client: anthropic.Anthropic, system: list[dict], messages: list) -> bool:
    """Run one user turn to completion, printing Jarvis's replies. Appends to `messages` in place.

    Returns False if the turn was refused, so the caller can drop it from the history."""
    for _ in range(5):  # restarts after pause_turn
        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=16000,
            system=system,
            tools=TOOLS,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": EFFORT},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        last = None
        for message in runner:
            last = message
            messages.append({"role": "assistant", "content": message.content})
            for block in message.content:
                if block.type == "text" and block.text.strip():
                    print(f"\nJarvis: {block.text}")
                elif block.type == "tool_use":
                    print(f"  [using {block.name}]")
            tool_response = runner.generate_tool_call_response()
            if tool_response is not None:
                messages.append(tool_response)
        if last is None:
            return True
        if last.stop_reason == "refusal":
            print("\nJarvis: I can't help with that one.")
            return False
        if last.stop_reason == "max_tokens":
            print("\n[reply was cut off; ask Jarvis to continue]")
        if last.stop_reason != "pause_turn":
            return True
    return True


DAILY = """Daily briefing. Check money_report, followups_due, open deals and leads, running \
experiments, plus Shopify and YouTube if they're connected. Then give me, short:
1. Scoreboard: profit this month vs goal, and $/hr by lane.
2. Follow-ups due today, each with the exact text or call script.
3. Today's plan: the top 5 actions in priority order, with numbers (e.g. "find 15 landscapers in \
<city> and build 3 demo sites").
4. One thing to stop doing, if the data says so."""

WEEKLY = """Weekly review. Pull money_report for 7 and 30 days, all experiments, and Shopify/YouTube \
if connected. Close any experiment that has enough data and record its lesson. Then tell me: what \
made money, what wasted time, which lane gets more hours next week and which gets fewer, the 3 \
experiments to run next week (log them), and whether I'm ready to move from Stage 1 to Stage 2."""


def main() -> None:
    client = anthropic.Anthropic()
    system = build_system()
    messages: list = []
    args = sys.argv[1:]
    if args:
        prompt = {"daily": DAILY, "weekly": WEEKLY}.get(" ".join(args), " ".join(args))
        messages.append({"role": "user", "content": prompt})
        run_turn(client, system, messages)
        return
    print("Jarvis ready. Type 'quit' to exit.")
    while True:
        try:
            text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue
        start = len(messages)
        messages.append({"role": "user", "content": text})
        try:
            ok = run_turn(client, system, messages)
        except anthropic.RateLimitError:
            print("\n[rate limited; wait a moment and try again]")
            ok = False
        except anthropic.APIStatusError as err:
            print(f"\n[API error {err.status_code}: {err.message}]")
            ok = False
        except anthropic.APIConnectionError:
            print("\n[network error; check your connection]")
            ok = False
        if not ok:
            del messages[start:]  # drop the failed turn so the conversation stays usable


if __name__ == "__main__":
    main()
