"""Turn a signal brief into finished posts, one slot at a time."""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import editorial, llm
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

ASSIGNED SOURCE BRIEF — derive the topic and useful tool from this material.
Do not substitute a generic evergreen opinion or force a pillar connection.

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
Do not copy example hooks from any instruction or reuse a recent premise.
The short `signal` supports the SAME promise. Never invent a precise number
for a thumbnail, even if another generated field repeats it. A number needs
evidence from the supplied source; otherwise use a plain-language contrast.
Choose `layout` from `signal`, `split`, or `stamp` to fit the visual.

BLOG-FIRST EDITORIAL CONTRACT (takes precedence over illustrative examples):
The supplied article determines the topic. Pillar keywords are suggestions,
not a reason to turn every article into procurement, compliance or budget advice.
Select a concrete tool, decision, example or disagreement from the source.
Put the useful part on screen early; do not spend most panels explaining why
the topic matters. Preserve specific steps and caveats from the article.
Supply `useful_takeaway`: `kind` (prompt/template/checklist/worked_example/
decision_test), and `visible_steps` (2-5 exact text snippets copied from the
rendered slide/beat text or visual items). These must collectively let someone
DO something: a prompt they can copy, fields they can fill, a test with a pass
condition, or an example that demonstrates a decision. Generic advice fails.
Reels have music, NOT spoken narration. All necessary explanation and the
takeaway must be in onscreen/visual fields; voiceover and direction are not seen.
Use only source-supported numbers. Never turn a percentage of respondents into
a performance improvement. Do not invent experience to make a hook interesting.
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
    editorial_history: list[dict] | None = None,
    source_article: dict | None = None,
) -> dict:
    # What actually happened to what we published. Returns an empty string
    # until there are enough measured posts to say something true, so early
    # runs are unchanged — feeding the model noise and calling it insight is
    # worse than telling it nothing.
    performance = brief_context()
    previous = editorial.history() if editorial_history is None else editorial_history
    full_brief = brief or "(no brief available this week — write evergreen)"
    if ideas := idea_context():
        full_brief = f"{ideas}\n\n{full_brief}"
    if performance:
        full_brief = f"{full_brief}\n\n{performance}"

    user = USER_TEMPLATE.format(
        pillar_name=(f"Source adaptation: {source_article['title']}" if source_article else pillar.name),
        fmt=fmt,
        when=when,
        keywords=("Choose a natural phrase from the assigned article's actual subject" if source_article else ", ".join(pillar.keywords)),
        long_tail=("Derive from the source; the calendar pillar does not determine the topic" if source_article else "; ".join(pillar.long_tail)),
        hashtags=("Choose three hashtags that describe this article; do not force AI or industry tags" if source_article else " ".join(pillar.hashtags)),
        brief=full_brief,
        recent=json.dumps(previous, ensure_ascii=False) if previous else "\n".join(recent_titles),
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

    system_prompt += (
        "\n\nEditorial priority: the assigned source controls the topic. Pillars and "
        "brand examples guide tone, not the argument. Never copy an example hook. "
        "Every post must deliver a distinct, concrete tool in visible text, with "
        "useful_takeaway.visible_steps copied from that text. Reels have music "
        "but no spoken voiceover. Preserve the source's meaning and caveats. "
        "Do not replace the source with generic evergreen advice."
    )
    messages = [{"role": "user", "content": user}]
    post: dict = {}

    # One generation pass, then up to two self-corrections if the post breaks
    # a hard quality rule. A post that still fails does not enter the queue:
    # warnings are too easy to merge and then become auto-approved content.
    for attempt in range(3):
        raw = llm.generate(system=system_prompt, messages=messages, max_tokens=6000)
        try:
            post = _extract_json(raw)
            if not isinstance(post, dict):
                raise ValueError('Expected a JSON object')
        except (ValueError, TypeError) as exc:
            if attempt == 2:
                raise ValueError('Model returned invalid JSON after two corrections') from exc
            messages += [{'role': 'assistant', 'content': raw},
                         {'role': 'user', 'content': 'Return a complete valid JSON object matching the schema. Your last response could not be parsed.'}]
            continue
        post["pillar"] = pillar.id
        post["format"] = fmt
        post["content_version"] = 3
        post = _normalise_generated_opening(post)

        problems = validate(post) + check_voice(post, brand.voice.get("banned_phrases", []))
        problems += editorial.duplicate_problems(post, previous)
        if source_article:
            evidence = post.get("evidence") or {}
            if evidence.get("type") != "source" or evidence.get("source_url", "").rstrip("/") != source_article["link"].rstrip("/"):
                problems.append("Evidence must cite the assigned blog URL with type=source")
        if not problems:
            review = editorial.review_result(llm.generate(
                system=editorial.REVIEW_SYSTEM,
                messages=[{"role": "user", "content": json.dumps({
                    "source": full_brief,
                    "recent_posts": previous,
                    "hook": post.get("hook"), "claim": post.get("claim"),
                    "cover": post.get("reel_cover"), "caption": post.get("caption"),
                    "visible_panels": editorial.visible_panels(post),
                    "useful_takeaway": post.get("useful_takeaway"),
                }, ensure_ascii=False)}], max_tokens=1800))
            if not review["approved"]:
                problems.extend(review["issues"])
            else:
                post["editorial_review"] = review
        if not problems:
            break

        if attempt == 2:
            raise ValueError(
                "generated post failed the publish-quality gate after two corrections:\n"
                + "\n".join(f"- {problem}" for problem in problems)
            )

        messages += [
            {"role": "assistant", "content": json.dumps(post, ensure_ascii=False)},
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
