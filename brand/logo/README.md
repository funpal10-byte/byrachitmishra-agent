# Logo marks

Three colour variants of the same lockup, extracted from the source PDFs with
transparency, sized 900px wide at roughly 2.6:1.

| File | Colour | Used on |
|---|---|---|
| `logo-light.png` | cream `#ece6db` | near-black slides, Reel cards |
| `logo-dark.png`  | charcoal `#272727` | off-white body slides |
| `logo-white.png` | pure white | the accent-colour CTA slide, where cream goes muddy |

Replace any of these to change the mark everywhere. Keep the filenames, keep
the transparency, and keep the artwork around 2.6:1 or the footer spacing will
need adjusting.

Size and opacity are set in `brand/brand.yml` under `design`:

```yaml
show_logo: true
logo_width: 230     # px on a 1080-wide slide
logo_opacity: 0.92
```

Set `show_logo: false` to drop back to the plain `@byrachitmishra` text mark.
