"""Animation timeline. Central source of truth for SMIL `begin` and `dur`
values across all primitives. Render uses this so that all six shots
animate in a coherent rhythm rather than each template guessing its
own timing.

Per-shot rhythm (deliberately slow enough for a 90-second demo):
    0.0s  shot label appears (text fade)
    0.2s  frame border begins drawing (perimeter stroke, 0.8s)
    1.0s  environment elements begin (fade, 0.6s; per-element delay 0.05s)
    1.6s  figures begin (fade, 0.6s)
    2.2s  annotations (eye-line arrows, focus rings) begin (0.4s)
    2.6s  metadata strip below frame fades in (0.5s)
    3.1s  italic caption fades in (0.5s)
    3.6s  shot complete

Total per shot: 3.6 seconds. With 6 shots staggered at 0.8s each, the
full board takes ~3.6 + (5 * 0.8) = 7.6 seconds end-to-end. A judge
watches one shot finish, the next starts before they look away.

If `streaming=True`, each shot's animation begins at delay=0 from its
own DOM-insertion moment, not from a global clock — the offsets are
applied relative to the shot's local timeline. This means streaming
works correctly even if shots arrive late or out of order.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShotTiming:
    """All animation begin offsets for a single shot, in seconds, relative
    to that shot's start moment."""
    label_in: float = 0.0
    label_dur: float = 0.3
    border_in: float = 0.2
    border_dur: float = 0.8
    env_in: float = 1.0
    env_dur: float = 0.6
    env_stagger: float = 0.05      # extra delay between env elements
    figure_in: float = 1.6
    figure_dur: float = 0.6
    annotation_in: float = 2.2
    annotation_dur: float = 0.4
    metadata_in: float = 2.6
    metadata_dur: float = 0.5
    caption_in: float = 3.1
    caption_dur: float = 0.5


SHOT_DURATION = 3.6              # seconds, end-to-end per shot
SHOT_STAGGER = 0.8               # seconds between consecutive shot starts
HEADER_DURATION = 0.8            # title + meta line in
HEADER_DELAY = 0.0


def shot_start_offset(index: int, *, streaming: bool = False) -> float:
    """When does this shot start, relative to scene time origin?

    In streaming mode every shot begins at 0 (its own local time), since
    they're inserted into the DOM as they arrive. In static mode (one
    SVG file), shots are staggered.
    """
    if streaming:
        return 0.0
    return HEADER_DELAY + HEADER_DURATION + index * SHOT_STAGGER


SHOT_TIMING = ShotTiming()


__all__ = ["ShotTiming", "SHOT_TIMING", "SHOT_DURATION", "SHOT_STAGGER",
           "HEADER_DURATION", "HEADER_DELAY", "shot_start_offset"]
