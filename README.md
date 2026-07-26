# @byrachitmishra — content agent

An agent that researches the week, writes five Instagram posts in your voice,
renders the carousel slides as finished images, and opens a pull request for
you to approve from your phone. Merge it and the posts publish themselves at
their scheduled times.

It runs entirely on GitHub Actions. There is no server to maintain and nothing
running on your laptop.

```
Sunday 06:00 IST                  You, whenever                    Hourly
┌──────────────────┐              ┌──────────────┐              ┌──────────────┐
│  research the    │              │   read the   │              │  publish what│
│  week → write 5  │─── PR ──────▶│   PR, merge  │─── main ────▶│  is now due  │
│  posts → render  │              │   to approve │              │              │
└──────────────────┘              └──────────────┘              └──────────────┘
   generate.yml                      promote.yml                   publish.yml
```

---

## What you get every Sunday

A pull request titled *"Week of 3 August — 5 posts ready"*. Inside it:

- `SIGNALS.md` — what actually happened in brand and marketing this week, with
  sources, so you can see what the posts are reacting to.
- One folder per post, each with:
  - `POST.md` — the caption ready to copy, the alt text, the slides embedded as
    images so you can review the whole thing on your phone, and an honest note
    on how the post might fail.
  - `slide-01.jpg` … `slide-07.jpg` — the finished 1080×1350 carousel images.
  - `post.json` — the structured version the publisher reads.

Merge the PR and every post in it is approved. Delete a folder before merging
and that post is dropped. Close the PR and the whole week is skipped.

---

## Setup

Roughly forty minutes end to end, and about fifteen of that is Meta's app
dashboard. You can stop after Part 2 and have a working drafting agent — Part 3
is only needed if you want it to publish for you.

### Part 1 — Get the repo running (10 minutes)

1. **Create the repository.**

   Make it **public**. This matters: Instagram's API fetches your images from a
   URL, and a public repo gives you `raw.githubusercontent.com` for free. If
   you'd rather keep it private, see *Keeping the repo private* below.

   ```bash
   gh repo create byrachitmishra-agent --public --source=. --push
   ```

   Or create it in the GitHub web UI and push this folder to it.

2. **Add an API key — free or paid, your choice.**

   The agent runs on either Google Gemini or Anthropic Claude. Supply one key
   and it works out which to use. Add it under **Settings → Secrets and
   variables → Actions → New repository secret**.

   | If you want | Get a key from | Secret name |
   |---|---|---|
   | **Free** — no card, good enough to start | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `GOOGLE_API_KEY` |
   | **Paid** — noticeably better writing, ~$3/month | [console.anthropic.com](https://console.anthropic.com) | `ANTHROPIC_API_KEY` |

   Two things to know about the free tier: Google's limits are far above what
   this uses (five posts a week is nothing against a 1,500-requests-a-day
   allowance), but Google may use free-tier prompts to improve their models.
   For public Instagram drafts that is probably fine. Decide for yourself.

   **Switching later takes one minute and no code changes.** Add the other
   key as a second secret, then set the `LLM_PROVIDER` repository *variable*
   to `gemini` or `anthropic` to pick between them.

3. **Run it once by hand.**

   **Actions → Draft the week → Run workflow.** It takes three or four minutes.
   When it finishes you should have a pull request waiting.

That is the whole drafting setup. From here it runs every Sunday on its own.

### Part 2 — Make it yours (20 minutes, worth doing properly)

Everything the agent believes about you lives in **`brand/brand.yml`**. Nothing
is hardcoded. Open it and go through:

- **`identity.positioning`** — the sentence everything hangs off. If this is
  wrong, every post will be subtly wrong.
- **`voice.banned_phrases`** — the most useful section in the file. Every time
  a draft says something that doesn't sound like you, add the phrase here and
  it will never appear again. This list is what stops the output drifting
  toward generic marketing-account English.
- **`pillars`** — the keywords feed both research and caption targeting.
- **`schedule.slots`** — which pillar goes out on which day.
- **`design`** — colours and type for the rendered slides.

To see your design changes without spending anything:

```bash
pip install -r requirements.txt
python -m playwright install chromium
python tools/preview.py     # renders a sample carousel into preview/
```

Iterate on `brand/brand.yml` and `templates/slide.html` until the slides look
right. This costs nothing and calls no API.

### Part 3 — Let it publish (optional, 15 minutes)

Skip this and the agent is a drafting machine: you copy the caption, upload the
images, and post yourself. Set it up and the posts go live on their own.

1. **Your Instagram account must be a professional account** — Creator or
   Business. Personal accounts cannot use the publishing API at all.

2. **Create a Meta app.** At
   [developers.facebook.com/apps](https://developers.facebook.com/apps) create
   an app, then add the **Instagram** product and choose **API setup with
   Instagram login**. Add your Instagram account as an app tester and accept
   the invitation from your Instagram account settings.

3. **Get a token.** In the same panel, generate a token with the scopes
   `instagram_business_basic` and `instagram_business_content_publish`. If you
   need to do the OAuth flow manually instead:

   ```bash
   python tools/get_token.py \
     --app-id <APP_ID> --app-secret <APP_SECRET> \
     --redirect-uri <YOUR_REDIRECT_URI> --code <CODE_FROM_REDIRECT>
   ```

   It prints the two values you need and exchanges your short-lived token for
   a 60-day one.

4. **Add the secrets and variables.**

   Secrets (**Settings → Secrets and variables → Actions → Secrets**):

   | Name | Value |
   |---|---|
   | `IG_USER_ID` | the numeric ID printed by the token helper |
   | `IG_ACCESS_TOKEN` | the long-lived token |
   | `GH_PAT` | a fine-grained personal access token with **Secrets: read and write** on this repo — used to rotate the Instagram token automatically |

   Variables (**the Variables tab, not Secrets**):

   | Name | Value |
   |---|---|
   | `PUBLISH_ENABLED` | leave unset for now |

5. **Watch it dry-run for two weeks.** With `PUBLISH_ENABLED` unset, the
   publish workflow runs hourly and logs exactly what it *would* have posted
   without touching your account. Read those logs. When you're satisfied, set
   `PUBLISH_ENABLED` to `true` and it goes live.

6. **Token upkeep is automatic.** Instagram's long-lived tokens expire after 60
   days. The *Refresh Instagram token* workflow runs on the 1st and 15th of
   each month and writes the refreshed token back into the secret, so it never
   silently stops working.

---

## Day to day

| What you do | When | How long |
|---|---|---|
| Read the PR, merge or trim it | Sunday or Monday | 10 minutes |
| Shoot the two Reels from the scripts | During the week | your call |
| Add a photography post by hand | Whenever | your call |
| Add a phrase to `banned_phrases` when a draft sounds off | As it happens | 30 seconds |

**Reels are generated as kinetic typography.** The agent writes the script,
then builds a 1080×1920 MP4 from it: each beat's on-screen text over an
AI-generated background, with a slow pan and hard cuts on the beat. It
publishes automatically like anything else.

What it cannot do is put you on camera, and a talking-head Reel does a
different job on a personal-brand page. So the generated video is a floor, not
a ceiling: film your own whenever you want, drop it into the post's folder as
`reel.mp4`, delete the `.generated-reel` marker beside it, and your footage
publishes instead. The agent never overwrites a file you supplied.

Two repository variables control this: `BUILD_REELS=false` for scripts only,
and `REEL_AI_BACKGROUNDS=false` to use designed gradients instead of spending
image-generation quota.

**Photography stays yours.** The `photography_travel` pillar is marked
`automate: false` and the agent skips it entirely.

---

## Costs

| Item | Cost |
|---|---|
| GitHub Actions | Free — public repos get unlimited minutes |
| Gemini free tier | ₹0 |
| Anthropic API, if you switch | Roughly $1.50–4 a month at five posts a week |
| Instagram API | Free |

Two quality knobs, in order of impact. First, `brand/brand.yml` — the
positioning sentence and the banned-phrases list do more for how the writing
sounds than any model change. Fix that before anything else. Second,
`AGENT_MODEL`, a repository variable that overrides the default model for
whichever provider you're on.

---

## Keeping the repo private

The Instagram API has to fetch your images from a public URL, so a private repo
needs somewhere else to host them. Upload the rendered JPEGs to any static host
— Cloudflare R2, S3, Cloudinary — and set the `ASSET_BASE_URL` repository
variable to that host's base URL. The publisher will build image URLs from it
instead of from `raw.githubusercontent.com`.

If you're only drafting and not auto-publishing, none of this applies — a
private repo works fine.

---

## When something breaks

**The PR didn't appear on Sunday.** Check **Actions → Draft the week** for a
red run. Nine times out of ten it's an expired or rate-limited API key.

**GitHub disabled the schedule.** Scheduled workflows are switched off
automatically after 60 days of no activity in the repository. Any commit
re-enables them. Merging your weekly PR counts, so this only bites if you stop
reviewing for two months.

**A post published with broken-looking slides.** The text overflowed the
template. The length limits live in `agent/schema.py` and are enforced during
generation with up to two self-corrections — tighten them there, or loosen the
type sizes in `templates/slide.html`.

**Publishing fails with an OAuth error.** Your token expired and the refresh
workflow didn't run. Trigger **Refresh Instagram token** by hand; if that also
fails, the token is past its 60-day window and you need to generate a new one
with `tools/get_token.py`.

**Everything looks right but nothing publishes.** `PUBLISH_ENABLED` is
probably still unset, which is the intended default. Check the workflow logs —
a dry run says so on its first line.

---

## What's in here

```
agent/
  config.py       loads brand.yml, holds every env-var setting
  llm.py          the provider switch — Gemini or Claude, one interface
  research.py     weekly signal brief, using the provider's own web search
  generate.py     brief + pillar → a finished post, with self-correction
  schema.py       the post contract, length limits, and the voice checker
  render.py       HTML → 1080×1350 JPEG slides via headless Chromium
  video.py        Reel script → 1080×1920 MP4 via Chromium + ffmpeg
  publish.py      Instagram Graph API: containers, publish, token refresh
  run_batch.py    Sunday entrypoint
  run_publish.py  hourly entrypoint
brand/brand.yml   ← everything you'll actually want to edit
prompts/system.md the strategist prompt, filled from brand.yml at run time
templates/        the slide design
tools/            preview.py (free design iteration), get_token.py (one-time)
content/
  queue/          drafted, awaiting your review
  approved/       merged, waiting for their scheduled time
  published/      archive, with the Instagram media ID of each post
```

## The platform rules this is built on

Worth knowing, because they are recent and most advice online is out of date:

- **Five hashtags maximum**, enforced by Instagram since December 2025. They
  classify content for the recommendation system; they do not drive reach.
- **Public posts from professional accounts are indexed by Google and Bing**
  since 10 July 2025. Captions are web copy now.
- **Sends via DM are the heaviest ranking signal on Reels**, which is why every
  generated CTA is written for forwarding rather than for liking.
- **Images must be JPEG** and reachable at a public URL when the API call is
  made. Carousels are 2–10 items. The publishing limit is 100 posts per 24
  hours, which you will never approach.
