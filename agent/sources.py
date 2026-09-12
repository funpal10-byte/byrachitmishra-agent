"""Non-blocking source preflight for factual Instagram posts."""

from __future__ import annotations

from urllib.parse import urlparse


def valid_http_url(value: str) -> bool:
    parsed = urlparse((value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def preflight(evidence: dict) -> dict:
    """Record whether a cited source is reachable without making drafts brittle.

    An outage, bot wall or redirect is review information, not a reason to lose
    an entire weekly batch. Malformed URLs are already rejected by the schema.
    """
    if not isinstance(evidence, dict) or evidence.get("type") != "source":
        return {"status": "not_required"}
    url = str(evidence.get("source_url") or "").strip()
    if not valid_http_url(url):
        return {"status": "invalid_url", "url": url}
    try:
        # Keep URL-format tests and non-publishing utilities usable in a plain
        # Python checkout; GitHub Actions installs requests from requirements.
        import requests

        response = requests.head(url, allow_redirects=True, timeout=8,
                                 headers={"User-Agent": "byrachitmishra-agent/1.0"})
        return {
            "status": "verified" if response.ok else "unreachable",
            "url": url,
            "final_url": response.url,
            "http_status": response.status_code,
        }
    except Exception as exc:  # network and optional-dependency failures are review data
        return {"status": "unreachable", "url": url, "detail": str(exc)[:160]}
