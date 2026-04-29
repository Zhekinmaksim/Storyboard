"""Schematic figures with silhouette variation.

Each figure now varies its shape based on the silhouette string carried
by the Figure (or looked up in the character bible by role). This is
the visual proof of cross-scene character continuity: the detective in
scene 1 has the same coat-shape as the detective in scene 4.

Silhouette parsing is keyword-based. A silhouette like
"long coat, narrow shoulders, hat" maps to:
  - coat_length = long  (taller, thinner trapezoid)
  - shoulder_width = narrow (thinner top edge)
  - has_hat = True (small rectangle on top of head)

A silhouette like "broad, short coat, square" maps to:
  - coat_length = short
  - shoulder_width = broad (wider top edge)
  - has_square_head = True

Unknown silhouettes degrade to the default schematic figure. The
keyword set is small and finite — see SILHOUETTE_KEYWORDS below.
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.scene import Facing, Figure, Pose
from scripts.style import DRY_INK, STROKE
from scripts.templates.svg_primitives import circle, group, line, path, rect

BASE_H = 50.0


@dataclass(frozen=True)
class SilhouetteParams:
    """Parsed shape parameters derived from a silhouette description."""
    coat_length: float = 1.0       # 0.7=short, 1.0=default, 1.3=long
    shoulder_width: float = 1.0    # 0.7=narrow, 1.0=default, 1.3=broad
    bottom_width: float = 1.0      # how flared the coat is at the hem
    has_hat: bool = False
    has_square_head: bool = False
    is_silhouette_only: bool = False  # render as black silhouette w/ no head circle


def parse_silhouette(silhouette: str | None) -> SilhouetteParams:
    """Map a free-text silhouette description to render parameters.
    Returns defaults for empty/unknown silhouettes — never raises.
    """
    if not silhouette:
        return SilhouetteParams()
    s = silhouette.lower()

    coat_length = 1.0
    if any(kw in s for kw in ("long coat", "trench", "duster")):
        coat_length = 1.3
    elif any(kw in s for kw in ("short coat", "jacket", "vest")):
        coat_length = 0.75

    shoulder_width = 1.0
    if any(kw in s for kw in ("narrow", "thin", "slim", "slender")):
        shoulder_width = 0.7
    elif any(kw in s for kw in ("broad", "wide shoulders", "tactical", "muscular", "burly")):
        shoulder_width = 1.35

    bottom_width = 1.0
    if "flared" in s or "wide coat" in s:
        bottom_width = 1.25
    elif "tight" in s or "fitted" in s:
        bottom_width = 0.85

    has_hat = any(kw in s for kw in ("hat", "fedora", "trilby", "cap", "helmet"))
    has_square_head = any(kw in s for kw in ("square jaw", "square head", "blocky"))
    silhouette_only = any(kw in s for kw in ("silhouette", "shadow figure", "unseen"))

    return SilhouetteParams(
        coat_length=coat_length,
        shoulder_width=shoulder_width,
        bottom_width=bottom_width,
        has_hat=has_hat,
        has_square_head=has_square_head,
        is_silhouette_only=silhouette_only,
    )


def _coat(scale: float, params: SilhouetteParams) -> str:
    """Detective-style coat: trapezoidal silhouette flaring at the bottom.

    For long-coat tags we add a visible coat tail — a small triangular
    flap on the lower right edge that breaks the silhouette and reads
    as 'this figure is wearing a coat', not 'this figure is a stick'.
    """
    h = BASE_H * scale * params.coat_length
    half_w_top = 5 * scale * params.shoulder_width
    half_w_bot = 9 * scale * params.bottom_width
    head_r = 4 * scale

    # Body trapezoid
    body = path(
        f"M {-half_w_top:.2f} {head_r:.2f} "
        f"L {-half_w_bot:.2f} {h:.2f} "
        f"L {half_w_bot:.2f} {h:.2f} "
        f"L {half_w_top:.2f} {head_r:.2f} Z",
        fill=DRY_INK["fg"],
    )
    # For long coats, add a visible coat tail as a flapping wedge
    if params.coat_length >= 1.2:
        tail = path(
            f"M {half_w_bot:.2f} {h:.2f} "
            f"L {half_w_bot * 1.45:.2f} {h * 1.08:.2f} "
            f"L {half_w_bot * 0.92:.2f} {h * 1.05:.2f} Z",
            fill=DRY_INK["fg"],
        )
        return body + tail
    return body


def _threat_halo(scale: float, h: float) -> str:
    """A soft red shadow halo behind a silhouette-only figure.
    Reads as 'unknown threat' instantly — visually distinguishes the
    killer from the detective without any text label.
    """
    half_w = 14 * scale
    grad_id = f"halo_{int(scale * 100)}"
    return (
        f"<defs><radialGradient id='{grad_id}' cx='50%' cy='50%' r='50%'>"
        f"<stop offset='0%' stop-color='{DRY_INK['accent']}' stop-opacity='0.42'/>"
        f"<stop offset='70%' stop-color='{DRY_INK['accent']}' stop-opacity='0.06'/>"
        f"<stop offset='100%' stop-color='{DRY_INK['accent']}' stop-opacity='0'/>"
        f"</radialGradient></defs>"
        f"<ellipse cx='0' cy='{h * 0.45:.2f}' rx='{half_w * 1.5:.2f}' ry='{h * 0.6:.2f}' "
        f"fill='url(#{grad_id})'/>"
    )


def _hat(scale: float) -> str:
    """Small fedora silhouette atop the head."""
    head_r = 4 * scale
    return path(
        f"M {-head_r * 1.4:.2f} {-head_r:.2f} "
        f"L {-head_r * 1.4:.2f} {-head_r * 1.6:.2f} "
        f"L {head_r * 1.4:.2f} {-head_r * 1.6:.2f} "
        f"L {head_r * 1.4:.2f} {-head_r:.2f} "
        f"L {head_r * 1.8:.2f} {-head_r:.2f} "
        f"L {-head_r * 1.8:.2f} {-head_r:.2f} Z",
        fill=DRY_INK["fg"],
    )


def _legs_running(scale: float) -> str:
    h = BASE_H * scale
    return (
        line(0, h * 0.6, -8 * scale, h, stroke=DRY_INK["fg"], width=STROKE["medium"]) +
        line(0, h * 0.6, 8 * scale, h * 0.95, stroke=DRY_INK["fg"], width=STROKE["medium"])
    )


def _arms_out(scale: float, side: int = 1) -> str:
    h = BASE_H * scale
    return line(
        0, h * 0.35,
        12 * scale * side, h * 0.5,
        stroke=DRY_INK["fg"], width=STROKE["medium"],
    )


def render_figure(fig: Figure, frame_w: float, frame_h: float,
                  *, draw_in: float = 0.0, delay: float = 0.0,
                  silhouette: str | None = None) -> str:
    """Place a Figure in a frame.

    `silhouette` is an optional override (caller can pass a value from
    the character bible). If None, falls back to the figure's own
    `state` field, which may carry silhouette hints in v0.1.
    """
    cx = fig.position[0] * frame_w
    cy = fig.position[1] * frame_h
    sil_text = silhouette or fig.state or ""
    params = parse_silhouette(sil_text)
    body = _figure_body(fig, params)
    return group(
        body,
        transform=f"translate({cx:.2f}, {cy:.2f})",
        fade_in=draw_in,
        delay=delay,
    )


def _figure_body(fig: Figure, params: SilhouetteParams) -> str:
    s = max(fig.scale, 0.1)
    head_r = 4 * s

    # Silhouette-only figures are taller (suspense reads as threat
    # standing above) and get a soft accent halo behind them.
    if params.is_silhouette_only:
        s = s * 1.18
        head_r = 4 * s

    if fig.pose == Pose.FALLEN:
        return path(
            f"M {-32 * s:.2f} 0 "
            f"Q {-30 * s:.2f} {-3 * s:.2f} {-22 * s:.2f} {-3 * s:.2f} "
            f"L {22 * s:.2f} {-3 * s:.2f} "
            f"Q {30 * s:.2f} {-3 * s:.2f} {32 * s:.2f} 0 "
            f"L {28 * s:.2f} {5 * s:.2f} L {-28 * s:.2f} {5 * s:.2f} Z",
            fill=DRY_INK["fg"],
        )

    # Head: circle by default, square if silhouette tag says so
    if params.has_square_head:
        head = rect(-head_r, -head_r, head_r * 2, head_r * 2, fill=DRY_INK["fg"])
    else:
        head = circle(0, 0, head_r, fill=DRY_INK["fg"])

    # Optional hat
    accessory = _hat(s) if params.has_hat else ""

    # Threat halo first (back-most), then figure on top
    h = BASE_H * s * params.coat_length
    halo = _threat_halo(s, h) if params.is_silhouette_only else ""

    if fig.pose == Pose.RUNNING:
        return halo + head + accessory + _coat(s, params) + _legs_running(s)

    if fig.pose == Pose.KNEELING:
        h = BASE_H * s * 0.7 * params.coat_length
        return halo + head + accessory + path(
            f"M {-5 * s * params.shoulder_width:.2f} {head_r:.2f} "
            f"L {-9 * s * params.bottom_width:.2f} {h:.2f} "
            f"L {9 * s * params.bottom_width:.2f} {h:.2f} "
            f"L {5 * s * params.shoulder_width:.2f} {head_r:.2f} Z",
            fill=DRY_INK["fg"],
        )

    body = halo + head + accessory + _coat(s, params)
    if fig.pose == Pose.WALKING:
        body += _arms_out(s, side=1)
    return body


def render_face_close_up(facing: Facing, *, draw_in: float = 0.0, delay: float = 0.0,
                         silhouette: str | None = None) -> str:
    """Schematic face for CLOSE_UP shots. Silhouette can add a hat."""
    params = parse_silhouette(silhouette)
    out = (
        f"<ellipse cx='0' cy='0' rx='60' ry='80' "
        f"fill='none' stroke='{DRY_INK['fg']}' stroke-width='{STROKE['border']:.2f}'/>"
    )
    # Hair / hat curve on top — bigger and more prominent if hat tag set
    if params.has_hat:
        # Fedora-style brim across the forehead
        out += path(
            "M -85 -40 L -85 -55 L 85 -55 L 85 -40 Z",
            fill=DRY_INK["fg"],
        )
        # Hat crown
        out += path(
            "M -55 -55 L -55 -90 L 55 -90 L 55 -55 Z",
            fill=DRY_INK["fg"],
        )
    else:
        out += path("M -60 -30 Q 0 -100 60 -30", fill=DRY_INK["fg"])

    eye_x = {
        Facing.LEFT: -25,
        Facing.RIGHT: 25,
        Facing.FRONT: 0,
        Facing.THREE_QUARTER_LEFT: -15,
        Facing.THREE_QUARTER_RIGHT: 15,
        Facing.BACK: None,
    }.get(facing, 0)
    if eye_x is not None:
        out += circle(eye_x, 0, 6, fill="none", stroke=DRY_INK["accent"], stroke_width=STROKE["medium"])
        out += circle(eye_x, 0, 2, fill=DRY_INK["accent"])

    if draw_in > 0:
        return group(out, fade_in=draw_in, delay=delay)
    return out


__all__ = ["render_figure", "render_face_close_up", "parse_silhouette",
           "SilhouetteParams", "BASE_H"]
