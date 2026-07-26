"""Instagram publishing via the Instagram API with Instagram Login.

Two-step flow for every post: create a media container, then publish it.
Carousels need one container per item first, then a parent container.

Requires:
  - an Instagram professional (Creator or Business) account
  - scopes: instagram_business_basic, instagram_business_content_publish
  - images reachable at a public HTTPS URL at the moment of the call
  - JPEG only

Meta's limit is 100 API-published posts per rolling 24 hours, which you will
never approach at five posts a week.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from . import config

BASE = "https://graph.instagram.com"
TIMEOUT = 60


class PublishError(RuntimeError):
    pass


def _url(path: str) -> str:
    return f"{BASE}/{config.IG_API_VERSION}/{path}"


def _post(path: str, params: dict) -> dict:
    params = {**params, "access_token": config.IG_ACCESS_TOKEN}
    r = requests.post(_url(path), data=params, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise PublishError(f"{r.status_code} on {path}: {r.text}")
    return r.json()


def _get(path: str, params: dict) -> dict:
    params = {**params, "access_token": config.IG_ACCESS_TOKEN}
    r = requests.get(_url(path), params=params, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise PublishError(f"{r.status_code} on {path}: {r.text}")
    return r.json()


def asset_url(local_path: Path) -> str:
    """Turn a repo-relative file path into the public URL Meta will fetch.

    Defaults to raw.githubusercontent.com, which requires the repo to be
    public. Set ASSET_BASE_URL if you host images somewhere else.
    """
    if not config.ASSET_BASE_URL:
        raise PublishError(
            "ASSET_BASE_URL is not set and GITHUB_REPOSITORY is unavailable — "
            "the API cannot fetch your images without a public URL."
        )
    rel = local_path.resolve().relative_to(config.ROOT).as_posix()
    return f"{config.ASSET_BASE_URL.rstrip('/')}/{rel}"


def _wait_ready(container_id: str, tries: int = 30, delay: int = 5) -> None:
    """Containers are processed asynchronously. Poll until FINISHED.

    Images are usually instant; video containers genuinely take a while, which
    is why this exists at all.
    """
    for _ in range(tries):
        status = _get(container_id, {"fields": "status_code,status"})
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code in {"ERROR", "EXPIRED"}:
            raise PublishError(f"container {container_id} failed: {status}")
        time.sleep(delay)
    raise PublishError(f"container {container_id} not ready after {tries * delay}s")


def _full_caption(post: dict) -> str:
    tags = " ".join(post.get("hashtags", [])[:5])
    return f"{post['caption'].rstrip()}\n\n{tags}".strip()


def publish_carousel(post: dict, image_paths: list[Path]) -> str:
    if not 2 <= len(image_paths) <= 10:
        raise PublishError(f"carousel needs 2-10 images, got {len(image_paths)}")

    children = []
    for p in image_paths:
        res = _post(
            f"{config.IG_USER_ID}/media",
            {"image_url": asset_url(p), "is_carousel_item": "true"},
        )
        children.append(res["id"])

    for cid in children:
        _wait_ready(cid)

    parent = _post(
        f"{config.IG_USER_ID}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": _full_caption(post),
        },
    )
    _wait_ready(parent["id"])

    published = _post(f"{config.IG_USER_ID}/media_publish", {"creation_id": parent["id"]})
    return published["id"]


def publish_image(post: dict, image_path: Path) -> str:
    params = {"image_url": asset_url(image_path), "caption": _full_caption(post)}
    if post.get("alt_text"):
        # Alt text on image posts has been supported since March 2025.
        params["alt_text"] = post["alt_text"][:100]

    container = _post(f"{config.IG_USER_ID}/media", params)
    _wait_ready(container["id"])
    published = _post(f"{config.IG_USER_ID}/media_publish", {"creation_id": container["id"]})
    return published["id"]


def publish_reel(post: dict, video_url: str, cover_url: str | None = None) -> str:
    """Only usable once you supply a public URL to a rendered MP4.

    The agent does not shoot video for you — this exists so that when you drop
    a finished MP4 into the post folder, publishing is already wired up.
    """
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": _full_caption(post),
        "share_to_feed": "true",
    }
    if cover_url:
        params["cover_url"] = cover_url

    container = _post(f"{config.IG_USER_ID}/media", params)
    _wait_ready(container["id"], tries=60)
    published = _post(f"{config.IG_USER_ID}/media_publish", {"creation_id": container["id"]})
    return published["id"]


def refresh_token(token: str) -> dict:
    """Long-lived tokens last 60 days and can be refreshed once they are at
    least 24 hours old. Returns {'access_token', 'token_type', 'expires_in'}."""
    r = requests.get(
        f"{BASE}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=TIMEOUT,
    )
    if r.status_code >= 400:
        raise PublishError(f"token refresh failed: {r.status_code} {r.text}")
    return r.json()
