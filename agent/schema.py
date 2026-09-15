"""The JSON contract between the model and the rest of the pipeline.

Kept in one place so the prompt, the validator, and the renderer can never
drift apart. If you widen the schema, widen the validator too.
"""

from __future__ import annotations

import re

from .sources import valid_http_url

VISUAL_SCHEMA = {
    "type": "object", "required": ["kind", "items", "note"],
    "properties": {
        "kind": {"type": "string", "enum": ["bottleneck", "comparison", "checklist"]},
        "items": {"type": "array", "minItems": 2, "maxItems": 4,
                  "items": {"type": "object", "required": ["label", "detail"],
                            "properties": {"label": {"type": "string", "maxLength": 24},
                                           "detail": {"type": "string", "maxLength": 48}}}},
        "note": {"type": "string", "maxLength": 60},
    },
}

POST_SCHEMA: dict = {
    "type": "object",
    "required": [
        "title",
        "pillar",
        "format",
        "primary_keyword",
        "claim",
        "hook",
        "evidence",
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
            "description": "The single opening promise. Under 48 characters and 10 words. It must be the caption's first line and the exact first on-screen line for a Reel or slide one headline for a carousel.",
        },
        "evidence": {
            "type": "object",
            "required": ["type", "detail"],
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["source", "case_study", "practitioner_observation", "framework"],
                },
                "detail": {
                    "type": "string",
                    "description": "The specific proof behind the claim: a source finding, named case, observed situation, or usable framework. Never invent a statistic.",
                },
                "source_url": {
                    "type": "string",
                    "description": "Required when type is source. A direct URL for the factual claim.",
                },
            },
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
                    "visual": VISUAL_SCHEMA,
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
                    "visual": VISUAL_SCHEMA,
                },
            },
        },
        "reel_cover": {
            "type": "object",
            "description": "Required for Reels only. The separate profile-grid cover; it must package the tension without repeating the first frame.",
            "required": ["headline", "signal", "layout", "visual"],
            "properties": {
                "visual": VISUAL_SCHEMA,
                "headline": {
                    "type": "string",
                    "description": "2-6 words, max 36 characters. A distinct curiosity line, not a rewrite of the hook.",
                },
                "signal": {
                    "type": "string",
                    "description": "Max 24 characters. A concrete number, trade-off, or proof fragment from the Reel, shown as a visual label.",
                },
                "layout": {
                    "type": "string",
                    "enum": ["signal", "split", "stamp"],
                    "description": "Choose the visual device that best fits the tension. Vary it deliberately across Reels.",
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
    "hook": 48,
    "hook_words": 10,
    "alt_text": 100,
    "slide_headline": 70,
    "slide_headline_edge": 60,
    "slide_body": 200,
    "slide_kicker": 24,
    "onscreen": 48,
    "reel_cover_headline": 36,
    "reel_cover_signal": 24,
    "caption": 2200,
    "hashtags": 5,
}

EVIDENCE_TYPES = {"source", "case_study", "practitioner_observation", "framework"}


def _normalise(text: str) -> str:
    """Compare copy independent of case, punctuation and repeated spaces."""
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def _opening_quality_problems(hook: str) -> list[str]:
    """Catch reliably-detectable hook failures before a post reaches review.

    This is intentionally a small rejection list. Whether an idea is original is
    a human/editorial judgement; these checks guard the repeated failure modes
    we can establish mechanically: topic labels and empty strategy aphorisms.
    """
    plain = _normalise(hook)
    problems: list[str] = []
    if "?" in hook:
        problems.append("hook is a question — open with a claim or tension instead")
    topic_openers = (
        r"^(how|when|what)\s+(ai|marketing|branding|brand|leadership|to\b|this\b)",
        r"^(a|an|the)\s+(guide|case study|breakdown)\b",
    )
    if any(re.search(pattern, plain) for pattern in topic_openers):
        problems.append("hook starts as a topic label — lead with the cost, tension or objection")
    filler_phrases = (
        "comes down to",
        "is built on",
        "is all about",
        "is about what",
        "the key to",
        "is important",
    )
    if any(phrase in plain for phrase in filler_phrases):
        problems.append("hook uses a generic strategy aphorism — name a concrete tension")
    return problems


def validate(post: dict, require_visuals: bool = True) -> list[str]:
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
    hook_words = len((post.get("hook") or "").split())
    if hook_words > LIMITS["hook_words"]:
        problems.append(
            f"hook has {hook_words} words, limit is {LIMITS['hook_words']} for a first-frame read"
        )
    problems.extend(_opening_quality_problems(post.get("hook", "")))
    too_long("alt_text", post.get("alt_text", ""), LIMITS["alt_text"])
    too_long("caption", post.get("caption", ""), LIMITS["caption"])

    hook = _normalise(post.get("hook", ""))
    caption_start = _normalise(((post.get("caption") or "").splitlines() or [""])[0])
    if hook and caption_start != hook:
        problems.append("caption first line must exactly match hook")
    primary_keyword = _normalise(post.get("primary_keyword", ""))
    if primary_keyword and primary_keyword not in _normalise((post.get("caption") or "")[:125]):
        problems.append("primary keyword must appear naturally in the first 125 caption characters")

    evidence = post.get("evidence") or {}
    if evidence and not isinstance(evidence, dict):
        problems.append("evidence must be an object with type and detail")
    elif evidence:
        if evidence.get("type") not in EVIDENCE_TYPES:
            problems.append("evidence type must be source, case_study, practitioner_observation or framework")
        if not str(evidence.get("detail", "")).strip():
            problems.append("evidence needs a specific detail behind the claim")
        if evidence.get("type") == "source" and not str(evidence.get("source_url", "")).strip():
            problems.append("source evidence requires source_url")
        elif evidence.get("type") == "source" and not valid_http_url(str(evidence.get("source_url", ""))):
            problems.append("source evidence source_url must be an http or https URL")

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
            if require_visuals and 0 < i < len(slides) - 1:
                problems.extend(validate_visual(s.get("visual"), f"slide {i + 1}"))
                too_long(f"slide {i + 1} visual body", s.get("body", ""), 120)
        if slides and hook and _normalise(slides[0].get("headline", "")) != hook:
            problems.append("slide 1 headline must exactly match hook")
    elif fmt == "reel":
        beats = post.get("reel_script") or []
        cover = post.get("reel_cover") or {}
        if not isinstance(cover, dict):
            problems.append("reel_cover must be an object")
            cover = {}
        for key in ("headline", "signal", "layout"):
            if require_visuals and not str(cover.get(key, "")).strip():
                problems.append(f"reel cover missing {key}")
        cover_headline = str(cover.get("headline", "")).strip()
        if require_visuals:
            problems.extend(validate_visual(cover.get("visual"), "reel cover"))
        cover_words = len(cover_headline.split())
        too_long("reel cover headline", cover_headline, LIMITS["reel_cover_headline"])
        too_long("reel cover signal", str(cover.get("signal", "")), LIMITS["reel_cover_signal"])
        if cover_headline and not 2 <= cover_words <= 6:
            problems.append(
                f"reel cover headline has {cover_words} words, expected 2-6 for profile-grid reading"
            )
        if cover_headline and hook and _normalise(cover_headline) == hook:
            problems.append("reel cover headline repeats the opening hook — package a different tension")
        if cover.get("layout") and cover.get("layout") not in {"signal", "split", "stamp"}:
            problems.append("reel cover layout must be signal, split or stamp")
        if not 6 <= len(beats) <= 10:
            problems.append(f"reel has {len(beats)} beats, expected 6-10")
        for i, b in enumerate(beats):
            too_long(f"beat {i + 1} onscreen", b.get("onscreen", ""), LIMITS["onscreen"])
            if b.get("visual"):
                problems.extend(validate_visual(b["visual"], f"beat {i + 1}"))
        visuals = [b.get("visual") for b in beats[1:] if isinstance(b.get("visual"), dict)]
        if require_visuals and len(visuals) < 2:
            problems.append("Reel needs at least two visual beats after its opener")
        if require_visuals and not any(v.get("kind") == "checklist" for v in visuals):
            problems.append("Reel needs a usable checklist visual")
        if beats:
            first = beats[0]
            if hook and _normalise(first.get("onscreen", "")) != hook:
                problems.append("Reel beat 1 onscreen text must exactly match hook")
            if hook and not _normalise(first.get("voiceover", "")).startswith(hook):
                problems.append("Reel beat 1 voiceover must start with the exact hook")
            if not str(first.get("timecode", "")).strip().startswith("0:00-"):
                problems.append("Reel beat 1 must start at 0:00")

    return problems


def validate_visual(visual, label: str) -> list[str]:
    if not isinstance(visual, dict):
        return [f"{label} needs a visual object"]
    problems = []
    kind = visual.get("kind")
    if kind not in {"bottleneck", "comparison", "checklist"}:
        problems.append(f"{label} has an unsupported visual kind")
    items = visual.get("items")
    if not isinstance(items, list) or not 2 <= len(items) <= 4:
        return problems + [f"{label} visual needs 2-4 items"]
    if kind in {"bottleneck", "comparison"} and len(items) != 2:
        problems.append(f"{label} {kind} visual needs exactly two items")
    for item in items:
        for field, limit in (("label", 24), ("detail", 48)):
            value = item.get(field) if isinstance(item, dict) else None
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                problems.append(f"{label} visual {field} must be 1-{limit} characters")
    note = visual.get("note")
    if not isinstance(note, str) or not note.strip() or len(note) > 60:
        problems.append(f"{label} visual needs a basis note of 1-60 characters")
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
