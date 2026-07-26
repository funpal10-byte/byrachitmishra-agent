"""Turn a signal brief into finished posts, one slot at a time."""

from __future__ import annotations

import json
import re

import anthropic

from . import config
from .schema import POST_SCHEMA, check_voice, validate


USER_TEMPLATE = """Write one Instagram post for this slot.

PILLAR: {pillar_name}
FORMAT: {fmt}
GOES LIVE: {when}

Keywords available for this pillar (pick ONE as the primary, and prefer a
long-tail phrase — it is easier to rank for and it makes a better hook):
  primary options : {keywords}
  long-tail options: {long_tail}

Suggested hashtags for this pillar (you may swap up to two for something more
specific to this post, but never exceed five total):
  {hashtags}

THIS WEEK'S SIGNAL BRIEF — use it if something here genuinely fits this pillar.
If nothing fits, write an evergreen post instead rather than forcing a
connection. A forced news hook is worse than no news hook.

{brief}

AVOID REPEATING these recent posts:
{recent}

Return only the JSON object. Schema:
{schema}
"""


def _extract_json(text: str) -> dict:
    """Models occasionally wrap JSON in fences despite instructions."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object found in model output:\n{text[:500]}")
    return json.loads(text[start : end + 1])


def generate_post(
    brand,
    system_prompt: str,
    pillar,
    fmt: str,
    when: str,
    brief: str,
    recent_titles: list[str],
) -> dict:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    user = USER_TEMPLATE.format(
        pillar_name=pillar.name,
        fmt=fmt,
        when=when,
        keywords=", ".join(pillar.keywords),
        long_tail="; ".join(pillar.long_tail),
        hashtags=" ".join(pillar.hashtags),
        brief=brief or "(no brief available this week — write evergreen)",
        recent="\n".join(f"- {t}" for t in recent_titles) or "(nothing yet)",
        schema=json.dumps(POST_SCHEMA, indent=2),
    )

    messages = [{"role": "user", "content": user}]
    post: dict = {}

    # One generation pass, then up to two self-corrections if the post breaks
    # a hard limit. Cheaper and more reliable than trying to get it perfect
    # in one shot, and it means overflowing slides never reach the renderer.
    for attempt in range(3):
        resp = client.messages.create(
            model=config.MODEL,
            max_tokens=6000,
            system=system_prompt,
            messages=messages,
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        post = _extract_json(raw)
        post.setdefault("pillar", pillar.id)
        post.setdefault("format", fmt)

        problems = validate(post) + check_voice(post, brand.voice.get("banned_phrases", []))
        if not problems:
            break

        if attempt == 2:
            post["_warnings"] = problems
            break

        messages += [
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "That output has problems. Fix every one of them and return "
                    "the corrected JSON object only:\n\n"
                    + "\n".join(f"- {p}" for p in problems)
                ),
            },
        ]

    return post
