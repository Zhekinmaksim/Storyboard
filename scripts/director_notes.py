"""Deterministic mapper: free-text director note → concrete shot mutations.

This is the bridge between what the user types in the revise/refine UI
and what actually changes on the rendered frame. Without it, a note
like "more Hitchcock — low angle, harder shadow" only ever updated a
caption, which silently broke the project's main product promise:

    "Hermes learns how you direct."

The mapper is intentionally narrow. It recognises a small vocabulary
of directing intents and applies the corresponding visual changes.
Anything it doesn't recognise falls through unchanged — no hallucinated
mutations.

Recognised intents (case-insensitive substring match):

    Camera angle
        "low angle", "low-angle"            → angle="Low angle", LOW_ANGLE
        "high angle", "crane"               → angle="High angle"
        "eye level", "eyeline", "level"     → angle="Eye level"
        "extreme low"                       → angle="Extreme low"

    Lighting / shadow
        "harder shadow", "darker shadow",
        "hard shadow", "deeper shadow"      → shadow_cone + torchlight
        "neon"                              → has_neon = True

    Visibility / presence
        "silhouette only", "silhouette",
        "unseen", "obscured"                → fig.state += "silhouette only"

    Camera movement
        "push in", "dolly in"               → movement="Push in (slow)"
        "pull out", "dolly out"             → movement="Pull out"
        "static", "hold"                    → movement="Static"
        "tilt up"                           → movement="Tilt up"
        "rack focus"                        → movement="Rack focus"

    Style references (compound effects)
        "hitchcock"                         → 50mm + low angle + shadow
        "tarkovsky"                         → static + wider lens
        "fincher"                           → harder shadow + push in (slow)

    Lens
        "wider", "wide"                     → 24mm
        "tighter", "tight", "close"         → 85mm
        "telephoto", "long lens"            → 100mm

The mapper returns the count of recognised intents — useful for telling
the user which note keywords actually landed, and for telemetry. Zero
recognised intents is a legitimate outcome (note was too abstract); the
caller can fall back to a pure caption update in that case.
"""

from __future__ import annotations

import re

from scripts.scene import Scene, Shot, ShotType


def apply_director_note_to_shot(shot: Shot, note: str) -> int:
    """Apply a note to a single Shot. Returns count of intents matched."""
    n = note.lower()
    matched = 0

    # ---- Camera angle ----
    if re.search(r"\bextreme\s+low\b", n):
        shot.angle = "Extreme low"
        matched += 1
    elif "low angle" in n or "low-angle" in n:
        shot.angle = "Low angle"
        if shot.shot_type in (ShotType.WIDE, ShotType.MEDIUM):
            shot.shot_type = ShotType.LOW_ANGLE
        matched += 1
    elif "high angle" in n or "crane" in n:
        shot.angle = "High angle"
        if shot.shot_type in (ShotType.WIDE, ShotType.MEDIUM):
            shot.shot_type = ShotType.HIGH_ANGLE
        matched += 1
    elif "eye level" in n or "eye-level" in n:
        shot.angle = "Eye level"
        matched += 1

    # ---- Lighting / shadow ----
    shadow_terms = ("harder shadow", "darker shadow", "hard shadow",
                    "deeper shadow", "noir shadow")
    if any(t in n for t in shadow_terms):
        shot.environment.has_shadow_cone = True
        shot.environment.has_torchlight = True
        matched += 1

    if "neon" in n:
        shot.environment.has_neon = True
        matched += 1

    # ---- Visibility / silhouette ----
    if "silhouette" in n or "unseen" in n or "obscured" in n:
        # Mark every figure as silhouette-only
        for fig in shot.figures:
            tag = "silhouette only, unseen"
            if not fig.state:
                fig.state = tag
            elif "silhouette" not in fig.state:
                fig.state = (fig.state + ", " + tag).strip(", ")
        matched += 1

    # ---- Camera movement ----
    if "push in" in n or "dolly in" in n:
        shot.movement = "Push in (slow)"
        matched += 1
    elif "pull out" in n or "dolly out" in n:
        shot.movement = "Pull out"
        matched += 1
    elif re.search(r"\b(static|hold|locked)\b", n):
        shot.movement = "Static"
        matched += 1
    elif "tilt up" in n:
        shot.movement = "Tilt up"
        matched += 1
    elif "rack focus" in n:
        shot.movement = "Rack focus"
        matched += 1

    # ---- Lens ----
    if re.search(r"\bwider\b|\bwide-angle\b", n):
        shot.lens = "24mm"
        matched += 1
    elif "tighter" in n or "tight close" in n:
        shot.lens = "85mm"
        matched += 1
    elif "telephoto" in n or "long lens" in n:
        shot.lens = "100mm"
        matched += 1

    # ---- Style references (compound effects) ----
    if "hitchcock" in n:
        shot.lens = "50mm"
        shot.angle = "Low angle"
        shot.environment.has_shadow_cone = True
        shot.environment.has_torchlight = True
        matched += 1

    if "tarkovsky" in n:
        shot.movement = "Static"
        shot.lens = "35mm"
        matched += 1

    if "fincher" in n:
        shot.environment.has_shadow_cone = True
        shot.movement = "Push in (slow)"
        matched += 1

    return matched


def apply_director_note_to_scene(scene: Scene, note: str) -> int:
    """Apply note to ALL shots in the scene. Used for refine_scene path
    where the user gives a scene-level instruction like "make it darker".

    Returns total intent matches across all shots.
    """
    total = 0
    for shot in scene.shots:
        total += apply_director_note_to_shot(shot, note)
    return total


__all__ = ["apply_director_note_to_shot", "apply_director_note_to_scene"]
