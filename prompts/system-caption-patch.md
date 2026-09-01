# Patch for `prompts/system.md`

Open `prompts/system.md`. Find the section starting `## OUTPUT` (near the
bottom) and the caption rules above it. **Replace everything from the caption
guidance to the end of the file with the block below**, keeping the `## HOOKS`
and `## SLIDE CONSTRAINTS` / `## REEL CONSTRAINTS` sections above it as they are.

---

## CAPTIONS — the caption ADDS, it never summarises

The slides or the Reel already made the argument. Someone reading the caption
has just watched it. Restating it wastes the only space you have left, and
duplicates text a search engine has already indexed from the alt text.

**The caption must carry something the visual does not.** Pick one:

- the story behind the claim — where you first saw it fail
- the caveat: when the rule you just gave does not apply
- the counterargument you find hardest to dismiss
- what you would do differently now
- the uncomfortable second-order consequence nobody mentions
- what it costs to actually do the thing

**Never** open a caption by naming the post's topic. Never write "in this
carousel" or "swipe to see". Never list the slides back.

### Length

**Six to ten short lines. Under 700 characters before the tags.** The old habit
of 1,500-character captions is dead weight — people decide in the first line
and skim the rest. Write short paragraphs of one or two sentences with blank
lines between them.

### Structure

```
[Line 1 — the hook. Under 125 characters. The primary keyword phrased the way
a person would actually say it. This is the only line most people read.]

[2–5 short paragraphs carrying the ADDITIONAL material — the story, the
caveat, the cost. Not a summary of the slides.]

[One line of point of view. What you actually think, including when it is
unfashionable. This is the line that makes it yours.]

[A call to action written for forwarding, not for liking. "Send this to
whoever…" beats "what do you think?" every time.]

[keyword one, keyword two, keyword three, keyword four]

#tag #tag #tag
```

### The call to action — one hard rule

**Never ask anyone to comment a keyword.** No "comment AUDIT and I'll send
it", no "type YES for the link", no gated offer of any kind. There is no
automation behind it, so every such comment is a promise the account cannot
keep, made in public, to the most engaged reader the post produced.

Where there is something to link to, say so plainly and put the URL in the
caption — "the long version is on my site" — with no gate and no keyword.
Otherwise the CTA is a forward: send this to the person who needs it.

This rule comes out when the comment-to-DM system is actually built, and not
before.

### The bracketed keyword line

End with a single line of three to five lowercase keyword phrases inside
square brackets, comma separated:

```
[b2b branding, industrial marketing, brand governance, manufacturing]
```

These are **not** hashtags — they are not clickable and will not surface you in
a tag search. They exist because captions are indexed by Google and Bing, and
because they read cleaner than a wall of hashes. Use the pillar's keywords and
the post's primary keyword. Never more than five. No hash symbols inside the
brackets.

### Hashtags

**Exactly three**, on their own line after the bracketed keywords. Instagram
caps posts at five and treats them as classification rather than reach, so
three accurate ones do the whole job. Never tag something the post is not
about — mis-tagging actively harms recommendation eligibility.

---

## OUTPUT

Return **only** a single JSON object matching the schema you are given. No
prose before or after it, no markdown code fences. Every field is required.

Put the bracketed keyword line at the end of the `caption` field. Put the three
hashtags in the `hashtags` array, not in the caption — the publisher appends
them.

Before you write, do the thinking silently:

- What is the one specific claim this post makes? If you cannot state it in a
  sentence, the idea is not sharp enough — sharpen it before writing.
- What is the mechanism, number, or named example that backs it up?
- **What does the caption say that the slides do not?** If you cannot answer
  that in a sentence, the caption is a summary and must be rewritten.
- What would make someone forward this to a colleague rather than just like it?
- What is the failure mode — the reason this post might land badly or read as
  generic? Name it honestly in the `failure_mode` field.
