"""Cross-post finished Reels to YouTube Shorts and LinkedIn via Zernio.

Why this exists rather than a direct YouTube integration: uploads from an
unaudited YouTube API project are locked to private, and a Google OAuth
consent screen left in "Testing" expires its refresh token every seven days.
Zernio is an approved partner on both platforms, so it carries that burden.
Its docs also state plainly that LinkedIn posts can go out "as a person or a
company page", which is the thing that decides whether LinkedIn is automatable
at all here.

    python -m agent.zernio --check                 # what is connected
    python -m agent.zernio --post <folder>         # dry run, prints payload
    python -m agent.zernio --post <folder> --send  # actually publishes

Nothing publishes without --send. The check is read-only and safe.

Media is passed to Zernio as a PUBLIC URL rather than uploaded, because the
repo is already public and every reel.mp4 is served from raw.githubusercontent
— the same mechanism Instagram publishing already relies on. If the API
rejects a URL the error will say so, and we switch to a real upload then
rather than guessing the multipart contract now.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent

BASE = (os.getenv("ZERNIO_API_BASE") or "https://zernio.com/api/v1").rstrip("/")

# Same `or` pattern as config.py — GitHub hands unset repository variables
# through as an empty string, not as absent.
ASSET_BASE_URL = (os.getenv("ASSET_BASE_URL") or "").strip() or (
    "https://raw.githubusercontent.com/"
    f"{os.getenv('GITHUB_REPO') or 'funpal10-byte/byrachitmishra-agent'}/"
    f"{os.getenv('GITHUB_BRANCH') or 'main'}"
)

WANTED = ("youtube", "linkedin")


def _key() -> str:
    key = (os.getenv("ZERNIO_API_KEY") or "").strip()
    if not key:
        raise SystemExit(
            "ZERNIO_API_KEY is not set.\n"
            "Get one from the Zernio dashboard (it starts with 'sk_') and add "
            "it as a repository secret named ZERNIO_API_KEY."
        )
    if not key.startswith("sk_"):
        print("[zernio] warning: key does not start with 'sk_' — check you "
              "copied the API key and not something else")
    return key


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_key()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, **kw) -> tuple[int, object]:
    url = f"{BASE}/{path.lstrip('/')}"
    r = requests.request(method, url, headers=_headers(), timeout=45, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text[:600]


# --------------------------------------------------------------------------
#  check
# --------------------------------------------------------------------------

def accounts() -> list[dict]:
    status, body = _request("GET", "/accounts")
    if status == 401 or status == 403:
        raise SystemExit(f"[zernio] key rejected ({status}). Check it is active.")
    if status != 200:
        raise SystemExit(f"[zernio] GET /accounts returned {status}: {body}")

    if isinstance(body, dict):
        for k in ("data", "accounts", "results", "items"):
            if isinstance(body.get(k), list):
                return body[k]
        return []
    return body if isinstance(body, list) else []


def _label(acc: dict) -> str:
    for k in ("name", "displayName", "username", "handle", "title"):
        if acc.get(k):
            return str(acc[k])
    return acc.get("_id") or acc.get("id") or "(unnamed)"


def check() -> int:
    rows = accounts()
    if not rows:
        print("[zernio] no accounts connected yet.\n"
              "In the Zernio dashboard, connect the accounts you want — for "
              "this project that is your YouTube channel and, if you want it, "
              "your LinkedIn PERSONAL profile (not a company page).")
        return 0

    print(f"[zernio] {len(rows)} connected account(s)\n")
    for acc in rows:
        platform = str(acc.get("platform") or "?").lower()
        acc_id = acc.get("_id") or acc.get("id") or "?"
        extra = {
            k: v for k, v in acc.items()
            if k in ("accountType", "type", "isOrganization", "organizationId",
                     "pageId", "profileType", "status", "connected")
        }
        print(f"  {platform:<12} {_label(acc):<32} id={acc_id}")
        if extra:
            print(f"               {extra}")

    found = {str(a.get('platform') or '').lower() for a in rows}
    print("\n--- verdict ---")
    for want in WANTED:
        hit = [a for a in rows if str(a.get("platform") or "").lower() == want]
        if not hit:
            print(f"{want:<10} not connected")
            continue
        print(f"{want:<10} connected ({len(hit)}) — ids: "
              + ", ".join(str(a.get('_id') or a.get('id')) for a in hit))

    if "linkedin" in found:
        print(
            "\nFor LinkedIn, read the account fields above rather than "
            "trusting the platform name. What matters is whether it is a "
            "member/personal profile or an organization page. If it is "
            "organization-only, LinkedIn stays manual."
        )
    return 0


# --------------------------------------------------------------------------
#  post
# --------------------------------------------------------------------------

def _read_post(folder: Path) -> dict:
    pj = folder / "post.json"
    if not pj.exists():
        raise SystemExit(f"[zernio] no post.json in {folder}")
    return json.loads(pj.read_text(encoding="utf-8"))


def _asset_url(path: Path) -> str:
    rel = path.resolve().relative_to(ROOT).as_posix()
    return f"{ASSET_BASE_URL}/{rel}"


def youtube_metadata(post: dict) -> dict:
    """YouTube is a SEARCH surface, unlike Instagram. The title carries the
    weight there that the hook carries in a feed, so it is written as a
    searchable phrase rather than reused verbatim."""
    hook = (post.get("hook") or "").strip().rstrip(".")
    keyword = (post.get("primary_keyword") or "").strip()
    title = hook if len(hook) <= 95 else hook[:92].rsplit(" ", 1)[0] + "…"
    if keyword and keyword.lower() not in title.lower() and len(title) + len(keyword) < 92:
        title = f"{title} | {keyword}"

    caption = (post.get("caption") or "").strip()
    src = post.get("source_url") or ""
    desc = caption
    if src:
        desc = f"{caption}\n\nThe long version: {src}"
    return {"title": title[:100], "description": desc[:4900]}


def build_payload(folder: Path, post: dict, targets: list[dict]) -> dict:
    reel = folder / "reel.mp4"
    if not reel.exists():
        raise SystemExit(
            f"[zernio] {folder.name} has no reel.mp4 — nothing to cross-post"
        )

    meta = youtube_metadata(post)
    payload: dict = {
        "content": meta["description"],
        "mediaUrls": [_asset_url(reel)],
        "platforms": targets,
        "publishNow": True,
    }
    # Platform-specific extras go alongside; unknown keys are typically
    # ignored rather than rejected, and the dry run shows exactly what is sent.
    payload["platformOptions"] = {
        "youtube": {
            "title": meta["title"],
            "privacyStatus": "public",
            "madeForKids": False,
        }
    }
    return payload


def post_folder(folder: Path, send: bool, only: str | None) -> int:
    post = _read_post(folder)
    rows = accounts()
    targets = []
    for acc in rows:
        platform = str(acc.get("platform") or "").lower()
        if platform not in WANTED:
            continue
        if only and platform != only:
            continue
        targets.append({"platform": platform,
                        "accountId": acc.get("_id") or acc.get("id")})

    if not targets:
        print("[zernio] no matching connected accounts — nothing to send")
        return 1

    payload = build_payload(folder, post, targets)

    print(f"[zernio] {folder.name} → " +
          ", ".join(t["platform"] for t in targets))
    print(json.dumps(payload, indent=2)[:1800])

    if not send:
        print("\n[zernio] DRY RUN — nothing was sent. Add --send to publish.")
        return 0

    status, body = _request("POST", "/posts", json=payload)
    if status not in (200, 201, 202):
        print(f"[zernio] POST /posts returned {status}: {body}")
        return 1
    print(f"[zernio] accepted: {json.dumps(body)[:400]}")
    return 0


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="list connected accounts and stop")
    ap.add_argument("--post", help="path to a post folder containing reel.mp4")
    ap.add_argument("--only", choices=WANTED,
                    help="send to just one platform")
    ap.add_argument("--send", action="store_true",
                    help="actually publish (without this it is a dry run)")
    args = ap.parse_args()

    if args.check or not args.post:
        return check()
    return post_folder(Path(args.post), args.send, args.only)


if __name__ == "__main__":
    sys.exit(main())
