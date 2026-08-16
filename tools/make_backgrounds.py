#!/usr/bin/env python3
"""Generate original background images in the brand palette.

Eight abstract textures, all built to the same brief: dark, quiet through the
middle band where the headline sits, with interest at the edges. No stock, no
licence, no attribution — these are generated from your palette in brand.yml,
so they change when your brand does.

    python tools/make_backgrounds.py            # writes into images/
    python tools/make_backgrounds.py --seed 12  # a different set

Re-run with a new seed whenever the page starts feeling repetitive.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import config  # noqa: E402

W, H = 1200, 2000  # portrait; cover-crops cleanly to both 9:16 and 4:5


def _hex(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=float)


def _grid():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    return x / W, y / H


def _blob(xs, ys, cx, cy, r, softness=1.0):
    d = np.sqrt(((xs - cx) * (W / H)) ** 2 + (ys - cy) ** 2)
    return np.clip(1.0 - (d / r) ** softness, 0, 1)


# The card templates already lay a dark scrim over these. Suppressing the
# centre too hard on top of that produces a black rectangle — legible, but
# there is then no reason to have an image at all. This dial trades legibility
# against visible texture; 0.55 is the balance point.
CALM_SCALE = 0.55


def _calm_centre(field: np.ndarray, strength: float = 0.72) -> np.ndarray:
    """Suppress detail through the middle third so text stays readable."""
    _, ys = _grid()
    band = np.exp(-(((ys - 0.5) / 0.24) ** 2))[..., None]
    return field * (1 - band * strength * CALM_SCALE)


def _finish(rgb: np.ndarray, rng, grain: float = 5.0) -> Image.Image:
    """Grain, a gentle vignette, and a hard clamp to keep everything dark."""
    noise = rng.normal(0, grain, rgb.shape[:2])[..., None]
    rgb = rgb + noise

    xs, ys = _grid()
    vig = 1.0 - 0.34 * np.clip(((xs - 0.5) ** 2 * 1.6 + (ys - 0.5) ** 2) * 2.2, 0, 1)
    rgb = rgb * vig[..., None]

    rgb = np.clip(rgb, 0, 224)  # never bright — the scrim would turn it grey
    return Image.fromarray(rgb.astype(np.uint8))


# --------------------------------------------------------------------------
#  The eight textures
# --------------------------------------------------------------------------

def mesh(rng, base, accent, second):
    xs, ys = _grid()
    field = np.zeros((H, W, 3))
    for _ in range(5):
        cx, cy = rng.uniform(-0.2, 1.2), rng.uniform(-0.1, 1.1)
        col = accent if rng.random() < 0.55 else second
        field += _blob(xs, ys, cx, cy, rng.uniform(0.45, 0.95), 1.5)[..., None] * col * 0.55
    return base + _calm_centre(field, 0.55)


def grid_lines(rng, base, accent, second):
    xs, ys = _grid()
    step = rng.integers(34, 52)
    gx = ((np.arange(W) % step) < 1.4).astype(np.float32)[None, :].repeat(H, 0)
    gy = ((np.arange(H) % step) < 1.4).astype(np.float32)[:, None].repeat(W, 1)
    lines = np.clip(gx + gy, 0, 1)
    glow = _blob(xs, ys, rng.uniform(0.1, 0.9), rng.uniform(0.05, 0.3), 0.8, 1.4)
    field = lines[..., None] * accent * 0.30 * (0.25 + glow[..., None])
    field += glow[..., None] * second * 0.32
    return base + _calm_centre(field, 0.62)


def contours(rng, base, accent, second):
    xs, ys = _grid()
    f = np.zeros((H, W))
    for _ in range(4):
        cx, cy = rng.uniform(0, 1), rng.uniform(0, 1)
        f += np.sqrt(((xs - cx) * 1.4) ** 2 + (ys - cy) ** 2) * rng.uniform(6, 11)
    bands = np.abs(np.sin(f * np.pi)) ** 22
    field = bands[..., None] * accent * 0.75
    field += _blob(xs, ys, 0.5, 0.9, 1.0, 1.2)[..., None] * second * 0.28
    return base + _calm_centre(field, 0.68)


def streaks(rng, base, accent, second):
    xs, ys = _grid()
    field = np.zeros((H, W, 3))
    ang = rng.uniform(0.25, 0.6)
    for _ in range(9):
        off = rng.uniform(-0.7, 1.4)
        band = np.exp(-(((xs * ang + ys - off) / rng.uniform(0.012, 0.045)) ** 2))
        col = accent if rng.random() < 0.5 else second
        field += band[..., None] * col * rng.uniform(0.18, 0.42)
    return base + _calm_centre(field, 0.60)


def particles(rng, base, accent, second):
    xs, ys = _grid()
    field = np.zeros((H, W, 3))
    for _ in range(150):
        cx, cy = rng.uniform(0, 1), rng.uniform(0, 1)
        r = rng.uniform(0.004, 0.05)
        col = accent if rng.random() < 0.5 else second
        field += _blob(xs, ys, cx, cy, r, 2.0)[..., None] * col * rng.uniform(0.25, 0.9)
    field += _blob(xs, ys, rng.uniform(0.2, 0.8), 0.15, 0.7, 1.5)[..., None] * second * 0.25
    return base + _calm_centre(field, 0.66)


def arcs(rng, base, accent, second):
    xs, ys = _grid()
    cx, cy = rng.uniform(0.1, 0.9), rng.uniform(-0.1, 0.25)
    d = np.sqrt(((xs - cx) * 1.5) ** 2 + (ys - cy) ** 2)
    rings = np.abs(np.sin(d * rng.uniform(16, 26))) ** 18
    field = rings[..., None] * accent * 0.62
    field += np.clip(1 - d, 0, 1)[..., None] * second * 0.34
    return base + _calm_centre(field, 0.70)


def clouds(rng, base, accent, second):
    small = rng.random((H // 24, W // 24))
    img = Image.fromarray((small * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(38))
    f = np.asarray(img, dtype=float) / 255.0
    f = (f - f.min()) / (np.ptp(f) + 1e-6)  # ndarray.ptp was removed in numpy 2
    field = (f ** 2.2)[..., None] * accent * 0.85
    field += ((1 - f) ** 3)[..., None] * second * 0.40
    return base + _calm_centre(field, 0.58)


def halftone(rng, base, accent, second):
    xs, ys = _grid()
    step = 26
    yy, xx = np.mgrid[0:H, 0:W]
    phase = ((xx % step) - step / 2) ** 2 + ((yy % step) - step / 2) ** 2
    grad = np.clip((ys - 0.15) * 1.5, 0, 1)
    dots = (phase < (grad * (step * 0.32) ** 2)).astype(np.float32)
    field = dots[..., None] * accent * 0.42
    field += _blob(xs, ys, 0.5, 1.05, 0.9, 1.3)[..., None] * second * 0.30
    return base + _calm_centre(field, 0.64)


TEXTURES = [
    ("brand_strategy-mesh", mesh),
    ("brand_strategy-contours", contours),
    ("ai_marketing-grid", grid_lines),
    ("ai_marketing-particles", particles),
    ("behind_the_brands-streaks", streaks),
    ("leadership-arcs", arcs),
    ("bg-clouds", clouds),
    ("bg-halftone", halftone),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(config.ROOT / "images"))
    args = ap.parse_args()

    brand = config.load_brand()
    d = brand.design
    base = _hex(d.get("bg_alt", "#14161a"))[None, None, :] * np.ones((H, W, 1))
    accent = _hex(d.get("accent", "#7c3aed"))
    second = _hex("#1e3a8a")  # midnight blue, to stop it reading as one-note

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for i, (name, fn) in enumerate(TEXTURES):
        rng = np.random.default_rng(args.seed * 1000 + i)
        img = _finish(fn(rng, base.copy(), accent, second), rng)
        path = out / f"{name}.jpg"
        img.save(path, quality=82, optimize=True, progressive=True)
        print(f"{path.name:38s} {path.stat().st_size / 1024:6.0f} KB")

    print(f"\n{len(TEXTURES)} backgrounds written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
