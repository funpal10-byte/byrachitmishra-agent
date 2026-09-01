"""
The feedback loop. Without this the agent generates every week with no idea
what happened to anything it published.

Pulls per-post insights from the Instagram Graph API into state/metrics.json,
writes a human-readable state/METRICS.md, and exposes brief_context() so the
generator can be told what worked.

    python -m agent.metrics              # fetch and write
    python -m agent.metrics --dry-run    # print, write nothing

Honest note on the numbers, kept in code because it keeps getting forgotten:
at fewer than ~30 posts and ~20 reach each, the differences between posts are
noise. This module reports them anyway, because the baseline has to start
somewhere, but brief_context() deliberately refuses to draw conclusions until
there is enough data to support one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
JSON_PATH = STATE / "metrics.json"
MD_PATH = STATE / "METRICS.md"

# Same `or` pattern as config.py — GitHub passes unset variables as an EMPTY
# STRING, so os.getenv(name, default) returns "" rather than the default.
API_VERSION = os.getenv("IG_API_VERSION") or "v25.0"
BASE = f"https://graph.instagram.com/{API_VERSION}"

# Enough posts before any comparison means anything.
MIN_POSTS_FOR_SIGNAL = 20

# Metric names drift. Ask for the full set, fall back progressively.
METRIC_SETS = [
    ["reach", "saved", "shares", "likes", "comments", "views", "total_interactions"],
    ["reach", "saved", "shares", "likes", "comments"],
    ["reach", "likes", "comments"],
    ["reach"],
]


def _token() -> str:
    tok = (os.getenv("IG_ACCESS_TOKEN") or "").strip()
    if not tok:
        raise SystemExit("[metrics] IG_ACCESS_TOKEN is not set — cannot fetch")
    return tok


def _get(path: str, params: dict) -> dict:
    params = {**params, "access_token": _token()}
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}/{path}", params=params, timeout=30)
        except requests.RequestException as exc:
            if attempt == 2:
                raise
            print(f"    network error ({exc}); retrying")
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503) and attempt < 2:
            time.sleep(5 * (attempt + 1))
            continue
        raise RuntimeError(f"{r.status_code} on {path}: {r.text[:300]}")
    return {}


def recent_media(limit: int = 50) -> list[dict]:
    data = _get(
        "me/media",
        {
            "fields": "id,caption,media_type,media_product_type,timestamp,permalink",
            "limit": limit,
        },
    )
    return data.get("data", [])


def insights(media_id: str) -> dict:
    """Insights for one post, degrading gracefully as metric names change."""
    for metrics in METRIC_SETS:
        try:
            data = _get(f"{media_id}/insights", {"metric": ",".join(metrics)})
        except RuntimeError as exc:
            if "does not support" in str(exc) or "nonexisting field" in str(exc).lower():
                continue  # try a smaller set
            if "400" in str(exc):
                continue
            raise
        out = {}
        for row in data.get("data", []):
            values = row.get("values") or []
            if values and isinstance(values[0], dict):
                out[row["name"]] = values[0].get("value", 0)
        if out:
            return out
    return {}


def collect(limit: int = 50) -> dict:
    media = recent_media(limit)
    print(f"[metrics] {len(media)} media items")

    rows = []
    for m in media:
        caption = (m.get("caption") or "").strip()
        first_line = caption.split("\n", 1)[0][:120] if caption else "(no caption)"
        stats = insights(m["id"])
        rows.append(
            {
                "id": m["id"],
                "posted": m.get("timestamp"),
                "type": m.get("media_product_type") or m.get("media_type"),
                "permalink": m.get("permalink"),
                "hook": first_line,
                **{k: stats.get(k, 0) for k in
                   ("reach", "views", "likes", "comments", "saved", "shares",
                    "total_interactions")},
            }
        )
        print(f"  {first_line[:60]:<62} reach={stats.get('reach', '-')}")

    rows.sort(key=lambda r: r.get("posted") or "", reverse=True)
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(rows),
        "posts": rows,
    }


def _num(rows: list[dict], key: str) -> list[int]:
    return [int(r.get(key) or 0) for r in rows]


def summarise(data: dict) -> str:
    rows = data.get("posts", [])
    if not rows:
        return "# Metrics\n\nNo posts returned.\n"

    n = len(rows)
    reach = _num(rows, "reach")
    total_reach = sum(reach)
    avg = total_reach / n if n else 0

    # "Sends" is the strongest ranking input Instagram currently has, so it is
    # worth watching even when the absolute numbers are tiny.
    by_sends = sorted(rows, key=lambda r: (r.get("shares") or 0, r.get("saved") or 0),
                      reverse=True)[:5]
    by_reach = sorted(rows, key=lambda r: r.get("reach") or 0, reverse=True)[:5]

    lines = [
        "# Metrics",
        "",
        f"_Fetched {data['fetched_at']}_",
        "",
        f"- Posts measured: **{n}**",
        f"- Total reach: **{total_reach:,}**",
        f"- Mean reach per post: **{avg:.1f}**",
        f"- Best single post: **{max(reach) if reach else 0}**",
        f"- Total saves: **{sum(_num(rows, 'saved')):,}**  ·  "
        f"sends: **{sum(_num(rows, 'shares')):,}**",
        "",
    ]

    if n < MIN_POSTS_FOR_SIGNAL or avg < 25:
        lines += [
            "> **Read this before drawing conclusions.** At this volume and",
            "> reach, the gap between the best and worst post here is noise,",
            "> not signal. Instagram shows a new account's post to a small",
            "> test audience; if it does not convert, distribution stops. No",
            "> hook, format, hashtag or posting time changes that. Treat this",
            "> file as a baseline being established, not as a verdict on any",
            "> individual post.",
            "",
        ]

    lines += ["## Most sent and saved", ""]
    for r in by_sends:
        lines.append(
            f"- **{r.get('shares', 0)} sends · {r.get('saved', 0)} saves · "
            f"{r.get('reach', 0)} reach** — {r['hook']}"
        )

    lines += ["", "## Widest reach", ""]
    for r in by_reach:
        lines.append(f"- **{r.get('reach', 0)}** — {r['hook']}")

    lines += ["", "## Every post", "",
              "| Posted | Type | Reach | Saves | Sends | Hook |",
              "|---|---|---:|---:|---:|---|"]
    for r in rows:
        posted = (r.get("posted") or "")[:10]
        lines.append(
            f"| {posted} | {r.get('type', '')} | {r.get('reach', 0)} | "
            f"{r.get('saved', 0)} | {r.get('shares', 0)} | {r['hook'][:70]} |"
        )
    return "\n".join(lines) + "\n"


def brief_context(max_examples: int = 5) -> str:
    """A block the generator can paste into its prompt. Empty when there is
    not enough data to say anything true — an empty string is much better
    than a confident lie about what is working."""
    if not JSON_PATH.exists():
        return ""
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""

    rows = data.get("posts", [])
    if len(rows) < MIN_POSTS_FOR_SIGNAL:
        return ""

    engaged = [r for r in rows if (r.get("shares") or 0) or (r.get("saved") or 0)]
    if not engaged:
        return (
            "PERFORMANCE SO FAR: nothing published has been saved or sent by "
            "anyone. Do not interpret this as a topic problem — the account is "
            "reaching a test audience only. Keep writing for the reader you "
            "want, not for the algorithm."
        )

    engaged.sort(key=lambda r: (r.get("shares") or 0) + (r.get("saved") or 0),
                 reverse=True)
    top = engaged[:max_examples]
    lines = [
        "PERFORMANCE SO FAR — the posts people actually saved or sent on. "
        "Sends and saves matter; likes do not. Note what these have in common "
        "and do more of it, without repeating the posts themselves:",
    ]
    for r in top:
        lines.append(
            f"  - [{r.get('shares', 0)} sends, {r.get('saved', 0)} saves] {r['hook']}"
        )
    dead = [r for r in rows if not (r.get("shares") or 0) and not (r.get("saved") or 0)]
    if dead:
        lines.append(
            f"  ({len(dead)} of {len(rows)} posts got neither a save nor a send.)"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = collect(args.limit)
    md = summarise(data)

    if args.dry_run:
        print("\n" + md)
        return 0

    STATE.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(md, encoding="utf-8")
    print(f"\n[metrics] wrote {JSON_PATH.relative_to(ROOT)} "
          f"and {MD_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
