# Noir scene — sample input prose

This is the input given to `storyboard full` to produce the artefacts
in this directory. Use it as a baseline for testing or a reference for
the kind of prose the skill works well on.

```
A detective enters a rain-soaked alley at night. He walks past silent
buildings, dispatch crackling in his ear. He finds a body. He kneels,
recognises the knot at the wrist — the same one as last week. He
straightens, calls his partner: "Marlowe. Third one this month."
```

## Run command

```bash
storyboard full --stream "A detective enters a rain-soaked alley at night..."
```

## What the pipeline produced

- `scene.json` — Kimi K2.5 parsed the prose into 6 shots (1A–1F) with
  full camera/lens/move/duration metadata.
- `board.svg` — static SVG render (used for PNG export and critique).
- `board.animated.svg` — same render but with SMIL stroke-draw
  animations on every primitive. **Open this in Firefox to see the
  board self-draw.**
- `board.png` — PNG export at 1400px wide.
- `revisions/round_1.json` — Kimi K2.5's critique output: two revisions
  flagged (1B movement, 1F lens) with film-grammar reasoning.
- `scene.v2.json` — scene after applying the revisions.
- `viewer-screenshot.png` — what the live viewer looks like mid-render.
- `character_bible.json` — persistent role memory. Detective + victim
  registered after this run; if you run a second scene referencing
  "detective", the bible silhouette is injected into the parse prompt.

## Reproducibility notes

The Kimi response cache is keyed on prompt sha256. To reproduce these
exact outputs, run with `--no-cache` if you want to hit the live API,
or copy the cached responses from `~/.cache/storyboard/` if you want
deterministic re-runs.

The `board.animated.svg` is the **demo asset**. It plays a ~9-second
stroke-by-stroke drawing sequence when opened in any modern browser
with SMIL support (Firefox, Safari).
