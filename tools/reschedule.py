#!/usr/bin/env python3
"""Put unpublished posts back into rotation on fresh dates.

Posts that missed their slot get archived with status "skipped" rather than
deleted, precisely so they can be reused. This walks the archive, re-dates
whatever it finds onto upcoming slots, and moves it back to content/approved.

    python tools/reschedule.py --per-day 2 --start 2026-08-18

Never touches anything already published — those are on Instagram and reusing
them would post a duplicate.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import config  # noqa: E402

# Well-spaced defaults. Instagram deliberately holds back posts published in
# quick succession, so two a day wants a morning slot and an evening one, not
# two slots an hour apart.
DEFAULT_TIMES = ["08:30", "19:00", "12:30", "21:00"]


def collect(include_approved: bool) -> list[Path]:
    """Every post.json that is unpublished and reusable, oldest first."""
    found: list[tuple[str, Path]] = []
    roots = [config.PUBLISHED_DIR] + ([config.APPROVED_DIR] if include_approved else [])

    for root in roots:
        for f in root.rglob("post.json"):
            try:
                post = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if post.get("status") == "published" or post.get("media_id"):
                continue
            found.append((post.get("scheduled_for", ""), f))

    found.sort(key=lambda pair: pair[0])
    return [f for _, f in found]


def slots(start: dt.date, per_day: int, times: list[str], count: int, tz) -> list[dt.datetime]:
    chosen = sorted(times[:per_day], key=lambda t: dt.time.fromisoformat(t))
    out: list[dt.datetime] = []
    day = start
    while len(out) < count:
        for t in chosen:
            if len(out) >= count:
                break
            out.append(dt.datetime.combine(day, dt.time.fromisoformat(t), tzinfo=tz))
        day += dt.timedelta(days=1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-day", type=int, default=2, help="posts per day (1-4)")
    ap.add_argument("--start", default="", help="YYYY-MM-DD, defaults to tomorrow")
    ap.add_argument("--limit", type=int, default=0, help="only reschedule the N oldest")
    ap.add_argument("--times", default="", help="comma-separated HH:MM, overrides defaults")
    ap.add_argument(
        "--include-approved",
        action="store_true",
        help="also re-date posts still sitting in content/approved",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    brand = config.load_brand()
    tz = brand.timezone
    per_day = max(1, min(4, args.per_day))
    times = [t.strip() for t in args.times.split(",") if t.strip()] or DEFAULT_TIMES

    start = (
        dt.date.fromisoformat(args.start)
        if args.start
        else dt.datetime.now(tz).date() + dt.timedelta(days=1)
    )

    posts = collect(args.include_approved)
    if args.limit:
        posts = posts[: args.limit]

    if not posts:
        print("Nothing to reschedule — no unpublished posts found in the archive.")
        return 0

    when = slots(start, per_day, times, len(posts), tz)
    batch = config.APPROVED_DIR / f"rescheduled-{start:%Y-%m-%d}"
    print(f"Rescheduling {len(posts)} post(s), {per_day}/day from {start}\n")

    moved = 0
    for f, new_time in zip(posts, when):
        folder = f.parent
        post = json.loads(f.read_text(encoding="utf-8"))
        label = post.get("title", folder.name)
        fmt = post.get("format", "?")
        print(f"  {new_time:%a %d %b %H:%M}  {fmt:9s}  {label}")

        if args.dry_run:
            continue

        post["scheduled_for"] = new_time.isoformat()
        post["status"] = "approved"
        post["rescheduled_from"] = post.pop("skipped_reason", "manual reschedule")
        f.write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")

        dest = batch / folder.name
        if dest.exists():
            dest = batch / f"{folder.name}-{moved}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(folder), str(dest))
        moved += 1

    if args.dry_run:
        print("\n(dry run — nothing moved)")
        return 0

    # Reels lose nothing on the way through, but rebuild any whose video is
    # missing so they are publishable rather than held.
    rebuilt = 0
    for f in sorted(batch.rglob("post.json")):
        post = json.loads(f.read_text(encoding="utf-8"))
        if post.get("format") != "reel" or (f.parent / "reel.mp4").exists():
            continue
        try:
            from agent import video

            if video.build_reel(post, brand, f.parent, index=rebuilt):
                rebuilt += 1
        except Exception as exc:
            print(f"  [video] could not rebuild {f.parent.name}: {exc}", file=sys.stderr)

    print(f"\nMoved {moved} post(s) into {batch.relative_to(config.ROOT)}")
    if rebuilt:
        print(f"Rebuilt {rebuilt} Reel video(s)")
    print("Commit and push, and the hourly publisher will pick them up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
