# Critique criteria — what Kimi K2.5 checks

The critique pass is not "make this more cinematic." It applies a small,
finite set of film-grammar rules. Both transparency and verifiability
demanded that we publish the rules.

## The five rules

### 1. 180-degree line

Across consecutive shots showing the same characters, screen direction
must remain consistent. A character looking camera-right in shot 1B
must continue looking camera-right in 1C, **unless** the Scene's
`eye_line.axis_status` for that shot is explicitly marked
`CROSSED_LINE` or `NEW_AXIS`.

**Why it matters:** Audiences track characters by where they're pointing
in the frame. Crossing the line without a transition shot breaks
spatial continuity and confuses viewers about who is where.

### 2. Eye-line continuity

In shot-reverse-shot dialogue coverage, character A looking
`CAMERA_RIGHT` must be matched by character B looking `CAMERA_LEFT`,
and vice versa. Mismatches break coverage.

**Why it matters:** When A looks right at B, B must look back left at
A — that's how the brain reads "they're facing each other." If both
look the same direction, the audience suddenly thinks they're looking
at someone else off-screen.

### 3. Coverage

Every dialogue scene needs at minimum:
- one establishing shot (WIDE or TWO_SHOT),
- close coverage of each speaker (CLOSE_UP, MEDIUM, or OTS),
- at least one reaction shot.

Action scenes need:
- one establishing shot,
- pacing close-ups for each beat.

**Why it matters:** Missing coverage means the editor has no choice in
the cut. The director shouldn't be forced into a single edit by a thin
shot list.

### 4. Lens motivation

Lens choice tracks emotional intensity. Wider lenses for context, longer
lenses for tension and isolation. Arbitrary lens swings without
narrative reason are flagged. The lens-emotion mapping is in
`references/shot-grammar.md`.

**Why it matters:** A lens change is a punctuation mark. Changing for
no reason is like a comma in the middle of a word.

### 5. Pacing

Action shots should be 0.5-2 seconds. Dialogue shots 2-5 seconds.
Establishing shots can be longer. Mismatch between content and duration
is flagged.

**Why it matters:** A 6-second action close-up reads as slow. A 0.5-second
dialogue shot reads as a flashback. Match form to function.

## What the critique CANNOT do

The critique is intentionally narrow. It does **not**:

- judge subjective composition (golden ratio, color theory)
- second-guess the genre (noir vs neo-noir, etc.)
- propose new shots (only revisions to existing shots)
- alter `figures` or `shot_type` (those would change the scene's
  meaning, not its grammar)

The whitelist of fields a revision may touch:
`angle`, `lens`, `movement`, `duration`, `caption`,
`eye_line.direction`, `eye_line.axis_status`.

Anything else is dropped with a stderr warning.

## Anti-hallucination

Every revision Kimi produces is cross-checked against the Scene before
being applied:

- the `shot_label` must exist in `scene.shots`
- the `field` must be in the whitelist above
- the `new_value` must parse correctly for that field's type (e.g.
  enum values for `eye_line.direction`)

Failed checks drop the revision silently with a warning. We never
silently invent a shot or extend the schema based on Kimi output.
