"""Scene → SVG renderer. Pure Python, no LLM. Deterministic.

Two modes:
  - static (default): single SVG file, all elements fully visible.
  - animated: every primitive carries SMIL animation; opening the file
    in a browser triggers a self-drawing playback. Used both for the
    standalone "open the SVG and watch" demo and for the streaming
    viewer (each shot is rendered animated and inserted into the live
    DOM as it arrives).

The animation timeline lives in scripts/templates/timeline.py.

Render also supports a single-shot mode (`render_shot`) used by the
streaming server to emit one frame at a time.
"""

from __future__ import annotations

from scripts.scene import Scene, Shot, ShotType
from scripts.style import DRY_INK, FONTS, PAGE, STROKE, TYPE
from scripts.templates.annotations import render_annotation, render_eyeline
from scripts.templates.environments import render_environment
from scripts.templates.figures import render_figure
from scripts.templates.svg_primitives import line, rect, text
from scripts.templates.timeline import (
    HEADER_DELAY, HEADER_DURATION, SHOT_TIMING, shot_start_offset,
)


def render_scene(scene: Scene, *, animated: bool = False,
                 static_filled: int | None = None,
                 patches_applied: int | None = None,
                 memory_active: bool = False) -> str:
    """Top-level: returns a complete SVG document string.

    `animated=True` wraps every primitive in SMIL animations so the SVG
    self-draws when opened in a browser. Total runtime ~7-8 seconds.

    `static_filled=k` (only meaningful in static mode) shows only the
    first k dots of the progress indicator filled — used to render
    progressive GIF preview frames.

    `patches_applied=N` and `memory_active=True` render a small footer
    badge showing the post-pipeline state of the board.
    """
    w = PAGE["width"]
    h = PAGE["height"]
    parts: list[str] = []
    parts.append(_svg_open(w, h))
    parts.append(_defs())
    parts.append(_background(w, h))
    parts.append(_header(scene, w, animated=animated, static_filled=static_filled))
    parts.extend(_frames(scene, animated=animated))
    parts.append(_footer(scene, w, h, animated=animated,
                         total_shots=len(scene.shots),
                         patches_applied=patches_applied,
                         memory_active=memory_active))
    parts.append("</svg>")
    return "".join(parts)


def render_shot(shot: Shot, scene: Scene, index: int,
                *, animated: bool = True) -> str:
    """Render a single shot as a positioned <g> group, suitable for
    appending into a streaming viewer. The group's local clock starts
    at 0, so animations begin when the element appears in the DOM.
    """
    cell_w, frame_w, cell_h, frame_h, x, y = _shot_position(index)
    return _render_one_shot(
        shot, x, y, frame_w, frame_h,
        animated=animated,
        global_offset=0.0,  # local time, see streaming-friendly timing
    )


def _svg_open(w: int, h: int) -> str:
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' "
        f"viewBox='0 0 {w} {h}' width='{w}' height='{h}'>"
    )


def _defs() -> str:
    return (
        f"<defs><style>"
        f".serif{{font-family:{FONTS['serif']};fill:{DRY_INK['fg']};}}"
        f".mono{{font-family:{FONTS['mono']};fill:{DRY_INK['fg']};}}"
        f".dim{{fill:{DRY_INK['fg_dim']};}}"
        f".accent{{fill:{DRY_INK['accent']};}}"
        f"</style></defs>"
    )


def _background(w: int, h: int) -> str:
    return rect(0, 0, w, h, fill=DRY_INK["bg"])


def _header(scene: Scene, w: int, *, animated: bool,
            static_filled: int | None = None) -> str:
    parts: list[str] = []
    draw = HEADER_DURATION if animated else 0.0
    delay = HEADER_DELAY if animated else 0.0
    parts.append(text(
        PAGE["margin_x"], PAGE["margin_y"] + 14, scene.title,
        font="serif", size=TYPE["title"], weight="500",
        draw_in=draw, delay=delay,
    ))
    info = (
        f"DIR. {scene.director.upper()} · "
        f"SCENE {scene.scene_number}: {scene.location.upper()} · "
        f"PG 1/1"
    )
    parts.append(text(
        PAGE["margin_x"], PAGE["margin_y"] + 38, info,
        font="mono", size=TYPE["caption"], fill=DRY_INK["fg_dim"], letter_spacing="0.05em",
        draw_in=draw, delay=delay + 0.2,
    ))
    rule_y = PAGE["margin_y"] + 60
    parts.append(line(
        PAGE["margin_x"], rule_y,
        w - PAGE["margin_x"], rule_y,
        stroke=DRY_INK["fg"], width=STROKE["medium"],
        draw_in=draw if animated else 0.0,
        delay=delay + 0.4,
    ))
    parts.append(_progress_indicator(scene, w, animated=animated,
                                     static_filled=static_filled))
    return "".join(parts)


def _progress_indicator(scene: Scene, w: int, *, animated: bool,
                        static_filled: int | None = None) -> str:
    """Right-aligned progress chip in the header area:

        1A → 1B → 1C → 1D → 1E → 1F
        ● ○ ○ ○ ○ ○

    In static mode, all dots filled by default. Pass `static_filled=k`
    to fill only the first k dots — used by progressive GIF frames where
    we render successive snapshots, each showing one more shot complete.

    In animated mode, each dot fills as the corresponding shot starts.
    """
    n = min(len(scene.shots), 6)
    if n == 0:
        return ""
    labels = [s.label for s in scene.shots[:n]]

    margin_x = PAGE["margin_x"]
    indicator_y = PAGE["margin_y"] + 28
    chip_x_right = w - margin_x

    parts: list[str] = []
    label_str = " → ".join(labels)
    parts.append(text(
        chip_x_right, indicator_y, label_str,
        font="mono", size=TYPE["tiny"], fill=DRY_INK["fg_dim"],
        letter_spacing="0.1em",
        anchor="end",
        draw_in=0.5 if animated else 0.0,
        delay=(HEADER_DELAY + 0.3) if animated else 0.0,
    ))

    dot_y = indicator_y + 14
    dot_spacing = 14.0
    total_dots_width = (n - 1) * dot_spacing
    dot_start_x = chip_x_right - total_dots_width

    fill_threshold = static_filled if static_filled is not None else n

    for i in range(n):
        cx = dot_start_x + i * dot_spacing
        if not animated:
            # Static: filled if i < fill_threshold, empty otherwise
            if i < fill_threshold:
                parts.append(
                    f"<circle cx='{cx:.2f}' cy='{dot_y:.2f}' r='3' "
                    f"fill='{DRY_INK['accent']}' stroke='{DRY_INK['accent']}' "
                    f"stroke-width='1'/>"
                )
            else:
                parts.append(
                    f"<circle cx='{cx:.2f}' cy='{dot_y:.2f}' r='3' "
                    f"fill='none' stroke='{DRY_INK['accent']}' "
                    f"stroke-width='1'/>"
                )
        else:
            # Animated: empty by default, fill swaps at shot_start_offset(i)
            shot_t = shot_start_offset(i)
            parts.append(
                f"<circle cx='{cx:.2f}' cy='{dot_y:.2f}' r='3' "
                f"fill='none' stroke='{DRY_INK['accent']}' "
                f"stroke-width='1'>"
                f"<set attributeName='fill' to='{DRY_INK['accent']}' "
                f"begin='{shot_t:.2f}s'/>"
                f"</circle>"
            )
    return "".join(parts)


def _shot_position(index: int) -> tuple[float, float, float, float, float, float]:
    """Compute (cell_w, frame_w, cell_h, frame_h, x, y) for shot at index."""
    cell_w = (PAGE["width"] - 2 * PAGE["margin_x"] - (PAGE["cols"] - 1) * PAGE["gutter_x"]) / PAGE["cols"]
    inner_h = PAGE["height"] - PAGE["header_h"] - PAGE["footer_h"] - 2 * PAGE["margin_y"]
    cell_h = (inner_h - (PAGE["rows"] - 1) * PAGE["gutter_y"]) / PAGE["rows"]
    frame_w = cell_w
    frame_h = cell_h * 0.62
    col = index % PAGE["cols"]
    row = index // PAGE["cols"]
    x = PAGE["margin_x"] + col * (cell_w + PAGE["gutter_x"])
    y = PAGE["margin_y"] + PAGE["header_h"] + row * (cell_h + PAGE["gutter_y"])
    return cell_w, frame_w, cell_h, frame_h, x, y


def _frames(scene: Scene, *, animated: bool) -> list[str]:
    shots = scene.shots[:6]
    parts: list[str] = []
    for idx, shot in enumerate(shots):
        _, frame_w, _, frame_h, x, y = _shot_position(idx)
        global_offset = shot_start_offset(idx) if animated else 0.0
        parts.append(_render_one_shot(
            shot, x, y, frame_w, frame_h,
            animated=animated,
            global_offset=global_offset,
        ))
    return parts


def _render_one_shot(shot: Shot, x: float, y: float,
                     frame_w: float, frame_h: float,
                     *, animated: bool = True,
                     global_offset: float = 0.0) -> str:
    """One frame cell: label header, frame box, content, metadata, caption.

    `global_offset` is the seconds-from-scene-start at which this shot's
    local timeline begins. In streaming mode it stays at 0.0; in static
    mode it stagger-offsets per shot.
    """
    parts: list[str] = []
    t = SHOT_TIMING

    # Label header above frame
    label_text = (
        f"{shot.label} · {shot.shot_type.value.replace('_', ' ')} · "
        f"{shot.description.upper()[:60]}"
    )
    parts.append(text(
        0, -8, label_text,
        font="mono", size=TYPE["label"], fill=DRY_INK["fg_dim"], letter_spacing="0.1em",
        draw_in=t.label_dur if animated else 0.0,
        delay=global_offset + t.label_in,
    ))

    # Frame border
    parts.append(rect(
        0, 0, frame_w, frame_h,
        stroke=DRY_INK["fg"], stroke_width=STROKE["border"],
        draw_in=t.border_dur if animated else 0.0,
        delay=global_offset + t.border_in,
    ))

    # Frame interior content
    parts.append(_frame_interior(
        shot, frame_w, frame_h,
        animated=animated, global_offset=global_offset,
    ))

    # Metadata strip
    parts.append(_metadata_strip(
        shot, frame_h + 14, frame_w=frame_w,
        animated=animated, global_offset=global_offset,
    ))

    # Italic caption
    if shot.caption:
        parts.append(text(
            0, frame_h + 64, shot.caption,
            font="serif", size=TYPE["subtitle"], style="italic",
            draw_in=t.caption_dur if animated else 0.0,
            delay=global_offset + t.caption_in,
        ))

    # Full-cell click target for the web director UI. Empty SVG space does
    # not receive pointer events unless we provide an explicit hit area.
    parts.append(
        f"<rect class='shot-hitbox' x='-8' y='-24' "
        f"width='{frame_w + 16:.2f}' height='{frame_h + 112:.2f}' "
        "fill='transparent' stroke='none' pointer-events='all'/>"
    )

    return (
        f"<g data-shot-label='{shot.label}' data-shot-type='{shot.shot_type.value}' "
        f"transform='translate({x:.2f}, {y:.2f})'>"
        + "".join(parts)
        + "</g>"
    )


def _frame_interior(shot: Shot, frame_w: float, frame_h: float,
                    *, animated: bool, global_offset: float) -> str:
    clip_id = f"clip_{shot.label.replace(' ', '_')}"
    inner: list[str] = []
    t = SHOT_TIMING

    is_closeup = shot.shot_type in (ShotType.CLOSE_UP, ShotType.ECU)

    if not is_closeup:
        # Prefer Kimi-enriched custom SVG if the enrich step generated one
        custom = getattr(shot.environment, "custom_svg", None)
        if custom:
            # Wrap the custom fragment in a fade-in group so it animates
            # in sync with the rest of the shot.
            from scripts.templates.svg_primitives import group as _g
            inner.append(_g(
                custom,
                fade_in=t.env_dur if animated else 0.0,
                delay=global_offset + t.env_in,
            ))
        else:
            # Environment sub-stagger via templates
            inner.append(render_environment(
                shot.environment, frame_w, frame_h,
                draw_in=t.env_dur if animated else 0.0,
                delay=global_offset + t.env_in,
                stagger=t.env_stagger,
            ))

    # Figures — look up silhouette in character_bible by role for visual continuity
    bible_silhouettes = _load_bible_silhouettes()

    if is_closeup and shot.figures:
        from scripts.templates.figures import render_face_close_up
        primary = shot.figures[0]
        primary_silhouette = bible_silhouettes.get(primary.role.lower(), primary.state or "")
        face_scale = (frame_h * 0.7) / 160
        face_svg = render_face_close_up(
            primary.facing,
            draw_in=t.figure_dur if animated else 0.0,
            delay=global_offset + t.figure_in,
            silhouette=primary_silhouette,
        )
        inner.append(
            f"<g transform='translate({frame_w * 0.5:.2f}, {frame_h * 0.5:.2f}) "
            f"scale({face_scale:.2f})'>{face_svg}</g>"
        )
    else:
        for fig in shot.figures:
            sil = bible_silhouettes.get(fig.role.lower(), fig.state or "")
            inner.append(render_figure(
                fig, frame_w, frame_h,
                draw_in=t.figure_dur if animated else 0.0,
                delay=global_offset + t.figure_in,
                silhouette=sil,
            ))

    if shot.eye_line:
        inner.append(render_eyeline(
            shot.eye_line, frame_w, frame_h,
            draw_in=t.annotation_dur if animated else 0.0,
            delay=global_offset + t.annotation_in,
        ))
    for ann in shot.annotations:
        inner.append(render_annotation(
            ann, frame_w, frame_h,
            draw_in=t.annotation_dur if animated else 0.0,
            delay=global_offset + t.annotation_in,
        ))

    return (
        f"<defs><clipPath id='{clip_id}'>"
        f"<rect width='{frame_w:.2f}' height='{frame_h:.2f}'/>"
        f"</clipPath></defs>"
        f"<g clip-path='url(#{clip_id})'>" + "".join(inner) + "</g>"
    )


def _metadata_strip(shot: Shot, y: float, frame_w: float = 424.0,
                    *, animated: bool = False, global_offset: float = 0.0) -> str:
    parts: list[str] = []
    t = SHOT_TIMING
    col_starts = [0.0, 0.18, 0.50, 0.76]
    col_widths = [0.18, 0.32, 0.26, 0.24]

    def char_budget(frac: float) -> int:
        return max(int((frac * frame_w) / 7.5) - 1, 4)

    cols = [
        ("LENS", shot.lens),
        ("MOVE", shot.movement),
        ("ANGLE", shot.angle),
        ("DURATION", shot.duration),
    ]
    for (label, value), start_frac, width_frac in zip(cols, col_starts, col_widths):
        x_pos = start_frac * frame_w
        budget = char_budget(width_frac)
        parts.append(text(
            x_pos, y, label,
            font="mono", size=TYPE["label"], fill=DRY_INK["fg_dim"], letter_spacing="0.1em",
            draw_in=t.metadata_dur if animated else 0.0,
            delay=global_offset + t.metadata_in,
        ))
        parts.append(text(
            x_pos, y + 16, _truncate(value, budget),
            font="mono", size=TYPE["caption"],
            draw_in=t.metadata_dur if animated else 0.0,
            delay=global_offset + t.metadata_in + 0.1,
        ))
    return "".join(parts)


def _truncate(s: str, max_len: int) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len - 1] + "…"


def _footer(scene: Scene, w: int, h: int, *, animated: bool, total_shots: int,
            patches_applied: int | None = None,
            memory_active: bool = False) -> str:
    coverage = " → ".join(s.shot_type.value.replace("_", " ") for s in scene.shots[:6])
    total_dur = _scene_duration(scene)
    left = f"SCENE {scene.scene_number} TOTAL · {total_dur} · {total_shots} SHOTS · COVERAGE: {coverage}"
    right = "generated by storyboard · draft v1"
    y = h - PAGE["margin_y"]
    # Footer appears late if animated — after the last shot finishes
    last_offset = shot_start_offset(min(total_shots, 6) - 1) if total_shots else 0
    footer_delay = (last_offset + 3.6) if animated else 0.0

    parts = [
        line(PAGE["margin_x"], y - 14, w - PAGE["margin_x"], y - 14,
             stroke=DRY_INK["fg"], width=STROKE["thin"],
             draw_in=0.5 if animated else 0.0,
             delay=footer_delay),
        text(PAGE["margin_x"], y, left,
             font="mono", size=TYPE["tiny"], fill=DRY_INK["fg_dim"], letter_spacing="0.08em",
             draw_in=0.5 if animated else 0.0,
             delay=footer_delay + 0.1),
        text(w - PAGE["margin_x"], y, right,
             font="mono", size=TYPE["tiny"], fill=DRY_INK["fg_dim"],
             style="italic", anchor="end",
             draw_in=0.5 if animated else 0.0,
             delay=footer_delay + 0.2),
    ]

    # Critique state badge — small mono line above the footer rule.
    # Only rendered if we have something to say.
    if patches_applied is not None or memory_active:
        bits: list[str] = []
        if patches_applied is not None:
            bits.append(
                f"critique: {patches_applied} patch{'es' if patches_applied != 1 else ''} applied"
            )
            bits.append("0 invalid refs")
        bits.append(f"memory: {'active' if memory_active else 'inactive'}")
        badge = "  ·  ".join(bits)
        parts.append(text(
            PAGE["margin_x"], y - 22, badge,
            font="mono", size=TYPE["tiny"],
            fill=DRY_INK["accent"],
            letter_spacing="0.08em",
            draw_in=0.5 if animated else 0.0,
            delay=footer_delay + 0.05,
        ))

    return "".join(parts)


def _scene_duration(scene: Scene) -> str:
    for shot in reversed(scene.shots):
        if "–" in shot.duration or "-" in shot.duration:
            try:
                end = shot.duration.replace("–", "-").split("-")[-1].strip()
                if end:
                    return f"0:{end.split(':')[-1].zfill(2)}"
            except (ValueError, IndexError):
                continue
    return f"~{len(scene.shots) * 6}s"


def _load_bible_silhouettes() -> dict[str, str]:
    """Load role → silhouette mapping from the persistent character bible.

    Cached only for the duration of one render — render is fast and the
    bible is small. Importing lazily so render.py stays usable in
    environments without the bible module wired up.
    """
    try:
        from scripts.character_bible import CharacterBible
        bible = CharacterBible.load()
        return {role: entry.silhouette or "" for role, entry in bible.entries.items()}
    except Exception:
        return {}


__all__ = ["render_scene", "render_shot"]
