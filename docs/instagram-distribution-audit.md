# Instagram Distribution and Scheduling Review

## Decision

Keep four of the five existing weekly posting windows. Thursday's Leadership
Reel now alternates deterministically between **13:00 IST** and **17:00 IST**;
09:30 is retired. Treat this as a starting experiment for an India-first
professional audience, not as a permanent algorithm rule. The account does not
yet have the retention history required to claim an account-specific optimum.

| Day | Format and pillar | Previous IST | Recommended IST | Decision |
|---|---|---:|---:|---|
| Monday | Brand Strategy Reel | 08:30 | 08:30 | Keep as a morning test window |
| Tuesday | AI in Marketing Reel | 19:00 | 19:00 | Keep |
| Wednesday | Behind the Brands Reel | 20:00 | 20:00 | Keep |
| Thursday | Leadership Reel | 09:30 | **13:00 / 17:00** | Automated time test |
| Saturday | Brand Strategy carousel | 10:30 | 10:30 | Keep as a save-oriented weekend test |

The schedule lives in `brand/brand.yml`. The metrics collector now also asks
for Reel average and total watch time where the connected Graph API version
exposes them. It writes a structured experiment ledger and a timing report,
but never changes the schedule automatically. That turns the hook review from a
taste judgement into a measurable learning loop without overfitting noise.

## What the available evidence can and cannot say

Large benchmark studies disagree on exact hours because their data pools,
markets, content categories and success metrics differ. Sprout Social's March
2026 analysis covers nearly two billion engagements and identifies broad
weekday afternoon windows: Monday 14:00–16:00, Tuesday 13:00–19:00, Wednesday
12:00–21:00 and Thursday 12:00–14:00 in local time.^1 Hootsuite's analysis of
more than one million posts instead finds Monday afternoon/evening, Tuesday
morning and afternoon, Wednesday around 17:00, Thursday 16:00–17:00, and
Saturday at 11:00 or 17:00.^2

Neither result is a substitute for this account's results. Both are largely
global studies; neither establishes a causal best hour for Indian B2B/brand
strategy content. A small India-specific practitioner study points to early
mornings, lunchtime and evening as plausible IST windows, but it covers a
limited collection of managed accounts and should be used only as a directional
cross-check.^3

The useful conclusion is narrower: Tuesday and Wednesday evening are credible
starting windows, Saturday morning is at least locally plausible for a
save-oriented carousel, and Thursday 09:30 is the least supported current
choice. Shifting Thursday to 13:00 matches the largest and newest benchmark's
Thursday peak while fitting the account's working-professional audience.

## Why timing is secondary to the opening

Publishing time affects the initial opportunity to be seen; it cannot rescue a
weak first frame. Instagram itself identifies total watch time and average
watch time as Reel insights and explicitly frames those metrics as a way to
see where a stronger hook is needed.^4 The code previously collected reach,
views, saves and shares but not watch time, making it impossible to separate a
poor hook from a poor time slot.

The new collection is intentionally additive. It requests
`ig_reels_avg_watch_time` and `ig_reels_video_view_total_time` separately for
Reels. If the account's API version or permissions do not expose those fields,
the existing metrics job still succeeds and records the core engagement data.

## Eight-week measurement plan

Do not make another schedule change until enough comparable posts exist. Run
the current windows for eight weeks, then review only posts that have had at
least seven days to mature.

For each Reel, record:

1. Average watch time and total watch time.
2. Reach and views.
3. Saves and shares per 1,000 reached accounts.
4. Follows or profile actions, if available in the professional dashboard.
5. The exact hook type: cost, objection, distinction, correction, case study
   or framework.

Evaluate content quality before time. Compare like with like: for example,
Thursday Leadership Reels against Thursday Leadership Reels, rather than a
case-study Reel against a checklist carousel. A slot should move only when it
has at least four comparable posts and its median watch time plus share/save
rate consistently trails an alternative window. A single high-reach Reel is
not evidence that its posting time caused the outcome.

## Recommended product improvements

### 1. Add a timing-experiment engine

**Priority: high.** The new schedule is static. Add a `schedule_experiments`
section to `brand.yml` with two permitted windows for each pillar and a simple
rotation. After 24 comparable posts, recommend a winner using median watch
time and shares/saves per reach. Do not automatically rewrite the schedule;
write a recommendation for review. This avoids overfitting tiny samples.

### 2. Build the Reel as a story, not sequential title cards

**Priority: high.** The current renderer turns every beat into large text over
one background. It does not turn the script's `voiceover` or `direction` into
audio or visual evidence. For a strategy account, add three reusable visual
beat types: a speaking-to-camera opener, a proof card with a cited chart or
document crop, and a keepable checklist/decision card. The hook contract now
ensures the first text is coherent; this feature would make the following
seconds worth watching.

### 3. Add source verification before rendering

**Priority: high.** The new `evidence` field prevents unsupported claims from
silently passing copy review, but it does not yet fetch or verify a cited page.
Add a preflight that checks source URLs resolve, saves the source title/date,
and blocks a statistic when no source is present. Keep practitioner observations
and frameworks as explicit alternatives; not every useful post needs a web
citation.

### 4. Use Trial Reels for high-variance concepts

**Priority: medium, manual workflow.** Instagram's Trial Reels are designed to
show a Reel to non-followers first and surface early engagement metrics before
the creator shares it broadly.^5 Use them for a new pillar, a more personal
point of view, or a controversial correction—not for every scheduled Reel.
This needs a manual Instagram-app step; it should not be faked through the
current publishing API.

### 5. Add a manual collaboration brief

**Priority: medium.** Once per month, generate a one-page brief for a relevant
Indian marketer, agency planner or founder: the mutual audience, a shared
claim, the proposed opening, and the asset required from each person. Instagram
supports Collabs on feed posts, carousels and Reels, including up to three
co-authors.^6 This is a distribution partnership, so it should remain
human-approved rather than automatically inviting people.

### 6. Create a community follow-up queue

**Priority: medium.** Create a daily human-review list: substantive comments
to answer, posts worth adding to Stories, and one discussion prompt for a
Broadcast Channel. Broadcast Channels support polls, prompts, replies and
insights, making them a useful retention layer once a base audience exists.^7
Do not automate replies in the author's voice.

### 7. Add a content experiment ledger

**Priority: medium.** Store structured metadata per post: hook type, evidence
type, length, format, topic, visual treatment, whether a person appears, and
CTA role. Join it to metrics weekly. This will reveal whether the account wins
with objections, named frameworks or case studies—and whether human-led Reels
outperform text-only ones—without relying on vague recall.

## What not to add yet

Do not add more hashtags, post more frequently, or build automatic comment
gates. None addresses the observed first-frame and proof deficits, and an
account with sparse data benefits more from clean experiments than additional
variables. Do not automate collaborator invitations or public replies either;
both are relationship decisions.

## Sources

1. Sprout Social, [“Best Times to Post on Instagram in 2026”](https://sproutsocial.com/insights/best-times-to-post-on-instagram/?languageid=1), March 2026. Global engagement benchmark and methodology.
2. Hootsuite, [“The best time to post on Instagram”](https://blog.hootsuite.com/best-time-to-post-on-instagram/), accessed September 2026. Global posting-time benchmark.
3. SalesBond, [“Best Time to Post on Instagram India (2026)”](https://www.salesbond.in/blog/best-time-post-instagram-india), March 2026. India-specific practitioner dataset; directional, not definitive.
4. Meta, [“New Features on Instagram Reels: Trends, Editing and Gifts”](https://about.fb.com/news/2023/04/instagram-reels-trending-audio-and-gifts-updates/), April 2023, updated October 2023. Definition and use of total and average watch time.
5. Meta, [“Test Content With Non-Followers Using Trial Reels”](https://about.fb.com/news/2024/12/trial-reels-try-content-non-followers-first-see-what-perfoms-best/), December 2024, updated June 2025.
6. Meta, [“New Ways to Create With Music and Collaborate With Friends on Instagram”](https://about.fb.com/news/2023/08/music-and-collabs-on-instagram/), August 2023. Collabs support for posts, carousels and Reels.
7. Meta, [“Get Closer to Your Community With Replies, Prompts and Insights”](https://about.fb.com/news/2024/12/get-closer-to-your-community-with-replies-prompts-and-insights/), December 2024, updated June 2025.
