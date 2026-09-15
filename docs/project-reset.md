# Project reset — 14 September 2026

## Purpose

Build recognition for Rachit's judgement in industrial B2B brand, corporate
reputation and enterprise AI. The audience is a professional peer inside an
organisation who needs to make or defend a decision. A useful post should earn
attention, demonstrate a mechanism, and leave an action worth keeping or sending.

## Findings from the actual pipeline

- The root `brand.yml` contains the developed B2B brief, boundaries and oxide
  palette. The loader still read the older `brand/brand.yml`. Root is now active;
  the older file is labelled historical. Thursday's existing time experiment
  is retained, although its new pillar means old results are not comparable.
- `ideas.md` promised to feed generation but was never read. Nonempty unchecked
  ideas now enter the brief. The bank is currently empty. No personal anecdotes
  should be invented to fill it.
- Covers copied beat one; the first repair only varied typography and stamps.
  Covers now draw an explicit workflow, comparison or checklist from post data.
- Carousel instructions demanded proof objects that the schema discarded and
  the renderer could not draw. These objects now pass through the full pipeline.
- Reel directions and voiceover text did not become footage or speech. They
  still do not. The automatic output now shows visual objects on multiple beats;
  the complete argument must remain readable without voiceover.
- The saved metrics snapshot (6 September) has 31 posts, 10 saves and zero sends.
  It does not establish a winning cover, or prove that any redesign will work.

## Acceptance standard

1. A recognisable situation for the intended peer, without a generic topic title.
2. A cover whose central object makes the tension visible at a small crop.
3. An opener that begins the argument and pays the cover's promise.
4. A visual explanation, with illustrative material clearly labelled.
5. A usable decision/checklist plus a concrete reason to send it to a colleague.
6. A rendered preview before approval, using production templates and brand data.

## Review sample

Run `python tools/preview_reset.py`; use `RENDER_BROWSER_CHANNEL=chrome` for an
installed Chrome, otherwise the normal Playwright Chromium installation is used.
Add `--video` with ffmpeg available to build the 30-second sample. Outputs live
in `preview/reset`, outside the publishing queue. The sample is a suggested
workflow, not a claim about an actual company's approval performance.

The three cover concepts demonstrate different subjects and visual mechanisms.
The first has a complete Reel and six-slide companion carousel. Review the
full artwork as well as its centre crop. These are candidates to test, not
proven performance improvements. No publishing or scheduling is performed by
the preview command.

## Remaining limitations

The weekly calendar now has ten slots, including three blog adaptations. The
blog feed check uses persisted posts to avoid reusing articles. Empty/unavailable
feeds produce labelled evergreen replacements. The former independent blog
conversion workflow is now a read-only check so it cannot add an extra calendar.
The completed Reel and companion carousel were explicitly approved in this task;
other weekly drafts continue to require approval before publication.

Source URL availability does not verify a factual claim. Editorial source review
is still necessary. The post's visual note describes its basis; it is not an
independent fact check. The system has no recorded footage or generated narration.
Live performance must be collected after release. Cover/layout metadata should
be compared within the same pillar and format, with small samples treated as
descriptive. Existing published assets are historical and are not regenerated.
