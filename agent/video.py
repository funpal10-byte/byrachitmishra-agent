"""Turn a Reel script into a publishable MP4, with no camera involved.

The result is a kinetic-typography Reel: the script's on-screen text, one beat
at a time, over an AI-generated background, with a slow Ken Burns push so the
frame is never static. Hard cuts on the beat rather than crossfades — that
reads better for this format and is far more reliable to assemble.

Deliberately not a talking head. If you film one yourself, drop your file into
the post folder as `reel.mp4` and it takes precedence over anything generated
here — see `should_generate()`.

Requires ffmpeg, which is preinstalled on GitHub's Ubuntu runners.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from . import assets, config

W, H, FPS = 1080, 1920, 30
MIN_BEAT, MAX_BEAT = 2.2, 7.0
TARGET_MAX_SECONDS = 88.0  # Reels under 90s reach cold audiences better

# One background per Reel rather than one per beat. Cheaper against a free
# quota, and it makes the video look like a single piece rather than eight.
# `or "true"` rather than a getenv default: GitHub passes unset repository
# variables through as an empty string, not as absent.
AI_BACKGROUNDS = (os.getenv("REEL_AI_BACKGROUNDS") or "true").lower() != "false"
IMAGE_MODEL_PREFERENCE = (
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",
    "gemini-3-pro-image",
)


class VideoError(RuntimeError):
    pass


# --------------------------------------------------------------------------
#  Timing
# --------------------------------------------------------------------------

def _seconds(timecode: str) -> float | None:
    """Parse '0:08-0:16' into a duration in seconds."""
    parts = re.findall(r"(\d+):(\d{1,2})", timecode or "")
    if len(parts) != 2:
        return None
    start = int(parts[0][0]) * 60 + int(parts[0][1])
    end = int(parts[1][0]) * 60 + int(parts[1][1])
    return end - start if end > start else None


def beat_durations(beats: list[dict]) -> list[float]:
    """Prefer the script's own timings, fall back to reading speed."""
    out: list[float] = []
    for b in beats:
        d = _seconds(b.get("timecode", ""))
        if d is None:
            # ~13 characters a second is a comfortable read for on-screen text.
            words = len((b.get("voiceover") or b.get("onscreen") or "").split())
            d = max(MIN_BEAT, min(MAX_BEAT, 1.6 + words / 2.6))
        out.append(max(MIN_BEAT, min(MAX_BEAT, float(d))))

    total = sum(out)
    if total > TARGET_MAX_SECONDS:
        scale = TARGET_MAX_SECONDS / total
        out = [max(MIN_BEAT, d * scale) for d in out]
    return out


# --------------------------------------------------------------------------
#  Background
# --------------------------------------------------------------------------

def _background_prompt(post: dict, brand) -> str:
    pillar = brand.pillars.get(post.get("pillar", ""))
    topic = post.get("primary_keyword") or (pillar.name if pillar else "marketing")
    return (
        "Abstract editorial background image for a premium business social video. "
        f"Theme: {topic}. "
        "Dark near-black base with deep violet and midnight blue light, soft "
        "gradients, subtle geometric structure, gentle film grain. Cinematic, "
        "restrained, expensive-looking. Vertical 9:16 composition with the centre "
        "kept visually calm and uncluttered so large white text can sit on top. "
        "Absolutely no text, no letters, no numbers, no logos, no people, no faces."
    )


def choose_background(post: dict, brand, out_dir: Path, index: int = 0) -> Path | None:
    """Background for the Reel, in order of preference.

    1. A photo you put in images/ — free, consistent, and the only option that
       works on a free Gemini key.
    2. A Gemini-generated image, if image generation is available to you.
    3. Nothing, and the template draws a designed gradient instead.
    """
    local = assets.pick_image(post.get("pillar", ""), index)
    if local:
        print(f"[video] background: {local.name}")
        return local
    return generate_background(post, brand, out_dir)


def generate_background(post: dict, brand, out_dir: Path) -> Path | None:
    """One AI background per Reel. Returns None on any failure — the template
    falls back to a designed gradient, which looks intentional rather than
    broken.

    Note that Gemini image generation is a paid-tier feature, so on a free key
    this always returns None. That is expected, not a fault.
    """
    if not AI_BACKGROUNDS or config.provider() != "gemini" or not config.GOOGLE_API_KEY:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GOOGLE_API_KEY)

        available = set()
        try:
            for m in client.models.list():
                available.add((getattr(m, "name", "") or "").removeprefix("models/"))
        except Exception:
            pass

        models = [m for m in IMAGE_MODEL_PREFERENCE if not available or m in available]
        if not models:
            models = sorted(
                (n for n in available if "image" in n and "preview" not in n), reverse=True
            )
        if not models:
            print("[video] no Gemini image model available, using designed background")
            return None

        prompt = _background_prompt(post, brand)
        for model in models[:2]:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
                )
                for cand in getattr(resp, "candidates", None) or []:
                    for part in getattr(getattr(cand, "content", None), "parts", None) or []:
                        blob = getattr(part, "inline_data", None)
                        if blob and getattr(blob, "data", None):
                            path = out_dir / "reel-bg.png"
                            path.write_bytes(blob.data)
                            print(f"[video] background generated with {model}")
                            return path
            except Exception as exc:
                print(f"[video] {model} background failed: {str(exc)[:140]}")
                continue
    except Exception as exc:
        print(f"[video] background generation unavailable: {str(exc)[:140]}")

    return None


# --------------------------------------------------------------------------
#  Music
# --------------------------------------------------------------------------
#
#  Worth being clear about what is and is not possible here.
#
#  Instagram's trending audio CANNOT be attached to a Reel published through
#  the API. Not a limitation of this code — the API has no mechanism for it.
#  Audio has to be baked into the file before upload. So an automated Reel
#  never gets the discovery lift that trending sounds provide. If a particular
#  Reel needs that lift, post that one by hand from the app.
#
#  What is possible is an original or properly-licensed bed mixed into the
#  video, which is what happens below.

# Lyria is Google's music model. It writes original instrumental music, so
# there is no licensing question at all — but it is a paid-tier feature, so
# this stays off unless you ask for it.
AI_MUSIC = (os.getenv("REEL_AI_MUSIC") or "false").lower() == "true"
MUSIC_MODELS = ("lyria-3-clip-preview", "lyria-3-pro-preview")


def _mood_for(post: dict, brand) -> str:
    moods = (brand.raw.get("music") or {}).get("moods") or {}
    return moods.get(post.get("pillar", ""), "calm, minimal, modern")


def generate_music(post: dict, brand, out_dir: Path, seconds: float) -> Path | None:
    """Original instrumental via Lyria. Returns None if unavailable."""
    if not AI_MUSIC or config.provider() != "gemini" or not config.GOOGLE_API_KEY:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=config.GOOGLE_API_KEY)
        prompt = (
            f"An instrumental background bed for a short business video about "
            f"{post.get('primary_keyword') or 'brand strategy'}. "
            f"Mood: {_mood_for(post, brand)}. "
            "Restrained, modern, no vocals, no lyrics, steady pulse, nothing "
            "attention-grabbing — it sits underneath spoken-word-style text. "
            f"About {int(max(30, seconds))} seconds."
        )
        for model in MUSIC_MODELS:
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                for part in getattr(resp, "parts", None) or []:
                    blob = getattr(part, "inline_data", None)
                    if blob and getattr(blob, "data", None):
                        path = out_dir / "bed.mp3"
                        path.write_bytes(blob.data)
                        print(f"[video] music generated with {model}")
                        return path
            except Exception as exc:
                print(f"[video] {model} unavailable: {str(exc)[:130]}")
    except Exception as exc:
        print(f"[video] music generation unavailable: {str(exc)[:130]}")
    return None


def pick_music(post: dict, brand, index: int = 0) -> Path | None:
    """A track from the repo's music/ folder, chosen by pillar."""
    return assets.pick_music(post.get("pillar", ""), index)


# --------------------------------------------------------------------------
#  Cards
# --------------------------------------------------------------------------

def _fit_size(text: str) -> int:
    """Shrink the type as the line gets longer so nothing ever overflows."""
    n = len(text or "")
    if n <= 24:
        return 108
    if n <= 40:
        return 92
    if n <= 60:
        return 78
    return 66


def render_cards(post: dict, brand, out_dir: Path, bg: Path | None) -> list[Path]:
    beats = post.get("reel_script") or []
    if not beats:
        return []

    env = Environment(
        loader=FileSystemLoader(str(config.TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("reel_card.html")
    pillar = brand.pillars.get(post.get("pillar", ""))
    logo_uri = (
        assets.data_uri(assets.logo("light")) if brand.design.get("show_logo", True) else ""
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    cards: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--force-color-profile=srgb"])
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)

        for i, beat in enumerate(beats):
            text = (beat.get("onscreen") or "").strip()
            html = tpl.render(
                text=text,
                size=_fit_size(text),
                kicker=(pillar.name if pillar and i == 0 else ""),
                bg_image=assets.data_uri(bg),
                logo=logo_uri,
                pct=round((i + 1) / len(beats) * 100),
                d=brand.design,
            )
            page.set_content(html, wait_until="networkidle")
            try:
                page.wait_for_function(
                    "document.fonts && document.fonts.status === 'loaded'", timeout=6000
                )
            except Exception:
                page.wait_for_timeout(800)

            path = out_dir / f"card-{i + 1:02d}.png"
            page.screenshot(path=str(path), type="png")
            cards.append(path)

        browser.close()

    return cards


# --------------------------------------------------------------------------
#  Assembly
# --------------------------------------------------------------------------

def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-12:])
        raise VideoError(f"ffmpeg failed:\n{tail}")


def assemble(
    cards: list[Path],
    durations: list[float],
    out_file: Path,
    music: Path | None = None,
) -> Path:
    """Slow pan on each card, hard cuts between them, music bed underneath.

    Instagram wants an audio stream even when there is nothing to hear, so a
    silent one is added when no music is available rather than shipping a
    video-only file.
    """
    if not shutil.which("ffmpeg"):
        raise VideoError("ffmpeg is not installed on this machine")

    total = sum(durations)

    cmd: list[str] = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for card, dur in zip(cards, durations):
        cmd += ["-loop", "1", "-t", f"{dur:.3f}", "-r", str(FPS), "-i", str(card)]

    if music:
        # Loop the bed in case the track is shorter than the Reel.
        cmd += ["-stream_loop", "-1", "-i", str(music)]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]

    # Motion is a slow pan across a slightly oversized frame. The obvious tool
    # is zoompan, but it rescales the source on every single frame and takes
    # roughly 11x realtime — minutes per Reel. scale-then-crop gives the same
    # drift for about a fifteenth of the cost.
    filters: list[str] = []
    for i, dur in enumerate(durations):
        d = f"{dur:.3f}"
        x, y = [
            (f"(iw-ow)*(t/{d})", "(ih-oh)*0.5"),
            (f"(iw-ow)*(1-t/{d})", "(ih-oh)*0.5"),
            ("(iw-ow)*0.5", f"(ih-oh)*(t/{d})"),
            ("(iw-ow)*0.5", f"(ih-oh)*(1-t/{d})"),
        ][i % 4]
        filters.append(
            f"[{i}:v]scale={int(W * 1.1)}:{int(H * 1.1)},"
            f"crop={W}:{H}:'{x}':'{y}',setsar=1[v{i}]"
        )

    joined = "".join(f"[v{i}]" for i in range(len(cards)))
    filters.append(f"{joined}concat=n={len(cards)}:v=1:a=0[cat]")
    # A short fade at each end stops the Reel starting and ending abruptly.
    filters.append(f"[cat]fade=t=in:st=0:d=0.35,fade=t=out:st={max(0, total - 0.45):.3f}:d=0.45[outv]")

    audio_idx = len(cards)
    if music:
        filters.append(
            f"[{audio_idx}:a]atrim=0:{total:.3f},asetpts=N/SR/TB,"
            # Normalise so a quiet track and a loud one land in the same place.
            # -15 LUFS rather than a timid background level: there is no
            # voiceover here, so the music is the entire audio experience and
            # should sit where social platforms expect it.
            f"aformat=channel_layouts=stereo,loudnorm=I=-15:TP=-1.5:LRA=11,"
            f"afade=t=in:st=0:d=1.0,afade=t=out:st={max(0, total - 2.0):.3f}:d=2.0[aout]"
        )
        audio_map = "[aout]"
    else:
        audio_map = f"{audio_idx}:a"

    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[outv]",
        "-map", audio_map,
        "-c:v", "libx264", "-profile:v", "high", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", "-r", str(FPS), "-g", str(FPS * 2),
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart", "-shortest",
        str(out_file),
    ]

    _run(cmd)
    return out_file


# --------------------------------------------------------------------------

def should_generate(folder: Path) -> bool:
    """Never overwrite a Reel you filmed yourself."""
    existing = folder / "reel.mp4"
    if not existing.exists():
        return True
    marker = folder / ".generated-reel"
    if marker.exists():
        return True  # ours, safe to replace
    print(f"[video] {folder.name}: reel.mp4 was supplied by hand, leaving it alone")
    return False


def build_reel(post: dict, brand, folder: Path, index: int = 0) -> Path | None:
    """Full pipeline. Returns the MP4 path, or None if it could not be built."""
    beats = post.get("reel_script") or []
    if not beats:
        return None
    if not should_generate(folder):
        return folder / "reel.mp4"

    work = folder / ".frames"
    work.mkdir(parents=True, exist_ok=True)
    try:
        bg = choose_background(post, brand, work, index)
        cards = render_cards(post, brand, work, bg)
        if not cards:
            return None
        durations = beat_durations(beats)[: len(cards)]

        # A track you supplied beats one Lyria generates, because a consistent
        # bed across Reels is worth more than novelty in each one.
        music = pick_music(post, brand, index) or generate_music(
            post, brand, work, sum(durations)
        )
        if music:
            print(f"[video] music: {music.name}")
        else:
            print("[video] no music available — publishing silent")

        out = folder / "reel.mp4"
        assemble(cards, durations, out, music)
        (folder / ".generated-reel").write_text("generated by agent/video.py\n", encoding="utf-8")
        size_mb = out.stat().st_size / 1_000_000
        print(f"[video] {folder.name}: {sum(durations):.1f}s, {size_mb:.1f} MB")
        return out
    finally:
        # The intermediate PNGs are large and add nothing to the repo.
        shutil.rmtree(work, ignore_errors=True)
