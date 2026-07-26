#!/usr/bin/env python3
"""Render a sample carousel without calling any API.

Use this to tune the look of your slides — colours, type sizes, layout — by
editing brand/brand.yml and templates/slide.html and re-running. No API key
needed, costs nothing.

    python tools/preview.py
    open preview/           # or however you view images
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import config, render  # noqa: E402

SAMPLE = {
    "title": "positioning is not a tagline",
    "pillar": "brand_strategy",
    "format": "carousel",
    "primary_keyword": "brand positioning",
    "slides": [
        {"headline": "Positioning is not a tagline"},
        {
            "kicker": "The confusion",
            "headline": "Most teams write the words before the decision",
            "body": "A tagline is the output. Positioning is the choice about who you are for and who you are not for.",
        },
        {
            "kicker": "The test",
            "headline": "Can a competitor claim your line?",
            "body": "If a rival could put their logo on your positioning statement and nothing would look wrong, you have a slogan, not a position.",
        },
        {
            "kicker": "The tradeoff",
            "headline": "A real position costs you customers",
            "body": "Deciding who you are not for is the part everyone skips, and it is the only part that makes the rest work.",
        },
        {
            "kicker": "In practice",
            "headline": "Write the sentence someone else says",
            "body": "Positioning is what people say about you when you are not in the room. Write that sentence, then earn it.",
        },
        {
            "kicker": "The check",
            "headline": "Two minutes, three questions",
            "body": "Who is this for. What do we do that others will not. Why should anyone believe us. If the answers wobble, start there.",
        },
        {
            "headline": "Save this for your next brand review",
            "body": "Send it to whoever keeps asking for a new tagline.",
        },
    ],
}


def main() -> int:
    brand = config.load_brand()
    out = config.ROOT / "preview"
    paths = render.render_carousel(SAMPLE, brand, out)
    for p in paths:
        print(p)
    print(f"\n{len(paths)} slides written to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
