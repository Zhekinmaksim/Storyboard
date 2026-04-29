# Changelog

All notable changes to `storyboard` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow
[SemVer](https://semver.org/).

## [0.1.0] — 2026-05-03

### Added — initial release for Nous Hermes Agent Creative Hackathon

- **Skill manifest** (`SKILL.md`) in agentskills.io format, registers
  `/storyboard` slash command in Hermes Agent.
- **Director memory** (`scripts/director_memory.py`) — the learning
  loop. When a user issues a targeted revision with a free-text note
  (`storyboard revise --frame 1F --note "more Hitchcock..."`), Kimi
  K2.5 extracts a generalised director style rule and persists it to
  `director_memory.json`. The rule is injected into the parse system
  prompt for all subsequent scenes, so future scenes inherit the
  director's preference automatically. `storyboard memory --show`
  inspects, `--clear` resets.
- **Visual character silhouette rendering** — figures vary by
  silhouette tag from the character bible: long coat, narrow
  shoulders, broad shoulders, fedora hat, square head, silhouette-only.
  Detective in scene 1 is visibly the same person in scene 4. Includes
  silhouette-aware close-up faces (fedora rendered on close-up if
  bible says so).
- **Production packet exporter** (`scripts/packet.py`,
  `storyboard packet`) — auto-exports four files for the production
  team: `shotlist.csv` for scheduling, `camera_notes.md` for the DP /
  1st AC, `dialogue.md` extracting quoted speech by shot label,
  `continuity.md` for the script supervisor. Auto-runs at the end of
  `storyboard full`. Positions the skill as upstream pre-production
  layer.
- **End-to-end pipeline**: prose → parse (Kimi K2.5 text, with memory
  + bible hints) → enrich (Kimi K2.5 text, only when templates miss)
  → render → critique (Kimi K2.5 multimodal) → iterate → approval gate
  → packet export.
- **Live drawing animation**: SMIL stroke-dasharray on every primitive
  emits SVGs that self-draw when opened in a browser (~9 seconds for
  a 6-shot board). Two render modes: static (for PNG export) and
  animated (for viewer wow).
- **Streaming server** (`storyboard full --stream`): local HTTP server
  on port 7777 with EventSource at `/events`. Pushes scene skeleton,
  per-shot SVG fragments, critique start, and per-revision events to
  the live viewer. Pure stdlib (http.server + threading + queue), no
  fastapi/async dependencies.
- **Live viewer** with on-canvas critique pulses: when Kimi flags a
  frame, that frame's `<g data-shot-label>` element pulses with a
  red drop-shadow, visibly tying critique to the spot it applies.
- **Kimi-as-environment-renderer** (`enrich.py`): for shots that don't
  match template keywords (alley, room, kitchen, exterior, interior),
  Kimi generates schematic SVG fragments validated against tag/color/
  stroke-width whitelists. Failed validations fall back to templates.
- **Hybrid critique loop**: one auto-critique round, then user-gated
  approval; targeted single-frame revisions via
  `storyboard revise --frame N --note "..."`.
- **Dry Ink renderer**: pure Python SVG emitter with cream/warm ink/
  accent red palette, Newsreader serif + Geist Mono fonts, fixed
  stroke scale (0.4 / 0.5 / 0.8 / 1.0 / 1.5 / 2.0 / 2.5 / 3.0).
- **Six-shot 3×2 page layout** with header (title, director, scene
  info), per-frame metadata strip (LENS / MOVE / ANGLE / DURATION),
  italic captions, and footer with coverage chain.
- **Shot type primitives**: WIDE, MEDIUM, CLOSE_UP (schematic face),
  ECU, OTS, LOW_ANGLE, HIGH_ANGLE, TWO_SHOT, POV.
- **Annotation primitives**: eye-line arrows, focus rings with cross-
  marks, movement arrows (push in, pull out, dolly left/right, tilt
  up), axis markers (180° tracking), torchlight cones (only allowed
  gradient).
- **Character bible** with persistent silhouette memory injected into
  parse prompts AND visually applied at render time.
- **HTML viewer**: single-file static page with side-by-side draft vs.
  critiqued board, revisions panel, character bible panel, download
  buttons. Self-contained, no external assets.
- **Anti-hallucination guards**: critique revisions are filtered against
  scene shot labels and a finite field whitelist (lens, movement,
  angle, duration, caption, eye_line.direction, eye_line.axis_status).
- **Response cache**: Kimi calls keyed on payload sha256, cached at
  `~/.cache/storyboard/`. Bypass with `--no-cache`.
- **Stub fallback**: if Kimi fails to produce valid Scene JSON twice,
  emit a stub single-shot Scene the user can edit by hand.
- **CLI** with subcommands: `full` (with `--stream` and `--skip-enrich`
  flags), `parse`, `render`, `critique`, `iterate`, `revise`
  (with `--no-memory` flag), `view`, `bible`, `memory`, `packet`.
- **Smoke tests** (33 deterministic, no Kimi calls): scene round-trip,
  render with/without animation, single-shot render, iterate,
  critique guards, enrich validation, silhouette parsing, director
  memory round-trip + tag matching + recency fallback, packet
  generation, dialogue extraction.
- **Integration tests** (live Kimi, skipped without
  `OPENROUTER_API_KEY`).
- **Reference docs**: shot grammar, critique criteria, Kimi model
  choice rationale, character bible format, Dry Ink style bible.
- **Reproducible example bundles** for judges to inspect without
  running code:
  - `examples/output/noir-run/` — full pipeline run for the noir scene
    (input prose, scene JSON, both static and animated SVG, PNG, Kimi
    critique JSON, post-critique v2 scene, character bible, viewer
    screenshot, full production packet).
  - `examples/output/learning-demo/` — the cold-vs-directed proof:
    scene 2 rendered both with no memory active and with the rule from
    a hypothetical scene-1 user revision. Side-by-side compare image
    documents the difference.
- **Animation snapshots**: `examples/pocs/anim-frame-{1.5,4,7,9}s.png`
  document the live-drawing sequence at four timestamps.
- **Live-drawing GIF**: `examples/pocs/live-drawing.gif` (~90KB) for
  README hero image.
- **Silhouette variation showcase**:
  `examples/pocs/silhouette-variation.png` shows two distinct
  characters in the same scene rendered from their bible silhouettes.
- **`make judge-demo`** and **`make judge-demo-offline`** — one-command
  evaluation paths for hackathon judges. Offline path renders the
  shipped example with no API call needed.

### Known limits in v0.1

- One page, six shots maximum. Multi-page boards in v0.2.
- Director memory rule extraction depends on Kimi K2.5 returning
  valid JSON. On extraction failure, the raw user note is stored
  as a free-text rule; still usable for prompt injection but less
  precisely tagged.
- Critique cannot propose new shots, only revise existing ones.
- Approval gate is CLI-driven; future versions may have a web/Hermes
  inline UI.
- Kimi env-renderer (enrich) drops occasionally on validation failures;
  this is by design (template fallback) but means some prompts produce
  template environments that don't perfectly match the description.
- SMIL animation requires a browser with SMIL support (Firefox, Safari
  fully; Chrome works but officially deprecated). Demo recording uses
  Firefox.
