# Learning loop demo — proof that memory changes future scenes

This bundle is the visual proof of the **director memory** feature. It
shows the same scene 2 prompt rendered two ways:

- **Cold:** generated with no memory active — Hermes has no idea how
  the user likes their suspense scenes.
- **Directed:** generated *after* the user issued a targeted revision
  on scene 1's frame 1F with the note `"more Hitchcock — low angle,
  harder shadow, killer as silhouette"`. Hermes extracted a generalised
  rule from that note, persisted it to `director_memory.json`, and
  injected it into the parse prompt for scene 2.

## What's in this directory

| File | What it is |
|------|-----------|
| `scene1.json` | Scene 1 (the noir alley, where the user revision happened) |
| `scene2.json` | Scene 2 prose: "Detective enters the stairwell. She listens. A killer is on the landing above. She draws her weapon. She climbs. He's gone." |
| `scene2-cold.json` | Scene 2 with **memory disabled** — eye-level, standard lens, killer rendered as a normal figure |
| `scene2-cold.png` | Render of the cold version |
| `scene2.png` | Render of the directed version (memory active) |
| `scene2.svg` / `scene2.animated.svg` | SVG sources, the animated one self-draws when opened |
| `cold-vs-directed.png` | **Side-by-side compare image — start here** |
| `director_memory.json` | The rule extracted from the user revision |
| `character_bible.json` | Detective Mara + The Killer silhouettes |

## Read the rule

Open `director_memory.json`. The rule was extracted by Kimi K2.5 from
the user's free-text revision note:

```json
{
  "preference": "For suspense, danger, and reveal moments, prefer
                 low-angle framing with stronger cast shadows. When
                 showing a threat or unseen antagonist, render them as
                 a partial silhouette rather than a fully-lit figure.",
  "applies_to": ["suspense", "reveal", "danger", "threat",
                 "killer entrance", "antagonist reveal", "stairwell",
                 "cornered", "pursuit"],
  "source_revision": {
    "scene": "01",
    "frame": "1F",
    "note": "more Hitchcock — low angle, harder shadow, killer as silhouette"
  }
}
```

## Compare the renders

Look at `cold-vs-directed.png`. Differences visible at a glance:

| Aspect | Cold (no memory) | Directed (memory active) |
|--------|------------------|--------------------------|
| Coverage chain | WIDE → MEDIUM → CLOSE → MEDIUM → MEDIUM → WIDE | WIDE → **LOW ANGLE** → CLOSE → **LOW ANGLE** → OTS → **LOW ANGLE** |
| Lens | all 35-50mm | varied: 24mm wide context, 85mm intimacy, 20mm low-angle |
| Detective figure | generic stick figure | silhouette from bible: long coat, narrow shoulders, fedora |
| Detective close-up | plain face | face **with fedora**, matching bible silhouette |
| Killer | normal medium shot | **silhouette only**, focus ring marked "THREAT", extreme low angle |
| Lighting | none | torchlight cones on suspense beats |

## How to reproduce

```bash
# Step 1: run scene 1, the user-driven Hitchcock revision
storyboard full "A detective enters a rain-soaked alley at night..."
storyboard revise scene.v2.json --frame 1F \
  --note "more Hitchcock — low angle, harder shadow, killer as silhouette"

# Step 2: check what Hermes learned
storyboard memory --show

# Step 3: run scene 2 — Hermes applies the rule automatically
storyboard full --stream "A detective enters the stairwell. She listens. \
  A killer is on the landing above. She draws her weapon. She climbs. \
  He's gone."

# Step 4: compare
storyboard view  # opens the live viewer; second scene reflects the rule
```

## Why this matters

Most AI tools treat each prompt as independent. Director memory is
what makes Hermes Storyboard **a director's assistant**, not a
prompt-to-image generator: it learns how *you* direct, persists that
knowledge, and applies it without being asked again.

This is the same loop pattern Hermes Painter uses for paint style
(stroke-by-stroke reflections → skill_promote → next run paints
differently). Storyboard does it for cinematic style — eye-line
choices, framing preferences, character silhouettes, mood lighting.
