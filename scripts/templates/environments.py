"""Environment primitives. Schematic buildings, ground hatching, rain,
neon signs, fire escapes, puddles, shadow cones, interior windows, props.

Each piece can carry its own animation delay, so during a stagger the
hatching draws after the buildings, the rain after the hatching, etc.
"""

from __future__ import annotations

from scripts.scene import Environment
from scripts.style import DRY_INK, STROKE
from scripts.templates.svg_primitives import group, line, path, rect, text


def render_environment(env: Environment, frame_w: float, frame_h: float,
                       *, draw_in: float = 0.0, delay: float = 0.0,
                       stagger: float = 0.05) -> str:
    """Compose env layers in back-to-front order.

    Order matters: ground hatching first (under everything), then back
    architecture, then mid-ground props, then atmospheric overlays
    (rain, shadow cones, neon glow). Foreground props go last so they
    visually pop.
    """
    parts: list[str] = []
    horizon_y = env.horizon_y * frame_h
    cur_delay = delay

    # 1. Ground hatching — always
    parts.append(_ground_hatching(
        frame_w, frame_h, horizon_y,
        intensity=0.4 if env.kind == "EXT" else 0.2,
        draw_in=draw_in, delay=cur_delay,
    ))
    cur_delay += stagger

    # 2. Architecture — back layer
    if env.kind == "EXT" and env.horizon_y <= 0.58:
        parts.append(_building_left(frame_h, horizon_y, draw_in=draw_in, delay=cur_delay))
        cur_delay += stagger
        parts.append(_building_right(frame_w, frame_h, horizon_y, draw_in=draw_in, delay=cur_delay))
        cur_delay += stagger
        if env.has_fire_escape:
            parts.append(_fire_escape(frame_w, frame_h, horizon_y,
                                      draw_in=draw_in, delay=cur_delay))
            cur_delay += stagger
        if env.has_neon:
            parts.append(_neon_sign(frame_w, frame_h, horizon_y,
                                    draw_in=draw_in, delay=cur_delay))
            cur_delay += stagger
    elif env.kind == "EXT":
        parts.append(line(0, horizon_y, frame_w, horizon_y,
                          stroke=DRY_INK["fg_dim"], width=0.6, opacity=0.5,
                          draw_in=draw_in, delay=cur_delay))
        cur_delay += stagger

    # 2b. Interior architecture
    if env.kind == "INT":
        if env.has_stairwell:
            parts.append(_stairwell(frame_w, frame_h, horizon_y,
                                    draw_in=draw_in, delay=cur_delay))
            cur_delay += stagger
        if env.has_window_grid:
            parts.append(_window_grid(frame_w, frame_h, horizon_y,
                                      draw_in=draw_in, delay=cur_delay))
            cur_delay += stagger
        if env.has_door_frame:
            parts.append(_door_frame(frame_w, frame_h, horizon_y,
                                     draw_in=draw_in, delay=cur_delay))
            cur_delay += stagger
        if env.has_table:
            parts.append(_table(frame_w, frame_h, draw_in=draw_in, delay=cur_delay))
            cur_delay += stagger

    # 3. Atmospheric — overlays
    if env.has_shadow_cone:
        parts.append(_shadow_cone(frame_w, frame_h, horizon_y,
                                  draw_in=draw_in, delay=cur_delay))
        cur_delay += stagger
    if env.has_rain:
        parts.append(_rain(frame_w, horizon_y, draw_in=draw_in, delay=cur_delay))
        cur_delay += stagger
    if env.has_puddle and env.kind == "EXT":
        parts.append(_puddle(frame_w, frame_h, horizon_y,
                             draw_in=draw_in, delay=cur_delay))
        cur_delay += stagger

    if env.has_torchlight:
        parts.append(_torchlight(frame_w * 0.5, horizon_y))

    # 4. Foreground props — pop above environment
    for prop in (env.props or []):
        rendered = _prop(prop, frame_w, frame_h, horizon_y,
                         draw_in=draw_in, delay=cur_delay)
        if rendered:
            parts.append(rendered)
            cur_delay += stagger

    return "".join(parts)


def _ground_hatching(w: float, h: float, horizon_y: float, *,
                     intensity: float = 0.4,
                     draw_in: float = 0.0, delay: float = 0.0) -> str:
    if horizon_y >= h:
        return ""
    span = h - horizon_y
    parts = []
    n = 5
    for i in range(1, n + 1):
        y = horizon_y + (span * i / (n + 1))
        # tiny per-line stagger for that "ink hatching" feel
        line_delay = delay + (i * 0.04 if draw_in > 0 else 0)
        parts.append(line(
            0, y, w, y,
            stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=intensity,
            draw_in=draw_in, delay=line_delay,
        ))
    return group(*parts)


def _building_left(frame_h: float, horizon_y: float,
                   *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    top = horizon_y * 0.15
    return path(
        f"M 0 {horizon_y:.2f} "
        f"L 0 {top:.2f} "
        f"L 50 {top:.2f} "
        f"L 50 {top - 10:.2f} "
        f"L 90 {top - 10:.2f} "
        f"L 90 {top + 15:.2f} "
        f"L 130 {top + 15:.2f} "
        f"L 130 {horizon_y:.2f} Z",
        fill=DRY_INK["fg"],
        draw_in=draw_in, delay=delay,
    )


def _building_right(w: float, frame_h: float, horizon_y: float,
                    *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    top = horizon_y * 0.1
    return path(
        f"M {w:.2f} {horizon_y:.2f} "
        f"L {w:.2f} {top:.2f} "
        f"L {w - 60:.2f} {top:.2f} "
        f"L {w - 60:.2f} {top - 12:.2f} "
        f"L {w - 110:.2f} {top - 12:.2f} "
        f"L {w - 110:.2f} {top + 20:.2f} "
        f"L {w - 160:.2f} {top + 20:.2f} "
        f"L {w - 160:.2f} {horizon_y:.2f} Z",
        fill=DRY_INK["fg"],
        draw_in=draw_in, delay=delay,
    )


def _rain(w: float, horizon_y: float,
          *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    parts = []
    bands = [(0, 8), (max(horizon_y * 0.4, 30), 6)]
    xs_offsets = [50, 120, 180, 230, 290, 360, 430]
    i = 0
    for y_start, count in bands:
        for x in xs_offsets[:count]:
            x_actual = (x * (w / 460))
            parts.append(line(
                x_actual, y_start,
                x_actual - 4, y_start + 22,
                stroke=DRY_INK["fg"], width=STROKE["medium"], opacity=0.55,
                draw_in=draw_in, delay=delay + (i * 0.025 if draw_in > 0 else 0),
            ))
            i += 1
    return group(*parts)


def _torchlight(cx: float, cy: float) -> str:
    grad_id = f"torch_{int(cx)}_{int(cy)}"
    return (
        f"<defs><radialGradient id='{grad_id}' cx='50%' cy='50%' r='50%'>"
        f"<stop offset='0%' stop-color='{DRY_INK['accent']}' stop-opacity='0.35'/>"
        f"<stop offset='70%' stop-color='{DRY_INK['fg']}' stop-opacity='0.05'/>"
        f"<stop offset='100%' stop-color='{DRY_INK['fg']}' stop-opacity='0'/>"
        f"</radialGradient></defs>"
        f"<circle cx='{cx:.2f}' cy='{cy:.2f}' r='80' fill='url(#{grad_id})'/>"
    )


def _fire_escape(w: float, h: float, horizon_y: float,
                 *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    """Diagonal zigzag metal staircase on the right building's facade."""
    base_x = w - 110
    top_y = horizon_y * 0.18
    bot_y = horizon_y - 4
    steps = 4
    parts = []
    # Vertical rails
    for rx in (base_x + 6, base_x + 32):
        parts.append(line(rx, top_y, rx, bot_y,
                          stroke=DRY_INK["bg"], width=STROKE["thin"], opacity=0.85,
                          draw_in=draw_in, delay=delay))
    # Zigzag steps
    for i in range(steps):
        t = i / steps
        y = top_y + (bot_y - top_y) * t
        y2 = top_y + (bot_y - top_y) * ((i + 0.5) / steps)
        if i % 2 == 0:
            parts.append(line(base_x + 6, y, base_x + 32, y2,
                              stroke=DRY_INK["bg"], width=STROKE["thin"], opacity=0.85,
                              draw_in=draw_in, delay=delay + i * 0.02))
        else:
            parts.append(line(base_x + 32, y, base_x + 6, y2,
                              stroke=DRY_INK["bg"], width=STROKE["thin"], opacity=0.85,
                              draw_in=draw_in, delay=delay + i * 0.02))
    return group(*parts)


def _neon_sign(w: float, h: float, horizon_y: float,
               *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    """Vertical neon sign hanging off the left building facade."""
    sign_x = 142
    sign_top = horizon_y * 0.22
    sign_h = 50
    sign_w = 14
    parts = []
    parts.append(rect(sign_x, sign_top, sign_w, sign_h,
                      fill="none", stroke=DRY_INK["accent"],
                      stroke_width=STROKE["medium"], opacity=0.9,
                      draw_in=draw_in, delay=delay))
    # Inner glow strokes — three vertical lines
    for i, y_off in enumerate((10, 22, 34)):
        parts.append(line(sign_x + 4, sign_top + y_off,
                          sign_x + sign_w - 4, sign_top + y_off,
                          stroke=DRY_INK["accent"], width=STROKE["thin"],
                          opacity=0.7,
                          draw_in=draw_in, delay=delay + i * 0.03))
    # Mounting bracket
    parts.append(line(sign_x + sign_w / 2, sign_top, sign_x + sign_w / 2, sign_top - 8,
                      stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.7,
                      draw_in=draw_in, delay=delay))
    return group(*parts)


def _puddle(w: float, h: float, horizon_y: float,
            *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    """Reflective puddle in foreground — a flattened ellipse with hatch lines."""
    cx = w * 0.32
    cy = horizon_y + (h - horizon_y) * 0.55
    rx = 38
    ry = 7
    parts = []
    # Outline
    parts.append(path(
        f"M {cx - rx} {cy} "
        f"Q {cx} {cy - ry * 1.3} {cx + rx} {cy} "
        f"Q {cx} {cy + ry * 0.8} {cx - rx} {cy} Z",
        fill="none", stroke=DRY_INK["fg"], stroke_width=STROKE["thin"],
        opacity=0.7,
        draw_in=draw_in, delay=delay,
    ))
    # Reflection hatch — short horizontal lines inside
    for i, dy in enumerate((-2, 0, 2)):
        parts.append(line(cx - rx * 0.6, cy + dy, cx + rx * 0.6, cy + dy,
                          stroke=DRY_INK["fg"], width=STROKE["thin"],
                          opacity=0.35,
                          draw_in=draw_in, delay=delay + i * 0.04))
    return group(*parts)


def _shadow_cone(w: float, h: float, horizon_y: float,
                 *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    """Streetlight shadow cone — light source upper area, cone fans down/right."""
    src_x = w * 0.72
    src_y = horizon_y * 0.35
    # Cone fans toward the ground
    left_x = src_x - 20
    right_x = src_x + 60
    bot_y = horizon_y + (h - horizon_y) * 0.4
    grad_id = f"cone_{int(src_x)}"
    # Soft cone fill via gradient
    defs = (
        f"<defs><linearGradient id='{grad_id}' x1='50%' y1='0%' x2='50%' y2='100%'>"
        f"<stop offset='0%' stop-color='{DRY_INK['accent']}' stop-opacity='0.18'/>"
        f"<stop offset='100%' stop-color='{DRY_INK['accent']}' stop-opacity='0'/>"
        f"</linearGradient></defs>"
    )
    cone = (
        f"<polygon points='{src_x:.1f},{src_y:.1f} "
        f"{left_x:.1f},{bot_y:.1f} {right_x:.1f},{bot_y:.1f}' "
        f"fill='url(#{grad_id})'/>"
    )
    # Cone outline (very faint)
    outline_parts = [
        line(src_x, src_y, left_x, bot_y,
             stroke=DRY_INK["accent"], width=STROKE["thin"], opacity=0.35,
             draw_in=draw_in, delay=delay),
        line(src_x, src_y, right_x, bot_y,
             stroke=DRY_INK["accent"], width=STROKE["thin"], opacity=0.35,
             draw_in=draw_in, delay=delay),
    ]
    # Tiny streetlight glyph at source
    src = circle_glyph(src_x, src_y, 3, color=DRY_INK["accent"])
    return defs + cone + "".join(outline_parts) + src


def circle_glyph(cx: float, cy: float, r: float, *, color: str = "#000") -> str:
    return f"<circle cx='{cx:.2f}' cy='{cy:.2f}' r='{r:.2f}' fill='{color}'/>"


def _window_grid(w: float, h: float, horizon_y: float,
                 *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    """Interior wall window — a 2x3 panes grid on the back wall."""
    win_x = w * 0.62
    win_y = horizon_y * 0.25
    win_w = w * 0.28
    win_h = horizon_y * 0.45
    parts = []
    parts.append(rect(win_x, win_y, win_w, win_h,
                      fill="none", stroke=DRY_INK["fg"], stroke_width=STROKE["thin"],
                      opacity=0.7,
                      draw_in=draw_in, delay=delay))
    # 2 vertical mullions, 1 horizontal
    parts.append(line(win_x + win_w / 3, win_y, win_x + win_w / 3, win_y + win_h,
                      stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.7,
                      draw_in=draw_in, delay=delay))
    parts.append(line(win_x + win_w * 2 / 3, win_y, win_x + win_w * 2 / 3, win_y + win_h,
                      stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.7,
                      draw_in=draw_in, delay=delay))
    parts.append(line(win_x, win_y + win_h / 2, win_x + win_w, win_y + win_h / 2,
                      stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.7,
                      draw_in=draw_in, delay=delay))
    return group(*parts)


def _door_frame(w: float, h: float, horizon_y: float,
                *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    """Doorway in midground — vertical frame on left side."""
    door_x = w * 0.08
    door_y = horizon_y * 0.20
    door_w = 38
    door_h = horizon_y * 0.7
    parts = []
    parts.append(line(door_x, door_y, door_x, door_y + door_h,
                      stroke=DRY_INK["fg"], width=STROKE["medium"],
                      draw_in=draw_in, delay=delay))
    parts.append(line(door_x + door_w, door_y, door_x + door_w, door_y + door_h,
                      stroke=DRY_INK["fg"], width=STROKE["medium"],
                      draw_in=draw_in, delay=delay))
    parts.append(line(door_x, door_y, door_x + door_w, door_y,
                      stroke=DRY_INK["fg"], width=STROKE["medium"],
                      draw_in=draw_in, delay=delay))
    return group(*parts)


def _stairwell(w: float, h: float, horizon_y: float,
               *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    """Diagonal stairwell with steps + railing + landing line.

    Reads as: stairs going up-right, with handrail running parallel.
    Most explicit interior cinematic location after a featureless room.
    """
    # Stair angle: roughly 35° going up-right
    base_x = w * 0.18
    base_y = h * 0.78
    top_x = w * 0.65
    top_y = h * 0.28
    n_steps = 8
    parts = []

    # Underside diagonal (the slope itself)
    parts.append(line(base_x, base_y, top_x, top_y,
                      stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.6,
                      draw_in=draw_in, delay=delay))

    # Steps — short horizontal then short vertical, like a sawtooth
    for i in range(n_steps):
        t1 = i / n_steps
        t2 = (i + 1) / n_steps
        x1 = base_x + (top_x - base_x) * t1
        y1 = base_y + (top_y - base_y) * t1
        x2 = base_x + (top_x - base_x) * t2
        y2 = base_y + (top_y - base_y) * t2
        # Tread (horizontal): from current to next x at y of next
        parts.append(line(x1, y1, x2, y1,
                          stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.85,
                          draw_in=draw_in, delay=delay + i * 0.02))
        # Riser (vertical): from y1 to y2 at x2
        parts.append(line(x2, y1, x2, y2,
                          stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.7,
                          draw_in=draw_in, delay=delay + i * 0.02))

    # Handrail: parallel diagonal slightly above the slope
    rail_offset_y = -22
    parts.append(line(base_x + 4, base_y + rail_offset_y,
                      top_x + 4, top_y + rail_offset_y,
                      stroke=DRY_INK["fg"], width=STROKE["medium"], opacity=0.85,
                      draw_in=draw_in, delay=delay + 0.05))
    # Rail balusters (short verticals connecting rail to slope)
    for i in range(0, n_steps, 2):
        t = i / n_steps
        x = base_x + (top_x - base_x) * t
        y_slope = base_y + (top_y - base_y) * t
        y_rail = y_slope + rail_offset_y
        parts.append(line(x, y_slope, x, y_rail,
                          stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.5,
                          draw_in=draw_in, delay=delay + i * 0.015))

    # Landing line above (the next floor)
    landing_y = top_y - 8
    parts.append(line(top_x, landing_y, w * 0.95, landing_y,
                      stroke=DRY_INK["fg"], width=STROKE["medium"], opacity=0.85,
                      draw_in=draw_in, delay=delay + 0.1))

    return group(*parts)


def _table(w: float, h: float, *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    """Foreground table — flat oblong with two visible legs."""
    tx = w * 0.18
    ty = h * 0.62
    tw = w * 0.5
    parts = []
    # Top
    parts.append(line(tx, ty, tx + tw, ty,
                      stroke=DRY_INK["fg"], width=STROKE["medium"],
                      draw_in=draw_in, delay=delay))
    parts.append(line(tx, ty, tx + tw, ty,
                      stroke=DRY_INK["fg"], width=STROKE["medium"],
                      draw_in=draw_in, delay=delay))
    # Front edge
    parts.append(rect(tx, ty, tw, 4, fill=DRY_INK["fg"], opacity=0.55,
                      draw_in=draw_in, delay=delay))
    # Two legs
    parts.append(line(tx + 8, ty + 4, tx + 8, ty + 22,
                      stroke=DRY_INK["fg"], width=STROKE["thin"],
                      draw_in=draw_in, delay=delay))
    parts.append(line(tx + tw - 8, ty + 4, tx + tw - 8, ty + 22,
                      stroke=DRY_INK["fg"], width=STROKE["thin"],
                      draw_in=draw_in, delay=delay))
    return group(*parts)


def _prop(name: str, w: float, h: float, horizon_y: float,
          *, draw_in: float = 0.0, delay: float = 0.0) -> str:
    """Render a foreground prop based on a recognised name."""
    if name == "body":
        # Horizontal body silhouette — short oblong with head circle, on ground
        bx = w * 0.42
        by = horizon_y + (h - horizon_y) * 0.65
        parts = []
        parts.append(rect(bx, by, 50, 6, fill=DRY_INK["fg"], opacity=0.85,
                          draw_in=draw_in, delay=delay))
        parts.append(f"<circle cx='{bx + 50:.1f}' cy='{by + 3:.1f}' r='4' "
                     f"fill='{DRY_INK['fg']}'/>")
        # Tag
        parts.append(text(
            bx, by - 4, "BODY",
            size=7, fill=DRY_INK["fg_dim"], letter_spacing="0.15em",
            anchor="start",
        ))
        return group(*parts)
    if name == "phone":
        px = w * 0.78
        py = horizon_y + (h - horizon_y) * 0.45
        return rect(px, py, 6, 12, fill=DRY_INK["fg"], opacity=0.8,
                    draw_in=draw_in, delay=delay)
    if name == "weapon":
        wx = w * 0.55
        wy = horizon_y + (h - horizon_y) * 0.5
        return path(
            f"M {wx} {wy} L {wx + 14} {wy + 2} L {wx + 14} {wy - 2} Z",
            fill=DRY_INK["fg"], draw_in=draw_in, delay=delay,
        )
    if name == "cup":
        cx = w * 0.35
        cy = h * 0.61
        parts = [
            rect(cx, cy - 8, 10, 8, fill="none", stroke=DRY_INK["fg"],
                 stroke_width=STROKE["thin"],
                 draw_in=draw_in, delay=delay),
            # Steam squiggles
            path(f"M {cx + 3} {cy - 12} q 2 -4 0 -8",
                 stroke=DRY_INK["fg_dim"], stroke_width=0.5, fill="none",
                 draw_in=draw_in, delay=delay + 0.05),
        ]
        return group(*parts)
    return ""


__all__ = ["render_environment"]
