# Weekly generation and recent developments

The calendar remains ten posts with the existing bottle-green design. At least
eight come from the author's full blog archive. Up to two can cover developments
reported during the seven days before the target Monday. A quiet week uses ten
blogs. Every post still needs a distinct visible tool, source attribution and
the existing editorial checks before it enters the review queue.

`Gather recent brand developments` collects public publisher feeds daily at
04:45 IST. Sources and relevance terms live in `brand.yml`. It stores dated,
readable source text and feed errors in `state/research/YYYY-MM-DD.json`. No API
key is used for collection. Public reporting can cover Instagram changes, but
this is not logged-in Instagram scrolling or a measurement of platform trends.
Additional publisher RSS feeds can be configured in the same list.

The weekly editor selects at most two sources, checks event dates and requires
a verbatim supporting excerpt. It proposes our own interpretation and a useful
decision tool. Source text is untrusted evidence, never agent instructions.
Publication dates alone do not establish when an event happened. Selection
failure falls back to blogs; unsupported facts and fabricated virality are
prohibited. Human review remains required before publishing.

`Draft the week` starts Saturday at 06:00 IST and retries at noon and 18:00,
then at the same times on Sunday. Runs are serialized. Approved/published
weeks and existing review PRs are skipped. Completed slots and source plans
are checkpointed between runs, so partial failures resume without rewriting
successful posts. Ten completed posts are required before opening the review
PR. Closed, unmerged review PRs are treated as rejected rather than recreated.

The model adapter uses explicit request timeouts, a bounded fallback window,
quota/service cooldowns and the last working model/configuration. Failed
generation remains visible as a failed Actions run, with a recovery artifact;
provider outages or exhausted account quota can still prevent completion.
Checkpoint caches can be evicted by GitHub. The artifact recovery input remains
available for that case. Nothing here approves or publishes drafts automatically.
