"""Dry Ink visual constants. The single source of truth for palette,
typography, and stroke scale. Anything that emits SVG imports from here.

Rationale: hardcoding these in render.py was the first temptation; pulling
them into one module makes the style enforceable and trivially tweakable
across all four POC genres without hunting through render code.
"""

from __future__ import annotations

# Palette — Dry Ink. Cream paper, warm ink, dried-blood accent.
DRY_INK = {
    "bg": "#f5f0e6",            # cream paper background
    "fg": "#1f1d1a",            # warm ink, almost black
    "fg_dim": "#6a5f56",        # muted ink for labels / metadata
    "accent": "#8a3a2c",        # dried-ink red (eye-lines, blood, alerts)
    "ok": "#2c5a3a",            # deep green (rare, status only)
    "rule": "#1f1d1a",          # rule lines, frame borders, identical to fg
}

# Fonts. Newsreader for serif (titles, captions, dialog), Geist Mono for
# metadata. Web-safe fallbacks are included so the SVG renders even when
# the user has neither installed.
FONTS = {
    "serif": "'Newsreader', 'Source Serif Pro', Georgia, serif",
    "mono": "'Geist Mono', 'IBM Plex Mono', 'Menlo', monospace",
}

# Stroke widths — fixed scale, no in-between values. If you reach for
# a value not on this list, you're decorating; stop.
STROKE = {
    "hairline": 0.4,
    "thin": 0.5,
    "regular": 0.8,
    "medium": 1.0,
    "frame": 1.5,
    "emphasis": 2.0,
    "border": 2.5,
    "heavy": 3.0,
}

# Type sizes (px) — also a fixed scale.
TYPE = {
    "tiny": 9,
    "label": 10,
    "caption": 13,
    "subtitle": 14,
    "title": 22,
}

# Page geometry. Default 6-shot 3x2 layout. Numbers chosen to render at
# a reasonable density on both screen and print.
PAGE = {
    "width": 1400,
    "height": 900,
    "margin_x": 40,
    "margin_y": 40,
    "header_h": 80,
    "footer_h": 40,
    "gutter_x": 24,
    "gutter_y": 60,        # extra room for caption + metadata under each frame
    "cols": 3,
    "rows": 2,
}


def frame_size() -> tuple[float, float]:
    """Computed cell size for a single shot, given current PAGE config."""
    inner_w = PAGE["width"] - 2 * PAGE["margin_x"]
    inner_h = PAGE["height"] - PAGE["header_h"] - PAGE["footer_h"] - 2 * PAGE["margin_y"]
    cell_w = (inner_w - (PAGE["cols"] - 1) * PAGE["gutter_x"]) / PAGE["cols"]
    cell_h = (inner_h - (PAGE["rows"] - 1) * PAGE["gutter_y"]) / PAGE["rows"]
    # Each cell allocates ~40% to the metadata + caption stack under the frame.
    frame_h = cell_h * 0.62
    return cell_w, frame_h


__all__ = ["DRY_INK", "FONTS", "STROKE", "TYPE", "PAGE", "frame_size"]
