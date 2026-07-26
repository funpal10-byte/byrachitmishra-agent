#!/usr/bin/env python3
"""One-time helper: turn the code Meta hands you into a 60-day token.

You only run this once, on your own laptop, when you first set up publishing.
After that the refresh-token workflow keeps it alive automatically.

    python tools/get_token.py --app-id 123 --app-secret abc \
        --redirect-uri https://localhost/ --code AQB...

Where to get the code: in your Meta app dashboard, open
  Instagram → API setup with Instagram login → Generate token
or complete the OAuth flow manually with:

  https://www.instagram.com/oauth/authorize
    ?client_id=<APP_ID>
    &redirect_uri=<REDIRECT_URI>
    &scope=instagram_business_basic,instagram_business_content_publish
    &response_type=code

Instagram appends #_ to the code in the redirect URL. Strip it.
"""

from __future__ import annotations

import argparse
import json
import sys

import requests


def short_lived(app_id: str, app_secret: str, redirect_uri: str, code: str) -> dict:
    r = requests.post(
        "https://api.instagram.com/oauth/access_token",
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code.rstrip("#_"),
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def long_lived(app_secret: str, token: str) -> dict:
    r = requests.get(
        "https://graph.instagram.com/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": token,
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def whoami(token: str) -> dict:
    r = requests.get(
        "https://graph.instagram.com/v25.0/me",
        params={"fields": "id,username,account_type", "access_token": token},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--app-secret", required=True)
    ap.add_argument("--redirect-uri", required=True)
    ap.add_argument("--code", required=True)
    args = ap.parse_args()

    short = short_lived(args.app_id, args.app_secret, args.redirect_uri, args.code)
    print("short-lived token acquired", file=sys.stderr)

    long = long_lived(args.app_secret, short["access_token"])
    me = whoami(long["access_token"])

    days = int(long.get("expires_in", 0)) // 86400
    print(json.dumps({**me, "expires_in_days": days}, indent=2), file=sys.stderr)
    print("\nAdd these to your repository secrets:\n", file=sys.stderr)
    print(f"IG_USER_ID      = {me['id']}")
    print(f"IG_ACCESS_TOKEN = {long['access_token']}")

    if me.get("account_type") not in {"BUSINESS", "MEDIA_CREATOR", "CREATOR"}:
        print(
            f"\n⚠️  account_type is {me.get('account_type')} — publishing needs a "
            "professional (Creator or Business) account.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
