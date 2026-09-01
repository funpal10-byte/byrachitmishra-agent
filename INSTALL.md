# What to put where, and the two lines to edit

Everything here is **additive**. Nothing you already have gets overwritten,
except one small edit to `agent/generate.py` described at the end — and the
system still runs correctly if you skip it.

---

## 1. Copy the files in

Drag these into your local repo folder, keeping the structure:

```
agent/llm_adapter.py            new
agent/repurpose.py              new
agent/metrics.py                new
agent/theme.py                  new
agent/from_blog.py              new
.github/workflows/from_blog.yml new
prompts/hooks.md                new
prompts/system-caption-patch.md new   (instructions, not loaded at runtime)
tools/zernio_check.py           new
ideas.md                        new   (repo root)
COLOUR-NOTE.md                  new   (repo root, reference only)
.github/workflows/repurpose.yml new
.github/workflows/metrics.yml   new
brand/brand.yml                 REPLACES your current one
```

`brand.yml` is the one replacement, with two changes from the version you
have: the company-naming rule now permits publicly verifiable facts about
companies you have no relationship with, and the `design:` block carries the
oxide palette plus the new `slide_roles`.

**The logo is untouched.** The three colourways in `brand/logo/` are neutral
marks and `assets.logo(variant)` already selects by background, so they keep
working as they are. Do not replace them.

GitHub Desktop will show fourteen changed files. Commit message:

> oxide palette, blog ingestion, repurpose, metrics feedback and hook library

### Optional: a repository variable for the feed

`from_blog.py` defaults to `https://www.rachitmishra.in/feed`. If that ever
changes, set a repository **variable** (not a secret) named `BLOG_FEED_URL`
rather than editing code.

Then **Push origin**.

---

## 2. Apply the caption patch to `prompts/system.md`

`prompts/system-caption-patch.md` is instructions for you, not a file the
agent reads. Open it, and follow it: replace everything in
`prompts/system.md` from the caption guidance to the end of the file with the
block it contains. Keep the `## HOOKS` and `## SLIDE CONSTRAINTS` /
`## REEL CONSTRAINTS` sections above it as they are.

It carries one rule worth calling out: **the agent must never ask anyone to
comment a keyword.** There is no automation behind that ask, so it would be a
public promise the account cannot keep. That rule comes back out when the
comment-to-DM system is actually built.

---

## 3. Check `requirements.txt`

`metrics.py` needs `requests` and `repurpose.py` needs `pyyaml`. Both are
almost certainly already there. Open `requirements.txt` and confirm you see
both lines; add them if not.

---

## 4. Run them once, by hand

**Actions → Metrics → Run workflow.** This is the safe one to run first: it
only reads. When it finishes, open `state/METRICS.md` in the repo — that is
the first time this system has ever looked at its own results.

**Actions → From Blog → Run workflow**, with *list_only* ticked. It prints the
ten articles in your feed and confirms nothing has been used yet. Then run it
again with `count: 2`, `per_day: 1` and read what it produced in
`content/queue/` before trusting it with more. Once you are happy, `count: 8`
and `per_day: 2` drains the backlog across four days.

**Actions → Repurpose → Run workflow.** Writes `linkedin.md` and `blog.md`
into each folder under `content/queue/`. Read one of the LinkedIn drafts. If
the voice is off, tell me and I will tune the prompt rather than you editing
by hand every week.

---

## 5. The two lines in `generate.py` (optional, do it when you have a minute)

This is what closes the loop. Near the top of `agent/generate.py`, with the
other imports:

```python
from agent.metrics import brief_context
```

Then find where the prompt is assembled — the place the brief or pillar text
is built into the string sent to the model — and add the returned block to it.
Something like:

```python
    performance = brief_context()
    if performance:
        brief = brief + "\n\n" + performance
```

`brief_context()` returns an empty string until there are at least twenty
measured posts, so nothing changes until there is enough data for the
statement to be true. That restraint is deliberate: feeding the model noise
and calling it insight is worse than telling it nothing.

To load the hook library at the same time, append `prompts/hooks.md` wherever
`prompts/system.md` is read:

```python
    system = (PROMPTS / "system.md").read_text(encoding="utf-8")
    hooks = (PROMPTS / "hooks.md")
    if hooks.exists():
        system += "\n\n" + hooks.read_text(encoding="utf-8")
```

If you would rather I made these edits precisely, upload your current
`generate.py` and I will hand it back done.

---

## 6. The palette — one command, one edit

Regenerate the eight background images so they match the new accent:

```
python tools/make_backgrounds.py --seed 42
```

Same seed, so the compositions are identical to the ones you have — only the
colours change. Commit the regenerated files with everything else.

Then wire the light/dark rule into the renderer. In `agent/render.py`, find
where the slide colours are read (direct lookups like `design["bg"]` and
`design["ink"]`) and replace them with:

```python
from agent.theme import palette, roles_for_carousel

roles = roles_for_carousel(len(slides), design)
for slide, role in zip(slides, roles):
    p = palette(design, role=role)
    #  ... use p["bg"], p["ink"], p["ink_soft"], p["accent"], p["rule"]
    #  ... and pass p["logo_variant"] to assets.logo()
```

In `agent/video.py`, the Reel cover takes `palette(design, role="reel_cover")`
and the rest of the frames take `role="body"`.

If you would rather not touch these by hand, upload your current `render.py`
and `video.py` and I will hand them back done. **Nothing breaks if you skip
this step** — the slides will simply all use the light ground, which is still
an improvement on what you have.

`COLOUR-NOTE.md` has the research behind the palette choice, including the
part that argues against it.

---

## 7. Zernio — verify before we build

Do not connect it to anything yet. Sign up, connect your **personal** LinkedIn
profile in their dashboard, get the API key, then run:

```
python tools/zernio_check.py
```

It prints what Zernio can actually see. If it reports a member/personal
profile, LinkedIn scheduling becomes buildable and I will write the publisher.
If it reports organisation pages only, we stop — and manual LinkedIn posting
stays the plan, which is what I would recommend for the first month anyway.

---

## What this changes, in one paragraph

Before: one research run produced one Instagram post, and the system had never
seen a single performance number. After: one research run produces an
Instagram post, a LinkedIn draft and a blog outline; the generator can see
what was saved and sent; your own half-formed ideas get first claim on the
week ahead of anything the web search finds; and the hooks are written against
a library built for your register rather than improvised each time.
