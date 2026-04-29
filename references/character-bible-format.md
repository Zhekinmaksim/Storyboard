# Character bible format

The character bible is the skill's persistent memory across scenes —
the thing that lets Hermes look like it "remembers" the detective from
session to session. Stored at
`$STORYBOARD_OUTPUT_DIR/character_bible.json`.

## v0.1 schema (deliberately minimal)

```json
{
  "entries": {
    "detective": {
      "role": "detective",
      "display_name": "Detective Mara",
      "silhouette": "schematic figure, dripping coat outline, tight stance",
      "first_seen_scene": "01"
    },
    "partner": {
      "role": "partner",
      "display_name": "Marlowe",
      "silhouette": "schematic figure",
      "first_seen_scene": "01"
    }
  }
}
```

### Field meanings

- `role` — the canonical key. Lower-cased, slug-like. Same `role` value
  in two different scenes refers to the same character.
- `display_name` — what shows up in director notes and dialog captions.
  Defaults to title-cased role on first creation.
- `silhouette` — a short adjective phrase describing the character's
  visual shape and demeanour. Used **only** as context injection into
  the parse prompt for subsequent scenes — the renderer in v0.1 does
  not yet vary stick-figures by silhouette. See "v0.2 plans" below.
- `first_seen_scene` — the `scene_number` where the character first
  appeared. Useful for the user when reviewing the bible.

## How the bible flows through the pipeline

1. **`storyboard full <prose>`** loads the bible at the start of each run.
2. **Before the parse Kimi call**, the `hint_for_prompt(prose)` method
   scans the prose for any role names already in the bible. Matches are
   formatted as a short addendum to the parse system prompt:
   ```
   Known characters from previous scenes (preserve their identity and
   visual silhouette in figure roles and states):
   - "detective": schematic figure, dripping coat outline [first seen: scene 01]
   ```
   This nudges Kimi to reuse the role tag and silhouette state rather
   than inventing a new character.
3. **After parse**, `upsert_from_scene(scene)` adds any new roles found
   in the new Scene's figures to the bible and persists.

## Editing the bible

CLI:
```bash
storyboard bible --show
storyboard bible --set-silhouette "detective=narrow shoulders, wet coat"
```

Or open `$STORYBOARD_OUTPUT_DIR/character_bible.json` in any editor.
The JSON is human-readable and the entries dict is keyed on role.

## What the bible does NOT do (v0.1)

- It does not yet store dialog quirks or speech patterns. Scope creep.
- It does not yet vary figure rendering by silhouette tag. The renderer
  remains schematic stick-figures, which keeps reproductions
  deterministic.
- It does not version itself. Edits overwrite previous values. Use git
  if you want history.

## v0.2 plans

- Renderer variation: silhouette tags like "long coat" or "short" map
  to figure-template selection.
- Scene-locality: keep multiple bibles for unrelated projects so a
  detective in project A doesn't bleed into a sci-fi project B. Likely
  keyed on `--project <name>` or workdir.
- Conflict resolution: if a role's state changes between scenes
  (wet → dry, calm → wounded), the bible should accept the change
  rather than always preferring the first-seen value.
