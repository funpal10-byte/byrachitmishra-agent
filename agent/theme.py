"""
Which ground a slide gets, and which colours go with it.

Rule, in one line: **light where people read, dark where people watch, and
dark once more as punctuation.**

Slide one of a carousel carries text somebody has to actually read, so it gets
the readable ground — that is the whole reason for the change away from a dark
opener. A Reel cover is consumed full-bleed with very little text, so contrast
wins there instead. And exactly one slide in a carousel inverts: the close.
One inverted frame in a light sequence reads as emphasis. Two read as noise.

Wire-up in render.py / video.py — replace the direct `design["bg"]` lookups:

    from agent.theme import palette

    p = palette(design, role="hook")            # or "body" / "close"
    ...  background: {p['bg']}; color: {p['ink']};

and for a Reel:

    p = palette(design, role="reel_cover")

`assets.logo(variant)` is untouched — pass `p["logo_variant"]` to it and the
existing three colourways keep working exactly as they do now.
"""

from __future__ import annotations

# Fallbacks only. brand.yml is the source of truth; these keep the renderer
# alive if a key is missing rather than blowing up mid-batch.
_DEFAULTS = {
    "bg": "#f5f4f1",
    "bg_alt": "#16181a",
    "ink": "#14161a",
    "ink_soft": "#52575c",
    "accent": "#b0492a",
    "accent_on_dark": "#e0855f",
    "rule": "#dedbd5",
}

_INK_ON_DARK = "#f2f1ee"
_INK_SOFT_ON_DARK = "#a9a7a2"
_RULE_ON_DARK = "#2f3134"

_DEFAULT_ROLES = {
    "hook": "light",
    "body": "light",
    "close": "inverted",
    "reel_cover": "inverted",
}


def _get(design: dict, key: str) -> str:
    value = (design or {}).get(key)
    # Same `or` pattern used throughout config.py: an empty string is not a
    # value, and YAML round-trips can leave one behind.
    return (value or "").strip() or _DEFAULTS[key]


def ground_for(design: dict, role: str) -> str:
    """'light' or 'inverted' for a slide role."""
    roles = {**_DEFAULT_ROLES, **((design or {}).get("slide_roles") or {})}
    return "inverted" if roles.get(role, "light") == "inverted" else "light"


def palette(design: dict, role: str = "body") -> dict:
    """Every colour the renderer needs for one slide, already resolved."""
    inverted = ground_for(design, role) == "inverted"

    if inverted:
        return {
            "ground": "inverted",
            "bg": _get(design, "bg_alt"),
            "ink": _INK_ON_DARK,
            "ink_soft": _INK_SOFT_ON_DARK,
            "accent": _get(design, "accent_on_dark"),
            "rule": _RULE_ON_DARK,
            "logo_variant": "white",
        }

    return {
        "ground": "light",
        "bg": _get(design, "bg"),
        "ink": _get(design, "ink"),
        "ink_soft": _get(design, "ink_soft"),
        "accent": _get(design, "accent"),
        "rule": _get(design, "rule"),
        "logo_variant": "dark",
    }


def roles_for_carousel(n_slides: int, design: dict | None = None) -> list[str]:
    """Role per slide for an n-slide carousel: hook, body…, close.

    Respects `invert_max_per_carousel` so a future brand.yml change cannot
    accidentally turn every slide dark.
    """
    if n_slides <= 0:
        return []
    if n_slides == 1:
        return ["hook"]

    roles = ["hook"] + ["body"] * (n_slides - 2) + ["close"]

    cap = (design or {}).get("invert_max_per_carousel", 1)
    try:
        cap = int(cap)
    except (TypeError, ValueError):
        cap = 1
    if cap < 1:
        roles = ["hook"] + ["body"] * (n_slides - 1)
    return roles
