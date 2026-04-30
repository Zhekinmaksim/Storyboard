"""Scene data model — dataclasses and JSON round-tripping.

This is the contract between every stage of the pipeline: parse →
render → critique → iterate all speak Scene/Shot. Keeping it explicit
and validated makes Kimi failures cheap to detect.

The model intentionally over-specifies fields (lens, movement, angle,
duration, eye_line, axis_status). It's easier for the LLM to produce
structured fields than for the renderer to infer them, and the critique
pass needs them to check 180-degree line and eye-line continuity.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ShotType(str, Enum):
    WIDE = "WIDE"
    MEDIUM = "MEDIUM"
    CLOSE_UP = "CLOSE_UP"
    ECU = "ECU"           # extreme close up
    OTS = "OTS"           # over the shoulder
    LOW_ANGLE = "LOW_ANGLE"
    HIGH_ANGLE = "HIGH_ANGLE"
    TWO_SHOT = "TWO_SHOT"
    POV = "POV"


class Pose(str, Enum):
    STANDING = "STANDING"
    RUNNING = "RUNNING"
    FALLEN = "FALLEN"
    KNEELING = "KNEELING"
    SEATED = "SEATED"
    WALKING = "WALKING"


class Facing(str, Enum):
    FRONT = "FRONT"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    BACK = "BACK"
    THREE_QUARTER_LEFT = "THREE_QUARTER_LEFT"
    THREE_QUARTER_RIGHT = "THREE_QUARTER_RIGHT"


class EyeLineDirection(str, Enum):
    CAMERA_LEFT = "CAMERA_LEFT"
    CAMERA_RIGHT = "CAMERA_RIGHT"
    INTO_CAMERA = "INTO_CAMERA"
    OFFSCREEN_UP = "OFFSCREEN_UP"
    OFFSCREEN_DOWN = "OFFSCREEN_DOWN"


class AxisStatus(str, Enum):
    ON_AXIS = "ON_AXIS"
    CROSSED_LINE = "CROSSED_LINE"
    NEW_AXIS = "NEW_AXIS"


@dataclass
class Figure:
    role: str                                     # "detective", "victim", "partner"
    pose: Pose = Pose.STANDING
    facing: Facing = Facing.FRONT
    position: tuple[float, float] = (0.5, 0.7)    # normalised in frame, (x, y)
    scale: float = 1.0                            # 1.0 = baseline figure height
    state: str | None = None                      # "wet", "wounded", "tense"


@dataclass
class EyeLine:
    direction: EyeLineDirection
    target_label: str = ""                        # "→ shot 1C" or "→ off-screen"
    axis_status: AxisStatus = AxisStatus.ON_AXIS


@dataclass
class Environment:
    kind: str = "EXT"                             # EXT, INT
    description: str = ""                         # "rain-soaked alley", "warehouse"
    horizon_y: float = 0.55                       # normalised (0 = top, 1 = bottom)
    has_rain: bool = False
    has_torchlight: bool = False                  # the ONE allowed gradient
    # Atmospheric layers — added v0.2 to make boards less empty.
    # Inferred from prose/description in parse.py; can be overridden in JSON.
    has_neon: bool = False                        # neon sign on a building
    has_fire_escape: bool = False                 # external metal staircase
    has_puddle: bool = False                      # foreground puddle
    has_shadow_cone: bool = False                 # streetlight shadow cone
    has_window_grid: bool = False                 # window panes (interior or exterior)
    has_table: bool = False                       # foreground table (interior)
    has_door_frame: bool = False                  # doorway midground
    has_stairwell: bool = False                   # interior stairs (diagonal)
    has_subway: bool = False                      # subway platform / rail station
    visual_motif: str = ""                        # repeated scene sign, e.g. red threat halo
    motif_source: str = ""                        # why this motif was selected
    props: list[str] = field(default_factory=list)  # ['body', 'phone', 'lotus', 'cup']
    # Source provenance: {"has_neon": "prose:alley", "has_rain": "prose:downpour"}
    # Lets us tell users which features came from their text vs were
    # inferred from heuristics. Empty by default.
    inferred_sources: dict[str, str] = field(default_factory=dict)


@dataclass
class Annotation:
    """Director annotations drawn on the frame: arrows, focus rings, axis markers."""
    kind: str                                     # "eye_line", "focus_ring", "axis_marker", "movement_arrow"
    label: str = ""                               # short text shown beside marker
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Shot:
    label: str                                    # "1A", "1B", ...
    shot_type: ShotType
    description: str                              # one-liner for the shot
    lens: str = "35mm"
    movement: str = "Static"                      # "Dolly left", "Push in (slow)"
    angle: str = "Eye level"                      # "High (crane)", "Low"
    duration: str = "0:00 – 0:06"
    caption: str = ""                             # italic line under frame
    is_hero_frame: bool = False                   # one strongest standalone still per board
    visual_hook: str = ""                         # short reason for hero/share emphasis
    eye_line: EyeLine | None = None
    figures: list[Figure] = field(default_factory=list)
    environment: Environment = field(default_factory=Environment)
    annotations: list[Annotation] = field(default_factory=list)


@dataclass
class Scene:
    title: str
    scene_number: str = "01"
    location: str = "EXT · DAY"
    director: str = "Zmaxx"
    shots: list[Shot] = field(default_factory=list)
    notes: str = ""

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scene":
        """Build a Scene from a plain dict (e.g. parsed Kimi JSON).

        Tolerant of missing fields (uses dataclass defaults). Strict on
        enum values: an unknown ShotType raises ValueError, which the
        parse retry handler catches and feeds back to Kimi.
        """
        shots = [_shot_from_dict(s) for s in data.get("shots", [])]
        return cls(
            title=data.get("title", "Untitled Scene"),
            scene_number=str(data.get("scene_number", "01")),
            location=data.get("location", "EXT · DAY"),
            director=data.get("director", "Zmaxx"),
            shots=shots,
            notes=data.get("notes", ""),
        )


def _shot_from_dict(data: dict[str, Any]) -> Shot:
    figures = [_figure_from_dict(f) for f in data.get("figures", [])]
    env_data = data.get("environment") or {}
    env = Environment(
        kind=env_data.get("kind", "EXT"),
        description=env_data.get("description", ""),
        horizon_y=_float_or(env_data.get("horizon_y"), 0.55),
        has_rain=bool(env_data.get("has_rain", False)),
        has_torchlight=bool(env_data.get("has_torchlight", False)),
        has_neon=bool(env_data.get("has_neon", False)),
        has_fire_escape=bool(env_data.get("has_fire_escape", False)),
        has_puddle=bool(env_data.get("has_puddle", False)),
        has_shadow_cone=bool(env_data.get("has_shadow_cone", False)),
        has_window_grid=bool(env_data.get("has_window_grid", False)),
        has_table=bool(env_data.get("has_table", False)),
        has_door_frame=bool(env_data.get("has_door_frame", False)),
        has_stairwell=bool(env_data.get("has_stairwell", False)),
        has_subway=bool(env_data.get("has_subway", False)),
        visual_motif=str(env_data.get("visual_motif", "")),
        motif_source=str(env_data.get("motif_source", "")),
        props=list(env_data.get("props", [])),
        inferred_sources=dict(env_data.get("inferred_sources", {})),
    )
    eye_line = None
    if data.get("eye_line"):
        eye_line = _eye_line_from_dict(data["eye_line"])
    annotations = [
        Annotation(
            kind=a["kind"],
            label=a.get("label", ""),
            payload=a.get("payload", {}),
        )
        for a in data.get("annotations", [])
    ]
    return Shot(
        label=data["label"],
        shot_type=_coerce_shot_type(data["shot_type"]),
        description=data.get("description", ""),
        lens=data.get("lens", "35mm"),
        movement=data.get("movement", "Static"),
        angle=data.get("angle", "Eye level"),
        duration=data.get("duration", "0:00 – 0:06"),
        caption=data.get("caption", ""),
        is_hero_frame=bool(data.get("is_hero_frame", False)),
        visual_hook=str(data.get("visual_hook", "")),
        eye_line=eye_line,
        figures=figures,
        environment=env,
        annotations=annotations,
    )


def _eye_line_from_dict(data: Any) -> EyeLine:
    if isinstance(data, str):
        return EyeLine(direction=_coerce_eye_line_direction(data))
    if not isinstance(data, dict):
        raise ValueError(f"eye_line must be an object, string, or null; got {type(data).__name__}")
    return EyeLine(
        direction=_coerce_eye_line_direction(data["direction"]),
        target_label=data.get("target_label", ""),
        axis_status=_coerce_axis_status(data.get("axis_status", "ON_AXIS")),
    )


def _figure_from_dict(data: dict[str, Any]) -> Figure:
    pos = _position_or(data.get("position"), (0.5, 0.7))
    return Figure(
        role=data.get("role", "figure"),
        pose=_coerce_pose(data.get("pose", "STANDING")),
        facing=_coerce_facing(data.get("facing", "FRONT")),
        position=pos,
        scale=_float_or(data.get("scale"), 1.0),
        state=data.get("state"),
    )


def _float_or(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _position_or(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return default
    x = _float_or(value[0], default[0])
    y = _float_or(value[1], default[1])
    return (x, y)


def _canon(value: Any) -> str:
    return str(value).strip().upper().replace("-", "_").replace(" ", "_")


def _coerce_shot_type(value: Any) -> ShotType:
    aliases = {
        "CLOSEUP": "CLOSE_UP",
        "CLOSE": "CLOSE_UP",
        "CLOSE_UP_SHOT": "CLOSE_UP",
        "EXTREME_CLOSE_UP": "ECU",
        "OVER_THE_SHOULDER": "OTS",
        "OVER_SHOULDER": "OTS",
        "LOW": "LOW_ANGLE",
        "HIGH": "HIGH_ANGLE",
        "TWO": "TWO_SHOT",
        "LONG_LENS": "CLOSE_UP",
        "TELEPHOTO": "CLOSE_UP",
        "INSERT": "ECU",
        "DETAIL": "ECU",
        "DETAIL_SHOT": "ECU",
        "ESTABLISHING": "WIDE",
        "ESTABLISHING_SHOT": "WIDE",
        "TRACKING": "MEDIUM",
        "TRACKING_SHOT": "MEDIUM",
    }
    return ShotType(aliases.get(_canon(value), _canon(value)))


def _coerce_pose(value: Any) -> Pose:
    aliases = {
        "SITTING": "SEATED",
        "SIT": "SEATED",
        "SITS": "SEATED",
        "SAT": "SEATED",
        "STAND": "STANDING",
        "STANDS": "STANDING",
        "WALK": "WALKING",
        "WALKS": "WALKING",
        "RUN": "RUNNING",
        "RUNS": "RUNNING",
        "KNEEL": "KNEELING",
        "KNEELS": "KNEELING",
        "LYING": "FALLEN",
        "PRONE": "FALLEN",
    }
    return Pose(aliases.get(_canon(value), _canon(value)))


def _coerce_facing(value: Any) -> Facing:
    aliases = {
        "FORWARD": "FRONT",
        "FACING_FRONT": "FRONT",
        "CAMERA": "FRONT",
        "TOWARD_CAMERA": "FRONT",
        "TOWARDS_CAMERA": "FRONT",
        "THREE_QUARTER": "THREE_QUARTER_LEFT",
        "THREE_QUARTER_L": "THREE_QUARTER_LEFT",
        "THREE_QUARTER_R": "THREE_QUARTER_RIGHT",
    }
    return Facing(aliases.get(_canon(value), _canon(value)))


def _coerce_eye_line_direction(value: Any) -> EyeLineDirection:
    aliases = {
        "LEFT": "CAMERA_LEFT",
        "RIGHT": "CAMERA_RIGHT",
        "UP": "OFFSCREEN_UP",
        "DOWN": "OFFSCREEN_DOWN",
        "OFFSCREEN_LEFT": "CAMERA_LEFT",
        "OFFSCREEN_RIGHT": "CAMERA_RIGHT",
    }
    return EyeLineDirection(aliases.get(_canon(value), _canon(value)))


def _coerce_axis_status(value: Any) -> AxisStatus:
    aliases = {
        "ON": "ON_AXIS",
        "CROSSED": "CROSSED_LINE",
        "CROSSING": "CROSSED_LINE",
        "NEW": "NEW_AXIS",
    }
    return AxisStatus(aliases.get(_canon(value), _canon(value)))


__all__ = [
    "Scene", "Shot", "Figure", "Environment", "EyeLine", "Annotation",
    "ShotType", "Pose", "Facing", "EyeLineDirection", "AxisStatus",
]
