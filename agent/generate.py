"""Turn a signal brief into finished posts, one slot at a time."""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import llm
from .schema import POST_SCHEMA, check_voice, validate

# Both of these are additive and both fail soft. A missing hook library or an
# empty metrics file must never stop a week from being generated.
try:
    from .metrics import brief_context
except Exception:  # noqa: BLE001
    def brief_context(max_examples: int = 5) -> str:  # type: ignore[misc]
        return ""

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _read_prompt(name: str) -> str:
    """A supplementary prompt file, or "" if it is not there.

    Missing files are never fatal: a week must still generate if someone
    renames or removes one of these.
    """
    try:
        return (_PROMPT_DIR / name).read_text(encoding="utf-8")
    except OSError:
        return ""


def _hook_library() -> str:
    """Opening structures written for this account's register.

    Appended to the system prompt rather than pasted into system.md so the
    two can be edited independently — the library changes as hooks are tested,
    the strategist brief does not.
    """
    return _read_prompt("hooks.md")


def idea_context() -> str:
    """Only unfinished, nonempty ideas are editorial inputs; examples are not."""
    path = _PROMPT_DIR.parent / "ideas.md"
    if not path.exists():
        return ""
    body = path.read_text(encoding="utf-8").split("## Ideas", 1)[-1]
    ideas = re.findall(r"^- \[ \] (\S.*)$", body, re.M)
    if not ideas:
        return ""
    return "AUTHOR'S IDEA BANK — prefer relevant ideas to news:\n" + "\n".join(ideas)


USER_TEMPLATE = """Write one Instagram post for this slot.

PILLAR: {pillar_name}
FORMAT: {fmt}
GOES LIVE: {when}

Keywords available for this pillar (pick ONE as the primary, and prefer a
long-tail phrase — it is easier to rank for, but do NOT force it into the
hook; a sharp opening tension is more important than keyword-shaped wording):
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

Non-negotiable opening contract: `hook` is a short tension-led claim, not a
topic label. It must exactly equal Reel beat 1 `onscreen` text and be the first
words of Reel beat 1 `voiceover`; for a carousel it must equal slide 1's
headline. The caption's first line must contain ONLY the hook, followed by
two newline characters. Put the primary keyword naturally in the next
sentence, within the first 125 caption characters. Interior carousel bodies
must be complete sentences of at most 120 characters; rewrite, never truncate.

Do not use an unsupported number. Supply the required `evidence` object with
the proof or usable framework that earns the claim.

Write the cover, hook and payoff as ONE connected promise. Before choosing,
silently compare three openings for concrete audience relevance, clarity,
curiosity and whether the body delivers. Return only the winning post JSON.
For a Reel, `reel_cover.headline` is 2-6 words: name a familiar object or
decision and the unresolved tension. A shortened or paraphrased hook is
welcome; do not copy the whole first-frame sentence. Repeat the subject
where needed for clarity. Avoid standalone labels like "The Enterprise AI
Trap", "Commodity pricing traps" or "The unmonitored tier".
The hook sharpens that SAME tension; beat two begins its explanation, and
the rest provides a concrete check the reader can use. Do not reveal a
different subject after the viewer taps. Carousel slide one and slide two
must follow the same promise-to-payoff relationship.
Example: cover "Same steel. Higher price."; hook "Why pay more for identical
steel?"; beat two explains how delivery reliability reduces buyer risk.
Use this structure only where the post actually supports it.
The short `signal` supports the SAME promise. Never invent a precise number
for a thumbnail, even if another generated field repeats it. A number needs
evidence from the supplied source; otherwise use a plain-language contrast.
Choose `layout` from `signal`, `split`, or `stamp` to fit the visual.
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


def _normalise_generated_opening(post: dict) -> dict:
    """Apply the non-creative parts of the publishing contract deterministically.

    Models commonly add punctuation, markdown or a preamble to an otherwise
    strong hook. That is not an editorial reason to throw away an entire
    weekly batch. Keep the model's copy and make the first line canonical.
    Keyword placement and shortening remain editorial correction tasks.
    """
    hook = str(post.get("hook") or "").strip()
    caption = str(post.get("caption") or "").strip()
    if hook:
        lines = caption.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines:
            opening = lines[0].strip().strip('*')
            if opening.casefold().startswith(hook.casefold()):
                remainder = opening[len(hook):].lstrip('.!? :;—–-')
                lines[0:1] = [hook] + (["", remainder] if remainder else [])
            else:
                # Preserve different opening copy so correction can rewrite
                # it without silently losing the first paragraph.
                lines[0:0] = [hook, ""]
        else:
            lines = [hook]
        caption = "\n".join(lines).strip()

        post["caption"] = caption

    # Never truncate prose to pass validation: the model must rewrite it.
    return post


def generate_post(
    brand,
    system_prompt: str,
    pillar,
    fmt: str,
    when: str,
    brief: str,
    recent_titles: list[str],
) -> dict:
    # What actually happened to what we published. Returns an empty string
    # until there are enough measured posts to say something true, so early
    # runs are unchanged — feeding the model noise and calling it insight is
    # worse than telling it nothing.
    performance = brief_context()
    full_brief = brief or "(no brief available this week — write evergreen)"
    if ideas := idea_context():
        full_brief = f"{ideas}\n\n{full_brief}"
    if performance:
        full_brief = f"{full_brief}\n\n{performance}"

    user = USER_TEMPLATE.format(
        pillar_name=pillar.name,
        fmt=fmt,
        when=when,
        keywords=", ".join(pillar.keywords),
        long_tail="; ".join(pillar.long_tail),
        hashtags=" ".join(pillar.hashtags),
        brief=full_brief,
        recent="\n".join(f"- {t}" for t in recent_titles) or "(nothing yet)",
        schema=json.dumps(POST_SCHEMA, indent=2),
    )

    hooks = _hook_library()
    if hooks:
        system_prompt = f"{system_prompt}\n\n---\n\n{hooks}"
    system_prompt += "\n\n" + _read_prompt("visual-story.md")

    # Carousels carry a fixed frame grammar; Reels do not. Loading it only for
    # the format that uses it keeps the Reel prompt from being padded with
    # rules it must then ignore.
    if fmt == "carousel":
        grammar = _read_prompt("carousel-grammar.md")
        if grammar:
            system_prompt = f"{system_prompt}\n\n---\n\n{grammar}"

    messages = [{"role": "user", "content": user}]
    post: dict = {}

    # One generation pass, then up to two self-corrections if the post breaks
    # a hard quality rule. A post that still fails does not enter the queue:
    # warnings are too easy to merge and then become auto-approved content.
    for attempt in range(3):
        raw = llm.generate(system=system_prompt, messages=messages, max_tokens=6000)
        post = _extract_json(raw)
        post["pillar"] = pillar.id
        post["format"] = fmt
        post = _normalise_generated_opening(post)

        problems = validate(post) + check_voice(post, brand.voice.get("banned_phrases", []))
        if not problems:
            break

        if attempt == 2:
            raise ValueError(
                "generated post failed the publish-quality gate after two corrections:\n"
                + "\n".join(f"- {problem}" for problem in problems)
            )

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
