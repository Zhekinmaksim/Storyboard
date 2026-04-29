"""Low-level SVG emitters. Pure string helpers — no Scene knowledge.

All higher-level templates compose these. Keeping them dumb and stateless
means render.py can stay declarative.

NEW in v0.1: every shape can be emitted with `draw_in=<seconds>` and
`delay=<seconds>` to make it animate as if hand-drawn (stroke-dasharray
trick + SMIL animate). Classic technique: set stroke-dasharray to the
path's perimeter and stroke-dashoffset to the same value, then animate
dashoffset to 0. Visible effect: a stroke that grows from one end.

For filled shapes (where dashoffset on a fill makes no sense), we
animate opacity 0 → 1 with a small stagger. Less dramatic but
consistent. Both modes use SMIL `fill='freeze'` so the end state is
preserved when the animation completes.

SMIL was deprecated by Chrome years ago but never actually removed; it
works in Firefox, Safari, librsvg, rsvg-convert. For the Hermes demo
we record in Firefox. The static SVG (with animations baked in) is
self-contained — open the file in a browser, it draws itself.
"""

from __future__ import annotations

import math
from xml.sax.saxutils import escape as xml_escape

from scripts.style import DRY_INK, FONTS, STROKE, TYPE


def text(
    x: float,
    y: float,
    content: str,
    *,
    font: str = "mono",
    size: int = TYPE["label"],
    fill: str = DRY_INK["fg"],
    weight: str = "normal",
    style: str = "normal",
    letter_spacing: str | None = None,
    anchor: str = "start",
    draw_in: float = 0.0,
    delay: float = 0.0,
) -> str:
    family = FONTS.get(font, FONTS["mono"])
    spacing = f" letter-spacing='{letter_spacing}'" if letter_spacing else ""
    open_tag = (
        f"<text x='{x:.2f}' y='{y:.2f}' "
        f"font-family=\"{family}\" font-size='{size}' fill='{fill}' "
        f"font-weight='{weight}' font-style='{style}' "
        f"text-anchor='{anchor}'{spacing}"
    )
    if draw_in > 0:
        return (
            f"{open_tag} opacity='0'>{xml_escape(content)}"
            f"{_fade_in_smil(draw_in, delay)}</text>"
        )
    return f"{open_tag}>{xml_escape(content)}</text>"


def line(x1: float, y1: float, x2: float, y2: float,
         *, stroke: str = DRY_INK["fg"], width: float = STROKE["thin"],
         dash: str | None = None, opacity: float = 1.0,
         draw_in: float = 0.0, delay: float = 0.0) -> str:
    if draw_in > 0:
        length = math.hypot(x2 - x1, y2 - y1)
        return (
            f"<line x1='{x1:.2f}' y1='{y1:.2f}' x2='{x2:.2f}' y2='{y2:.2f}' "
            f"stroke='{stroke}' stroke-width='{width:.2f}' "
            f"stroke-dasharray='{length:.1f}' stroke-dashoffset='{length:.1f}'>"
            f"{_stroke_draw_smil(length, draw_in, delay)}"
            f"</line>"
        )
    dash_attr = f" stroke-dasharray='{dash}'" if dash else ""
    op_attr = f" opacity='{opacity:.2f}'" if opacity != 1.0 else ""
    return (
        f"<line x1='{x1:.2f}' y1='{y1:.2f}' x2='{x2:.2f}' y2='{y2:.2f}' "
        f"stroke='{stroke}' stroke-width='{width:.2f}'{dash_attr}{op_attr}/>"
    )


def rect(x: float, y: float, w: float, h: float,
         *, stroke: str | None = None, fill: str = "none",
         stroke_width: float = STROKE["regular"], opacity: float = 1.0,
         draw_in: float = 0.0, delay: float = 0.0) -> str:
    stroke_attr = f"stroke='{stroke}' stroke-width='{stroke_width:.2f}'" if stroke else "stroke='none'"
    op_attr = f" opacity='{opacity:.2f}'" if opacity < 1.0 else ""

    if draw_in > 0 and stroke:
        # Animate the perimeter as a single stroke
        perimeter = 2 * (w + h)
        return (
            f"<rect x='{x:.2f}' y='{y:.2f}' width='{w:.2f}' height='{h:.2f}' "
            f"fill='{fill}' {stroke_attr} "
            f"stroke-dasharray='{perimeter:.1f}' stroke-dashoffset='{perimeter:.1f}'>"
            f"{_stroke_draw_smil(perimeter, draw_in, delay)}"
            f"</rect>"
        )

    if draw_in > 0 and fill != "none":
        return (
            f"<rect x='{x:.2f}' y='{y:.2f}' width='{w:.2f}' height='{h:.2f}' "
            f"fill='{fill}' {stroke_attr} opacity='0'>"
            f"{_fade_in_smil(draw_in, delay)}"
            f"</rect>"
        )

    return f"<rect x='{x:.2f}' y='{y:.2f}' width='{w:.2f}' height='{h:.2f}' fill='{fill}' {stroke_attr}{op_attr}/>"


def path(d: str, *, fill: str = "none", stroke: str | None = None,
         stroke_width: float = STROKE["regular"], opacity: float = 1.0,
         draw_in: float = 0.0, delay: float = 0.0,
         path_length: float | None = None) -> str:
    """Render a path. For animated drawing, supply path_length (rough
    perimeter estimate). 1000 is a safe generic value if unknown — the
    dashoffset just needs to be ≥ true length.
    """
    stroke_attr = f"stroke='{stroke}' stroke-width='{stroke_width:.2f}'" if stroke else "stroke='none'"
    op_attr = f" opacity='{opacity:.2f}'" if opacity < 1.0 else ""

    if draw_in > 0 and stroke:
        plen = path_length or 1000
        return (
            f"<path d='{d}' fill='{fill}' {stroke_attr}{op_attr} "
            f"stroke-dasharray='{plen:.0f}' stroke-dashoffset='{plen:.0f}'>"
            f"{_stroke_draw_smil(plen, draw_in, delay)}"
            f"</path>"
        )

    if draw_in > 0 and fill != "none":
        return (
            f"<path d='{d}' fill='{fill}' {stroke_attr} opacity='0'>"
            f"{_fade_in_smil(draw_in, delay)}"
            f"</path>"
        )

    return f"<path d='{d}' fill='{fill}' {stroke_attr}{op_attr}/>"


def circle(cx: float, cy: float, r: float,
           *, fill: str = DRY_INK["fg"], stroke: str | None = None,
           stroke_width: float = STROKE["regular"],
           draw_in: float = 0.0, delay: float = 0.0) -> str:
    stroke_attr = f"stroke='{stroke}' stroke-width='{stroke_width:.2f}'" if stroke else "stroke='none'"

    if draw_in > 0 and stroke:
        circumference = 2 * math.pi * r
        return (
            f"<circle cx='{cx:.2f}' cy='{cy:.2f}' r='{r:.2f}' fill='{fill}' {stroke_attr} "
            f"stroke-dasharray='{circumference:.1f}' stroke-dashoffset='{circumference:.1f}'>"
            f"{_stroke_draw_smil(circumference, draw_in, delay)}"
            f"</circle>"
        )

    if draw_in > 0 and fill != "none":
        return (
            f"<circle cx='{cx:.2f}' cy='{cy:.2f}' r='{r:.2f}' fill='{fill}' {stroke_attr} opacity='0'>"
            f"{_fade_in_smil(draw_in, delay)}"
            f"</circle>"
        )

    return f"<circle cx='{cx:.2f}' cy='{cy:.2f}' r='{r:.2f}' fill='{fill}' {stroke_attr}/>"


def polygon(points: list[tuple[float, float]], *, fill: str = DRY_INK["fg"],
            draw_in: float = 0.0, delay: float = 0.0) -> str:
    pt_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    if draw_in > 0:
        return (
            f"<polygon points='{pt_str}' fill='{fill}' opacity='0'>"
            f"{_fade_in_smil(draw_in, delay)}"
            f"</polygon>"
        )
    return f"<polygon points='{pt_str}' fill='{fill}'/>"


def group(*children: str, transform: str | None = None,
          clip_path: str | None = None,
          fade_in: float = 0.0, delay: float = 0.0) -> str:
    attrs = []
    if transform:
        attrs.append(f"transform='{transform}'")
    if clip_path:
        attrs.append(f"clip-path='url(#{clip_path})'")
    attr_str = (" " + " ".join(attrs)) if attrs else ""

    if fade_in > 0:
        return (
            f"<g{attr_str} opacity='0'>"
            + "".join(children)
            + _fade_in_smil(fade_in, delay)
            + "</g>"
        )
    return f"<g{attr_str}>" + "".join(children) + "</g>"


# =================== SMIL helpers ===================

def _stroke_draw_smil(length: float, duration: float, delay: float) -> str:
    """Animate stroke-dashoffset from `length` to 0 — the classic
    "drawing the line" effect. fill='freeze' preserves the final state.
    """
    return (
        f"<animate attributeName='stroke-dashoffset' "
        f"from='{length:.1f}' to='0' "
        f"begin='{delay:.2f}s' dur='{duration:.2f}s' "
        f"fill='freeze'/>"
    )


def _fade_in_smil(duration: float, delay: float) -> str:
    """Animate opacity 0 → 1. Used for filled shapes and groups."""
    return (
        f"<animate attributeName='opacity' "
        f"from='0' to='1' "
        f"begin='{delay:.2f}s' dur='{duration:.2f}s' "
        f"fill='freeze'/>"
    )


__all__ = ["text", "line", "rect", "path", "circle", "polygon", "group"]
