"""
The blog feeds Instagram, not the other way round.

rachitmishra.in publishes a full-content RSS feed — `<content:encoded>` carries
the whole article, not a summary — so the agent can read a real, researched,
already-written piece and turn it into a carousel or a Reel. That is a much
better input than the weekly web search: the search finds what happened, the
blog contains what you think.

Pairs with agent/repurpose.py, which runs the other direction (Instagram post →
blog outline). Between them, one idea reaches three surfaces regardless of
where it started.

    python -m agent.from_blog --count 2          # next 2 unused articles
    python -m agent.from_blog --count 5 --per-day 2
    python -m agent.from_blog --url https://...  # one specific article
    python -m agent.from_blog --list             # show what is unused

Already-used articles are tracked in state/blog_seen.json so nothing is
posted twice.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
import yaml

from agent.llm_adapter import complete

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "content" / "queue"
PUBLISHED = ROOT / "content" / "published"
STATE = ROOT / "state"
SEEN = STATE / "blog_seen.json"
BRAND = ROOT / "brand" / "brand.yml"

FEED_URL = os.getenv("BLOG_FEED_URL") or "https://www.rachitmishra.in/feed"

NS = {"content": "http://purl.org/rss/1.0/modules/content/"}

# Which key in post.json carries the scheduled time. Detected from an existing
# post so this keeps working whatever generate.py calls it.
SCHEDULE_KEY_CANDIDATES = (
    "publish_at", "scheduled_at", "scheduled_for", "publish_time",
    "slot_at", "when", "datetime",
)


# --------------------------------------------------------------------------
# feed
# --------------------------------------------------------------------------

def _strip_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)</(p|div|h[1-6]|li|blockquote)>", "\n\n", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = html.unescape(raw).replace("\xa0", " ")
    raw = re.sub(r"[ \t]+", " ", raw)
    return re.sub(r"\n{3,}", "\n\n", raw).strip()


def fetch_feed(url: str = FEED_URL) -> list[dict]:
    r = requests.get(url, timeout=45, headers={"User-Agent": "byrachitmishra-agent"})
    r.raise_for_status()
    root = ET.fromstring(r.content)

    items = []
    for item in root.iter("item"):
        def text(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""

        body_el = item.find("content:encoded", NS)
        body = _strip_html(body_el.text or "") if body_el is not None else ""
        if not body:
            body = _strip_html(text("description"))

        link = text("link")
        if not link:
            continue
        items.append({
            "title": text("title"),
            "link": link,
            "published": text("pubDate"),
            "body": body,
            "words": len(body.split()),
        })
    return items


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------

def load_seen() -> dict:
    if not SEEN.exists():
        return {"used": {}}
    try:
        return json.loads(SEEN.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"used": {}}


def save_seen(seen: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(seen, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# schedule
# --------------------------------------------------------------------------

def detect_schedule_key() -> str:
    """Read an existing post.json to learn what generate.py calls the slot."""
    for folder in list(QUEUE.glob("*")) + list(PUBLISHED.glob("*")):
        pj = folder / "post.json"
        if not pj.exists():
            continue
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for key in SCHEDULE_KEY_CANDIDATES:
            if key in data:
                return key
    return "publish_at"


def _slot_times(brand: dict) -> list[str]:
    slots = ((brand.get("schedule") or {}).get("slots")) or []
    times = sorted({(s.get("time") or "").strip() for s in slots if s.get("time")})
    return times or ["08:30", "19:00"]


def plan_schedule(n: int, brand: dict, per_day: int, start_days: int = 1) -> list[str]:
    """ISO timestamps for n backlog posts, per_day each day, using the times
    already defined in brand.yml so nothing lands at an odd hour."""
    times = _slot_times(brand)
    per_day = max(1, min(per_day, len(times)))
    # Spread across the day rather than taking the first N — brand.yml's slots
    # sort alphabetically, so the naive slice puts two posts inside one hour.
    if per_day == 1:
        times = [times[0]]
    else:
        step = (len(times) - 1) / (per_day - 1)
        times = [times[round(i * step)] for i in range(per_day)]
    out = []
    day = datetime.now().replace(second=0, microsecond=0) + timedelta(days=start_days)
    while len(out) < n:
        for t in times[:per_day]:
            if len(out) >= n:
                break
            hh, mm = (t.split(":") + ["0"])[:2]
            out.append(day.replace(hour=int(hh), minute=int(mm)).isoformat(timespec="minutes"))
        day += timedelta(days=1)
    return out


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------

SYSTEM = """You are turning one of the author's own published articles into a
single Instagram post.

{voice}

This article is already researched and already his. Your job is compression,
not invention. Do not add claims the article does not make. Do not soften an
argument to make it more postable — the sharpness is why it is worth posting.

Pick the ONE strongest idea in the piece. An article contains several; a post
carries one. Everything else is cut.

Return ONLY a JSON object, no prose and no code fence:

{{
  "pillar": "<one of: {pillars}>",
  "format": "carousel" | "reel",
  "hook": "<under 10 words, the opening line, no question mark>",
  "slides": [
     {{"heading": "<optional short heading>", "body": "<25-45 words>"}}
  ],
  "caption": "<6-10 short lines. The caption ADDS — the story, the caveat, the cost — it never summarises the slides. End with a bracketed line of 3-5 lowercase keyword phrases, comma separated.>",
  "hashtags": ["#tag", "#tag", "#tag"],
  "source_url": "<the article URL, unchanged>",
  "failure_mode": "<one honest sentence: why this post might land badly>"
}}

Five to seven slides for a carousel. The last slide lands the argument — it is
the one that inverts to the dark ground, so it must be a sentence that can
stand alone. For a reel, 5-6 slides read as spoken beats.

The caption must point to the full article once, naturally, near the end —
"the long version is on my site" — never as a hard sell."""


def _voice(brand: dict) -> str:
    ident, voice = brand.get("identity", {}), brand.get("voice", {})
    parts = [f"POSITIONING:\n{ident.get('positioning','').strip()}",
             f"\nVOICE:\n{voice.get('description','').strip()}"]
    if voice.get("exemplars"):
        parts.append("\nCALIBRATION:\n" + "\n".join(f"  - {e}" for e in voice["exemplars"]))
    if voice.get("banned_phrases"):
        parts.append("\nNEVER USE: " + ", ".join(f'"{p}"' for p in voice["banned_phrases"]))
    if voice.get("banned_patterns"):
        parts.append("\nHARD RULES:\n" + "\n".join(f"  - {p}" for p in voice["banned_patterns"]))
    return "\n".join(parts)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:48] or "post"


def build(article: dict, brand: dict, when: str, schedule_key: str) -> Path | None:
    pillars = ", ".join(p["id"] for p in brand.get("pillars", [])
                        if p.get("automate", True))
    body = article["body"]
    if len(body) > 14000:          # keep well inside the context budget
        body = body[:14000] + "\n\n[article truncated]"

    try:
        raw = complete(
            system=SYSTEM.format(voice=_voice(brand), pillars=pillars),
            user=(f"TITLE: {article['title']}\nURL: {article['link']}\n\n"
                  f"ARTICLE:\n{body}"),
            max_tokens=2600,
        )
        post = _parse_json(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] {article['title'][:60]}: {exc}")
        return None

    if not post.get("slides"):
        print(f"  [FAIL] {article['title'][:60]}: no slides returned")
        return None

    post.setdefault("source_url", article["link"])
    post["source"] = "blog"
    post[schedule_key] = when
    post.setdefault("status", "queued")

    folder = QUEUE / f"{when[:10]}-{_slug(article['title'])}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "post.json").write_text(json.dumps(post, indent=2) + "\n",
                                      encoding="utf-8")
    print(f"  [ok]   {folder.name}  ({len(post['slides'])} slides, {when})")
    return folder


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--per-day", type=int, default=1,
                    help="posts per day when draining the backlog")
    ap.add_argument("--url", help="one specific article URL")
    ap.add_argument("--list", action="store_true", help="show unused articles")
    ap.add_argument("--feed", default=FEED_URL)
    args = ap.parse_args()

    brand = yaml.safe_load(BRAND.read_text(encoding="utf-8")) if BRAND.exists() else {}
    if not brand:
        print(f"[from_blog] WARNING: {BRAND} missing — voice will be generic")

    articles = fetch_feed(args.feed)
    print(f"[from_blog] {len(articles)} articles in feed")

    seen = load_seen()
    used = seen.setdefault("used", {})

    if args.url:
        pool = [a for a in articles if a["link"].rstrip("/") == args.url.rstrip("/")]
        if not pool:
            print(f"[from_blog] {args.url} is not in the feed")
            return 1
    else:
        pool = [a for a in articles if a["link"] not in used]

    if args.list:
        print(f"\nUnused ({len(pool)}):")
        for a in pool:
            print(f"  - {a['title']}  ({a['words']} words)")
        print(f"\nAlready used: {len(used)}")
        return 0

    if not pool:
        print("[from_blog] every article has been used — nothing to do")
        return 0

    take = pool[:max(1, args.count)]
    times = plan_schedule(len(take), brand, args.per_day)
    key = detect_schedule_key()
    print(f"[from_blog] scheduling with key '{key}', "
          f"{args.per_day}/day, {len(take)} post(s)\n")

    made = 0
    for article, when in zip(take, times):
        print(f"- {article['title']}")
        folder = build(article, brand, when, key)
        if folder:
            used[article["link"]] = {
                "title": article["title"],
                "folder": folder.name,
                "at": datetime.now().isoformat(timespec="seconds"),
            }
            made += 1

    save_seen(seen)
    print(f"\n[from_blog] queued {made} post(s); {len(pool) - made} article(s) left")
    if made == 0:
        print("::error::from_blog produced nothing")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
