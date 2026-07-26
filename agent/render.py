"""Render carousel slides (and Reel cover cards) to JPEG.

Instagram's publishing API only accepts JPEG for images, so everything is
written as JPEG regardless of format. Uses headless Chromium via Playwright,
which is already installed in the GitHub Actions runner image.
"""

from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from . import assets, config


def _await_fonts(page) -> None:
    """Inter is loaded from Google Fonts. Without this the screenshot can fire
    mid-swap and you get a serif fallback baked into the JPEG."""
    try:
        page.wait_for_function("document.fonts && document.fonts.status === 'loaded'", timeout=8000)
    except Exception:
        page.wait_for_timeout(1200)


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(config.TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _slide_kind(i: int, total: int) -> str:
    if i == 0:
        return "hook"
    if i == total - 1:
        return "cta"
    return "body"


# Photos behind carousel hook slides are opt-in: the typographic look is
# deliberate, and a grid of photo covers is a different design decision.
PHOTO_HOOK = (os.getenv("SLIDE_PHOTO_HOOK") or "false").lower() == "true"


def render_carousel(post: dict, brand, out_dir: Path, index: int = 0) -> list[Path]:
    """Write one JPEG per slide. Returns the paths in order."""
    slides = post.get("slides") or []
    if not slides:
        return []

    hook_bg = assets.pick_image(post.get("pillar", ""), index) if PHOTO_HOOK else None

    d = brand.design
    tpl = _env().get_template("slide.html")
    pillar_name = brand.pillars.get(post.get("pillar", ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--force-color-profile=srgb"])
        page = browser.new_page(
            viewport={"width": d["slide_width"], "height": d["slide_height"]},
            device_scale_factor=1,
        )
        for i, slide in enumerate(slides):
            html = tpl.render(
                kind=_slide_kind(i, len(slides)),
                kicker=slide.get("kicker", ""),
                headline=slide.get("headline", ""),
                body=slide.get("body", ""),
                pillar=pillar_name.name if pillar_name else "",
                index=i + 1,
                total=len(slides),
                bg_image=(hook_bg.resolve().as_uri() if hook_bg and i == 0 else ""),
                d=d,
                W=d["slide_width"],
                H=d["slide_height"],
            )
            page.set_content(html, wait_until="networkidle")
            _await_fonts(page)
            path = out_dir / f"slide-{i + 1:02d}.jpg"
            page.screenshot(path=str(path), type="jpeg", quality=92)
            written.append(path)
        browser.close()

    return written


def render_reel_cover(post: dict, brand, out_dir: Path) -> Path | None:
    """A single title card you can drop on the front of the Reel, or use as
    the cover frame. Reels themselves still need you to shoot them."""
    beats = post.get("reel_script") or []
    if not beats:
        return None

    d = brand.design
    tpl = _env().get_template("slide.html")
    pillar_name = brand.pillars.get(post.get("pillar", ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "reel-cover.jpg"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--force-color-profile=srgb"])
        # 9:16 for a Reel cover rather than the 4:5 carousel ratio.
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        html = tpl.render(
            kind="hook",
            headline=beats[0].get("onscreen", post.get("hook", "")),
            body="",
            kicker="",
            pillar=pillar_name.name if pillar_name else "",
            index=1,
            total=1,
            d=d,
            W=1080,
            H=1920,
        )
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=str(path), type="jpeg", quality=92)
        browser.close()

    return path
