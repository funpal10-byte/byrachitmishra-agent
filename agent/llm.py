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

    cfg: dict = {"max_output_tokens": max_tokens}
    if system:
        cfg["system_instruction"] = system
    if web_search:
        # Gemini has no per-call search budget the way Anthropic does; the
        # model decides how many searches to run.
        cfg["tools"] = [types.Tool(google_search=types.GoogleSearch())]

    resp = client.models.generate_content(
        model=config.model_name(),
        contents=contents,
        config=types.GenerateContentConfig(**cfg),
    )

    text = getattr(resp, "text", None)
    if text:
        return text

    # Fall back to walking the parts if .text is empty, which happens when the
    # response is split across several parts by the grounding step.
    out: list[str] = []
    for cand in getattr(resp, "candidates", None) or []:
        for part in getattr(getattr(cand, "content", None), "parts", None) or []:
            if getattr(part, "text", None):
                out.append(part.text)
    if not out:
        raise LLMError(f"Gemini returned no text. Full response: {resp}")
    return "".join(out)


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
