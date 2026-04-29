# Dry Ink — visual style bible

Single source of truth for the storyboard skill's aesthetic. Implementation
constants live in `scripts/style.py`; this document explains *why*.

## Palette

| Token | Hex | Use |
|-------|-----|-----|
| `bg` | `#f5f0e6` | Page background — cream paper |
| `fg` | `#1f1d1a` | Warm ink — strokes, fills, text |
| `fg_dim` | `#6a5f56` | Muted ink — labels, footnotes, axis markers |
| `accent` | `#8a3a2c` | Dried-blood red — eye-lines, focus markers, alerts |
| `ok` | `#2c5a3a` | Deep green — status only, rare |

The palette comes from architectural-sketch tradition: cream pulp paper
with a single warm pigment. Industry storyboards use this lineage; we
do not reinvent it. The accent red is reserved for **information**, not
decoration.

## Type

| Token | Family | Use |
|-------|--------|-----|
| `serif` | Newsreader → Source Serif Pro → Georgia | Titles, italic captions, dialog |
| `mono` | Geist Mono → IBM Plex Mono → Menlo | Metadata, labels, technical values |

Web-safe fallbacks are included so the SVG renders even when the user
has neither installed. Newsreader and Geist Mono should be loaded by
the HTML viewer for the polished look; the SVG itself never embeds
fonts.

## Stroke scale

```
hairline 0.4
thin     0.5
regular  0.8
medium   1.0
frame    1.5
emphasis 2.0
border   2.5  ← frame border
heavy    3.0
```

If you reach for a stroke width not on this list, you're decorating;
stop and pick the nearest. The fixed scale is what gives the boards
their unified feel across genres.

## Type sizes

```
tiny     9
label   10
caption 13
subtitle 14
title   22
```

## Ironclad rules

- **No gradients**, except torchlight cones (radial only, sci-fi/horror
  scenes only). Everything else is flat fill.
- **No drop shadows**. The frame is a sketch, not a render.
- **Frame border is always `border` (2.5)**, ink colour. No exceptions.
- **Captions are italic serif**. Metadata is regular mono. Never mix.
- **Red accent is reserved for**: eye-lines, focus rings, danger/blood
  markers, axis indicators. Never as decoration. Never used for the
  frame border, never for text headings.
- **Backgrounds are cream**. Not white. White breaks the paper illusion.

## Genre adaptations

The palette and rules are constant across genres. Variation comes from
*content*, not *style*:

- **Noir** uses heavy ink fills (buildings, body silhouettes), sparse
  rain hatches, low horizons. Accent on focus rings.
- **Action** keeps the same palette but adds motion lines (regular
  weight, low opacity) and impact bursts (emphasis weight). Pacing
  notation in the metadata strip.
- **Dialogue** removes most environment — figures and eye-line arrows
  carry the frame. Two-shot establishes; CU/OTS pairs cover.
- **Sci-fi** allows the ONE permitted gradient (torchlight cone). HUD
  overlays are mono, regular weight, top-right corner of the frame.

The constraint *is* the differentiator. A user opens the storyboard
and immediately knows which tool produced it — without seeing a logo.
