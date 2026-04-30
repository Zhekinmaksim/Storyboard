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
                       stagger: float = 0.05,
                       variant: int = 0) -> str:
    """Compose env layers in back-to-front order.

    Order matters: ground hatching first (under everything), then back
    architecture, then mid-ground props, then atmospheric overlays
    (rain, shadow cones, neon glow). Foreground props go last so they
    visually pop.
    """
    parts: list[str] = []
    horizon_y = env.horizon_y * frame_h
    cur_delay = delay

    # Specialised shot boards for subway/train scenes. These are intentionally
    # complete compositions, not just background layers, so repeated shots do
    # not look like the same platform with a few props moved around.
    if env.kind == "INT" and env.has_subway:
        return _subway_storyboard_frame(
            frame_w, frame_h, horizon_y,
            draw_in=draw_in, delay=delay, variant=variant,
        )
    if env.kind == "INT" and env.has_table:
        return _table_storyboard_frame(
            frame_w, frame_h, horizon_y,
            draw_in=draw_in, delay=delay, variant=variant,
            props=env.props,
        )

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
        if env.has_subway:
            parts.append(_subway_station(frame_w, frame_h, horizon_y,
                                         draw_in=draw_in, delay=cur_delay,
                                         variant=variant))
            cur_delay += stagger
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
                         draw_in=draw_in, delay=cur_delay, variant=variant)
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


def _table_storyboard_frame(w: float, h: float, horizon_y: float,
                            *, draw_in: float = 0.0, delay: float = 0.0,
                            variant: int = 0, props: list[str] | None = None) -> str:
    """Six distinct kitchen/table compositions.

    Table scenes often carry small dramatic beats. These boards make the
    prop/relationship readable even when Kimi emits sparse figure data.
    """
    v = variant % 6
    has_phone = "phone" in (props or [])
    parts: list[str] = []

    if v == 0:
        # Wide establishing: both sides of the table and the prop between them.
        parts.extend(_kitchen_wall(w, h, horizon_y, window_side="right",
                                   draw_in=draw_in, delay=delay))
        parts.append(_table_top(w * 0.18, h * 0.62, w * 0.58, perspective=0.10,
                                draw_in=draw_in, delay=delay + 0.05))
        parts.append(_table_person(w * 0.30, h * 0.64, scale=0.9,
                                   draw_in=draw_in, delay=delay + 0.08))
        parts.append(_table_person(w * 0.75, h * 0.69, scale=0.72,
                                   draw_in=draw_in, delay=delay + 0.10))
        parts.append(_table_phone(w * 0.52, h * 0.63, scale=0.9 if has_phone else 0.65,
                                  draw_in=draw_in, delay=delay + 0.12))
        parts.append(path(
            f"M {w * 0.18:.2f} {h * 0.57:.2f} Q {w * 0.50:.2f} {h * 0.36:.2f} "
            f"{w * 0.92:.2f} {h * 0.58:.2f}",
            fill="none", stroke=DRY_INK["accent"], stroke_width=STROKE["thin"],
            opacity=0.32, draw_in=draw_in, delay=delay + 0.14,
        ))

    elif v == 1:
        # Medium confrontation: one sibling dominates foreground, one recedes.
        parts.extend(_kitchen_wall(w, h, horizon_y, window_side="center",
                                   draw_in=draw_in, delay=delay))
        parts.append(_table_top(w * 0.18, h * 0.58, w * 0.50, perspective=0.03,
                                draw_in=draw_in, delay=delay + 0.04))
        parts.append(path(
            f"M {w * 0.14:.2f} {h:.2f} L {w * 0.20:.2f} {h * 0.24:.2f} "
            f"L {w * 0.25:.2f} {h:.2f} Z",
            fill=DRY_INK["fg"], opacity=0.45,
            draw_in=draw_in, delay=delay + 0.07,
        ))
        parts.append(_table_person(w * 0.46, h * 0.64, scale=0.78,
                                   draw_in=draw_in, delay=delay + 0.10))
        parts.append(path(
            f"M {w * 0.80:.2f} {h:.2f} L {w * 0.84:.2f} {h * 0.16:.2f} "
            f"L {w * 0.90:.2f} {h:.2f} Z",
            fill=DRY_INK["fg"], opacity=0.45,
            draw_in=draw_in, delay=delay + 0.12,
        ))
        parts.append(line(w * 0.50, h * 0.40, w * 0.50, h * 0.82,
                          stroke=DRY_INK["accent"], width=STROKE["thin"],
                          opacity=0.45, draw_in=draw_in, delay=delay + 0.14))

    elif v == 2:
        # Isolating close-up read: face/attention geometry, not the same table again.
        cx = w * 0.50
        cy = h * 0.48
        parts.append(path(
            f"M {cx - 58:.2f} {cy - 14:.2f} "
            f"Q {cx:.2f} {cy - 76:.2f} {cx + 58:.2f} {cy - 14:.2f} "
            f"Q {cx + 70:.2f} {cy + 80:.2f} {cx:.2f} {cy + 92:.2f} "
            f"Q {cx - 70:.2f} {cy + 80:.2f} {cx - 58:.2f} {cy - 14:.2f} Z",
            fill="none", stroke=DRY_INK["fg"], stroke_width=STROKE["medium"],
            draw_in=draw_in, delay=delay,
        ))
        parts.append(path(
            f"M {cx - 56:.2f} {cy - 18:.2f} "
            f"Q {cx:.2f} {cy - 48:.2f} {cx + 56:.2f} {cy - 18:.2f} "
            f"L {cx + 56:.2f} {cy + 8:.2f} L {cx - 56:.2f} {cy + 8:.2f} Z",
            fill=DRY_INK["fg"], opacity=0.88,
            draw_in=draw_in, delay=delay + 0.04,
        ))
        parts.append(path(
            f"M {cx:.2f} {cy + 8:.2f} L {cx:.2f} {cy + 78:.2f}",
            fill="none", stroke=DRY_INK["accent"], stroke_width=STROKE["thin"],
            opacity=0.58, draw_in=draw_in, delay=delay + 0.08,
        ))
        parts.append(circle_glyph(cx, cy + 8, 4, color=DRY_INK["accent"]))
        parts.append(circle_glyph(cx + 22, cy - 4, 3, color=DRY_INK["fg_dim"]))

    elif v == 3:
        # Insert: the phone is the frame, with vibration/action lines.
        parts.append(_table_insert_surface(w, h, draw_in=draw_in, delay=delay))
        parts.append(_table_phone(w * 0.50, h * 0.52, scale=3.0,
                                  draw_in=draw_in, delay=delay + 0.04))
        parts.extend(_phone_vibration(w * 0.50, h * 0.52, 64,
                                      draw_in=draw_in, delay=delay + 0.08))
        parts.append(line(w * 0.16, h * 0.78, w * 0.84, h * 0.78,
                          stroke=DRY_INK["fg"], width=STROKE["thin"],
                          opacity=0.42, draw_in=draw_in, delay=delay + 0.1))

    elif v == 4:
        # Two-shot standoff with the object held in the middle.
        parts.extend(_kitchen_wall(w, h, horizon_y, window_side="right",
                                   draw_in=draw_in, delay=delay))
        parts.append(_table_top(w * 0.18, h * 0.61, w * 0.62, perspective=0.04,
                                draw_in=draw_in, delay=delay + 0.04))
        parts.append(_table_person(w * 0.34, h * 0.63, scale=0.82,
                                   draw_in=draw_in, delay=delay + 0.08))
        parts.append(_table_person(w * 0.72, h * 0.70, scale=0.66,
                                   draw_in=draw_in, delay=delay + 0.10))
        parts.append(_table_phone(w * 0.58, h * 0.65, scale=0.95,
                                  draw_in=draw_in, delay=delay + 0.12))
        parts.append(line(w * 0.34, h * 0.50, w * 0.58, h * 0.64,
                          stroke=DRY_INK["accent"], width=STROKE["thin"],
                          opacity=0.4, draw_in=draw_in, delay=delay + 0.14))

    else:
        # Empty kitchen aftermath: readable negative space, not an empty frame.
        parts.extend(_kitchen_wall(w, h, horizon_y, window_side="right",
                                   draw_in=draw_in, delay=delay))
        parts.append(_table_top(w * 0.10, h * 0.52, w * 0.68, perspective=-0.02,
                                draw_in=draw_in, delay=delay + 0.04))
        parts.append(_table_phone(w * 0.82, h * 0.67, scale=0.9,
                                  draw_in=draw_in, delay=delay + 0.08))
        parts.append(path(
            f"M {w * 0.18:.2f} {h * 0.18:.2f} L {w * 0.18:.2f} {h * 0.86:.2f}",
            fill="none", stroke=DRY_INK["fg"], stroke_width=STROKE["medium"],
            opacity=0.34, draw_in=draw_in, delay=delay + 0.1,
        ))
        parts.append(path(
            f"M {w * 0.80:.2f} {h * 0.18:.2f} L {w * 0.80:.2f} {h * 0.86:.2f}",
            fill="none", stroke=DRY_INK["fg"], stroke_width=STROKE["medium"],
            opacity=0.34, draw_in=draw_in, delay=delay + 0.12,
        ))

    return f"<g class='env-table env-table-{v} table-board-{v}'>{''.join(parts)}</g>"


def _kitchen_wall(w: float, h: float, horizon_y: float, *,
                  window_side: str, draw_in: float, delay: float) -> list[str]:
    parts = [
        line(0, horizon_y, w, horizon_y,
             stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.55,
             draw_in=draw_in, delay=delay),
        line(0, horizon_y + (h - horizon_y) * 0.30, w, horizon_y + (h - horizon_y) * 0.30,
             stroke=DRY_INK["fg_dim"], width=STROKE["thin"], opacity=0.30,
             draw_in=draw_in, delay=delay + 0.02),
    ]
    if window_side == "center":
        wx = w * 0.62
    else:
        wx = w * 0.68
    wy = h * 0.13
    ww = w * 0.28
    wh = h * 0.24
    parts.append(rect(wx, wy, ww, wh, fill="none", stroke=DRY_INK["fg"],
                      stroke_width=STROKE["thin"], opacity=0.65,
                      draw_in=draw_in, delay=delay + 0.04))
    parts.append(line(wx + ww / 3, wy, wx + ww / 3, wy + wh,
                      stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.55,
                      draw_in=draw_in, delay=delay + 0.05))
    parts.append(line(wx + ww * 2 / 3, wy, wx + ww * 2 / 3, wy + wh,
                      stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.55,
                      draw_in=draw_in, delay=delay + 0.06))
    parts.append(line(wx, wy + wh / 2, wx + ww, wy + wh / 2,
                      stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.55,
                      draw_in=draw_in, delay=delay + 0.07))
    return parts


def _table_top(x: float, y: float, tw: float, *,
               perspective: float, draw_in: float, delay: float) -> str:
    depth = 34
    skew = tw * perspective
    parts = [
        path(
            f"M {x:.2f} {y:.2f} L {x + tw:.2f} {y:.2f} "
            f"L {x + tw + skew:.2f} {y + depth:.2f} "
            f"L {x - skew:.2f} {y + depth:.2f} Z",
            fill=DRY_INK["fg"], opacity=0.16,
            draw_in=draw_in, delay=delay,
        ),
        line(x, y, x + tw, y, stroke=DRY_INK["fg"],
             width=STROKE["heavy"], opacity=0.9,
             draw_in=draw_in, delay=delay + 0.02),
        line(x - skew, y + depth, x + tw + skew, y + depth,
             stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.55,
             draw_in=draw_in, delay=delay + 0.04),
        line(x + 10, y + depth, x + 10, y + depth + 24,
             stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.62,
             draw_in=draw_in, delay=delay + 0.05),
        line(x + tw - 10, y + depth, x + tw - 10, y + depth + 24,
             stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.62,
             draw_in=draw_in, delay=delay + 0.06),
    ]
    return f"<g class='table-top'>{''.join(parts)}</g>"


def _table_insert_surface(w: float, h: float, *,
                          draw_in: float, delay: float) -> str:
    parts = [
        rect(w * 0.08, h * 0.16, w * 0.84, h * 0.62,
             fill=DRY_INK["fg"], opacity=0.06,
             draw_in=draw_in, delay=delay),
        line(w * 0.10, h * 0.28, w * 0.90, h * 0.28,
             stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.28,
             draw_in=draw_in, delay=delay + 0.02),
        line(w * 0.10, h * 0.70, w * 0.90, h * 0.70,
             stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.20,
             draw_in=draw_in, delay=delay + 0.04),
    ]
    return f"<g class='table-insert-surface'>{''.join(parts)}</g>"


def _table_phone(cx: float, cy: float, *, scale: float,
                 draw_in: float, delay: float) -> str:
    pw = 12 * scale
    ph = 28 * scale
    parts = [
        rect(cx - pw / 2, cy - ph / 2, pw, ph,
             fill=DRY_INK["bg"], stroke=DRY_INK["fg"],
             stroke_width=STROKE["thin"], opacity=0.95,
             draw_in=draw_in, delay=delay),
        circle_glyph(cx, cy + ph * 0.30, max(1.6, 2.0 * scale), color=DRY_INK["accent"]),
        line(cx - pw * 0.26, cy - ph * 0.22, cx + pw * 0.26, cy - ph * 0.22,
             stroke=DRY_INK["fg_dim"], width=STROKE["thin"], opacity=0.5,
             draw_in=draw_in, delay=delay + 0.03),
    ]
    return f"<g class='prop-phone table-phone'>{''.join(parts)}</g>"


def _phone_vibration(cx: float, cy: float, radius: float,
                     *, draw_in: float, delay: float) -> list[str]:
    parts = []
    for i, r in enumerate((radius, radius + 16, radius + 32)):
        parts.append(path(
            f"M {cx - r * 0.72:.2f} {cy - r * 0.18:.2f} "
            f"Q {cx:.2f} {cy - r * 0.70:.2f} {cx + r * 0.72:.2f} {cy - r * 0.18:.2f}",
            fill="none", stroke=DRY_INK["accent"], stroke_width=STROKE["thin"],
            opacity=0.46 - i * 0.10, draw_in=draw_in, delay=delay + i * 0.04,
        ))
        parts.append(path(
            f"M {cx - r * 0.72:.2f} {cy + r * 0.18:.2f} "
            f"Q {cx:.2f} {cy + r * 0.70:.2f} {cx + r * 0.72:.2f} {cy + r * 0.18:.2f}",
            fill="none", stroke=DRY_INK["accent"], stroke_width=STROKE["thin"],
            opacity=0.38 - i * 0.08, draw_in=draw_in, delay=delay + i * 0.04,
        ))
    return parts


def _table_person(x: float, y: float, *, scale: float,
                  draw_in: float, delay: float) -> str:
    h = 52 * scale
    parts = [
        path(
            f"M {x - 7 * scale:.2f} {y - h * 0.64:.2f} "
            f"L {x - 13 * scale:.2f} {y:.2f} "
            f"L {x + 13 * scale:.2f} {y:.2f} "
            f"L {x + 7 * scale:.2f} {y - h * 0.64:.2f} Z",
            fill=DRY_INK["fg"], opacity=0.92,
            draw_in=draw_in, delay=delay,
        ),
        circle_glyph(x, y - h * 0.76, 4 * scale, color=DRY_INK["fg"]),
    ]
    return f"<g class='table-person'>{''.join(parts)}</g>"


def _subway_station(w: float, h: float, horizon_y: float,
                    *, draw_in: float = 0.0, delay: float = 0.0,
                    variant: int = 0) -> str:
    """Subway platform: tunnel mouth, tiled wall, columns, platform edge.

    This gives train/platform scenes a readable architecture instead of
    generic floor hatching.
    """
    parts = []
    v = variant % 6
    wall_y = horizon_y * (0.16 + 0.03 * (v % 3))
    platform_y = horizon_y + (h - horizon_y) * (0.28 + 0.05 * (v % 2))

    # Tunnel mouth in back wall.
    tunnel_x = w * (0.08 if v == 1 else 0.62 if v in (0, 4) else 0.48)
    tunnel_w = w * (0.34 if v in (2, 5) else 0.26)
    tunnel_h = horizon_y * (0.62 + 0.05 * (v % 3))
    parts.append(path(
        f"M {tunnel_x:.2f} {horizon_y:.2f} "
        f"L {tunnel_x:.2f} {wall_y + tunnel_h * 0.45:.2f} "
        f"Q {tunnel_x + tunnel_w * 0.5:.2f} {wall_y:.2f} "
        f"{tunnel_x + tunnel_w:.2f} {wall_y + tunnel_h * 0.45:.2f} "
        f"L {tunnel_x + tunnel_w:.2f} {horizon_y:.2f} Z",
        fill=DRY_INK["fg"], opacity=0.88,
        draw_in=draw_in, delay=delay,
    ))

    # Tile seams on the back wall.
    tile_rows = 3 + (v % 2)
    for i in range(1, tile_rows + 1):
        y = wall_y + i * (horizon_y - wall_y) / (tile_rows + 1)
        parts.append(line(0, y, w, y,
                          stroke=DRY_INK["fg_dim"], width=STROKE["thin"], opacity=0.28,
                          draw_in=draw_in, delay=delay + i * 0.025))
    tile_cols = 4 + (v % 3)
    for i in range(1, tile_cols + 1):
        x = i * w / (tile_cols + 1)
        parts.append(line(x, wall_y, x, horizon_y,
                          stroke=DRY_INK["fg_dim"], width=STROKE["thin"], opacity=0.18,
                          draw_in=draw_in, delay=delay + i * 0.015))

    # Platform edge and rails.
    parts.append(line(0, platform_y, w, platform_y,
                      stroke=DRY_INK["fg"], width=STROKE["medium"], opacity=0.75,
                      draw_in=draw_in, delay=delay + 0.04))
    parts.append(line(0, platform_y + 18, w, platform_y + 18,
                      stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.7,
                      draw_in=draw_in, delay=delay + 0.06))
    parts.append(line(0, platform_y + 34, w, platform_y + 34,
                      stroke=DRY_INK["fg"], width=STROKE["thin"], opacity=0.55,
                      draw_in=draw_in, delay=delay + 0.08))

    # Upright station columns.
    column_sets = (
        (w * 0.16, w * 0.42),
        (w * 0.28, w * 0.68),
        (w * 0.12, w * 0.52, w * 0.84),
    )
    for i, x in enumerate(column_sets[v % len(column_sets)]):
        parts.append(rect(x, wall_y + 8, 8, platform_y - wall_y - 8,
                          fill=DRY_INK["fg"], opacity=0.18,
                          draw_in=draw_in, delay=delay + i * 0.04))

    if v in (2, 3):
        # Overhead beam or far platform silhouette, enough to change the read.
        parts.append(rect(w * 0.05, wall_y + 10, w * 0.9, 12,
                          fill=DRY_INK["fg"], opacity=0.9,
                          draw_in=draw_in, delay=delay + 0.12))

    return f"<g class='env-subway env-subway-{v}'>{''.join(parts)}</g>"


def _subway_storyboard_frame(w: float, h: float, horizon_y: float,
                             *, draw_in: float = 0.0, delay: float = 0.0,
                             variant: int = 0) -> str:
    """Six distinct subway storyboard compositions.

    This deliberately draws the whole shot language: establishing station,
    agent reveal, low tracking run, over-shoulder gunfire, gap leap, and
    aftermath/train doors. It makes arbitrary subway prompts read as a film
    sequence rather than six copies of the same set.
    """
    v = variant % 6
    parts: list[str] = []

    if v == 0:
        parts.extend(_subway_tiles(w, h, horizon_y, rows=4, cols=6,
                                   draw_in=draw_in, delay=delay))
        parts.append(_subway_tunnel(w * 0.64, horizon_y, w * 0.30, horizon_y * 0.72,
                                    draw_in=draw_in, delay=delay + 0.04))
        parts.append(rect(w * 0.08, horizon_y * 0.25, w * 0.28, 18,
                          fill="none", stroke=DRY_INK["fg"], stroke_width=STROKE["thin"],
                          opacity=0.8, draw_in=draw_in, delay=delay + 0.06))
        parts.append(text(w * 0.1, horizon_y * 0.36, "PLATFORM",
                          font="mono", size=7, fill=DRY_INK["fg_dim"],
                          letter_spacing="0.12em"))
        parts.extend(_subway_platform_edges(w, h, horizon_y, depth=0.25,
                                            draw_in=draw_in, delay=delay + 0.08))
        parts.extend(_subway_columns(w, horizon_y, h, (0.16, 0.42),
                                     draw_in=draw_in, delay=delay + 0.1))

    elif v == 1:
        parts.append(rect(0, horizon_y * 0.18, w, horizon_y * 0.58,
                          fill=DRY_INK["fg"], opacity=0.08,
                          draw_in=draw_in, delay=delay))
        parts.append(_subway_tunnel(w * 0.12, horizon_y, w * 0.42, horizon_y * 0.85,
                                    draw_in=draw_in, delay=delay + 0.02))
        parts.extend(_subway_platform_edges(w, h, horizon_y, depth=0.18,
                                            draw_in=draw_in, delay=delay + 0.06))
        # Three approaching agents as the dominant read.
        for i, x in enumerate((w * 0.58, w * 0.70, w * 0.82)):
            scale = 1.0 + i * 0.08
            parts.append(_subway_person(x, horizon_y + (h - horizon_y) * 0.50,
                                        scale=scale, draw_in=draw_in,
                                        delay=delay + 0.1 + i * 0.04))
        parts.append(rect(w * 0.72, horizon_y * 0.2, 18, 58,
                          fill="none", stroke=DRY_INK["accent"],
                          stroke_width=STROKE["thin"], opacity=0.75,
                          draw_in=draw_in, delay=delay + 0.16))
        parts.append(circle_glyph(w * 0.74, horizon_y * 0.34, 5, color=DRY_INK["accent"]))

    elif v == 2:
        # Low tracking: rails dominate the foreground, station is compressed.
        vanish_x = w * 0.62
        vanish_y = horizon_y * 0.48
        parts.append(rect(0, 0, w, horizon_y * 0.22,
                          fill=DRY_INK["fg"], opacity=0.12,
                          draw_in=draw_in, delay=delay))
        for i in range(7):
            x1 = i * w / 6
            parts.append(line(x1, h, vanish_x, vanish_y,
                              stroke=DRY_INK["fg"], width=STROKE["thin"],
                              opacity=0.38, draw_in=draw_in, delay=delay + i * 0.02))
        parts.append(path(
            f"M 0 {h:.2f} L {w * 0.42:.2f} {vanish_y:.2f} "
            f"L {w * 0.58:.2f} {vanish_y:.2f} L {w:.2f} {h:.2f} Z",
            fill=DRY_INK["fg"], opacity=0.14,
            draw_in=draw_in, delay=delay + 0.05,
        ))
        for i in range(6):
            y = h * (0.28 + i * 0.09)
            parts.append(line(w * 0.08, y, w * 0.42, y - 10,
                              stroke=DRY_INK["fg_dim"], width=STROKE["thin"],
                              opacity=0.35, draw_in=draw_in, delay=delay + i * 0.015))
        parts.append(_subway_train(w * 0.62, horizon_y * 0.16, w * 0.34, horizon_y * 0.58,
                                   headlights=True, draw_in=draw_in, delay=delay + 0.08))

    elif v == 3:
        # OTS gunfire: foreground shoulder + framed target across platform.
        parts.extend(_subway_tiles(w, h, horizon_y, rows=3, cols=4,
                                   draw_in=draw_in, delay=delay))
        parts.append(rect(w * 0.08, horizon_y * 0.20, w * 0.72, horizon_y * 0.48,
                          fill="none", stroke=DRY_INK["fg"], stroke_width=STROKE["thin"],
                          opacity=0.75, draw_in=draw_in, delay=delay + 0.04))
        parts.append(path(
            f"M {w:.2f} {h:.2f} L {w * 0.76:.2f} {h:.2f} "
            f"Q {w * 0.84:.2f} {h * 0.55:.2f} {w:.2f} {h * 0.40:.2f} Z",
            fill=DRY_INK["fg"], opacity=0.88,
            draw_in=draw_in, delay=delay + 0.06,
        ))
        parts.append(line(w * 0.72, h * 0.54, w * 0.28, h * 0.54,
                          stroke=DRY_INK["accent"], width=STROKE["medium"],
                          opacity=0.7, draw_in=draw_in, delay=delay + 0.08))
        parts.extend(_subway_sparks(w * 0.28, h * 0.58, draw_in=draw_in, delay=delay + 0.1))
        parts.extend(_subway_platform_edges(w, h, horizon_y, depth=0.2,
                                            draw_in=draw_in, delay=delay + 0.12))

    elif v == 4:
        # Gap leap: black void between two platforms with a clear jump arc.
        parts.append(rect(0, horizon_y * 0.1, w, horizon_y * 0.58,
                          fill="none", stroke=DRY_INK["fg"],
                          stroke_width=STROKE["thin"], opacity=0.5,
                          draw_in=draw_in, delay=delay))
        parts.append(rect(w * 0.28, h * 0.62, w * 0.44, h * 0.28,
                          fill=DRY_INK["fg"], opacity=0.92,
                          draw_in=draw_in, delay=delay + 0.04))
        parts.append(line(0, h * 0.60, w * 0.28, h * 0.62,
                          stroke=DRY_INK["fg"], width=STROKE["heavy"],
                          opacity=0.85, draw_in=draw_in, delay=delay + 0.06))
        parts.append(line(w * 0.72, h * 0.62, w, h * 0.58,
                          stroke=DRY_INK["fg"], width=STROKE["heavy"],
                          opacity=0.85, draw_in=draw_in, delay=delay + 0.06))
        parts.append(path(
            f"M {w * 0.10:.2f} {h * 0.66:.2f} Q {w * 0.50:.2f} {h * 0.18:.2f} "
            f"{w * 0.90:.2f} {h * 0.62:.2f}",
            fill="none", stroke=DRY_INK["accent"], stroke_width=STROKE["thin"],
            opacity=0.75, draw_in=draw_in, delay=delay + 0.08,
        ))
        parts.append(_subway_train(w * 0.60, horizon_y * 0.16, w * 0.34, horizon_y * 0.58,
                                   headlights=True, draw_in=draw_in, delay=delay + 0.1))

    else:
        # Aftermath: side train doors and smoke, slower final beat.
        parts.extend(_subway_tiles(w, h, horizon_y, rows=3, cols=5,
                                   draw_in=draw_in, delay=delay))
        parts.append(_subway_train(w * 0.42, horizon_y * 0.12, w * 0.50, horizon_y * 0.72,
                                   headlights=False, doors=True,
                                   draw_in=draw_in, delay=delay + 0.04))
        parts.extend(_subway_platform_edges(w, h, horizon_y, depth=0.22,
                                            draw_in=draw_in, delay=delay + 0.08))
        parts.extend(_subway_smoke(w * 0.62, h * 0.58, draw_in=draw_in, delay=delay + 0.1))
        parts.extend(_subway_columns(w, horizon_y, h, (0.14, 0.86),
                                     draw_in=draw_in, delay=delay + 0.12))

    return f"<g class='env-subway env-subway-{v} subway-board-{v}'>{''.join(parts)}</g>"


def _subway_tiles(w: float, h: float, horizon_y: float, *, rows: int, cols: int,
                  draw_in: float, delay: float) -> list[str]:
    parts = []
    for i in range(1, rows + 1):
        y = horizon_y * (0.15 + i * 0.15)
        parts.append(line(0, y, w, y,
                          stroke=DRY_INK["fg_dim"], width=STROKE["thin"], opacity=0.28,
                          draw_in=draw_in, delay=delay + i * 0.015))
    for i in range(1, cols + 1):
        x = i * w / (cols + 1)
        parts.append(line(x, horizon_y * 0.12, x, horizon_y * 0.95,
                          stroke=DRY_INK["fg_dim"], width=STROKE["thin"], opacity=0.2,
                          draw_in=draw_in, delay=delay + i * 0.01))
    return parts


def _subway_platform_edges(w: float, h: float, horizon_y: float, *,
                           depth: float, draw_in: float, delay: float) -> list[str]:
    y0 = horizon_y + (h - horizon_y) * depth
    return [
        line(0, y0, w, y0, stroke=DRY_INK["fg"], width=STROKE["medium"],
             opacity=0.78, draw_in=draw_in, delay=delay),
        line(0, y0 + 18, w, y0 + 18, stroke=DRY_INK["fg"], width=STROKE["thin"],
             opacity=0.65, draw_in=draw_in, delay=delay + 0.02),
        line(0, y0 + 34, w, y0 + 34, stroke=DRY_INK["fg"], width=STROKE["thin"],
             opacity=0.45, draw_in=draw_in, delay=delay + 0.04),
    ]


def _subway_columns(w: float, horizon_y: float, h: float, xs: tuple[float, ...],
                    *, draw_in: float, delay: float) -> list[str]:
    return [
        rect(w * frac, horizon_y * 0.16, 8, h * 0.72,
             fill=DRY_INK["fg"], opacity=0.88,
             draw_in=draw_in, delay=delay + idx * 0.03)
        for idx, frac in enumerate(xs)
    ]


def _subway_tunnel(x: float, base_y: float, tw: float, th: float,
                   *, draw_in: float, delay: float) -> str:
    return path(
        f"M {x:.2f} {base_y:.2f} L {x:.2f} {base_y - th * 0.55:.2f} "
        f"Q {x + tw * 0.5:.2f} {base_y - th:.2f} {x + tw:.2f} {base_y - th * 0.55:.2f} "
        f"L {x + tw:.2f} {base_y:.2f} Z",
        fill=DRY_INK["fg"], opacity=0.9,
        draw_in=draw_in, delay=delay,
    )


def _subway_train(x: float, y: float, tw: float, th: float, *,
                  headlights: bool, draw_in: float, delay: float,
                  doors: bool = False) -> str:
    parts = [
        rect(x, y, tw, th, fill=DRY_INK["fg"], opacity=0.86,
             draw_in=draw_in, delay=delay),
        rect(x + tw * 0.05, y + th * 0.12, tw * 0.9, th * 0.22,
             fill=DRY_INK["bg"], opacity=0.22,
             draw_in=draw_in, delay=delay + 0.02),
    ]
    if doors:
        parts.extend([
            rect(x + tw * 0.18, y + th * 0.18, tw * 0.18, th * 0.62,
                 fill=DRY_INK["bg"], opacity=0.2, draw_in=draw_in, delay=delay + 0.04),
            rect(x + tw * 0.42, y + th * 0.18, tw * 0.18, th * 0.62,
                 fill=DRY_INK["bg"], opacity=0.16, draw_in=draw_in, delay=delay + 0.06),
        ])
    if headlights:
        parts.append(circle_glyph(x + tw * 0.82, y + th * 0.64, 5, color=DRY_INK["accent"]))
        parts.append(circle_glyph(x + tw * 0.92, y + th * 0.64, 5, color=DRY_INK["accent"]))
        parts.append(line(x + tw * 0.86, y + th * 0.66, x + tw * 0.15, y + th * 1.25,
                          stroke=DRY_INK["accent"], width=STROKE["thin"], opacity=0.32,
                          draw_in=draw_in, delay=delay + 0.08))
    return f"<g class='prop-train'>{''.join(parts)}</g>"


def _subway_person(x: float, y: float, *, scale: float,
                   draw_in: float, delay: float) -> str:
    h = 42 * scale
    return path(
        f"M {x - 5 * scale:.2f} {y - h * 0.72:.2f} "
        f"L {x - 11 * scale:.2f} {y:.2f} "
        f"L {x + 11 * scale:.2f} {y:.2f} "
        f"L {x + 5 * scale:.2f} {y - h * 0.72:.2f} Z",
        fill=DRY_INK["fg"], opacity=0.94,
        draw_in=draw_in, delay=delay,
    ) + circle_glyph(x, y - h * 0.82, 4 * scale, color=DRY_INK["fg"])


def _subway_sparks(x: float, y: float, *, draw_in: float, delay: float) -> list[str]:
    parts = []
    for i, (dx, dy) in enumerate(((0, 0), (16, -8), (31, 7), (48, -3))):
        sx = x + dx
        sy = y + dy
        parts.append(line(sx - 7, sy, sx + 7, sy,
                          stroke=DRY_INK["accent"], width=STROKE["medium"],
                          opacity=0.85, draw_in=draw_in, delay=delay + i * 0.025))
        parts.append(line(sx, sy - 7, sx, sy + 7,
                          stroke=DRY_INK["accent"], width=STROKE["thin"],
                          opacity=0.55, draw_in=draw_in, delay=delay + i * 0.025))
    return parts


def _subway_smoke(x: float, y: float, *, draw_in: float, delay: float) -> list[str]:
    parts = []
    for i, r in enumerate((18, 28, 38)):
        parts.append(
            f"<ellipse cx='{x + i * 20:.2f}' cy='{y - i * 10:.2f}' "
            f"rx='{r:.2f}' ry='{r * 0.42:.2f}' fill='none' "
            f"stroke='{DRY_INK['fg_dim']}' stroke-width='{STROKE['thin']}' "
            f"opacity='{0.18 + i * 0.07:.2f}'/>"
        )
    return parts


def _prop(name: str, w: float, h: float, horizon_y: float,
          *, draw_in: float = 0.0, delay: float = 0.0,
          variant: int = 0) -> str:
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
        return f"<g class='prop-body'>{''.join(parts)}</g>"
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
        return f"<g class='prop-cup'>{''.join(parts)}</g>"
    if name == "train":
        v = variant % 6
        tx = w * (0.03 if v in (0, 3) else 0.38 if v in (2, 5) else 0.14)
        ty = horizon_y * (0.18 if v in (1, 4) else 0.28)
        tw = w * (0.92 if v in (0, 3) else 0.58 if v in (2, 5) else 0.72)
        th = horizon_y * (0.48 if v in (1, 4) else 0.58)
        parts = [
            rect(tx, ty, tw, th, fill="none", stroke=DRY_INK["fg"],
                 stroke_width=STROKE["medium"], opacity=0.75,
                 draw_in=draw_in, delay=delay),
            rect(tx, ty + th * 0.12, tw, th * 0.26, fill=DRY_INK["fg"],
                 opacity=0.12, draw_in=draw_in, delay=delay + 0.03),
        ]
        window_count = 2 if v in (2, 5) else 4
        for i in range(window_count):
            wx = tx + tw * (0.08 + i * (0.8 / max(window_count, 1)))
            parts.append(rect(wx, ty + th * 0.18, tw * 0.13, th * 0.18,
                              fill="none", stroke=DRY_INK["fg"],
                              stroke_width=STROKE["thin"], opacity=0.7,
                              draw_in=draw_in, delay=delay + i * 0.03))
        head_x = tx + (tw - 24 if v % 2 == 0 else 24)
        parts.append(circle_glyph(head_x, ty + th * 0.7, 5, color=DRY_INK["accent"]))
        parts.append(circle_glyph(head_x + (-18 if v % 2 == 0 else 18),
                                  ty + th * 0.7, 5, color=DRY_INK["accent"]))
        if v in (1, 4):
            parts.append(line(head_x, ty + th * 0.72, w * 0.5, horizon_y + 40,
                              stroke=DRY_INK["accent"], width=STROKE["thin"],
                              opacity=0.32, draw_in=draw_in, delay=delay + 0.08))
        return f"<g class='prop-train prop-train-{v}'>{''.join(parts)}</g>"
    if name == "tracks":
        v = variant % 6
        y1 = horizon_y + (h - horizon_y) * (0.34 + 0.03 * (v % 3))
        y2 = horizon_y + (h - horizon_y) * (0.68 + 0.02 * (v % 2))
        vanish_x = w * (0.2 if v in (1, 4) else 0.78 if v in (2, 5) else 0.5)
        parts = [
            line(0, y1, vanish_x, horizon_y + 10, stroke=DRY_INK["fg"], width=STROKE["thin"],
                 opacity=0.65, draw_in=draw_in, delay=delay),
            line(w, y2, vanish_x, horizon_y + 10, stroke=DRY_INK["fg"], width=STROKE["thin"],
                 opacity=0.65, draw_in=draw_in, delay=delay),
        ]
        for i in range(8):
            x = w * (i + 0.5) / 8
            slant = -18 if v % 2 else 18
            parts.append(line(x - slant, y1 + 3, x + slant, y2 - 3,
                              stroke=DRY_INK["fg_dim"], width=STROKE["thin"],
                              opacity=0.35, draw_in=draw_in, delay=delay + i * 0.015))
        return f"<g class='prop-tracks prop-tracks-{v}'>{''.join(parts)}</g>"
    if name == "tunnel":
        cx = w * 0.76
        base = horizon_y
        tunnel = path(
            f"M {cx - 58:.2f} {base:.2f} L {cx - 58:.2f} {base - 46:.2f} "
            f"Q {cx:.2f} {base - 92:.2f} {cx + 58:.2f} {base - 46:.2f} "
            f"L {cx + 58:.2f} {base:.2f} Z",
            fill="none", stroke=DRY_INK["fg"], stroke_width=STROKE["medium"],
            opacity=0.65, draw_in=draw_in, delay=delay,
        )
        return f"<g class='prop-tunnel'>{tunnel}</g>"
    if name == "sparks":
        v = variant % 6
        sx = w * (0.18 if v % 2 == 0 else 0.62)
        sy = horizon_y + (h - horizon_y) * (0.18 + 0.06 * (v % 3))
        parts = []
        for i, (dx, dy) in enumerate(((0, 0), (15, -10), (28, 6), (44, -4), (58, 10))):
            x = sx + dx
            y = sy + dy
            parts.append(line(x - 6, y, x + 6, y,
                              stroke=DRY_INK["accent"], width=STROKE["medium"],
                              opacity=0.85, draw_in=draw_in, delay=delay + i * 0.03))
            parts.append(line(x, y - 6, x, y + 6,
                              stroke=DRY_INK["accent"], width=STROKE["thin"],
                              opacity=0.65, draw_in=draw_in, delay=delay + i * 0.03))
        return f"<g class='prop-sparks prop-sparks-{v}'>{''.join(parts)}</g>"
    if name == "smoke":
        v = variant % 6
        sx = w * (0.28 if v in (1, 4) else 0.72)
        sy = horizon_y + (h - horizon_y) * (0.2 + 0.03 * (v % 3))
        parts = []
        for i, r in enumerate((18, 28, 38)):
            parts.append(
                f"<ellipse cx='{sx + i * 20:.2f}' cy='{sy - i * 10:.2f}' "
                f"rx='{r:.2f}' ry='{r * 0.42:.2f}' fill='none' "
                f"stroke='{DRY_INK['fg_dim']}' stroke-width='{STROKE['thin']}' "
                f"opacity='{0.18 + i * 0.07:.2f}'/>"
            )
        return f"<g class='prop-smoke prop-smoke-{v}'>{''.join(parts)}</g>"
    if name == "computer":
        mx = w * 0.58
        my = horizon_y + (h - horizon_y) * 0.25
        computer = group(
            rect(mx, my, 52, 30, fill="none", stroke=DRY_INK["fg"],
                 stroke_width=STROKE["thin"], draw_in=draw_in, delay=delay),
            line(mx + 26, my + 30, mx + 26, my + 42,
                 stroke=DRY_INK["fg"], width=STROKE["thin"], draw_in=draw_in, delay=delay),
            line(mx + 12, my + 42, mx + 40, my + 42,
                 stroke=DRY_INK["fg"], width=STROKE["thin"], draw_in=draw_in, delay=delay),
        )
        return f"<g class='prop-computer'>{computer}</g>"
    if name == "car":
        cx = w * 0.36
        cy = horizon_y + (h - horizon_y) * 0.45
        parts = [
            path(
                f"M {cx - 54:.2f} {cy:.2f} L {cx - 28:.2f} {cy - 22:.2f} "
                f"L {cx + 24:.2f} {cy - 22:.2f} L {cx + 54:.2f} {cy:.2f} Z",
                fill="none", stroke=DRY_INK["fg"], stroke_width=STROKE["medium"],
                draw_in=draw_in, delay=delay,
            ),
            circle_glyph(cx - 32, cy + 4, 5, color=DRY_INK["fg"]),
            circle_glyph(cx + 32, cy + 4, 5, color=DRY_INK["fg"]),
        ]
        return f"<g class='prop-car'>{''.join(parts)}</g>"
    return ""


__all__ = ["render_environment"]
