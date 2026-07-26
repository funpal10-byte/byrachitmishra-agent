# Music beds for generated Reels

Drop audio files in this folder and the agent mixes one under every Reel it
builds. Nothing here to start with — that's deliberate, see licensing below.

## How selection works

Any `.mp3`, `.m4a`, `.aac`, `.wav` or `.ogg` file in this folder is eligible.

If a filename contains a **pillar id**, it's reserved for that pillar. So
`ai_marketing-drive.mp3` is only used on AI-in-marketing Reels. A file with no
pillar id in its name — `bed-calm.mp3` — can be used by anything.

Pillar ids, from `brand/brand.yml`: `brand_strategy`, `ai_marketing`,
`behind_the_brands`, `leadership`, `photography_travel`.

Within the eligible pool the agent rotates by position in the batch, so the
week's two Reels never share a track.

**A sensible starting set is four to six instrumental tracks**, 60–120 seconds
each. Fewer than three and the page starts sounding repetitive within a month.

## What to put here

Instrumental only. The bed sits at low volume under large on-screen text; a
vocal track fights with reading and makes the Reel harder to follow.

The agent normalises loudness and applies its own fades, so you don't need to
edit anything — raw downloads are fine.

## Licensing — read this before you add anything

**Do not put commercial music here.** Not chart music, not anything you found
on YouTube, not a track from a Reel you liked. Instagram's audio matching will
find it, and the consequence lands on your account, not on this repo.

Genuinely safe sources:

- **YouTube Audio Library** (studio.youtube.com → Audio library) — free, most
  tracks require no attribution, filterable by mood. The easiest starting point.
- **Free Music Archive** — filter to **CC0** or **CC BY**. CC0 needs nothing;
  CC BY needs credit, which you'd put in the caption.
- **Pixabay Music** — free for commercial use including social.
- **Uppbeat / Mixkit free tiers** — check the terms, some require credit.

If a licence requires attribution, add the credit line to the caption yourself
— the agent doesn't know about your licences and won't add it for you.

## Generated music instead

Set the `REEL_AI_MUSIC` repository variable to `true` and the agent will
generate an original instrumental with Google's Lyria model when this folder is
empty. Original music has no licensing question at all.

Two caveats: Lyria is a **paid-tier** Gemini feature, so it will fail silently
on a free key and the Reel will publish without music. And a fresh track each
week means your page has no consistent sonic identity — a small set of files in
this folder usually serves a personal brand better.

## What this cannot do

**Instagram's trending audio is not available through the API.** There is no
mechanism to attach a track from Instagram's library to a Reel published
programmatically — audio has to be inside the video file before upload. So an
automated Reel never gets the discovery boost that a trending sound provides.

If a particular Reel is worth that boost, publish that one by hand from the
app and let the agent handle the rest.
