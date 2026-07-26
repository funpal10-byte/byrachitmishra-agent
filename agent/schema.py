"""The JSON contract between the model and the rest of the pipeline.

Kept in one place so the prompt, the validator, and the renderer can never
drift apart. If you widen the schema, widen the validator too.
"""

from __future__ import annotations

POST_SCHEMA: dict = {
    "type": "object",
    "required": [
        "title",
        "pillar",
        "format",
        "primary_keyword",
        "hook",
        "caption",
        "alt_text",
        "hashtags",
        "failure_mode",
    ],
    "properties": {
        "title": {
            "type": "string",
            "description": "Short internal label for this post. Used as the folder name. Lowercase, no punctuation.",
        },
        "pillar": {"type": "string"},
        "format": {"type": "string", "enum": ["carousel", "reel", "still"]},
        "primary_keyword": {
            "type": "string",
            "description": "The single search term this post targets.",
        },
        "claim": {
            "type": "string",
            "description": "The one specific claim this post makes, in a sentence.",
        },
        "hook": {
            "type": "string",
            "description": "First line of the caption. Under 125 characters. Contains the primary keyword phrased naturally.",
        },
        "slides": {
            "type": "array",
            "description": "Required when format is carousel. 6-8 items.",
            "items": {
                "type": "object",
                "required": ["headline"],
                "properties": {
                    "kicker": {"type": "string", "description": "Max 24 chars. Omit on slide 1."},
                    "headline": {"type": "string", "description": "Max 70 chars (60 on slides 1 and last)."},
                    "body": {"type": "string", "description": "Max 200 chars. Omit on slide 1."},
                },
            },
        },
        "reel_script": {
            "type": "array",
            "description": "Required when format is reel. 6-10 beats, total under 90 seconds.",
            "items": {
                "type": "object",
                "required": ["timecode", "onscreen", "voiceover"],
                "properties": {
                    "timecode": {"type": "string", "description": "e.g. 0:00-0:03"},
                    "onscreen": {"type": "string", "description": "Max 48 chars. Burned onto the video."},
                    "voiceover": {"type": "string"},
                    "direction": {"type": "string", "description": "What is on camera during this beat."},
                },
            },
        },
        "caption": {
            "type": "string",
            "description": "Full caption WITHOUT hashtags. Structure: hook, payoff, substance, POV line, send-oriented CTA.",
        },
        "alt_text": {"type": "string", "description": "Max 100 characters. Honestly descriptive."},
        "hashtags": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {"type": "string"},
            "description": "Exactly 5 or fewer. Instagram enforces a hard cap of 5.",
        },
        "cta": {"type": "string", "description": "The send-oriented call to action, repeated separately for reference."},
        "failure_mode": {
            "type": "string",
            "description": "The honest reason this post might land badly or read as generic.",
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
            },
        },
    },
}


LIMITS = {
    "hook": 125,
    "alt_text": 100,
    "slide_headline": 70,
    "slide_headline_edge": 60,
    "slide_body": 200,
    "slide_kicker": 24,
    "onscreen": 48,
    "caption": 2200,
    "hashtags": 5,
}


def validate(post: dict) -> list[str]:
    """Return a list of human-readable problems. Empty list means it is clean.

    These are checked after generation and written into the pull request, so a
    borderline post is visible rather than silently shipped.
    """
    problems: list[str] = []

    def too_long(label: str, text: str, limit: int) -> None:
        if text and len(text) > limit:
            problems.append(f"{label} is {len(text)} chars, limit is {limit}: {text[:60]}...")

    for key in POST_SCHEMA["required"]:
        if not post.get(key):
            problems.append(f"missing required field: {key}")

    too_long("hook", post.get("hook", ""), LIMITS["hook"])
    too_long("alt_text", post.get("alt_text", ""), LIMITS["alt_text"])
    too_long("caption", post.get("caption", ""), LIMITS["caption"])

    tags = post.get("hashtags", [])
    if len(tags) > LIMITS["hashtags"]:
        problems.append(f"{len(tags)} hashtags — Instagram caps posts at 5")
    for t in tags:
        if not t.startswith("#"):
            problems.append(f"hashtag missing '#': {t}")

    fmt = post.get("format")
    if fmt == "carousel":
        slides = post.get("slides") or []
        if not 6 <= len(slides) <= 8:
            problems.append(f"carousel has {len(slides)} slides, expected 6-8")
        for i, s in enumerate(slides):
            edge = i == 0 or i == len(slides) - 1
            limit = LIMITS["slide_headline_edge"] if edge else LIMITS["slide_headline"]
            too_long(f"slide {i + 1} headline", s.get("headline", ""), limit)
            too_long(f"slide {i + 1} body", s.get("body", ""), LIMITS["slide_body"])
            too_long(f"slide {i + 1} kicker", s.get("kicker", ""), LIMITS["slide_kicker"])
    elif fmt == "reel":
        beats = post.get("reel_script") or []
        if not 6 <= len(beats) <= 10:
            problems.append(f"reel has {len(beats)} beats, expected 6-10")
        for i, b in enumerate(beats):
            too_long(f"beat {i + 1} onscreen", b.get("onscreen", ""), LIMITS["onscreen"])

    return problems


def check_voice(post: dict, banned_phrases: list[str]) -> list[str]:
    """Catch the phrases that make a post read like everyone else's."""
    blob = " ".join(
        [
            post.get("caption", ""),
            post.get("hook", ""),
            " ".join(s.get("headline", "") + " " + s.get("body", "") for s in post.get("slides") or []),
            " ".join(b.get("voiceover", "") for b in post.get("reel_script") or []),
        ]
    ).lower()
    return [f"banned phrase in copy: '{p}'" for p in banned_phrases if p.lower() in blob]
