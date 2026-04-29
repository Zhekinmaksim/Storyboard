# Shot grammar

The canonical shot vocabulary the skill uses. Both Kimi (during parse)
and the renderer key off these; adding a new type requires changes in
`scene.py`, the parse system prompt, and the renderer's clip-path logic.

## Canonical types

| Type | Lens range | Frames | Used for |
|------|-----------|--------|----------|
| `WIDE` | 14-28mm | Establishing | Show place, scale, isolation. Figures small (0.4-0.6 scale). |
| `MEDIUM` | 35-50mm | Subject in context | Most dialogue and action coverage. Figures 0.9-1.2. |
| `CLOSE_UP` | 85-100mm | Single face | Recognition, decision moments. Schematic face primitive. |
| `ECU` | 100-200mm | Detail | A single eye, a clenched hand, the knot at the wrist. |
| `OTS` | 50-85mm | Reaction | Over-the-shoulder; the speaker's POV of the listener. |
| `LOW_ANGLE` | varies | Power, threat | Camera below eye level. Buildings/figures loom. |
| `HIGH_ANGLE` | varies | Vulnerability | Camera above eye level. Subject made small. |
| `TWO_SHOT` | 35-50mm | Two figures | Establishing relationship in a scene. |
| `POV` | varies | Subjective | What the character sees. Often paired with reaction shot. |

## When to use each

**Establishing flow** typically opens with WIDE or TWO_SHOT to anchor
geography, then drops to MEDIUM for dialogue, with CU/ECU for emotional
beats and OTS for reverse coverage.

**Action flow** uses tighter cuts: MEDIUM-WIDE → CU → MEDIUM → CU pattern
with shorter durations (0.5-2s per shot). Establishing shots can be
single-second flashes.

**Dialogue coverage** rule of thumb: every speaker needs at minimum a
TWO_SHOT (or MEDIUM) plus their own CLOSE_UP. Reaction shots come from
OTS or short CU on the listener.

## Shot label convention

Labels are scene-prefixed alphanumeric: `1A` `1B` `1C` ... within scene 1,
`2A` `2B` ... within scene 2. The label is preserved through every
pipeline stage. **Do not** change a shot's label across iterations —
revisions reference labels.

## Lens-emotion mapping (heuristic)

This is what Kimi K2.5 leans on for the lens-motivation critique. It is
*not* a hard rule — narrative beats can override it — but consistent
violations get flagged.

| Lens | Emotional register |
|------|--------------------|
| 14-24mm | Disorientation, scale, isolation in environment |
| 28-35mm | Naturalism, observational distance |
| 50mm | Default — neutral, "the camera is here" |
| 85mm | Intimacy, warmth, focused attention |
| 100mm+ | Compression, surveillance, detached observation |

Wide lenses isolate; long lenses compress. Use them deliberately.
