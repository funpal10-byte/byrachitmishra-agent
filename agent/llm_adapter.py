"""
A thin, defensive wrapper around whatever `agent/llm.py` already exposes.

Why this exists: `llm.py` has been rewritten a few times (provider switch,
Gemini model discovery, the three request shapes). Rather than hard-code a
function name that might have drifted, this finds the first callable that
looks like a completion entrypoint and uses it.

If none matches, the error message tells you exactly what to do — it does NOT
fail silently, because a silent LLM failure is how you end up with empty posts
committed to the repo.
"""

from __future__ import annotations

import inspect

from agent import llm as _llm

# In preference order. The first one that exists wins.
_CANDIDATES = (
    "complete",
    "generate",
    "call",
    "chat",
    "run",
    "completion",
    "ask",
)


def _find():
    for name in _CANDIDATES:
        fn = getattr(_llm, name, None)
        if callable(fn):
            return name, fn
    exported = sorted(
        n for n, o in vars(_llm).items()
        if callable(o) and not n.startswith("_")
    )
    raise RuntimeError(
        "llm_adapter could not find a completion function in agent/llm.py.\n"
        f"Functions it does export: {exported}\n"
        "Fix: add the right name to _CANDIDATES at the top of this file."
    )


def complete(system: str, user: str, max_tokens: int = 2000) -> str:
    """Send a system + user prompt, get text back.

    Tries the adapted function with a few common signatures. Whichever shape
    `llm.py` actually uses, one of these should land.
    """
    name, fn = _find()
    params = set(inspect.signature(fn).parameters)

    attempts = []
    if {"system", "user"} <= params:
        attempts.append(((), {"system": system, "user": user}))
    if {"system", "prompt"} <= params:
        attempts.append(((), {"system": system, "prompt": user}))
    if "prompt" in params:
        attempts.append(((), {"prompt": f"{system}\n\n---\n\n{user}"}))
    # Positional fallbacks, most likely last.
    attempts.append(((system, user), {}))
    attempts.append(((f"{system}\n\n---\n\n{user}",), {}))

    last = None
    for args, kwargs in attempts:
        if "max_tokens" in params:
            kwargs = {**kwargs, "max_tokens": max_tokens}
        elif "max_output_tokens" in params:
            kwargs = {**kwargs, "max_output_tokens": max_tokens}
        try:
            out = fn(*args, **kwargs)
        except TypeError as exc:
            last = exc
            continue
        if isinstance(out, str):
            return out
        # Some versions returned (text, meta) or a dict.
        if isinstance(out, tuple) and out and isinstance(out[0], str):
            return out[0]
        if isinstance(out, dict):
            for k in ("text", "content", "output"):
                if isinstance(out.get(k), str):
                    return out[k]
        last = TypeError(f"{name}() returned unusable type {type(out)!r}")

    raise RuntimeError(
        f"llm_adapter matched agent.llm.{name} but every call shape failed. "
        f"Last error: {last}"
    )
