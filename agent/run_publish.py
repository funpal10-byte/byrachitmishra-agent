"""Publish anything that has been approved and is now due.

Approval is the pull request merge: merging moves a batch from content/queue
into content/approved. This script runs hourly, finds approved posts whose
scheduled time has passed, publishes them, and files them under
content/published so they are never published twice.

With PUBLISH_ENABLED unset it does a full dry run and prints exactly what it
would have done — which is how you should run it for the first fortnight.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import sys
from pathlib import Path

from . import config, publish


def due_posts(now: dt.datetime) -> list[Path]:
    out: list[Path] = []
    for f in sorted(config.APPROVED_DIR.rglob("post.json")):
        try:
            post = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[skip] unreadable {f}: {exc}", file=sys.stderr)
            continue
        if post.get("status") == "published":
            continue
        when = post.get("scheduled_for")
        if not when:
            continue
        if dt.datetime.fromisoformat(when) <= now:
            out.append(f)
    return out


def archive(folder: Path) -> None:
    dest = config.PUBLISHED_DIR / folder.parent.name / folder.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(folder), str(dest))


def main() -> int:
    brand = config.load_brand()
    now = dt.datetime.now(brand.timezone)
    pending = due_posts(now)

    if not pending:
        print(f"[publish] nothing due as of {now:%Y-%m-%d %H:%M %Z}")
        return 0

    if not config.PUBLISH_ENABLED:
        print("[publish] DRY RUN — PUBLISH_ENABLED is not true. Would publish:")
        for f in pending:
            post = json.loads(f.read_text(encoding="utf-8"))
            imgs = [f.parent / Path(p).name for p in post.get("images", [])]
            ok = sum(1 for p in imgs if p.exists())
            note = f"{ok}/{len(imgs)} images"
            if post.get("format") == "reel":
                vid = f.parent / "reel.mp4"
                note = (
                    f"video {vid.stat().st_size / 1_000_000:.1f} MB"
                    if vid.exists()
                    else "NO VIDEO — will be held"
                )
            print(
                f"  · {post.get('scheduled_for')} · {post.get('format')} · "
                f"{post.get('title', '').strip()} · {note}"
            )
        return 0

    if not (config.IG_USER_ID and config.IG_ACCESS_TOKEN):
        print("[publish] IG_USER_ID / IG_ACCESS_TOKEN missing", file=sys.stderr)
        return 1

    failures = 0
    for f in pending:
        folder = f.parent
        post = json.loads(f.read_text(encoding="utf-8"))
        # Images live beside post.json. Resolve by filename rather than by the
        # path recorded at generation time — the folder moves from queue/ to
        # approved/ to published/, and the recorded path goes stale.
        images = [folder / Path(p).name for p in post.get("images", [])]
        missing = [p.name for p in images if not p.exists()]
        if missing:
            print(f"[hold] {folder.name}: missing images {missing}", file=sys.stderr)
            continue
        fmt = post.get("format")

        try:
            if fmt == "carousel" and len(images) >= 2:
                media_id = publish.publish_carousel(post, images)
            elif fmt == "still" and images:
                media_id = publish.publish_image(post, images[0])
            elif fmt == "reel":
                video = folder / "reel.mp4"
                if not video.exists():
                    print(f"[hold] {folder.name}: no reel.mp4 yet, leaving in approved/")
                    continue
                cover = images[0] if images else None
                media_id = publish.publish_reel(
                    post,
                    publish.asset_url(video),
                    publish.asset_url(cover) if cover else None,
                )
            else:
                print(f"[hold] {folder.name}: nothing publishable for format={fmt}")
                continue
        except Exception as exc:
            failures += 1
            print(f"[publish] FAILED {folder.name}: {exc}", file=sys.stderr)
            continue

        post["status"] = "published"
        post["published_at"] = dt.datetime.now(brand.timezone).isoformat()
        post["media_id"] = media_id
        f.write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")

        # The video is on Instagram now. Keeping a copy in git would add a few
        # megabytes a week to a repository that never forgets anything.
        stale = folder / "reel.mp4"
        if stale.exists():
            stale.unlink()
            (folder / ".generated-reel").unlink(missing_ok=True)

        archive(folder)
        print(f"[publish] live: {post.get('title')} → media {media_id}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
