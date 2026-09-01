# What the research actually says about colour and attention

You asked for the evidence rather than the assertion. Here it is, including
the part that cuts against the change I recommended.

## The headline finding is not what marketing blogs claim

The popular version — "warm colours grab attention, use red and orange" — is
much weaker than it sounds. In the attention literature, a uniquely coloured
item in a display is a *colour singleton*, and the question of whether
singletons automatically capture the eye has been argued for thirty years.
The current consensus is the **signal suppression hypothesis**: a salient
colour does generate an initial bottom-up signal, but a viewer with any goal
in mind can actively suppress it.

The evidence is fairly stark. In eye-tracking work at the Lab for Integrative
Vision, when observers were searching for something specific, their first eye
movement landed on the salient colour singleton only **4–5% of the time**,
versus 10–12% for an average non-salient item. The singleton was not just
ignored — it was suppressed *below* baseline. Being the brightest thing on
screen can actively cost you attention when the viewer has a purpose.

**The critical methodological caveat, and it is the useful part:** those
studies used *isoluminant* stimuli — colours differing only in hue, matched
for brightness. The authors say plainly that their findings do not extend to
singletons defined by luminance contrast.

So: **hue is suppressible. Luminance contrast is much less so.**

## What that means for a slide in a feed

Three practical consequences.

**Contrast beats colour.** What stops a scroll is a large luminance step
against the surrounding feed, not a particular hue. A near-white slab with
near-black type is a bigger luminance event in most feeds than any saturated
accent, because the feed is mostly mid-tone photography. This is an argument
*for* the light slide, not against it — and it is a stronger argument than the
readability one I gave you earlier.

**Uniqueness is local, not absolute.** Salience is relative to neighbours.
Purple is not intrinsically more or less eye-catching than oxide; what matters
is whether it differs from what sits around it. In a B2B and marketing feed,
saturated purple and blue are the ambient condition — which means purple is
close to camouflage there, while a desaturated rust is genuinely uncommon.

**Attention capture and reach are different problems.** Everything above
governs whether someone stops on a post *they were already shown*. It does not
influence how many people are shown it. At ~12 reach per post, colour is
optimising the wrong end of the funnel. I would make this change because it is
cheap, correct and compounds — not because it will move your numbers.

## So why oxide, honestly

Not for attention. On salience grounds oxide and purple are roughly
interchangeable, and both lose to the luminance contrast of the paper ground.

The reason is **semantic fit and recall**. Colour's reliable effect in brand
work is on memory and association, not capture. `#7c3aed` carries a strong,
specific association right now — AI products and SaaS launches — and that
association contradicts a positioning built on steel, freight and procurement.
Oxide draws from the subject's own material world, and it is rare enough in
marketing content to become a recognition cue over time.

That is a smaller, slower claim than "this colour gets more views." It is also
the one the evidence supports.

## The one thing to actually watch

Contrast ratios, because they are measurable and they affect whether the text
is read at thumbnail size. On the new palette: `#14161a` on `#f5f4f1` is about
16:1, and `#52575c` on `#f5f4f1` is about 7:1 — both comfortable. Oxide
`#b0492a` on paper is around 6:1, fine for the kicker and for emphasis inside
a headline, but **not** for body text at small sizes. That is why
`accent_on_dark` exists as a separate token: `#b0492a` on `#16181a` is roughly
3.5:1 and would fail on the inverted slides.

Sources: [Suppression of overt attentional capture by salient-but-irrelevant
colour singletons](https://clas.ucdenver.edu/lab-for-integrative-vision/sites/default/files/attached-files/suppression_of_overt_attentional_capture_by_salient-but-irrelevant_color_singletons.pdf),
[Decoding colour perception: an eye-tracking perspective (Journal of Sensory
Studies, 2025)](https://onlinelibrary.wiley.com/doi/10.1111/joss.70044),
[The attentional guidance of individual colours in increasingly complex
displays](https://www.sciencedirect.com/science/article/abs/pii/S0003687019301176).
