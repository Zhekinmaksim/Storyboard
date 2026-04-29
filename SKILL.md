---
name: storyboard
description: |
  Turn prose scene descriptions into editable Dry Ink SVG storyboards with
  camera direction, blocking, and a multimodal critic loop. Use when the
  user asks for a storyboard, shot list, scene blocking, or pre-production
  visualisation. Kimi K2.5 parses prose into a structured Scene, renders
  it as SVG, then visually critiques its own output and proposes
  revisions before user approval. Schematic by convention, not by limit.
version: 0.1.0
author: Zmaxx (Zhekinmaksim)
license: MIT
homepage: https://github.com/Zhekinmaksim/storyboard
platforms: [linux, macos]
metadata:
  hermes:
    tags: [creative, film, storyboard, svg, kimi, multimodal, agentic]
    category: creative
required_environment_variables:
  - name: OPENROUTER_API_KEY
    description: For Kimi K2.5 access via openrouter.ai
    required: true
  - name: STORYBOARD_OUTPUT_DIR
    description: Where SVG, PNG, HTML viewer, and revision logs are written.
    default: ~/storyboard-output
    required: false
---

# Storyboard

Generate film storyboards from prose. Schematic SVG in the Dry Ink
palette (cream paper, warm ink, muted accent red), with frame metadata,
captions, eye-line annotations, and a self-critique loop powered by
Kimi K2.5 multimodal.

The loop is **hybrid**: the agent drafts a board, runs one auto-critique
round, applies revisions, and **stops for user approval** before
finalising. The user can request targeted edits ("make frame 4 more
Hitchcock — low angle, harder shadow") and only that frame re-renders.
Character continuity is preserved across scenes via a small
character bible.

## When to Use

Trigger this skill when the user:

- asks for a storyboard, shot list, scene blocking, camera coverage, or
  pre-production sketch ("draft a storyboard for…", "block out this
  scene", "сделай раскадровку")
- supplies a prose scene description and wants frames out
- wants to revise a specific frame from a previous board
- asks for a character bible to be saved or reused
- wants to export an existing board to HTML, PNG pack, or PDF

Do **not** trigger for: photorealistic concept art (use a diffusion
skill), animation/video generation, or hand-drawn comic panels.

## Quick Reference

```bash
# Full pipeline — prose to approved board, hybrid loop with user gate
python -m scripts.storyboard full "Detective enters a rain-soaked alley..."

# Just parse prose into a Scene JSON (no rendering)
python -m scripts.storyboard parse "..." > scene.json

# Render an existing scene JSON to SVG (no LLM)
python -m scripts.storyboard render scene.json > board.svg

# Critique a rendered board, get revision suggestions
python -m scripts.storyboard critique scene.json board.svg

# Apply critique revisions to scene JSON (deterministic)
python -m scripts.storyboard iterate scene.json revisions.json > scene.v2.json

# Re-render only one frame after a user note
python -m scripts.storyboard revise scene.json --frame 4 --note "low angle, harder shadow"

# Open the HTML viewer for the latest board
python -m scripts.storyboard view
```

Outputs land in `$STORYBOARD_OUTPUT_DIR` (default `~/storyboard-output/`):
`scene.json`, `board.svg`, `board.png`, `revisions/`, and `viewer.html`.

## Procedure

1. **Check environment.** Verify `OPENROUTER_API_KEY` is set. If not,
   tell the user to run `export OPENROUTER_API_KEY=sk-or-...` and stop.

2. **Parse prose to Scene.** Call `scripts/parse.py` with the user's
   prose. This sends a strict-JSON system prompt to Kimi K2.5 and
   validates the returned Scene against the dataclass schema. If
   validation fails, retry once with a stricter instruction; second
   failure surfaces a clear error to the user.

3. **Load or create character bible.** Open
   `$STORYBOARD_OUTPUT_DIR/character_bible.json`. For each
   `Figure.role` referenced in the new Scene, look up the character.
   If absent, populate from the Scene's `figures[*].role` and any
   `state` annotations, and persist back. This is what gives
   continuity across scenes.

4. **Render to SVG.** Call `scripts/render.py` with the Scene + bible.
   Output is one SVG per scene, 6-shot 3×2 grid, Dry Ink style. Convert
   to PNG via `rsvg-convert` for the critique step.

5. **Auto-critique (round 1).** Call `scripts/critique.py` with the PNG
   + Scene JSON + `references/critique-criteria.md`. Kimi K2.5 returns
   a JSON list of revisions. Reject any revision that names a shot
   label not present in the scene (anti-hallucination guard).

6. **Apply revisions, re-render.** Call `scripts/iterate.py` to merge
   revisions into the Scene. Re-render. **Stop here.** Do not loop
   further automatically.

7. **Present for approval.** Open the HTML viewer with the before/after
   side-by-side. Tell the user: "draft + 1 critique round done; review
   and approve, request specific changes, or accept as final."

8. **Targeted revision (optional).** If the user requests changes for a
   specific frame, call `scripts/storyboard.py revise --frame N --note "..."`.
   This re-renders only that frame; other frames are untouched.

9. **Finalise.** On approval, write `final.svg`, `final.png`, and a
   `revisions.log` documenting every change made.

## Pitfalls

- **Kimi returns malformed JSON for parse step.** Mitigation: strict
  system prompt + schema validation + one retry. If second attempt
  fails, fall back to a keyword-based stub Scene the user can edit by
  hand. Do not silently invent fields.
- **Critique hallucinates shots.** Mitigation: cross-check every
  revision's `shot_label` against the Scene before applying. Drop
  invalid revisions with a warning.
- **Character drift between scenes.** Mitigation: always load
  `character_bible.json` before render. If a role is in the bible but
  silhouette differs in this scene, prefer the bible value and log a
  warning.
- **rsvg-convert version differences.** PNG output may differ slightly
  across librsvg versions. CI pins `librsvg2-bin` from Ubuntu 22.04.
  Document the exact version in CHANGELOG.
- **OpenRouter rate limits during demo recording.** Mitigation:
  responses are cached to `~/.cache/storyboard/` keyed on prompt hash,
  so re-runs during dev don't hit the API. Cache is bypassed with
  `--no-cache`.
- **Approval gate forgotten in scripts.** The auto-loop is hard-capped
  at 1 critique round. There is no flag to bypass this in v0.1.

## Verification

After running `storyboard full "..."`, confirm:

```bash
ls $STORYBOARD_OUTPUT_DIR
# scene.json  board.svg  board.png  revisions/  viewer.html  character_bible.json

# Sanity check: SVG renders, contains frame metadata
grep -c "data-shot-label" $STORYBOARD_OUTPUT_DIR/board.svg
# Should match the number of shots in scene.json

# Critique log exists and has content
test -s $STORYBOARD_OUTPUT_DIR/revisions/round_1.json && echo OK

# Open the viewer
xdg-open $STORYBOARD_OUTPUT_DIR/viewer.html  # or `open` on macOS
```

Tests:

```bash
pytest tests/  # all green
```

For deeper context see `references/`:

- `style-bible.md` — Dry Ink palette, fonts, stroke scale
- `shot-grammar.md` — what each shot type means
- `critique-criteria.md` — exact rules Kimi K2.5 checks
- `kimi-model-choice.md` — why K2.5 specifically
- `character-bible-format.md` — bible JSON schema and behaviour
