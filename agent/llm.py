"""One interface, two providers.

The rest of the agent never imports a vendor SDK directly. It calls
`llm.generate(...)` and this module decides who answers. That means switching
between the free Gemini tier and paid Claude is a settings change, not a code
change — set the LLM_PROVIDER repository variable and the next run uses it.

Both providers support server-side web search, so the weekly research pass
works either way.
"""

from __future__ import annotations

import time

from . import config


class LLMError(RuntimeError):
    pass


# --------------------------------------------------------------------------
#  Anthropic
# --------------------------------------------------------------------------

def _anthropic_generate(
    system: str,
    messages: list[dict],
    max_tokens: int,
    web_search: int = 0,
) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    kwargs: dict = {
        "model": config.model_name(),
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if web_search:
        kwargs["tools"] = [
            {"type": config.WEB_SEARCH_TOOL, "name": "web_search", "max_uses": web_search}
        ]

    resp = client.messages.create(**kwargs)
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


# --------------------------------------------------------------------------
#  Google Gemini
# --------------------------------------------------------------------------

# Preference order, best first. Deliberately no "-latest" aliases: those move
# without warning and often carry a much smaller free-tier quota than the
# pinned IDs they point at. Anything unavailable is skipped.
_GEMINI_PREFERENCE = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
)

_gemini_candidates_cache: list[str] | None = None

# Free-tier quotas are per-minute as well as per-day, and a batch fires five
# posts back to back. A small gap between calls is the difference between a
# clean run and a wall of 429s.
_MIN_GAP_SECONDS = 4.0
_last_call_at = 0.0


def _pace() -> None:
    global _last_call_at
    wait = _MIN_GAP_SECONDS - (time.monotonic() - _last_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_call_at = time.monotonic()


def _status_code(exc: Exception) -> int | None:
    for attr in ("code", "status_code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    text = str(exc)
    for code in (429, 400, 404, 403, 500, 503):
        if str(code) in text[:40]:
            return code
    return None


def _gemini_candidates(client) -> list[str]:
    """Ordered list of models worth trying, best first.

    Returns several rather than one so that a model with no free-tier quota
    can be stepped past at run time instead of failing the whole batch.
    """
    global _gemini_candidates_cache

    if forced := config.model_name():
        return [forced]
    if _gemini_candidates_cache:
        return _gemini_candidates_cache

    try:
        available = set()
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if actions and "generateContent" not in actions:
                continue
            available.add((getattr(m, "name", "") or "").removeprefix("models/"))
    except Exception as exc:
        print(f"[llm] could not list models ({exc}); trying the preference list blind")
        return list(_GEMINI_PREFERENCE)

    ranked = [n for n in _GEMINI_PREFERENCE if n in available]

    # Anything else that looks like a usable Flash text model, newest first.
    # Sorting the IDs descending puts higher version numbers at the front.
    extras = sorted(
        (
            n
            for n in available
            if "flash" in n
            and n not in ranked
            and not any(bad in n for bad in ("image", "latest", "preview", "tts", "audio", "embedding"))
        ),
        reverse=True,
    )
    ranked += extras

    if not ranked:
        raise LLMError(f"no usable Gemini text model found. Available: {sorted(available)}")

    _gemini_candidates_cache = ranked
    print(f"[llm] Gemini candidates, in order: {', '.join(ranked[:4])}")
    return ranked


def _gemini_generate(
    system: str,
    messages: list[dict],
    max_tokens: int,
    web_search: int = 0,
) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GOOGLE_API_KEY)

    contents = [
        types.Content(
            # Gemini calls the assistant turn "model", Anthropic calls it
            # "assistant". Translate so callers can use one vocabulary.
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]

    base: dict = {"max_output_tokens": max_tokens}
    if system:
        base["system_instruction"] = system

    if web_search:
        # Gemini has no per-call search budget the way Anthropic does; the
        # model decides how many searches to run.
        base["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    else:
        # Structured output. Not combinable with the search tool, so it is
        # only used on the generation calls, which is where it matters.
        base["response_mime_type"] = "application/json"

    plain = {k: v for k, v in base.items() if k != "response_mime_type"}

    # Progressively simpler requests. Model families disagree about which of
    # these options they accept — 2.5 wants thinking disabled so it does not
    # eat the output budget, 3.x refuses to have it disabled at all — and the
    # API reports the disagreement as a generic "invalid argument". Rather
    # than encode which model wants what, try each shape and keep the first
    # that works.
    variants = [
        ("thinking off", dict(base, thinking_config=types.ThinkingConfig(thinking_budget=0))),
        ("thinking on, wider budget", dict(base, max_output_tokens=max_tokens * 3)),
        ("plain", dict(plain, max_output_tokens=max_tokens * 3)),
    ]

    problems: list[str] = []

    for model in _gemini_candidates(client)[:3]:
        quota_hit = False
        for label, conf in variants:
            for attempt in range(2):
                try:
                    _pace()
                    resp = client.models.generate_content(
                        model=model,
                        contents=contents,
                        config=types.GenerateContentConfig(**conf),
                    )
                    return _gemini_text(resp)
                except LLMError:
                    raise
                except Exception as exc:
                    code = _status_code(exc)
                    if code == 429:
                        if attempt == 0:
                            print(f"[llm] {model}: rate limited, waiting 30s")
                            time.sleep(30)
                            continue
                        # Out of quota on this model — a different config
                        # won't help, so move on to the next model.
                        quota_hit = True
                    problems.append(f"{model} [{label}]: {str(exc)[:160]}")
                    break
            if quota_hit:
                print(f"[llm] {model}: quota exhausted, trying next model")
                break

    raise LLMError("every Gemini attempt failed:\n  " + "\n  ".join(problems))


def _gemini_text(resp) -> str:
    """Pull the text out, and explain clearly when there isn't any."""
    if getattr(resp, "text", None):
        return resp.text

    # .text can be empty when the response is split across parts by grounding.
    out: list[str] = []
    finish = None
    for cand in getattr(resp, "candidates", None) or []:
        finish = getattr(cand, "finish_reason", None) or finish
        for part in getattr(getattr(cand, "content", None), "parts", None) or []:
            if getattr(part, "text", None):
                out.append(part.text)
    if out:
        return "".join(out)

    if finish and "MAX_TOKENS" in str(finish).upper():
        raise LLMError(
            "Gemini hit the output token limit before writing anything — usually "
            "thinking tokens eating the budget. Raise max_tokens or switch model."
        )
    if finish and "SAFETY" in str(finish).upper():
        raise LLMError("Gemini blocked the response on safety filters.")
    raise LLMError(f"Gemini returned no text (finish_reason={finish}).")


# --------------------------------------------------------------------------

_BACKENDS = {"anthropic": _anthropic_generate, "gemini": _gemini_generate}


def generate(
    system: str,
    messages: list[dict],
    max_tokens: int = 4000,
    web_search: int = 0,
) -> str:
    """Send a conversation, get text back.

    messages : [{"role": "user"|"assistant", "content": "..."}]
    web_search : 0 to disable, or the max number of searches to allow.
    """
    provider = config.provider()
    backend = _BACKENDS.get(provider)
    if not backend:
        raise LLMError(f"unknown LLM_PROVIDER '{provider}' — expected anthropic or gemini")
    if not config.api_key():
        raise LLMError(
            f"provider is '{provider}' but its API key is not set. "
            f"Add {'GOOGLE_API_KEY' if provider == 'gemini' else 'ANTHROPIC_API_KEY'} "
            "to your repository secrets."
        )
    return backend(system, messages, max_tokens, web_search)
