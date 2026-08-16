# Background images

Drop photos in this folder and the agent uses them behind generated Reels —
and, if you switch it on, behind carousel hook slides.

**Eight originals are already here**, generated in your brand palette by
`tools/make_backgrounds.py`. They cost nothing, carry no licence, and change
when your palette does. To get a different set:

```
python tools/make_backgrounds.py --seed 42
```

Add your own photos alongside them whenever you like — the two mix freely.

This is the better option on a free Gemini key, because Gemini's image
generation is a paid-tier feature. A folder of images you chose also gives the
page a consistent look, which an AI generating a fresh image every week never
will.

## How selection works

Any `.jpg`, `.jpeg`, `.png` or `.webp` file here is eligible.

If a filename contains a **pillar id**, it's reserved for that pillar:

```
ai_marketing-circuits.jpg      → only AI in marketing posts
leadership-desk.jpg            → only leadership posts
bg-abstract-01.jpg             → any post
```

Files with no pillar id are general-purpose. Selection rotates by position in
the batch, so the week's posts don't all share one image.

Pillar ids: `brand_strategy`, `ai_marketing`, `behind_the_brands`,
`leadership`, `photography_travel`.

## What works, and what doesn't

The image sits behind large white text under a dark scrim, so it is texture
rather than subject. That means:

**Good** — abstract textures, architecture, out-of-focus city light, gradients,
paper and concrete surfaces, dark moody landscapes, anything with a calm centre.

**Bad** — busy detail, high contrast across the middle of the frame, anything
with text or logos in it, and faces. A face behind your headline reads as a
stock-photo advert, and it competes with the words.

**Dark or mid-tone images work best.** The scrim darkens whatever you give it,
so a bright image ends up muddy grey rather than bright.

## Sizing

**Reels** use the image at 1080×1920 — portrait suits them best, but landscape
works since it's cropped to centre.

**Carousel hooks** use 1080×1350.

Anything 1500px or larger on the short edge is plenty. Keep each file under
about **1MB** — git remembers every version of every file forever, so a folder
of 8MB photos bloats the repository permanently. Resize before committing if
your downloads are large.

## Where to get them

**Pixabay** (pixabay.com) — free for commercial use, no attribution required.
The same licence as the music, so nothing new to think about.

**Unsplash** and **Pexels** also work and have better photography. Both allow
commercial use without attribution, though crediting the photographer in your
caption is a decent thing to do when an image is doing real work.

**Your own photography.** You have a travel-and-photography pillar — your own
frames as backgrounds would tie the whole page together in a way stock never
will, and it's free.

Don't use images you found on Google, Pinterest, or someone else's Instagram.

## Turning on carousel hook photos

Off by default, because the typographic covers are a deliberate look and a grid
of photo covers is a different design decision. To try it, add a repository
variable `SLIDE_PHOTO_HOOK` set to `true`, then run **Draft the week** and
compare. Only the first slide changes; the rest stay clean and readable.
