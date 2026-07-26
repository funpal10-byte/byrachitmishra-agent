"""Configuration loading. Everything tunable lives in brand/brand.yml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
BRAND_FILE = ROOT / "brand" / "brand.yml"
PROMPT_FILE = ROOT / "prompts" / "system.md"
TEMPLATE_DIR = ROOT / "templates"
CONTENT_DIR = ROOT / "content"
QUEUE_DIR = CONTENT_DIR / "queue"
APPROVED_DIR = CONTENT_DIR / "approved"
PUBLISHED_DIR = CONTENT_DIR / "published"


# --- model + API settings, all overridable from workflow env -----------------

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Which provider writes the posts. Leave LLM_PROVIDER unset and the agent
# picks whichever key you have supplied — Gemini first, since that is the one
# with a free tier. Set it explicitly to pin a choice.
# Gemini deliberately has no default here: model IDs are retired often, so
# agent/llm.py asks the API which models exist and picks the best available.
# Set AGENT_MODEL to override that and pin a specific one.
DEFAULT_MODELS = {
    "gemini": "",                     # auto-resolved at run time
    "anthropic": "claude-sonnet-5",   # paid, better writing
}


def provider() -> str:
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    if GOOGLE_API_KEY:
        return "gemini"
    return "anthropic"


def api_key() -> str:
    return GOOGLE_API_KEY if provider() == "gemini" else ANTHROPIC_API_KEY


def model_name() -> str:
    """AGENT_MODEL wins if set, otherwise the provider's sensible default."""
    return os.getenv("AGENT_MODEL", "").strip() or DEFAULT_MODELS.get(provider(), "")


# Anthropic's web search tool version. `web_search_20250305` is the widely
# available baseline; newer versions add filtering you do not need here.
# Ignored when running on Gemini, which uses Google Search grounding instead.
WEB_SEARCH_TOOL = os.getenv("WEB_SEARCH_TOOL", "web_search_20250305")

IG_API_VERSION = os.getenv("IG_API_VERSION", "v25.0")
IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")

# Publishing is opt-in. With this unset the agent is a drafting machine and
# never touches your account.
PUBLISH_ENABLED = os.getenv("PUBLISH_ENABLED", "false").lower() == "true"

# Where rendered images are served from, so Meta can fetch them.
# Defaults to raw.githubusercontent.com for the current repo.
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "")
GITHUB_BRANCH = os.getenv("ASSET_BRANCH", "main")
ASSET_BASE_URL = os.getenv(
    "ASSET_BASE_URL",
    f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}" if GITHUB_REPO else "",
)


@dataclass
class Pillar:
    id: str
    name: str
    weight: int = 0
    default_format: str = "carousel"
    automate: bool = True
    keywords: list[str] = field(default_factory=list)
    long_tail: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)


@dataclass
class Brand:
    raw: dict[str, Any]

    @property
    def identity(self) -> dict[str, Any]:
        return self.raw["identity"]

    @property
    def handle(self) -> str:
        return self.identity["handle"]

    @property
    def design(self) -> dict[str, Any]:
        return self.raw["design"]

    @property
    def voice(self) -> dict[str, Any]:
        return self.raw["voice"]

    @property
    def research(self) -> dict[str, Any]:
        return self.raw.get("research", {})

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.raw["schedule"].get("timezone", "Asia/Kolkata"))

    @property
    def slots(self) -> list[dict[str, Any]]:
        return self.raw["schedule"]["slots"]

    @property
    def pillars(self) -> dict[str, Pillar]:
        out: dict[str, Pillar] = {}
        for p in self.raw["pillars"]:
            out[p["id"]] = Pillar(
                id=p["id"],
                name=p["name"],
                weight=p.get("weight", 0),
                default_format=p.get("default_format", "carousel"),
                automate=p.get("automate", True),
                keywords=p.get("keywords", []),
                long_tail=p.get("long_tail", []),
                hashtags=p.get("hashtags", []),
            )
        return out


def load_brand() -> Brand:
    with BRAND_FILE.open(encoding="utf-8") as fh:
        return Brand(yaml.safe_load(fh))


def load_system_prompt(brand: Brand) -> str:
    """Fill the system prompt template from brand.yml."""
    tpl = PROMPT_FILE.read_text(encoding="utf-8")
    v = brand.voice
    a = brand.raw["audience"]

    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {i}" for i in items)

    return (
        tpl.replace("{handle}", brand.handle)
        .replace("{name}", brand.identity["name"])
        .replace("{positioning}", brand.identity["positioning"].strip())
        .replace("{audience_core}", a["core"].strip())
        .replace("{audience_adjacent}", a["adjacent"].strip())
        .replace("{audience_market}", a["market"].strip())
        .replace("{voice_description}", v["description"].strip())
        .replace("{banned_phrases}", bullets(v.get("banned_phrases", [])))
        .replace("{banned_patterns}", bullets(v.get("banned_patterns", [])))
        .replace("{voice_must}", bullets(v.get("must", [])))
    )
