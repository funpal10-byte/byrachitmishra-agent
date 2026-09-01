"""
One research run, three surfaces.

Reads every post sitting in content/queue/ and, for each, writes two sibling
files next to post.json:

    linkedin.md   — the same idea, rewritten for a professional feed
    blog.md       — an outline for a long-form piece on rachitmishra.in

Neither is published by anything. They are drafts for a human. That is
deliberate: LinkedIn has no publishing API worth trusting for a personal
profile, and auto-posting under a senior in-house leader's name is a
reputational risk that no amount of convenience justifies.

Run it standalone — it does not require any edit to generate.py:

    python -m agent.repurpose
    python -m agent.repurpose --force      # rewrite even if files exist
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from agent.llm_adapter import complete

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "content" / "queue"
BRAND = ROOT / "brand" / "brand.yml"


def _brand() -> dict:
    if not BRAND.exists():
        return {}
    return yaml.safe_load(BRAND.read_text(encoding="utf-8")) or {}


def _voice_block(brand: dict) -> str:
    ident = brand.get("identity", {})
    voice = brand.get("voice", {})
    lines = [
        f"POSITIONING:\n{ident.get('positioning', '').strip()}",
        f"\nVOICE:\n{voice.get('description', '').strip()}",
    ]
    if voice.get("exemplars"):
        lines.append(
            "\nCALIBRATION — his own sentences. Anything that could not sit "
            "beside these is off voice:\n"
            + "\n".join(f"  - {e}" for e in voice["exemplars"])
        )
    if voice.get("banned_phrases"):
        lines.append(
            "\nNEVER USE: " + ", ".join(f'"{p}"' for p in voice["banned_phrases"])
        )
    if voice.get("banned_patterns"):
        lines.append(
            "\nHARD RULES:\n"
            + "\n".join(f"  - {p}" for p in voice["banned_patterns"])
        )
    return "\n".join(lines)


LINKEDIN_SYSTEM = """You are rewriting one idea for LinkedIn.

{voice}

LinkedIn is NOT Instagram with longer text. The differences that matter:

- The reader is a working professional, at a desk, in a professional frame of
  mind. They will read 900 characters if the first two lines earn it.
- There are no slides carrying the argument. The post must be complete on its
  own — it cannot reference or depend on a visual.
- Hashtags are close to useless here. Use none, or at most two.
- The first two lines appear before "…see more". Everything hangs on them.
  No preamble, no throat-clearing, no rhetorical question.
- Line breaks do the work of formatting. Short paragraphs, one to three
  sentences, blank line between. Never bullet points — they read as a
  deliverable, not a thought.
- The close should invite a specific disagreement or a specific experience,
  not "thoughts?". Comments are the ranking signal, and vague prompts get
  vague comments.

Length: 900-1,400 characters. Under 900 reads thin for this audience.

Write the post and nothing else. No title, no commentary, no markdown
headings, no code fence."""

BLOG_SYSTEM = """You are turning one idea into an outline for a long-form
article on the author's own site.

{voice}

This is the surface where the work compounds — search indexes it, AI
assistants cite it, and it does not disappear down a feed. So the standard is
higher than a social post: it must say something a reader could not get from
the first page of search results.

Return GitHub-flavoured markdown with exactly these sections:

# <the working title — specific, not clever>

**Target keyword:** <the phrase someone would actually search>
**Secondary:** <two or three related phrases, comma separated>
**Reader:** <one line: who this is for and what they want>

## The argument in one paragraph
<The whole thesis, stated plainly. If this paragraph is not interesting, the
article is not worth writing — say so here rather than proceeding.>

## Outline
<Five to eight H2-level sections. For each: the heading, then one or two
sentences on what it covers and what evidence or example carries it. Be
concrete about the evidence — "a figure from the sector's annual reports",
not "supporting data".>

## What this needs that I do not have yet
<Honest list: the numbers to look up, the source to verify, the example to
find. This is the section that makes the outline actionable.>

## Internal links
<Two or three other pieces this should link to, described by topic.>

No commentary outside these sections."""


def _post_context(post: dict) -> str:
    parts = [f"PILLAR: {post.get('pillar', 'unknown')}"]
    for key in ("hook", "title", "claim", "thesis"):
        if post.get(key):
            parts.append(f"{key.upper()}: {post[key]}")
    slides = post.get("slides") or post.get("script") or []
    if slides:
        rendered = []
        for i, s in enumerate(slides, 1):
            if isinstance(s, dict):
                text = " / ".join(
                    str(v) for v in s.values() if isinstance(v, str) and v.strip()
                )
            else:
                text = str(s)
            rendered.append(f"  {i}. {text}")
        parts.append("SLIDES OR SCRIPT:\n" + "\n".join(rendered))
    if post.get("caption"):
        parts.append(f"INSTAGRAM CAPTION:\n{post['caption']}")
    return "\n\n".join(parts)


def repurpose_one(folder: Path, brand: dict, force: bool = False) -> list[str]:
    post_file = folder / "post.json"
    if not post_file.exists():
        return []

    try:
        post = json.loads(post_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"  [skip] {folder.name}: post.json is not valid JSON ({exc})")
        return []

    voice = _voice_block(brand)
    context = _post_context(post)
    written = []

    targets = (
        ("linkedin.md", LINKEDIN_SYSTEM, 1200),
        ("blog.md", BLOG_SYSTEM, 2400),
    )

    for name, system, budget in targets:
        out = folder / name
        if out.exists() and not force:
            print(f"  [have] {folder.name}/{name}")
            continue
        try:
            text = complete(
                system=system.format(voice=voice),
                user=(
                    "Here is the post that was written for Instagram. Rework "
                    "the IDEA, not the words — this is a different surface "
                    "with a different reader, and a copy-paste would fail on "
                    "both.\n\n" + context
                ),
                max_tokens=budget,
            ).strip()
        except Exception as exc:  # noqa: BLE001 — one bad post must not stop the batch
            print(f"  [FAIL] {folder.name}/{name}: {exc}")
            continue

        if len(text) < 200:
            print(f"  [FAIL] {folder.name}/{name}: model returned {len(text)} chars")
            continue

        # Models like to wrap output in a fence despite being told not to.
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3].rstrip()

        out.write_text(text + "\n", encoding="utf-8")
        print(f"  [ok]   {folder.name}/{name}  ({len(text)} chars)")
        written.append(str(out.relative_to(ROOT)))

    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="rewrite files that already exist")
    args = ap.parse_args()

    if not QUEUE.exists():
        print(f"[repurpose] no queue at {QUEUE} — nothing to do")
        return 0

    folders = sorted(p for p in QUEUE.iterdir() if p.is_dir())
    if not folders:
        print("[repurpose] queue is empty — nothing to do")
        return 0

    brand = _brand()
    if not brand:
        print(f"[repurpose] WARNING: {BRAND} missing or empty — voice will be generic")

    print(f"[repurpose] {len(folders)} queued post(s)")
    total = []
    for folder in folders:
        print(f"- {folder.name}")
        total.extend(repurpose_one(folder, brand, force=args.force))

    print(f"\n[repurpose] wrote {len(total)} file(s)")
    # Unlike the generator, producing nothing here is not an error — the files
    # may simply already exist. Only a hard crash should fail the workflow.
    return 0


if __name__ == "__main__":
    sys.exit(main())
