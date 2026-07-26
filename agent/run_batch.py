"""Weekly batch: research once, write five posts, render the images, and lay
everything out so it can be reviewed on a phone and posted with a copy-paste.

Run by .github/workflows/generate.yml every Sunday morning IST.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

from . import config, generate, render, research
from .schema import check_voice, validate

DAY_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "post"


def next_week_dates(brand, today: dt.date) -> dict[str, dt.date]:
    """Map each slot's day name to a date in the week starting the coming Monday."""
    monday = today + dt.timedelta(days=(7 - today.weekday()) % 7 or 7)
    return {d: monday + dt.timedelta(days=i) for d, i in DAY_INDEX.items()}


def recent_titles(limit: int = 25) -> list[str]:
    """So the agent stops re-writing the same post every third week."""
    titles: list[str] = []
    for base in (config.PUBLISHED_DIR, config.APPROVED_DIR, config.QUEUE_DIR):
        for f in sorted(base.rglob("post.json"), reverse=True):
            try:
                titles.append(json.loads(f.read_text(encoding="utf-8")).get("title", ""))
            except Exception:
                continue
    return [t for t in titles if t][:limit]


def write_readable(post: dict, folder: Path, images: list[Path], problems: list[str]) -> None:
    """The copy-paste artefact. This is what you actually read on your phone."""
    lines: list[str] = []
    a = lines.append

    a(f"# {post.get('title', 'Untitled')}")
    a("")
    a(f"**{post.get('format', '').upper()}** · {post.get('pillar', '')} · goes live **{post.get('scheduled_for', 'TBD')}**")
    a("")
    a(f"> Targeting: `{post.get('primary_keyword', '')}`")
    if post.get("claim"):
        a(f">")
        a(f"> Claim: {post['claim']}")
    a("")

    if problems:
        a("## ⚠️ Check these before approving")
        a("")
        for p in problems:
            a(f"- {p}")
        a("")

    if post.get("format") == "carousel" and post.get("slides"):
        a("## Slides")
        a("")
        a(f"{len(images)} rendered images sit in this folder — upload them in filename order.")
        a("")
        for i, s in enumerate(post["slides"], 1):
            a(f"**{i}.** {s.get('kicker', '')}")
            a(f"### {s.get('headline', '')}")
            if s.get("body"):
                a(s["body"])
            # Embedded so the whole carousel is reviewable on a phone, in the
            # GitHub app, without downloading anything.
            if i <= len(images):
                a("")
                a(f"![slide {i}]({images[i - 1].name})")
            a("")

    if post.get("format") == "reel" and post.get("reel_script"):
        a("## Reel script")
        a("")
        a("| Time | On screen | Voiceover | Direction |")
        a("|---|---|---|---|")
        for b in post["reel_script"]:
            a(
                f"| {b.get('timecode','')} | **{b.get('onscreen','')}** | "
                f"{b.get('voiceover','').replace('|','/')} | {b.get('direction','').replace('|','/')} |"
            )
        a("")

    a("## Caption — copy from here")
    a("")
    a("```")
    a(post.get("caption", "").rstrip())
    a("")
    a(" ".join(post.get("hashtags", [])[:5]))
    a("```")
    a("")
    a("## Alt text")
    a("")
    a("```")
    a(post.get("alt_text", ""))
    a("```")
    a("")

    if post.get("failure_mode"):
        a("## How this post could fail")
        a("")
        a(post["failure_mode"])
        a("")

    if post.get("sources"):
        a("## Sources")
        a("")
        for s in post["sources"]:
            a(f"- [{s.get('title', s.get('url',''))}]({s.get('url','')})")
        a("")

    (folder / "POST.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not config.api_key():
        want = "GOOGLE_API_KEY" if config.provider() == "gemini" else "ANTHROPIC_API_KEY"
        print(
            f"No API key found. Provider is '{config.provider()}', so add {want} "
            "to your repository secrets (Settings → Secrets and variables → Actions).",
            file=sys.stderr,
        )
        return 1

    print(f"[setup] provider={config.provider()} model={config.model_name()}")

    brand = config.load_brand()
    system_prompt = config.load_system_prompt(brand)
    pillars = brand.pillars
    today = dt.datetime.now(brand.timezone).date()
    dates = next_week_dates(brand, today)

    print(f"[research] gathering signals for week of {dates['mon']}")
    try:
        brief = research.weekly_brief(brand)
    except Exception as exc:  # research is a nice-to-have, not a blocker
        print(f"[research] failed, falling back to evergreen: {exc}", file=sys.stderr)
        brief = ""

    batch_dir = config.QUEUE_DIR / f"{dates['mon']:%Y-%m-%d}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    if brief:
        (batch_dir / "SIGNALS.md").write_text(
            f"# Signal brief — week of {dates['mon']}\n\n{brief}\n", encoding="utf-8"
        )

    seen = recent_titles()
    summary: list[str] = []

    for slot in brand.slots:
        pillar = pillars.get(slot["pillar"])
        if not pillar or not pillar.automate:
            print(f"[skip] {slot['pillar']} is marked manual")
            continue

        when = f"{dates[slot['day']]:%a %d %b} {slot['time']} IST"
        print(f"[write] {pillar.name} · {slot['format']} · {when}")

        try:
            post = generate.generate_post(
                brand, system_prompt, pillar, slot["format"], when, brief, seen
            )
        except Exception as exc:
            print(f"[write] FAILED for {pillar.name}: {exc}", file=sys.stderr)
            continue

        scheduled = dt.datetime.combine(
            dates[slot["day"]],
            dt.time.fromisoformat(slot["time"]),
            tzinfo=brand.timezone,
        )
        post["scheduled_for"] = scheduled.isoformat()
        post["status"] = "draft"
        seen.append(post.get("title", ""))

        folder = batch_dir / f"{slot['day']}-{slugify(post.get('title', pillar.id))}"
        folder.mkdir(parents=True, exist_ok=True)

        images: list[Path] = []
        try:
            if post.get("format") == "carousel":
                images = render.render_carousel(post, brand, folder)
            elif post.get("format") == "reel":
                cover = render.render_reel_cover(post, brand, folder)
                images = [cover] if cover else []
        except Exception as exc:
            print(f"[render] FAILED for {folder.name}: {exc}", file=sys.stderr)

        post["images"] = [p.relative_to(config.ROOT).as_posix() for p in images]
        problems = validate(post) + check_voice(post, brand.voice.get("banned_phrases", []))
        post["warnings"] = problems

        (folder / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False), encoding="utf-8")
        write_readable(post, folder, images, problems)

        flag = " ⚠️" if problems else ""
        summary.append(
            f"- **{when}** · {pillar.name} · {post.get('format')} — "
            f"[{post.get('title','untitled').strip()}]({folder.name}/POST.md){flag}"
        )

    (batch_dir / "README.md").write_text(
        "\n".join(
            [
                f"# Week of {dates['mon']:%d %B %Y}",
                "",
                "Five posts, drafted and rendered. Open each POST.md, read the caption,",
                "check the images. Merge this pull request to approve the whole batch.",
                "Delete a folder before merging to drop that post.",
                "",
                *summary,
                "",
                "⚠️ means the post tripped a length or voice check — worth a closer look.",
            ]
        ),
        encoding="utf-8",
    )

    print(f"[done] {len(summary)} posts written to {batch_dir}")
    # Expose the batch path to later workflow steps.
    if out := os.getenv("GITHUB_OUTPUT"):
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"batch_dir={batch_dir.relative_to(config.ROOT).as_posix()}\n")
            fh.write(f"week={dates['mon']:%Y-%m-%d}\n")
            fh.write(f"count={len(summary)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
