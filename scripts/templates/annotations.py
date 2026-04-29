"""Director annotations — drawing-aware. Eye-line arrows, focus rings,
movement arrows, axis markers. All accept draw_in + delay.
"""

from __future__ import annotations

from scripts.scene import Annotation, EyeLine, EyeLineDirection
from scripts.style import DRY_INK, STROKE, TYPE
from scripts.templates.svg_primitives import circle, group, line, polygon, text


def render_eyeline(eye_line: EyeLine, frame_w: float, frame_h: float,
                   *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    cy = frame_h * 0.45
    if eye_line.direction == EyeLineDirection.CAMERA_LEFT:
        x_start, x_end = frame_w * 0.45, frame_w * 0.1
    elif eye_line.direction == EyeLineDirection.CAMERA_RIGHT:
        x_start, x_end = frame_w * 0.55, frame_w * 0.9
    elif eye_line.direction == EyeLineDirection.INTO_CAMERA:
        return group(
            line(frame_w * 0.4, frame_h * 0.4, frame_w * 0.5, frame_h * 0.6,
                 stroke=DRY_INK["accent"], width=STROKE["medium"], dash="3,3",
                 draw_in=draw_in, delay=delay),
            line(frame_w * 0.6, frame_h * 0.4, frame_w * 0.5, frame_h * 0.6,
                 stroke=DRY_INK["accent"], width=STROKE["medium"], dash="3,3",
                 draw_in=draw_in, delay=delay + 0.1),
        )
    elif eye_line.direction == EyeLineDirection.OFFSCREEN_UP:
        return line(frame_w * 0.5, frame_h * 0.4, frame_w * 0.5, 5,
                    stroke=DRY_INK["accent"], width=STROKE["medium"], dash="3,3",
                    draw_in=draw_in, delay=delay)
    else:  # OFFSCREEN_DOWN
        return line(frame_w * 0.5, frame_h * 0.6, frame_w * 0.5, frame_h - 5,
                    stroke=DRY_INK["accent"], width=STROKE["medium"], dash="3,3",
                    draw_in=draw_in, delay=delay)

    arrow = line(x_start, cy, x_end, cy, stroke=DRY_INK["accent"], width=STROKE["medium"], dash="4,3",
                 draw_in=draw_in, delay=delay)
    direction = -1 if x_end < x_start else 1
    head = polygon(
        [(x_end, cy), (x_end - 8 * direction, cy - 4), (x_end - 8 * direction, cy + 4)],
        fill=DRY_INK["accent"],
        draw_in=draw_in, delay=delay + (draw_in if draw_in > 0 else 0),
    )
    return arrow + head


def render_focus_ring(cx: float, cy: float, label: str = "FOCUS",
                      *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    return (
        circle(cx, cy, 14, fill="none", stroke=DRY_INK["accent"], stroke_width=STROKE["medium"],
               draw_in=draw_in, delay=delay) +
        line(cx - 4, cy, cx + 4, cy, stroke=DRY_INK["accent"], width=STROKE["medium"],
             draw_in=draw_in, delay=delay + 0.1) +
        line(cx, cy - 4, cx, cy + 4, stroke=DRY_INK["accent"], width=STROKE["medium"],
             draw_in=draw_in, delay=delay + 0.15) +
        text(cx + 22, cy + 4, label, font="mono", size=TYPE["label"], fill=DRY_INK["accent"],
             letter_spacing="0.1em", draw_in=draw_in, delay=delay + 0.3)
    )


def render_movement_arrow(label: str, frame_w: float, frame_h: float,
                          *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    label_l = label.lower()
    accent = DRY_INK["accent"]
    if "left" in label_l:
        return (
            line(frame_w - 10, frame_h - 14, 18, frame_h - 14,
                 stroke=accent, width=STROKE["medium"], dash="3,3",
                 draw_in=draw_in, delay=delay) +
            polygon([(18, frame_h - 14), (28, frame_h - 18), (28, frame_h - 10)],
                    fill=accent, draw_in=draw_in, delay=delay + 0.2)
        )
    if "right" in label_l:
        return (
            line(10, frame_h - 14, frame_w - 18, frame_h - 14,
                 stroke=accent, width=STROKE["medium"], dash="3,3",
                 draw_in=draw_in, delay=delay) +
            polygon([(frame_w - 18, frame_h - 14), (frame_w - 28, frame_h - 18),
                     (frame_w - 28, frame_h - 10)], fill=accent,
                    draw_in=draw_in, delay=delay + 0.2)
        )
    if "tilt up" in label_l or "crane up" in label_l:
        anchor_y = frame_h - 20
        return (
            line(20, anchor_y, 20, anchor_y - 36,
                 stroke=accent, width=STROKE["medium"], dash="3,3",
                 draw_in=draw_in, delay=delay) +
            polygon([(20, anchor_y - 36), (16, anchor_y - 28), (24, anchor_y - 28)],
                    fill=accent, draw_in=draw_in, delay=delay + 0.2) +
            text(28, anchor_y - 24, "TILT UP",
                 font="mono", size=TYPE["tiny"], fill=accent, letter_spacing="0.1em",
                 draw_in=draw_in, delay=delay + 0.3)
        )
    if "push" in label_l or "in" in label_l:
        return (
            line(8, frame_h - 8, 30, frame_h - 30,
                 stroke=accent, width=STROKE["medium"], dash="3,3",
                 draw_in=draw_in, delay=delay) +
            polygon([(30, frame_h - 30), (24, frame_h - 22), (32, frame_h - 22)],
                    fill=accent, draw_in=draw_in, delay=delay + 0.15) +
            text(38, frame_h - 22, "PUSH IN",
                 font="mono", size=TYPE["tiny"], fill=accent, letter_spacing="0.1em",
                 draw_in=draw_in, delay=delay + 0.25)
        )
    if "out" in label_l or "pull" in label_l:
        return (
            line(30, frame_h - 30, 8, frame_h - 8,
                 stroke=accent, width=STROKE["medium"], dash="3,3",
                 draw_in=draw_in, delay=delay) +
            polygon([(8, frame_h - 8), (16, frame_h - 8), (8, frame_h - 16)],
                    fill=accent, draw_in=draw_in, delay=delay + 0.15) +
            text(38, frame_h - 22, "PULL OUT",
                 font="mono", size=TYPE["tiny"], fill=accent, letter_spacing="0.1em",
                 draw_in=draw_in, delay=delay + 0.25)
        )
    return ""


def render_axis_marker(side: str, frame_w: float, frame_h: float,
                       *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    x = 12 if side.upper() == "A" else frame_w - 12
    return (
        line(x, frame_h - 4, x, frame_h - 14, stroke=DRY_INK["fg_dim"], width=STROKE["regular"],
             draw_in=draw_in, delay=delay) +
        text(x, frame_h + 8, f"AXIS {side.upper()}",
             font="mono", size=TYPE["tiny"], fill=DRY_INK["fg_dim"],
             anchor="middle", letter_spacing="0.1em",
             draw_in=draw_in, delay=delay + 0.1)
    )


def render_annotation(ann: Annotation, frame_w: float, frame_h: float,
                      *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    if ann.kind == "focus_ring":
        cx = float(ann.payload.get("x", 0.5)) * frame_w
        cy = float(ann.payload.get("y", 0.5)) * frame_h
        return render_focus_ring(cx, cy, ann.label or "FOCUS",
                                 draw_in=draw_in, delay=delay)
    if ann.kind == "axis_marker":
        return render_axis_marker(ann.payload.get("side", "A"), frame_w, frame_h,
                                  draw_in=draw_in, delay=delay)
    if ann.kind == "movement_arrow":
        return render_movement_arrow(ann.label, frame_w, frame_h,
                                     draw_in=draw_in, delay=delay)
    return ""


__all__ = [
    "render_eyeline", "render_focus_ring", "render_movement_arrow",
    "render_axis_marker", "render_annotation",
]
