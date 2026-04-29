"""Production packet exporter.

A storyboard is the start of pre-production, not the end. This module
exports an approved Scene as the ancillary documents the production
team actually needs to run the shoot:

  - shotlist.csv     — one row per shot, all camera/lens/move/duration
                       data, plus location and figures, ready to be
                       opened in any spreadsheet for scheduling.
  - camera_notes.md  — director-readable per-shot notes: shot type,
                       movement, lens motivation, eye-line, axis status.
                       The kind of thing a 1st AC or DP gets handed
                       before the shoot day.
  - dialogue.md      — pulled from each shot's caption when it contains
                       quoted speech ("..."), formatted as a clean
                       dialogue list with shot labels.

This positions Storyboard as the **upstream pre-production layer** for
any downstream pipeline (audio drama, animation, live-action shoot).
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from scripts.scene import Scene


_QUOTED_SPEECH = re.compile(r'["“](.+?)["”]')


def export_packet(scene: Scene, out_dir: Path) -> dict[str, Path]:
    """Write the production packet files into out_dir/packet/.
    Returns a dict {filename: path} of what was written.
    """
    packet_dir = out_dir / "packet"
    packet_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    written["shotlist.csv"] = _write_shotlist(scene, packet_dir)
    written["camera_notes.md"] = _write_camera_notes(scene, packet_dir)
    written["dialogue.md"] = _write_dialogue(scene, packet_dir)
    written["continuity.md"] = _write_continuity(scene, packet_dir)
    return written


def _write_shotlist(scene: Scene, packet_dir: Path) -> Path:
    path = packet_dir / "shotlist.csv"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "shot", "type", "description", "lens", "movement", "angle",
        "duration", "location", "figures", "caption", "eye_line", "axis",
    ])
    for shot in scene.shots:
        figures = "; ".join(
            f"{f.role} ({f.pose.value}, {f.facing.value})" for f in shot.figures
        )
        eye_line = ""
        axis = ""
        if shot.eye_line:
            eye_line = shot.eye_line.direction.value
            axis = shot.eye_line.axis_status.value
        writer.writerow([
            shot.label,
            shot.shot_type.value,
            shot.description,
            shot.lens,
            shot.movement,
            shot.angle,
            shot.duration,
            shot.environment.description or scene.location,
            figures,
            shot.caption,
            eye_line,
            axis,
        ])
    path.write_text(buf.getvalue(), encoding="utf-8")
    return path


def _write_camera_notes(scene: Scene, packet_dir: Path) -> Path:
    path = packet_dir / "camera_notes.md"
    lines: list[str] = [
        f"# Camera notes — {scene.title}",
        "",
        f"**Director:** {scene.director}  ",
        f"**Scene:** {scene.scene_number} — {scene.location}  ",
        f"**Shots:** {len(scene.shots)}  ",
        "",
        "These notes are for the DP and 1st AC. Each shot lists lens, "
        "movement, angle, and the director's intent in one line. Use "
        "alongside the storyboard SVG.",
        "",
    ]
    for shot in scene.shots:
        lines.append(f"## {shot.label} — {shot.shot_type.value.replace('_', ' ')}")
        lines.append("")
        lines.append(f"**Lens:** {shot.lens}  ")
        lines.append(f"**Movement:** {shot.movement}  ")
        lines.append(f"**Angle:** {shot.angle}  ")
        lines.append(f"**Duration:** {shot.duration}  ")
        if shot.eye_line:
            lines.append(
                f"**Eye-line:** {shot.eye_line.direction.value} "
                f"({shot.eye_line.axis_status.value})  "
            )
        lines.append(f"**Description:** {shot.description}  ")
        if shot.caption:
            lines.append(f"*{shot.caption}*")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_dialogue(scene: Scene, packet_dir: Path) -> Path:
    """Extract quoted speech from captions, listed by shot label."""
    path = packet_dir / "dialogue.md"
    lines: list[str] = [
        f"# Dialogue — {scene.title}",
        "",
        "Lines pulled from shot captions, in shot order. Speaker "
        "attribution is omitted in v0.1; cross-reference with the "
        "shotlist for who is on-camera in each line.",
        "",
    ]
    found = 0
    for shot in scene.shots:
        if not shot.caption:
            continue
        matches = _QUOTED_SPEECH.findall(shot.caption)
        if not matches:
            continue
        for line in matches:
            found += 1
            lines.append(f"**{shot.label}** &nbsp;&nbsp; \"{line.strip()}\"")
            lines.append("")
    if found == 0:
        lines.append("*(no quoted speech detected in this scene's captions)*")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_continuity(scene: Scene, packet_dir: Path) -> Path:
    """A continuity sheet — characters in each shot, their state, position."""
    path = packet_dir / "continuity.md"
    lines: list[str] = [
        f"# Continuity sheet — {scene.title}",
        "",
        "Per-shot character presence, state, and pose. For the script "
        "supervisor on set.",
        "",
        "| Shot | Characters | Pose / state | Notes |",
        "|------|-----------|--------------|-------|",
    ]
    for shot in scene.shots:
        if not shot.figures:
            chars = "(empty)"
            pose = "—"
        else:
            chars = "; ".join(f.role for f in shot.figures)
            pose = "; ".join(
                f"{f.role}: {f.pose.value.lower()}" + (f" ({f.state})" if f.state else "")
                for f in shot.figures
            )
        notes = shot.environment.description or "—"
        lines.append(f"| {shot.label} | {chars} | {pose} | {notes} |")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


__all__ = ["export_packet"]
