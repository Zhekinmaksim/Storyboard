"""Smoke tests — pure Python only, no Kimi calls.

These tests run in CI on every push. They prove the deterministic parts
of the pipeline (scene round-trip, render, iterate, critique guards)
work without a network.

Live Kimi tests live in tests/test_integration.py and are skipped unless
OPENROUTER_API_KEY is set, so CI without secrets stays green.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.critique import ALLOWED_FIELDS, Revision, critique_board
from scripts.iterate import apply_revisions
from scripts.kimi_client import KimiError, extract_text
from scripts.parse import stub_scene
from scripts.render import render_scene
from scripts.scene import (
    EyeLine, EyeLineDirection, Facing,
    Figure, Scene, ShotType,
)


# =================== Scene round-trip ===================

def test_scene_from_dict_minimal():
    s = Scene.from_dict({"title": "Test", "shots": []})
    assert s.title == "Test"
    assert s.scene_number == "01"
    assert s.shots == []


def test_scene_round_trip_preserves_fields():
    payload = {
        "title": "Rain",
        "scene_number": "02",
        "location": "EXT alley · night",
        "director": "Zmaxx",
        "shots": [{
            "label": "1A",
            "shot_type": "WIDE",
            "description": "alley",
            "lens": "24mm",
            "movement": "Static",
            "angle": "High",
            "duration": "0:00 – 0:06",
            "caption": "first",
            "figures": [{
                "role": "detective",
                "pose": "STANDING",
                "facing": "FRONT",
                "position": [0.5, 0.7],
                "scale": 0.5,
            }],
            "environment": {"kind": "EXT", "horizon_y": 0.55, "has_rain": True},
            "annotations": [],
        }],
    }
    s = Scene.from_dict(payload)
    rebuilt = Scene.from_dict(json.loads(s.to_json()))
    assert rebuilt.title == s.title
    assert len(rebuilt.shots) == 1
    assert rebuilt.shots[0].label == "1A"
    assert rebuilt.shots[0].shot_type == ShotType.WIDE
    assert rebuilt.shots[0].figures[0].role == "detective"


def test_scene_rejects_unknown_shot_type():
    with pytest.raises(ValueError):
        Scene.from_dict({
            "title": "X",
            "shots": [{
                "label": "1A",
                "shot_type": "INVALID_TYPE",
                "description": "",
            }],
        })


def test_scene_accepts_string_eye_line():
    scene = Scene.from_dict({
        "title": "X",
        "shots": [{
            "label": "1A",
            "shot_type": "CLOSE_UP",
            "description": "looks left",
            "eye_line": "CAMERA_LEFT",
        }],
    })
    assert scene.shots[0].eye_line is not None
    assert scene.shots[0].eye_line.direction == EyeLineDirection.CAMERA_LEFT


def test_scene_accepts_common_kimi_enum_aliases():
    scene = Scene.from_dict({
        "title": "X",
        "shots": [{
            "label": "1A",
            "shot_type": "close up",
            "description": "sits and looks left",
            "eye_line": {"direction": "left", "axis_status": "on"},
            "figures": [{
                "role": "sibling",
                "pose": "SITTING",
                "facing": "toward camera",
            }],
        }],
    })
    shot = scene.shots[0]
    assert shot.shot_type == ShotType.CLOSE_UP
    assert shot.figures[0].pose.value == "SEATED"
    assert shot.figures[0].facing.value == "FRONT"
    assert shot.eye_line is not None
    assert shot.eye_line.direction == EyeLineDirection.CAMERA_LEFT


def test_scene_accepts_cinematic_shot_type_aliases():
    scene = Scene.from_dict({
        "title": "X",
        "shots": [
            {"label": "1A", "shot_type": "LONG_LENS", "description": "compressed face"},
            {"label": "1B", "shot_type": "INSERT", "description": "clock hand"},
            {"label": "1C", "shot_type": "ESTABLISHING", "description": "empty station"},
        ],
    })
    assert scene.shots[0].shot_type == ShotType.CLOSE_UP
    assert scene.shots[1].shot_type == ShotType.ECU
    assert scene.shots[2].shot_type == ShotType.WIDE


def test_scene_tolerates_null_numeric_fields_from_kimi():
    scene = Scene.from_dict({
        "title": "X",
        "shots": [{
            "label": "1A",
            "shot_type": "WIDE",
            "description": "figure in room",
            "figures": [{
                "role": "subject",
                "position": None,
                "scale": None,
            }],
            "environment": {
                "kind": "INT",
                "horizon_y": None,
            },
        }],
    })
    assert scene.shots[0].figures[0].position == (0.5, 0.7)
    assert scene.shots[0].figures[0].scale == 1.0
    assert scene.shots[0].environment.horizon_y == 0.55


def test_scene_preserves_subway_environment_flag():
    scene = Scene.from_dict({
        "title": "Subway",
        "shots": [{
            "label": "1A",
            "shot_type": "WIDE",
            "description": "subway platform",
            "environment": {"kind": "INT", "has_subway": True},
        }],
    })
    rebuilt = Scene.from_dict(json.loads(scene.to_json()))
    assert rebuilt.shots[0].environment.has_subway is True


def test_stub_scene_produces_six_shots():
    scene = stub_scene("A detective enters a rain-soaked alley at night. A phone rings.")
    assert len(scene.shots) == 6
    assert [shot.label for shot in scene.shots] == ["1A", "1B", "1C", "1D", "1E", "1F"]


def test_extract_text_rejects_empty_content():
    with pytest.raises(KimiError):
        extract_text({"choices": [{"message": {"content": None}}]})


# =================== Render ===================

def _minimal_scene() -> Scene:
    return Scene(
        title="Smoke Test",
        scene_number="01",
        location="EXT · DAY",
        director="Tester",
        shots=[
            type(_minimal_shot())(**vars(_minimal_shot()))
            if False else _minimal_shot()
        ],
    )


def _minimal_shot():
    from scripts.scene import Environment, Shot
    return Shot(
        label="1A",
        shot_type=ShotType.WIDE,
        description="empty",
        figures=[Figure(role="subject")],
        environment=Environment(kind="EXT"),
    )


def test_render_returns_well_formed_svg():
    svg = render_scene(_minimal_scene())
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "data-shot-label='1A'" in svg
    assert "Smoke Test" in svg


def test_render_includes_dry_ink_palette():
    svg = render_scene(_minimal_scene())
    assert "#f5f0e6" in svg  # cream bg
    assert "#1f1d1a" in svg  # warm ink


def test_render_emits_metadata_strip():
    svg = render_scene(_minimal_scene())
    assert "LENS" in svg
    assert "MOVE" in svg
    assert "ANGLE" in svg
    assert "DURATION" in svg


def test_render_handles_six_shots():
    """Build a 6-shot scene and confirm all six render."""
    from scripts.scene import Environment, Shot
    scene = Scene(
        title="Six Shots",
        shots=[
            Shot(label=f"1{c}", shot_type=ShotType.MEDIUM, description=str(i),
                 figures=[Figure(role="x")], environment=Environment(kind="INT"))
            for i, c in enumerate("ABCDEF")
        ],
    )
    svg = render_scene(scene)
    for c in "ABCDEF":
        assert f"data-shot-label='1{c}'" in svg


def test_render_subway_visual_vocabulary():
    from scripts.scene import Environment, Shot
    scene = Scene(
        title="Subway Pursuit",
        location="INT SUBWAY STATION · NIGHT",
        shots=[
            Shot(
                label="1A",
                shot_type=ShotType.WIDE,
                description="train roars through tunnel as bullets spark",
                figures=[Figure(role="runner")],
                environment=Environment(
                    kind="INT",
                    has_subway=True,
                    props=["train", "tracks", "tunnel", "sparks", "smoke"],
                ),
            )
        ],
    )
    svg = render_scene(scene, animated=False)
    assert "env-subway-0" in svg
    assert "prop-train-0" in svg
    assert "prop-tracks-0" in svg
    assert "class='prop-tunnel'" in svg
    assert "prop-sparks-0" in svg
    assert "prop-smoke-0" in svg


def test_render_header_labels_use_two_short_rows():
    from scripts.scene import Environment, Shot
    long_description = (
        "a very long description that used to collide with the next frame header "
        "when rendered above the board"
    )
    scene = Scene(
        title="Labels",
        shots=[
            Shot(
                label="1A",
                shot_type=ShotType.WIDE,
                description=long_description,
                environment=Environment(kind="INT"),
            )
        ],
    )
    svg = render_scene(scene, animated=False)
    assert ">1A · WIDE</text>" in svg
    assert "A VERY LONG DESCRIPTION THAT USED TO COLL…" in svg
    assert long_description.upper() not in svg


def test_render_close_up_uses_face_primitive():
    """CLOSE_UP shots render an oval face, not a stick figure."""
    from scripts.scene import Environment, Shot
    scene = Scene(
        title="CU Test",
        shots=[Shot(
            label="1A",
            shot_type=ShotType.CLOSE_UP,
            description="recognition",
            figures=[Figure(role="detective", facing=Facing.THREE_QUARTER_LEFT)],
            environment=Environment(kind="EXT"),
        )],
    )
    svg = render_scene(scene)
    # Face primitive emits <ellipse> for the head
    assert "<ellipse" in svg


# =================== Iterate ===================

def test_apply_revisions_changes_field():
    from scripts.scene import Environment, Shot
    scene = Scene(
        title="x",
        shots=[Shot(
            label="1A", shot_type=ShotType.WIDE, description="", lens="24mm",
            figures=[], environment=Environment(),
        )],
    )
    revs = [Revision("1A", "lens", "85mm", "more isolation")]
    new = apply_revisions(scene, revs)
    assert new.shots[0].lens == "85mm"
    # Original untouched
    assert scene.shots[0].lens == "24mm"


def test_apply_revisions_drops_unknown_label():
    from scripts.scene import Environment, Shot
    scene = Scene(
        title="x",
        shots=[Shot(label="1A", shot_type=ShotType.WIDE, description="",
                    figures=[], environment=Environment())],
    )
    revs = [Revision("9X", "lens", "85mm", "")]  # not in scene
    new = apply_revisions(scene, revs)
    assert new.shots[0].lens == "35mm"  # default unchanged


def test_apply_eye_line_direction():
    from scripts.scene import Environment, Shot
    scene = Scene(
        title="x",
        shots=[Shot(
            label="1A", shot_type=ShotType.CLOSE_UP, description="",
            figures=[], environment=Environment(),
            eye_line=EyeLine(direction=EyeLineDirection.CAMERA_LEFT),
        )],
    )
    revs = [Revision("1A", "eye_line.direction", "CAMERA_RIGHT", "180-line crossed")]
    new = apply_revisions(scene, revs)
    assert new.shots[0].eye_line.direction == EyeLineDirection.CAMERA_RIGHT


# =================== Critique guards ===================

def test_allowed_fields_are_finite():
    """The critique field whitelist exists to prevent runaway revisions."""
    assert "lens" in ALLOWED_FIELDS
    assert "movement" in ALLOWED_FIELDS
    assert "shot_type" not in ALLOWED_FIELDS  # cannot change shot type via critique
    assert "figures" not in ALLOWED_FIELDS    # cannot edit figures via critique


def test_critique_drops_invalid_labels(monkeypatch):
    """If Kimi hallucinates a shot label, the revision is filtered out."""
    from scripts import critique
    # Stub kimi_vision to return a hallucinated revision
    fake_response = json.dumps({
        "revisions": [
            {"shot_label": "1A", "field": "lens", "new_value": "85mm", "reason": "ok"},
            {"shot_label": "9Z", "field": "lens", "new_value": "24mm", "reason": "bad"},
        ]
    })

    def fake_vision(*args, **kwargs):
        return fake_response

    monkeypatch.setattr(critique, "kimi_vision", fake_vision)

    from scripts.scene import Environment, Shot
    scene = Scene(
        title="x",
        shots=[Shot(label="1A", shot_type=ShotType.WIDE, description="",
                    figures=[], environment=Environment())],
    )
    revs = critique_board(scene, b"fake-png", use_cache=False)
    assert len(revs) == 1
    assert revs[0].shot_label == "1A"
    assert revs[0].new_value == "85mm"


def test_critique_drops_unsupported_fields(monkeypatch):
    """If Kimi proposes a field not on the whitelist, drop it."""
    from scripts import critique
    fake_response = json.dumps({
        "revisions": [
            {"shot_label": "1A", "field": "figures", "new_value": "[]", "reason": "no"},
        ]
    })
    monkeypatch.setattr(critique, "kimi_vision", lambda *a, **k: fake_response)

    from scripts.scene import Environment, Shot
    scene = Scene(
        title="x",
        shots=[Shot(label="1A", shot_type=ShotType.WIDE, description="",
                    figures=[], environment=Environment())],
    )
    revs = critique_board(scene, b"fake-png", use_cache=False)
    assert revs == []


# =================== Examples reproduction ===================

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def test_noir_example_reproduces_six_shot_grid():
    """The shipped examples/noir-scene.json renders to a six-shot board."""
    path = EXAMPLES_DIR / "noir-scene.json"
    if not path.exists():
        pytest.skip("noir-scene.json not yet shipped")
    data = json.loads(path.read_text(encoding="utf-8"))
    scene = Scene.from_dict(data)
    assert len(scene.shots) == 6
    svg = render_scene(scene)
    for shot in scene.shots:
        assert f"data-shot-label='{shot.label}'" in svg


# =================== Animation ===================

def test_animated_render_includes_smil():
    """Animated mode emits SMIL <animate> tags."""
    from scripts.scene import Environment, Shot
    scene = Scene(
        title="Anim Test",
        shots=[Shot(label="1A", shot_type=ShotType.WIDE, description="",
                    figures=[Figure(role="x")], environment=Environment(kind="EXT"))],
    )
    svg = render_scene(scene, animated=True)
    assert "<animate" in svg
    assert "fill='freeze'" in svg
    # Should also have stroke-dashoffset for the drawing-stroke trick
    assert "stroke-dashoffset" in svg


def test_static_render_has_no_smil():
    """Default static mode emits no animations."""
    from scripts.scene import Environment, Shot
    scene = Scene(
        title="Static Test",
        shots=[Shot(label="1A", shot_type=ShotType.WIDE, description="",
                    figures=[Figure(role="x")], environment=Environment(kind="EXT"))],
    )
    svg = render_scene(scene, animated=False)
    assert "<animate" not in svg


def test_render_shot_returns_group():
    """Single-shot render emits a positioned <g> wrapper."""
    from scripts.render import render_shot
    from scripts.scene import Environment, Shot
    shot = Shot(label="1A", shot_type=ShotType.WIDE, description="test",
                figures=[Figure(role="x")], environment=Environment(kind="EXT"))
    scene = Scene(title="x", shots=[shot])
    g = render_shot(shot, scene, 0)
    assert g.startswith("<g data-shot-label='1A'")
    assert "class='shot-hitbox'" in g
    assert "pointer-events='all'" in g
    assert "</g>" in g


# =================== Enrich validation ===================

def test_enrich_validation_rejects_disallowed_tags():
    from scripts.enrich import _validate_fragment
    bad = "<text>hello</text><line x1='0' y1='0' x2='10' y2='10'/>"
    assert _validate_fragment(bad) is False


def test_enrich_validation_rejects_bad_color():
    from scripts.enrich import _validate_fragment
    bad = "<line x1='0' y1='0' x2='10' y2='10' stroke='#ff00ff' stroke-width='1.0'/>"
    assert _validate_fragment(bad) is False


def test_enrich_validation_accepts_valid_dry_ink_fragment():
    from scripts.enrich import _validate_fragment
    good = (
        "<line x1='0' y1='0' x2='100' y2='0' stroke='#1f1d1a' stroke-width='1.5'/>"
        "<rect x='10' y='10' width='50' height='30' fill='none' "
        "stroke='#6a5f56' stroke-width='0.8'/>"
    )
    assert _validate_fragment(good) is True


def test_enrich_skips_template_friendly_descriptions():
    """needs_enrichment returns False for descriptions that match template kw."""
    from scripts.enrich import needs_enrichment
    from scripts.scene import Environment, Shot
    shot = Shot(
        label="1A", shot_type=ShotType.WIDE, description="alley at night",
        environment=Environment(kind="EXT", description="rain-soaked alley"),
    )
    assert needs_enrichment(shot) is False


def test_enrich_triggers_for_unusual_descriptions():
    from scripts.enrich import needs_enrichment
    from scripts.scene import Environment, Shot
    shot = Shot(
        label="1A", shot_type=ShotType.WIDE, description="spaceship corridor",
        environment=Environment(kind="INT", description="crashed spaceship corridor with smoke"),
    )
    assert needs_enrichment(shot) is True


# =================== Silhouette parsing ===================

def test_silhouette_parses_long_coat():
    from scripts.templates.figures import parse_silhouette
    p = parse_silhouette("long coat, narrow shoulders, fedora hat")
    assert p.coat_length > 1.0
    assert p.shoulder_width < 1.0
    assert p.has_hat is True


def test_silhouette_parses_broad_short():
    from scripts.templates.figures import parse_silhouette
    p = parse_silhouette("broad shoulders, short jacket, square jaw")
    assert p.coat_length < 1.0
    assert p.shoulder_width > 1.0
    assert p.has_square_head is True


def test_silhouette_parses_silhouette_only():
    from scripts.templates.figures import parse_silhouette
    p = parse_silhouette("silhouette only, broad, no face")
    assert p.is_silhouette_only is True


def test_silhouette_empty_returns_defaults():
    from scripts.templates.figures import parse_silhouette
    p = parse_silhouette("")
    assert p.coat_length == 1.0
    assert p.shoulder_width == 1.0
    assert p.has_hat is False


# =================== Director memory ===================

def test_director_memory_round_trip(tmp_path, monkeypatch):
    """Save a rule, load it back, verify identical."""
    monkeypatch.setenv("STORYBOARD_OUTPUT_DIR", str(tmp_path))
    from scripts.director_memory import DirectorMemory, DirectorRule
    memory = DirectorMemory()
    rule = DirectorRule(
        id="rule_test_1",
        preference="prefer low-angle for suspense",
        applies_to=["suspense", "reveal"],
        source_revision={"scene": "01", "frame": "1F", "note": "Hitchcock"},
        created_at="2026-04-26T00:00:00+00:00",
    )
    memory.add_rule(rule)

    reloaded = DirectorMemory.load()
    assert len(reloaded.rules) == 1
    assert reloaded.rules[0].preference == rule.preference
    assert reloaded.rules[0].applies_to == ["suspense", "reveal"]


def test_director_memory_hint_matches_tags(tmp_path, monkeypatch):
    """When prose contains a tag word, the hint surfaces the rule."""
    monkeypatch.setenv("STORYBOARD_OUTPUT_DIR", str(tmp_path))
    from scripts.director_memory import DirectorMemory, DirectorRule
    memory = DirectorMemory()
    memory.add_rule(DirectorRule(
        id="r1",
        preference="prefer low-angle for suspense",
        applies_to=["suspense", "stairwell"],
    ))
    hint = memory.hint_for_prompt("She enters the stairwell. He follows.")
    assert "low-angle" in hint
    assert "stairwell" in hint or "applies to" in hint


def test_director_memory_hint_no_match_returns_empty(tmp_path, monkeypatch):
    """Without tag match, NO rule is surfaced — to avoid leaking
    irrelevant style preferences into unrelated scenes (e.g. a noir
    rule contaminating a comedy scene). The website explicitly
    promises 'future scenes that match the tags', and we honour that.
    """
    monkeypatch.setenv("STORYBOARD_OUTPUT_DIR", str(tmp_path))
    monkeypatch.delenv("STORYBOARD_MEMORY_FALLBACK", raising=False)
    from scripts.director_memory import DirectorMemory, DirectorRule
    memory = DirectorMemory()
    memory.add_rule(DirectorRule(id="r1", preference="rule one", applies_to=[]))
    memory.add_rule(DirectorRule(id="r2", preference="rule two", applies_to=[]))
    hint = memory.hint_for_prompt("totally unrelated prose about gardening")
    assert hint == ""


def test_director_memory_hint_fallback_opt_in(tmp_path, monkeypatch):
    """STORYBOARD_MEMORY_FALLBACK=1 brings back the old behaviour
    (surface most recent rule when nothing tag-matches). Used by CLI
    workflows where the user expects 'remember what I just told you'."""
    monkeypatch.setenv("STORYBOARD_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("STORYBOARD_MEMORY_FALLBACK", "1")
    from scripts.director_memory import DirectorMemory, DirectorRule
    memory = DirectorMemory()
    memory.add_rule(DirectorRule(id="r1", preference="rule one", applies_to=[]))
    memory.add_rule(DirectorRule(id="r2", preference="rule two", applies_to=[]))
    hint = memory.hint_for_prompt("totally unrelated prose about gardening")
    assert "rule two" in hint


def test_director_memory_empty_returns_no_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYBOARD_OUTPUT_DIR", str(tmp_path))
    from scripts.director_memory import DirectorMemory
    memory = DirectorMemory()
    assert memory.hint_for_prompt("anything") == ""


# =================== Production packet ===================

def test_packet_writes_all_files(tmp_path):
    """Export packet for a minimal scene, verify all four files exist."""
    from scripts.packet import export_packet
    from scripts.scene import Environment, Shot
    scene = Scene(
        title="Test Scene",
        scene_number="01",
        location="EXT day",
        director="Test",
        shots=[
            Shot(
                label="1A", shot_type=ShotType.WIDE, description="opening",
                lens="24mm", caption='"Hello there."',
                figures=[Figure(role="hero")], environment=Environment(kind="EXT"),
            ),
        ],
    )
    written = export_packet(scene, tmp_path)
    assert "shotlist.csv" in written
    assert "camera_notes.md" in written
    assert "dialogue.md" in written
    assert "continuity.md" in written
    for path in written.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_packet_dialogue_extracts_quoted_speech(tmp_path):
    """Captions with quoted speech show up in dialogue.md."""
    from scripts.packet import export_packet
    from scripts.scene import Environment, Shot
    scene = Scene(
        title="Dialogue test",
        shots=[Shot(
            label="1A", shot_type=ShotType.MEDIUM, description="",
            caption='He says: "Marlowe. Third one this month."',
            figures=[], environment=Environment(),
        )],
    )
    written = export_packet(scene, tmp_path)
    dialogue = written["dialogue.md"].read_text(encoding="utf-8")
    assert "Marlowe. Third one this month." in dialogue
    assert "1A" in dialogue
