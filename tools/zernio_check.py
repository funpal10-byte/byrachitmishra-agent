"""
Answer the one question that decides whether Zernio is useful to us:

    can it post to a PERSONAL LinkedIn profile, or only to company pages?

Their public docs list LinkedIn as a supported platform but do not make that
distinction, and it is the whole ballgame — you do not have a company page and
would not post from one if you did. So we verify against the live account
rather than trusting the marketing copy.

    export ZERNIO_API_KEY=sk_...
    python tools/zernio_check.py

Run this BEFORE any code is written against Zernio. If the answer is "company
pages only", we build nothing and keep posting to LinkedIn by hand.
"""

from __future__ import annotations

import json
import os
import sys

import requests

BASE = os.getenv("ZERNIO_API_BASE") or "https://api.zernio.com"
CANDIDATE_PATHS = [
    "/v1/accounts",
    "/v1/social-accounts",
    "/v1/channels",
    "/v1/profiles",
    "/accounts",
]


def main() -> int:
    key = (os.getenv("ZERNIO_API_KEY") or "").strip()
    if not key:
        print("ZERNIO_API_KEY is not set.\n"
              "Get one from the Zernio dashboard (it starts with 'sk_') and:\n"
              "  export ZERNIO_API_KEY=sk_...")
        return 2

    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}

    payload = None
    used = None
    for path in CANDIDATE_PATHS:
        try:
            r = requests.get(BASE + path, headers=headers, timeout=30)
        except requests.RequestException as exc:
            print(f"  {path}: network error {exc}")
            continue
        print(f"  {path}: HTTP {r.status_code}")
        if r.status_code == 200:
            used = path
            try:
                payload = r.json()
            except ValueError:
                print("    (200 but not JSON — check the base URL)")
            break
        if r.status_code in (401, 403):
            print("    key rejected — check it is active and has API scope")
            return 1

    if payload is None:
        print("\nNo account-listing endpoint responded. The API surface has "
              "probably moved.\nCheck docs.zernio.com and add the correct path "
              "to CANDIDATE_PATHS.")
        return 1

    print(f"\nUsing {used}\n")
    print(json.dumps(payload, indent=2)[:4000])

    blob = json.dumps(payload).lower()
    linkedin = "linkedin" in blob
    personal_hint = any(w in blob for w in
                        ("personal", "member", "profile", "individual"))
    company_hint = any(w in blob for w in
                       ("organization", "organisation", "company_page", "page"))

    print("\n--- verdict ---")
    if not linkedin:
        print("No LinkedIn account is connected yet. Connect one in the Zernio "
              "dashboard — choosing a PERSONAL profile, not a company page — "
              "then run this again.")
        return 0
    print(f"LinkedIn present: yes")
    print(f"Looks like a personal/member profile: {personal_hint}")
    print(f"Mentions company page/organisation: {company_hint}")
    print(
        "\nRead the JSON above rather than trusting these flags. What you are\n"
        "looking for is an account whose type is a member/personal profile.\n"
        "If it is organisation-only, stop here — Zernio does not solve the\n"
        "problem we wanted it for, and manual posting remains the plan."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
