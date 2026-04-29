"""Live Kimi K2.5 tests via OpenRouter. Skipped unless OPENROUTER_API_KEY
is set, so CI without secrets stays green.

Run locally with:
    OPENROUTER_API_KEY=sk-or-... pytest tests/test_integration.py -v
"""

from __future__ import annotations

import os

import pytest

from scripts.parse import parse_prose
from scripts.render import render_scene


pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set — skipping live Kimi tests",
)


def test_parse_short_prose_returns_valid_scene():
    prose = (
        "A detective enters a rain-soaked alley at night. She finds a body. "
        "She calls her partner."
    )
    scene = parse_prose(prose)
    assert 3 <= len(scene.shots) <= 8
    assert all(s.label for s in scene.shots)
    # All shots should have a caption (Kimi was instructed)
    assert all(s.caption for s in scene.shots)


def test_parse_then_render_produces_svg():
    prose = "Two characters argue across a kitchen table at noon."
    scene = parse_prose(prose)
    svg = render_scene(scene)
    assert svg.startswith("<svg")
    assert "</svg>" in svg
