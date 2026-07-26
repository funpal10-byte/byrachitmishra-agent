"""Picking files out of the images/ and music/ folders.

Shared by the slide renderer and the video builder so both follow the same
rule: a filename containing a pillar id belongs to that pillar, anything else
is general-purpose, and selection rotates by position in the batch so two
posts in the same week never reuse the same asset.
"""

from __future__ import annotations

from pathlib import Path

from . import config

IMAGE_DIR = config.ROOT / "images"
MUSIC_DIR = config.ROOT / "music"

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".wav", ".ogg")


def _candidates(directory: Path, exts: tuple[str, ...]) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in exts and not p.name.startswith(".")
    )


def pick(directory: Path, exts: tuple[str, ...], pillar: str, index: int = 0) -> Path | None:
    """Best match for a pillar, or None if the folder is empty.

    Files whose name contains the pillar id are reserved for that pillar. If
    none exist, anything that isn't reserved for a *different* pillar is fair
    game — so a photo named `leadership-desk.jpg` never turns up on an AI post,
    but `bg-abstract-01.jpg` can turn up anywhere.
    """
    files = _candidates(directory, exts)
    if not files:
        return None

    known = {p.id for p in config.load_brand().pillars.values()}

    reserved = [f for f in files if pillar and pillar in f.stem.lower()]
    if reserved:
        return reserved[index % len(reserved)]

    general = [f for f in files if not any(k in f.stem.lower() for k in known)]
    pool = general or files
    return pool[index % len(pool)]


def pick_image(pillar: str, index: int = 0) -> Path | None:
    return pick(IMAGE_DIR, IMAGE_EXTS, pillar, index)


def pick_music(pillar: str, index: int = 0) -> Path | None:
    return pick(MUSIC_DIR, AUDIO_EXTS, pillar, index)
