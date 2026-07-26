"""One interface, two providers.

The rest of the agent never imports a vendor SDK directly. It calls
`llm.generate(...)` and this module decides who answers. That means switching
between the free Gemini tier and paid Claude is a settings change, not a code
change — set the LLM_PROVIDER repository variable and the next run uses it.

Both providers support server-side web search, so the weekly research pass
works either way.
"""

from __future__ import annotations

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

# Preference order, best first. Google retires model IDs fairly often, so
# this is a wish list rather than a promise — anything unavailable is skipped
# and the resolver falls through to whatever Flash model does exist.
_GEMINI_PREFERENCE = (
    "gemini-flash-latest",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
)

_resolved_gemini_model: str | None = None


def _pick_gemini_model(client) -> str:
    """Ask the API what it actually offers, rather than trusting a hardcoded
    name that goes stale the moment Google retires a version."""
    global _resolved_gemini_model

    if forced := config.model_name():
        return forced
    if _resolved_gemini_model:
        return _resolved_gemini_model

    try:
        available = set()
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if actions and "generateContent" not in actions:
                continue
            available.add((getattr(m, "name", "") or "").removeprefix("models/"))
    except Exception as exc:
        print(f"[llm] could not list models ({exc}); falling back to {_GEMINI_PREFERENCE[1]}")
        return _GEMINI_PREFERENCE[1]

    for want in _GEMINI_PREFERENCE:
        if want in available:
            _resolved_gemini_model = want
            break
    else:
        # Nothing on the wish list. Take the newest-looking Flash model, since
        # sorting these IDs descending puts higher version numbers first.
        flashes = sorted((n for n in available if "flash" in n and "image" not in n), reverse=True)
        if not flashes:
            raise LLMError(f"no usable Gemini text model found. Available: {sorted(available)}")
        _resolved_gemini_model = flashes[0]

    print(f"[llm] using Gemini model: {_resolved_gemini_model}")
    return _resolved_gemini_model


def _gemini_generate(
    system: str,
    messages: list[dict],
    max_tokens: int,
    web_search: int = 0,
) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GOOGLE_API_KEY)
    model = _pick_gemini_model(client)

    contents = [
        types.Content(
            # Gemini calls the assistant turn "model", Anthropic calls it
            # "assistant". Translate so callers can use one vocabulary.
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in messages
    ]

    cfg: dict = {"max_output_tokens": max_tokens}
    if system:
        cfg["system_instruction"] = system

    if web_search:
        # Gemini has no per-call search budget the way Anthropic does; the
        # model decides how many searches to run.
        cfg["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    else:
        # Structured output. Not combinable with the search tool, so it is
        # only used on the generation calls, which is where it matters.
        cfg["response_mime_type"] = "application/json"

    # Gemini 2.5+ models think by default, and thinking tokens are billed
    # against max_output_tokens. Left alone, the model can spend the entire
    # budget reasoning and return an empty response. Switch it off: these are
    # structured writing tasks, not puzzles.
    thinking_off = dict(cfg, thinking_config=types.ThinkingConfig(thinking_budget=0))

    def _call(conf: dict):
        return client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(**conf),
        )

    try:
        resp = _call(thinking_off)
    except Exception as exc:
        # Some models refuse to have thinking disabled. Fall back rather than
        # dying, and give the budget more room so thinking cannot starve the
        # actual answer.
        if "thinking" not in str(exc).lower():
            raise
        resp = _call(dict(cfg, max_output_tokens=max_tokens * 3))

    return _gemini_text(resp)


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
