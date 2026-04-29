"""Apply Revisions from critique back to a Scene. Pure deterministic logic.

This is the only place in the pipeline where Scene mutates after parse,
so all revision-handling lives here. Returns a NEW Scene; the input
is not modified.
"""

from __future__ import annotations

from copy import deepcopy

from scripts.critique import Revision
from scripts.scene import AxisStatus, EyeLine, EyeLineDirection, Scene, Shot


def apply_revisions(scene: Scene, revisions: list[Revision]) -> Scene:
    """Return a new Scene with all revisions applied."""
    new_scene = deepcopy(scene)
    by_label = {s.label: s for s in new_scene.shots}
    for rev in revisions:
        shot = by_label.get(rev.shot_label)
        if shot is None:
            continue  # silently drop — already validated upstream
        _apply_one(shot, rev)
    return new_scene


def _apply_one(shot: Shot, rev: Revision) -> None:
    """Mutate a single Shot field per revision spec."""
    field = rev.field
    value = rev.new_value

    if field in ("angle", "lens", "movement", "duration", "caption"):
        setattr(shot, field, value)
        return

    if field == "eye_line.direction":
        try:
            direction = EyeLineDirection(value)
        except ValueError:
            return
        if shot.eye_line is None:
            shot.eye_line = EyeLine(direction=direction)
        else:
            shot.eye_line.direction = direction
        return

    if field == "eye_line.axis_status":
        try:
            status = AxisStatus(value)
        except ValueError:
            return
        if shot.eye_line is None:
            shot.eye_line = EyeLine(direction=EyeLineDirection.CAMERA_LEFT, axis_status=status)
        else:
            shot.eye_line.axis_status = status
        return


__all__ = ["apply_revisions"]
