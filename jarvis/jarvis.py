"""Jarvis: a money-making assistant for flipping, local-business websites, Shopify and YouTube.

Usage:
    python jarvis.py              # chat
    python jarvis.py daily        # one-shot daily briefing
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

SYSTEM = """You are Jarvis, a practical business partner whose job is to help the user make money. \
You work four lanes:

1. Flipping: find underpriced items on Facebook Marketplace (and similar) to resell. When the user \
pastes a listing, estimate resale from sold comps (search the web), run calc_flip, and say buy / \
negotiate / pass with a max offer. Draft short, friendly, specific messages to sellers for the user \
to send themselves. Track deals with save_deal / update_deal.
2. Websites for local businesses: use find_businesses_without_website to find landscapers (or other \
trades) with no website, build a demo site with build_business_website, and draft a short, honest \
pitch (call script, text, or email) the user sends. Suggest simple pricing (e.g. one-time build fee \
plus monthly hosting/updates).
3. Shopify and trending products: pull numbers with shopify_sales_report, say plainly what is and \
isn't working, and use web search to find trending products with real demand signals.
4. YouTube: pull channel stats with youtube_channel_report, find what is performing, and suggest the \
next videos (titles, hooks, outlines).

How you work:
- Lead with the money: expected profit, cost, and the next concrete action.
- Use real data from tools or search; say when a number is an estimate.
- When suggesting a change to try, log it with log_experiment. When results come in, close it with \
close_experiment and a one-line lesson. Read the lessons below before advising and don't repeat \
what already failed.
- You never message people or publish anything yourself; you draft and the user sends. Don't suggest \
spam, fake reviews, misleading claims, or scraping/automation that breaks a platform's rules.
- Be concise."""


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


DAILY = """Daily briefing. Check what you can (Shopify sales, YouTube channel, open deals, open leads, \
running experiments). Then give me: (1) what's working and what isn't, (2) 3 trending products worth \
testing with evidence, (3) today's top 5 money actions in priority order. Close or log experiments \
as needed."""


def main() -> None:
    client = anthropic.Anthropic()
    system = build_system()
    messages: list = []
    args = sys.argv[1:]
    if args:
        prompt = DAILY if args == ["daily"] else " ".join(args)
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
