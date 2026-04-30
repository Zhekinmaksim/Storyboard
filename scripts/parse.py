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

from scripts.kimi_client import KimiError, kimi_text
from scripts.scene import Scene


SYSTEM_PROMPT = """Convert prose into a compact six-shot storyboard JSON.

Return STRICT JSON only. No markdown, no commentary. Exactly 6 shots.

Allowed shot_type values:
WIDE, MEDIUM, CLOSE_UP, ECU, OTS, LOW_ANGLE, HIGH_ANGLE, TWO_SHOT, POV

Allowed eye_line direction values:
CAMERA_LEFT, CAMERA_RIGHT, INTO_CAMERA, OFFSCREEN_UP, OFFSCREEN_DOWN

Allowed pose values:
STANDING, RUNNING, FALLEN, KNEELING, SEATED, WALKING

Allowed facing values:
FRONT, LEFT, RIGHT, BACK, THREE_QUARTER_LEFT, THREE_QUARTER_RIGHT

Schema:
{
  "title": "short title",
  "scene_number": "01",
  "location": "INT/EXT place · time",
  "director": "Zmaxx",
  "notes": "one short note",
  "shots": [
    {
      "label": "1A",
      "shot_type": "WIDE",
      "description": "visual action in this frame",
      "lens": "24mm",
      "movement": "Static",
      "angle": "Eye level",
      "duration": "0:00 – 0:05",
      "caption": "short italic caption, max 9 words",
      "is_hero_frame": false,
      "visual_hook": "",
      "eye_line": null,
      "figures": [
        {
          "role": "detective",
          "pose": "STANDING",
          "facing": "FRONT",
          "position": [0.45, 0.70],
          "scale": 0.8,
          "state": "optional visual state"
        }
      ],
      "environment": {
        "kind": "EXT",
        "description": "rain-soaked alley",
        "horizon_y": 0.55,
        "has_rain": false,
        "has_table": false,
        "has_stairwell": false,
        "has_subway": false,
        "visual_motif": "",
        "motif_source": "",
        "props": []
      },
      "annotations": []
    }
  ]
}

Use labels 1A, 1B, 1C, 1D, 1E, 1F in order.
Use 1-2 figures per shot when people are visible.
Use normalized figure positions: x 0.15-0.85, y 0.35-0.82.
Use scale 0.45-1.15 for wide/medium shots and 1.6-2.4 for close-ups.
Use concise fields: no long prose.
Dialogue scenes should include CLOSE_UP or OTS with eye_line.
Exactly one shot must be marked is_hero_frame=true.
The hero frame must contain the strongest silhouette, threat, reveal, or visual metaphor.
It must be readable as a standalone still.
Captions must be cinematic, short, and memorable. Avoid generic prose and keep each caption under 9 words.
Return only the JSON object."""


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
        raw = kimi_text(
            user_prompt,
            system=effective_system,
            use_cache=use_cache,
            temperature=0.2,
            max_tokens=1600,
            timeout=10,
            retries=0,
            response_format={"type": "json_object"},
            reasoning={"effort": "none", "exclude": True},
        )
        return _parse_and_validate(raw)
    except KimiError as exc:
        raise ParseError(f"Kimi parse unavailable: {exc}") from exc
    except (ValueError, KeyError, TypeError) as exc:
        # Retry with feedback
        print(f"[parse] first attempt failed: {exc}; retrying with feedback", file=sys.stderr)
        retry_prompt = (
            f"{user_prompt}\n\n"
            f"Your previous response failed validation with: {exc}\n"
            f"Return ONLY a valid JSON Scene object matching the schema exactly."
        )
        try:
            raw = kimi_text(
                retry_prompt,
                system=effective_system,
                use_cache=False,
                temperature=0.1,
                max_tokens=1600,
                timeout=8,
                retries=0,
                response_format={"type": "json_object"},
                reasoning={"effort": "none", "exclude": True},
            )
            return _parse_and_validate(raw)
        except KimiError as exc2:
            raise ParseError(f"Kimi parse unavailable after validation retry: {exc2}") from exc2
        except (ValueError, KeyError, TypeError) as exc2:
            raise ParseError(
                f"Kimi returned invalid Scene JSON after 2 attempts: {exc2}"
            ) from exc2


def _parse_and_validate(raw: str) -> Scene:
    """Strip any accidental markdown, parse JSON, build Scene with strict enums."""
    cleaned = _strip_codeblock(raw).strip()
    data = json.loads(cleaned)  # raises ValueError on bad JSON
    scene = Scene.from_dict(data)  # raises ValueError on bad enum
    if len(scene.shots) != 6:
        raise ValueError(f"Scene must contain exactly 6 shots; got {len(scene.shots)}")
    for idx, shot in enumerate(scene.shots):
        shot.label = f"1{chr(ord('A') + idx)}"
    _infer_atmospheric_flags(scene)
    _quality_gate(scene)
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
_SUBWAY_TERMS = (
    "subway", "metro", "underground", "train station", "station platform",
    "platform", "tracks", "rail", "rails", "tunnel",
)
_PROP_BODY = ("body", "corpse", "victim", "dead")
_PROP_PHONE = ("phone", "calls", "calling", "dispatch")
_PROP_KNIFE = ("knife", "weapon", "gun", "pistol")
_PROP_CUP = ("cup", "mug", "coffee", "tea", "glass")
_PROP_TRAIN = ("train", "subway car", "carriage", "headlights", "roars")
_PROP_TRACKS = ("track", "tracks", "rail", "rails", "gap", "platform")
_PROP_TUNNEL = ("tunnel", "underground")
_PROP_SPARKS = ("bullet", "bullets", "gunfire", "ricochet", "spark", "sparks")
_PROP_SMOKE = ("smoke", "steam", "fog", "mist")
_PROP_COMPUTER = ("computer", "monitor", "screen", "terminal", "laptop")
_PROP_CAR = ("car", "taxi", "vehicle", "motorcycle", "truck")


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
        ctx = (scene.location + " " + env.description + " " + shot.description + " " +
               (shot.caption or "")).lower()
        local_ctx = (env.description + " " + shot.description + " " +
                     (shot.caption or "")).lower()

        # Helper: given a flag name + matched keyword tuple, record source
        def _record(flag_name: str, keyword_set, text: str = ctx):
            for kw in keyword_set:
                if kw in text:
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
            if not env.has_window_grid and _record("has_window_grid", _WINDOW_TERMS, local_ctx):
                env.has_window_grid = True
            if not env.has_table and _record("has_table", _TABLE_TERMS, local_ctx):
                env.has_table = True
            if not env.has_door_frame and _record("has_door_frame", _DOOR_TERMS, local_ctx):
                env.has_door_frame = True
            if not env.has_stairwell and _record("has_stairwell", _STAIRWELL_TERMS, local_ctx):
                env.has_stairwell = True
            if not env.has_subway and _record("has_subway", _SUBWAY_TERMS, local_ctx):
                env.has_subway = True

        # Props — also tag source
        existing = set(env.props or [])
        prop_to_terms = [
            ("body", _PROP_BODY),
            ("phone", _PROP_PHONE),
            ("weapon", _PROP_KNIFE),
            ("cup", _PROP_CUP),
            ("train", _PROP_TRAIN),
            ("tracks", _PROP_TRACKS),
            ("tunnel", _PROP_TUNNEL),
            ("sparks", _PROP_SPARKS),
            ("smoke", _PROP_SMOKE),
            ("computer", _PROP_COMPUTER),
            ("car", _PROP_CAR),
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
    int_has_stairwell = any(s.environment.has_stairwell for s in scene.shots
                            if s.environment.kind == "INT")
    int_has_subway = any(s.environment.has_subway for s in scene.shots
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
            env.has_stairwell = env.has_stairwell or int_has_stairwell
            env.has_subway = env.has_subway or int_has_subway


def _quality_gate(scene: Scene) -> None:
    """Deterministic pass for shareable boards: hero, motif, captions, coverage."""
    _assign_visual_motif(scene)
    _assign_single_hero_frame(scene)
    _enforce_shot_diversity(scene)
    _tighten_captions(scene)


def _assign_visual_motif(scene: Scene) -> None:
    text = " ".join(
        [scene.title, scene.location, scene.notes]
        + [s.description + " " + (s.caption or "") + " " + s.environment.description
           for s in scene.shots]
    ).lower()
    if any(term in text for term in ("subway", "train", "platform", "tracks", "tunnel")):
        motif = "track line / tunnel light"
        source = "deterministic:subway"
    elif any(term in text for term in ("stair", "landing", "above")):
        motif = "red threat halo"
        source = "deterministic:stairwell"
    elif any(term in text for term in ("kitchen", "table", "phone", "burger", "breakfast")):
        motif = "table edge / red phone mark"
        source = "deterministic:table"
    elif any(term in text for term in ("alley", "rain", "noir", "detective")):
        motif = "red neon reflection"
        source = "deterministic:noir"
    else:
        motif = "red focus mark"
        source = "deterministic:generic"
    for shot in scene.shots:
        if not shot.environment.visual_motif:
            shot.environment.visual_motif = motif
            shot.environment.motif_source = source


def _assign_single_hero_frame(scene: Scene) -> None:
    for shot in scene.shots:
        shot.is_hero_frame = False
    if not scene.shots:
        return
    hero_idx = len(scene.shots) - 1
    for i, shot in enumerate(scene.shots):
        ctx = f"{shot.description} {shot.caption} {shot.shot_type.value} {shot.angle}".lower()
        if any(term in ctx for term in (
            "reveal", "killer", "threat", "body", "gun", "weapon", "silhouette",
            "empty", "alone", "above", "explodes", "chaos",
        )):
            hero_idx = i
    hero = scene.shots[hero_idx]
    hero.is_hero_frame = True
    if not hero.visual_hook:
        hero.visual_hook = "standalone reveal / strongest visual beat"


def _enforce_shot_diversity(scene: Scene) -> None:
    if len(scene.shots) < 6:
        return
    from scripts.scene import ShotType
    shot_types = [ShotType.WIDE, ShotType.MEDIUM, ShotType.CLOSE_UP,
                  ShotType.OTS, ShotType.ECU, ShotType.WIDE]
    lenses = ["24mm", "35mm", "85mm", "50mm", "100mm", "28mm"]
    moves = ["Static", "Slow dolly in", "Static", "Handheld drift", "Push in", "Pull back"]
    angles = ["Eye level", "Slight low", "Eye level", "Low", "Top down", "Slight high"]
    if len({s.shot_type for s in scene.shots}) < 4:
        for shot, shot_type in zip(scene.shots, shot_types):
            shot.shot_type = shot_type
    if len({(s.angle or "").lower() for s in scene.shots}) < 3:
        for shot, angle in zip(scene.shots, angles):
            shot.angle = angle
    for shot, lens, move in zip(scene.shots, lenses, moves):
        if not shot.lens or shot.lens == "35mm":
            shot.lens = lens
        if not shot.movement or shot.movement == "Static":
            shot.movement = move


def _tighten_captions(scene: Scene) -> None:
    generic = {"walks", "looks", "sees", "stands", "enters", "moves", "goes"}
    for idx, shot in enumerate(scene.shots):
        words = [w.strip() for w in (shot.caption or shot.description).split() if w.strip()]
        if not words:
            shot.caption = _fallback_caption(idx)
            continue
        low = {w.lower().strip(".,;:!?\"'") for w in words}
        if len(words) > 9:
            words = words[:8] + ["..."]
        caption = " ".join(words)
        if len(words) <= 3 or low.intersection(generic):
            caption = _fallback_caption(idx)
        shot.caption = caption


def _fallback_caption(idx: int) -> str:
    beats = [
        "The room gives itself away.",
        "Nobody moves first.",
        "The silence picks a side.",
        "One detail changes everything.",
        "The threat enters the frame.",
        "The aftermath holds.",
    ]
    return beats[idx % len(beats)]


_CODEBLOCK_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_codeblock(s: str) -> str:
    """Tolerate Kimi occasionally wrapping JSON in markdown despite instructions."""
    m = _CODEBLOCK_RE.match(s.strip())
    if m:
        return m.group(1)
    return s


def stub_scene(prose: str) -> Scene:
    """Fallback when Kimi cannot produce valid JSON.

    Keep the public demo useful: generate a full six-shot deterministic
    board from the prose instead of leaving users with an error panel.
    """
    text = prose.strip()
    low = text.lower()
    is_int = any(term in low for term in ("kitchen", "room", "stairwell", "table", "interior"))
    is_stairwell = "stair" in low or "landing" in low
    is_kitchen = "kitchen" in low or "table" in low
    is_rain = any(term in low for term in ("rain", "alley", "night", "detective", "noir"))
    title = (
        "Kitchen confrontation" if is_kitchen else
        "The Stairwell" if is_stairwell else
        "The Rain Investigation" if is_rain else
        "Untitled scene"
    )
    location = (
        "INT KITCHEN · DAY" if is_kitchen else
        "INT STAIRWELL · NIGHT" if is_stairwell else
        "EXT ALLEY · NIGHT" if is_rain else
        ("INT · DAY" if is_int else "EXT · DAY")
    )
    env = {
        "kind": "INT" if is_int else "EXT",
        "description": "kitchen table" if is_kitchen else "dim stairwell" if is_stairwell else "rain-soaked alley" if is_rain else "scene",
        "horizon_y": 0.55,
        "has_rain": is_rain,
        "has_table": is_kitchen,
        "has_stairwell": is_stairwell,
        "has_shadow_cone": is_rain or is_stairwell,
        "has_puddle": is_rain,
        "props": ["phone"] if "phone" in low else [],
    }
    snippets = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    while len(snippets) < 6:
        snippets.append(snippets[-1] if snippets else "The scene holds.")
    shot_specs = [
        ("1A", "WIDE", "24mm", "Static", "Eye level", 0.45, 0.62),
        ("1B", "MEDIUM", "35mm", "Dolly left", "Eye level", 0.85, 0.64),
        ("1C", "CLOSE_UP", "50mm", "Static", "Eye level", 2.1, 0.52),
        ("1D", "OTS", "50mm", "Static", "Slight low", 1.0, 0.62),
        ("1E", "CLOSE_UP", "85mm", "Push in (slow)", "Profile", 2.2, 0.52),
        ("1F", "WIDE", "35mm", "Pull out", "Slight high", 0.55, 0.66),
    ]
    shots = []
    for idx, (label, shot_type, lens, move, angle, scale, y) in enumerate(shot_specs):
        shot = {
            "label": label,
            "shot_type": shot_type,
            "description": snippets[idx][:120],
            "lens": lens,
            "movement": move,
            "angle": angle,
            "duration": f"0:{idx * 5:02d} – 0:{idx * 5 + 5:02d}",
            "caption": snippets[idx][:120],
            "eye_line": "CAMERA_LEFT" if shot_type in ("CLOSE_UP", "OTS") else None,
            "figures": [{
                "role": "detective" if "detective" in low else "sibling" if is_kitchen else "subject",
                "pose": "SEATED" if is_kitchen and idx < 3 else "STANDING",
                "facing": "THREE_QUARTER_LEFT" if idx % 2 else "FRONT",
                "position": [0.38 + (idx % 3) * 0.12, y],
                "scale": scale,
            }],
            "environment": env,
            "annotations": [],
        }
        shots.append(shot)
    scene = Scene.from_dict({
        "title": title,
        "scene_number": "01",
        "location": location,
        "director": "Zmaxx",
        "notes": f"Parse fallback. Original prose: {prose[:200]}",
        "shots": shots,
    })
    _quality_gate(scene)
    return scene


__all__ = ["parse_prose", "stub_scene", "ParseError", "SYSTEM_PROMPT"]
