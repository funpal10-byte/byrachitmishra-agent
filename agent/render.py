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


def launch_browser(pw):
    channel = os.getenv("RENDER_BROWSER_CHANNEL") or None
    return pw.chromium.launch(channel=channel, args=["--force-color-profile=srgb"])


# Photos behind carousel hook slides are opt-in: the typographic look is
# deliberate, and a grid of photo covers is a different design decision.
PHOTO_HOOK = (os.getenv("SLIDE_PHOTO_HOOK") or "false").lower() == "true"


def render_carousel(post: dict, brand, out_dir: Path, index: int = 0) -> list[Path]:
    """Write one JPEG per slide. Returns the paths in order."""
    slides = post.get("slides") or []
    if not slides:
        return []

    hook_bg = assets.pick_image(post.get("pillar", ""), index) if PHOTO_HOOK else None

    # Ground per slide, and therefore which mark reads on it. The hook slide
    # moved from dark to light (see templates/slide.html), so it now takes the
    # dark mark like the body slides; only the closing slide is inverted. A
    # photo hook is the exception — it keeps its dark scrim, so it keeps the
    # light mark.
    show_logo = brand.design.get("show_logo", True)
    marks = {
        k: (assets.data_uri(assets.logo(k)) if show_logo else "")
        for k in ("light", "dark", "white")
    }

    d = brand.design
    tpl = _env().get_template("slide.html")
    pillar_name = brand.pillars.get(post.get("pillar", ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    with sync_playwright() as pw:
        browser = launch_browser(pw)
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
                visual=slide.get("visual"),
                pillar=pillar_name.name if pillar_name else "",
                index=i + 1,
                total=len(slides),
                bg_image=(assets.data_uri(hook_bg) if i == 0 else ""),
                logo=marks[
                    "light" if (i == 0 and hook_bg) else
                    {"cta": "white"}.get(_slide_kind(i, len(slides)), "dark")
                ],
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
    """Render the Reel's grid cover, deliberately distinct from beat one.

    A profile visitor sees this without autoplay. Reusing the first frame
    spends the same sentence twice, so the generator supplies a second,
    compact tension line plus an evidence signal for a separate cover design.
    """
    cover = post.get("reel_cover") or {}
    if not isinstance(cover, dict) or not cover.get("headline"):
        return None

    d = brand.design
    tpl = _env().get_template("editorial_cover.html")
    pillar_name = brand.pillars.get(post.get("pillar", ""))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "reel-cover.jpg"

    with sync_playwright() as pw:
        browser = launch_browser(pw)
        # The content is centre-locked: a Reel cover is 9:16, but the profile
        # grid crops it to 4:5 (and sometimes closer to square).
        page = browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        html = tpl.render(
            pillar=pillar_name.name if pillar_name else "",
            headline=cover.get("headline", ""),
            signal=cover.get("signal", ""),
            layout=cover.get("layout", "signal"),
            visual=cover.get("visual"),
            logo=(assets.data_uri(assets.logo("dark")) if d.get("show_logo", True) else ""),
            d=d,
        )
        page.set_content(html, wait_until="networkidle")
        _await_fonts(page)
        if page.evaluate("""() => {
            const text = document.querySelector('.signal').getBoundingClientRect();
            const footer = document.querySelector('.brand').getBoundingClientRect();
            return text.bottom + 20 > footer.top;
        }"""):
            browser.close()
            raise ValueError("Cover content overlaps the brand footer; shorten the copy or visual")
        page.screenshot(path=str(path), type="jpeg", quality=92)
        browser.close()

    return path
