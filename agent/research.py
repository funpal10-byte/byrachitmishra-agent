"""Weekly research pass.

Uses whichever provider is configured, with its own server-side web search —
Claude's web_search tool, or Gemini's Google Search grounding. Either way the
agent needs exactly one API key. Produces a short "signal brief" of what
actually happened this week, which is then handed to the generator.
"""

from __future__ import annotations

import datetime as dt

from . import llm


BRIEF_PROMPT = """You are researching for a brand-strategy and marketing Instagram page.

Today is {today}. Search the web and tell me what actually happened in the last
7 days that is worth a post for this audience:

{audience}

Cover these areas:
{queries}

Return a brief of 6-10 signals. For each one give me, in this shape:

SIGNAL: <one sentence on what happened>
WHY IT MATTERS: <one sentence on why this audience should care>
ANGLE: <the specific, non-obvious take this page could make on it>
SOURCE: <url>

Rules:
- Only include things you actually found and can cite. If a week was quiet,
  return fewer signals rather than padding with generic evergreen topics.
- Skip anything in these areas: {avoid}
- Prefer specific, named, verifiable events — a campaign that launched, a
  product that shipped, a report with numbers in it, a company that changed
  its positioning — over trend-piece abstractions.
- At least two signals should be relevant to India specifically.
"""


def weekly_brief(brand) -> str:
    """Return a plain-text brief of this week's signals, with sources."""
    rc = brand.research
    a = brand.raw["audience"]

    prompt = BRIEF_PROMPT.format(
        today=dt.date.today().isoformat(),
        audience=f"{a['core'].strip()}\n{a['adjacent'].strip()}",
        queries="\n".join(f"- {q}" for q in rc.get("queries", [])),
        avoid=", ".join(rc.get("avoid_topics", [])) or "none",
    )

    return llm.generate(
        system="",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        web_search=rc.get("max_searches", 8),
    ).strip()
