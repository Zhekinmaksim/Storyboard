"""Parse prose scene descriptions into Scene JSON via Kimi K2.5.

Strategy:
1. Send a strict-JSON system prompt with the schema embedded.
2. Validate the response against Scene.from_dict — this catches enum
   typos, missing required fields, malformed positions.
3. If validation fails, retry once with the validation error message
   appended to the user prompt as feedback.
4. Two failures → raise ParseError. Caller can fall back to a stub Scene.
"""

from __future__ import annotations

import json
import re
import sys

from scripts.kimi_client import kimi_text
from scripts.scene import Scene


SYSTEM_PROMPT = """You are a senior film director's assistant. Your job is to convert prose
scene descriptions into structured shot lists for a storyboard.

Output STRICT, VALID JSON only. No markdown fences, no commentary.

Aim for 4–6 shots per scene, occasionally 7–8 for action sequences.

Use ONLY these canonical shot types:
WIDE, MEDIUM, CLOSE_UP, ECU, OTS, LOW_ANGLE, HIGH_ANGLE, TWO_SHOT, POV

Use ONLY these poses:
STANDING, RUNNING, FALLEN, KNEELING, SEATED, WALKING

Use ONLY these facing values:
FRONT, LEFT, RIGHT, BACK, THREE_QUARTER_LEFT, THREE_QUARTER_RIGHT

Use ONLY these eye-line directions (when present):
CAMERA_LEFT, CAMERA_RIGHT, INTO_CAMERA, OFFSCREEN_UP, OFFSCREEN_DOWN

Use ONLY these axis statuses (when present):
ON_AXIS, CROSSED_LINE, NEW_AXIS

Schema:
{
  "title": "string",
  "scene_number": "01",
  "location": "EXT alley · night",
  "director": "Zmaxx",
  "notes": "optional director note",
  "shots": [
    {
      "label": "1A",
      "shot_type": "WIDE",
      "description": "rain-soaked alley, lone figure",
      "lens": "24mm",
      "movement": "Static",
      "angle": "High (crane)",
      "duration": "0:00 – 0:06",
      "caption": "italic line under frame",
      "eye_line": null,
      "figures": [
        {
          "role": "detective",
          "pose": "STANDING",
          "facing": "FRONT",
          "position": [0.5, 0.7],
          "scale": 0.5,
          "state": "wet"
        }
      ],
      "environment": {
        "kind": "EXT",
        "description": "rain-soaked alley",
        "horizon_y": 0.55,
        "has_rain": true,
        "has_torchlight": false
      },
      "annotations": []
    }
  ]
}

Constraints:
- Position coordinates are normalised 0..1 inside the frame (x left→right, y top→bottom).
- Wide shots: figure scale 0.4–0.6. Medium: 0.9–1.2. Close: 2.0–3.0.
- For dialogue scenes, ALWAYS specify eye_line for CLOSE_UP and OTS shots.
- For action scenes, durations are 0:00–0:02 per shot. Dialogue: 0:00–0:05.
- Lens choice tracks emotional intensity: wider for context, longer for tension.
- Mark axis_status: NEW_AXIS only on intentional crossings. ON_AXIS by default.

Return ONLY the JSON object. No prose. No backticks."""


class ParseError(RuntimeError):
    """Raised when Kimi cannot produce a valid Scene after retries."""


def parse_prose(prose: str, *, use_cache: bool = True) -> Scene:
    """Convert prose to a Scene. Raises ParseError on persistent failure.

    Pulls in two sources of accumulated context:
      - DirectorMemory: style rules learned from prior user revisions
      - CharacterBible: silhouettes of named characters from prior scenes

    Both are concatenated as an addendum to the system prompt so the
    model sees them but the schema instructions stay primary.
    """
    # Lazy imports to avoid circular deps and keep parse.py importable
    # in environments without the bible/memory modules wired up.
    try:
        from scripts.character_bible import CharacterBible
        from scripts.director_memory import DirectorMemory
        bible = CharacterBible.load()
        memory = DirectorMemory.load()
        memory_hint = memory.hint_for_prompt(prose)
        bible_hint = bible.hint_for_prompt(prose)
        addendum = (memory_hint or "") + (bible_hint or "")
    except Exception as exc:
        # If memory/bible loading fails, parse still works — degrade gracefully
        print(f"[parse] memory/bible unavailable: {exc}", file=sys.stderr)
        addendum = ""

    effective_system = SYSTEM_PROMPT + addendum
    user_prompt = f"Scene description:\n\n{prose.strip()}\n\nReturn the Scene JSON."

    # First attempt
    try:
        raw = kimi_text(user_prompt, system=effective_system, use_cache=use_cache,
                        temperature=0.5, max_tokens=4000)
        return _parse_and_validate(raw)
    except (ValueError, KeyError, TypeError) as exc:
        # Retry with feedback
        print(f"[parse] first attempt failed: {exc}; retrying with feedback", file=sys.stderr)
        retry_prompt = (
            f"{user_prompt}\n\n"
            f"Your previous response failed validation with: {exc}\n"
            f"Return ONLY a valid JSON Scene object matching the schema exactly."
        )
        try:
            raw = kimi_text(retry_prompt, system=effective_system, use_cache=False,
                            temperature=0.3, max_tokens=4000)
            return _parse_and_validate(raw)
        except (ValueError, KeyError, TypeError) as exc2:
            raise ParseError(
                f"Kimi returned invalid Scene JSON after 2 attempts: {exc2}"
            ) from exc2


def _parse_and_validate(raw: str) -> Scene:
    """Strip any accidental markdown, parse JSON, build Scene with strict enums."""
    cleaned = _strip_codeblock(raw).strip()
    data = json.loads(cleaned)  # raises ValueError on bad JSON
    scene = Scene.from_dict(data)  # raises ValueError on bad enum
    _infer_atmospheric_flags(scene)
    return scene


# =================== Atmospheric inference ===================
# Kimi K2.5 fills in description fields, but rarely sets atmospheric flags
# explicitly. This pass reads each shot's description + environment.description
# and turns recognised keywords into has_neon / has_puddle / etc., so the
# renderer can lay down rich layers without a per-token Kimi roundtrip.

_NEON_TERMS = ("neon", "sign", "signage", "marquee", "led", "alley", "noir", "downtown")
_FIRE_ESCAPE_TERMS = ("fire escape", "metal stair", "iron stair", "scaffold", "alley")
_PUDDLE_TERMS = ("puddle", "rain", "wet ground", "reflection", "soaked")
_SHADOW_CONE_TERMS = ("streetlight", "lamp", "shadow", "torch", "lantern", "spotlight",
                     "alley", "night", "dim")
_RAIN_TERMS = ("rain", "rain-soaked", "downpour", "drizzle", "wet", "storm")
_WINDOW_TERMS = ("window", "panes", "blinds", "venetian")
_TABLE_TERMS = ("table", "desk", "counter", "kitchen")
_DOOR_TERMS = ("door", "doorway", "entrance", "threshold")
_STAIRWELL_TERMS = ("stairwell", "stairs", "stairway", "staircase", "landing",
                    "flights", "spiral", "steps")
_PROP_BODY = ("body", "corpse", "victim", "dead")
_PROP_PHONE = ("phone", "calls", "calling", "dispatch")
_PROP_KNIFE = ("knife", "weapon", "gun", "pistol")
_PROP_CUP = ("cup", "mug", "coffee", "tea", "glass")


def _has_any(text: str, terms) -> bool:
    t = text.lower()
    return any(term in t for term in terms)


def _infer_atmospheric_flags(scene) -> None:
    """Walk every shot, look at env+description, set rich-layer flags.
    Then propagate any flag that's true on ANY shot to ALL EXT shots
    (or all INT shots) — keeps the same scene visually consistent.

    Also sets default figure silhouettes for common roles so figures
    look distinct without Kimi having to specify it explicitly.
    """
    # Default silhouettes — keyed on lowercase role keyword
    ROLE_DEFAULTS = {
        "detective": "long coat, narrow shoulders, fedora",
        "noir detective": "long coat, narrow shoulders, fedora",
        "killer": "silhouette, tall, unseen",
        "threat": "silhouette, tall, unseen",
        "antagonist": "silhouette, tall, unseen",
        "samurai": "long coat, narrow shoulders",
        "victim": "fallen",
    }
    for shot in scene.shots:
        for fig in shot.figures:
            if fig.state and fig.state.strip():
                continue  # already specified
            role = (getattr(fig, "role", "") or "").lower()
            for keyword, default_silhouette in ROLE_DEFAULTS.items():
                if keyword in role:
                    fig.state = default_silhouette
                    break

    for shot in scene.shots:
        env = shot.environment
        ctx = (env.description + " " + shot.description + " " +
               (shot.caption or "")).lower()

        # Helper: given a flag name + matched keyword tuple, record source
        def _record(flag_name: str, keyword_set):
            for kw in keyword_set:
                if kw in ctx:
                    env.inferred_sources[flag_name] = f"prose:{kw}"
                    return True
            return False

        # Atmospheric layers — only set if Kimi didn't already
        if env.kind == "EXT":
            if not env.has_rain and _record("has_rain", _RAIN_TERMS):
                env.has_rain = True
            if not env.has_neon and _record("has_neon", _NEON_TERMS):
                env.has_neon = True
            if not env.has_fire_escape and _record("has_fire_escape", _FIRE_ESCAPE_TERMS):
                env.has_fire_escape = True
            if not env.has_puddle and (env.has_rain or _record("has_puddle", _PUDDLE_TERMS)):
                env.has_puddle = True
                if "has_puddle" not in env.inferred_sources and env.has_rain:
                    env.inferred_sources["has_puddle"] = "implied:rain"
            if not env.has_shadow_cone and _record("has_shadow_cone", _SHADOW_CONE_TERMS):
                env.has_shadow_cone = True
        else:  # INT
            if not env.has_window_grid and _record("has_window_grid", _WINDOW_TERMS):
                env.has_window_grid = True
            if not env.has_table and _record("has_table", _TABLE_TERMS):
                env.has_table = True
            if not env.has_door_frame and _record("has_door_frame", _DOOR_TERMS):
                env.has_door_frame = True
            if not env.has_stairwell and _record("has_stairwell", _STAIRWELL_TERMS):
                env.has_stairwell = True

        # Props — also tag source
        existing = set(env.props or [])
        prop_to_terms = [
            ("body", _PROP_BODY),
            ("phone", _PROP_PHONE),
            ("weapon", _PROP_KNIFE),
            ("cup", _PROP_CUP),
        ]
        for prop_name, terms in prop_to_terms:
            if prop_name not in existing:
                for kw in terms:
                    if kw in ctx:
                        existing.add(prop_name)
                        env.inferred_sources[f"prop:{prop_name}"] = f"prose:{kw}"
                        break
        env.props = sorted(existing)

    # ---- Scene-wide propagation ----
    # If ANY EXT shot has neon/fire/rain, all EXT shots in the same scene
    # share that vibe — keeps the visual world consistent across cuts.
    ext_has_neon = any(s.environment.has_neon for s in scene.shots
                       if s.environment.kind == "EXT")
    ext_has_fire = any(s.environment.has_fire_escape for s in scene.shots
                       if s.environment.kind == "EXT")
    ext_has_rain = any(s.environment.has_rain for s in scene.shots
                       if s.environment.kind == "EXT")
    ext_has_shadow = any(s.environment.has_shadow_cone for s in scene.shots
                         if s.environment.kind == "EXT")

    int_has_window = any(s.environment.has_window_grid for s in scene.shots
                         if s.environment.kind == "INT")
    int_has_table = any(s.environment.has_table for s in scene.shots
                        if s.environment.kind == "INT")
    int_has_stairwell = any(s.environment.has_stairwell for s in scene.shots
                            if s.environment.kind == "INT")

    for shot in scene.shots:
        env = shot.environment
        if env.kind == "EXT":
            env.has_neon = env.has_neon or ext_has_neon
            env.has_fire_escape = env.has_fire_escape or ext_has_fire
            env.has_rain = env.has_rain or ext_has_rain
            env.has_shadow_cone = env.has_shadow_cone or ext_has_shadow
            if env.has_rain and not env.has_puddle:
                env.has_puddle = True
        else:
            env.has_window_grid = env.has_window_grid or int_has_window
            env.has_table = env.has_table or int_has_table
            env.has_stairwell = env.has_stairwell or int_has_stairwell


_CODEBLOCK_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_codeblock(s: str) -> str:
    """Tolerate Kimi occasionally wrapping JSON in markdown despite instructions."""
    m = _CODEBLOCK_RE.match(s.strip())
    if m:
        return m.group(1)
    return s


def stub_scene(prose: str) -> Scene:
    """Fallback when Kimi cannot produce valid JSON. A single WIDE shot
    placeholder so the user has something to edit by hand instead of
    nothing.
    """
    return Scene.from_dict({
        "title": "Untitled (parse fallback)",
        "scene_number": "01",
        "location": "EXT · DAY",
        "director": "Zmaxx",
        "notes": f"Parse fallback. Original prose: {prose[:200]}",
        "shots": [{
            "label": "1A",
            "shot_type": "WIDE",
            "description": prose[:80],
            "lens": "35mm",
            "movement": "Static",
            "angle": "Eye level",
            "duration": "0:00 – 0:06",
            "caption": prose[:120],
            "figures": [{
                "role": "subject",
                "pose": "STANDING",
                "facing": "FRONT",
                "position": [0.5, 0.7],
                "scale": 0.6,
            }],
            "environment": {
                "kind": "EXT",
                "description": "scene",
                "horizon_y": 0.55,
            },
            "annotations": [],
        }],
    })


__all__ = ["parse_prose", "stub_scene", "ParseError", "SYSTEM_PROMPT"]
