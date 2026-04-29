"""Per-shot environment SVG generation via Kimi K2.5.

When a Scene's shot describes something the template environments
can't represent (a spaceship corridor, a swamp, an operating theatre,
a desert dune), we ask Kimi to draw it as Dry Ink schematic SVG inline.

Strategy:
1. Inspect each shot's `environment.description`. If it matches a
   template-friendly category (alley, room, kitchen, generic exterior/
   interior), skip enrich — use the existing environments.py templates.
2. Otherwise, ask Kimi for a small SVG fragment (≤30 strokes,
   single-color, fits 400×300 viewbox) drawn in Dry Ink style.
3. Validate the returned SVG: must parse via xml.etree, must use only
   whitelisted tags, must have stroke/fill colors from the Dry Ink
   palette (or no color = inherit). If validation fails, drop the
   custom env and use the template fallback.
4. Embed the validated fragment into the Scene's `environment.custom_svg`
   field so render.py picks it up.

The enrich step adds one Kimi call per non-template shot. Cached on
description hash so repeat scenes don't pay twice.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from typing import Optional

from scripts.kimi_client import KimiError, kimi_text
from scripts.scene import Scene, Shot
from scripts.style import DRY_INK


# Categories the template engine handles natively. Anything else gets
# Kimi-generated SVG. Keep these matchers loose — false positives just
# mean "use templates", which is the safe path.
TEMPLATE_KEYWORDS = (
    "alley", "street", "road", "sidewalk",
    "room", "kitchen", "bedroom", "office", "hallway",
    "exterior", "interior", "ext", "int",
    "rain", "rainy", "wet",
)


ENRICH_SYSTEM_PROMPT = f"""You are a storyboard artist. You draw schematic environments
in Dry Ink style — cream paper, warm ink, restrained accent red.

You return a single SVG fragment (no full document, no <svg> wrapper),
suitable for embedding inside a 700×300 frame at coordinates (0, 0).

Hard rules — non-negotiable:

1. Use ONLY these stroke and fill colors:
   - "{DRY_INK['fg']}" (warm ink, primary)
   - "{DRY_INK['fg_dim']}" (muted, for distant elements)
   - "{DRY_INK['accent']}" (dried-blood red, ONLY for hazards/focus)

2. Use ONLY these tags: <line>, <rect>, <circle>, <ellipse>, <path>,
   <polygon>, <g>. No <text>, no <image>, no <foreignObject>, no
   <script>, no <style>, no <defs>, no gradients, no filters.

3. Keep it sparse. ≤30 elements total. Schematic, not detailed.

4. Stroke widths: only 0.5, 0.8, 1.0, 1.5, 2.0, or 2.5. No others.

5. NO fill="white", NO fill="black" — use the Dry Ink colors above.

6. The fragment occupies the rectangle (0,0)-(700,300). Stay inside it.

7. Return ONLY the SVG fragment. No prose, no markdown fences, no
   explanation. Start your response with `<` and end with `>`."""


# Whitelist for validation
ALLOWED_TAGS = {"line", "rect", "circle", "ellipse", "path", "polygon", "g"}
DRY_INK_COLORS = {DRY_INK["fg"], DRY_INK["fg_dim"], DRY_INK["accent"], "none", "inherit"}


class EnrichError(RuntimeError):
    pass


def needs_enrichment(shot: Shot) -> bool:
    """Decide whether this shot's environment can use templates or
    needs Kimi-generated SVG.
    """
    desc = (shot.environment.description or "").lower()
    if not desc:
        return False
    for kw in TEMPLATE_KEYWORDS:
        if kw in desc:
            return False
    # Not in template set → Kimi
    return True


def enrich_shot(shot: Shot, *, use_cache: bool = True) -> Optional[str]:
    """Ask Kimi for an environment SVG fragment for this shot. Returns
    the validated SVG string, or None if generation/validation fails
    (caller falls back to template).
    """
    desc = shot.environment.description or shot.description
    user_prompt = (
        f"Draw the environment for this storyboard frame:\n\n"
        f"Shot type: {shot.shot_type.value}\n"
        f"Description: {desc}\n"
        f"Time/mood: {shot.caption or '(none)'}\n\n"
        f"Return only a Dry Ink SVG fragment per the rules."
    )
    try:
        raw = kimi_text(
            user_prompt,
            system=ENRICH_SYSTEM_PROMPT,
            use_cache=use_cache,
            temperature=0.6,
            max_tokens=1500,
        )
    except KimiError as exc:
        print(f"[enrich] Kimi call failed for shot {shot.label}: {exc}", file=sys.stderr)
        return None

    fragment = _strip_codeblock(raw).strip()
    if not _validate_fragment(fragment):
        print(f"[enrich] Kimi fragment for shot {shot.label} failed validation; "
              f"falling back to template", file=sys.stderr)
        return None
    return fragment


def enrich_scene(scene: Scene, *, use_cache: bool = True) -> int:
    """Walk the scene, enrich shots that need it. Mutates the Scene in
    place by setting custom env on shots. Returns count of enriched shots.
    """
    count = 0
    for shot in scene.shots:
        if not needs_enrichment(shot):
            continue
        fragment = enrich_shot(shot, use_cache=use_cache)
        if fragment is None:
            continue
        # Stash on the environment via a Python-only attribute. The
        # render code reads this and includes it in place of templates.
        # (We don't add it to the Scene.from_dict schema because it's
        # transient and shouldn't survive a JSON round-trip — Kimi
        # would re-generate next run if needed.)
        setattr(shot.environment, "custom_svg", fragment)
        count += 1
    return count


def _strip_codeblock(s: str) -> str:
    m = re.match(r"^```(?:svg|xml)?\s*(.*?)\s*```\s*$", s.strip(), re.DOTALL)
    if m:
        return m.group(1)
    # Some models prepend "Here is the SVG:" — strip prose before first <
    idx = s.find("<")
    if idx > 0:
        s = s[idx:]
    return s


def _validate_fragment(fragment: str) -> bool:
    """Parse SVG fragment and verify it adheres to whitelist rules."""
    if not fragment.startswith("<"):
        return False
    # Wrap so xml.etree can parse a fragment with multiple top-level tags
    wrapped = f"<root xmlns='http://www.w3.org/2000/svg'>{fragment}</root>"
    try:
        root = ET.fromstring(wrapped)
    except ET.ParseError:
        return False

    elem_count = 0
    for elem in root.iter():
        if elem is root:
            continue
        # Strip namespace
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag not in ALLOWED_TAGS:
            return False
        elem_count += 1
        # Color whitelist on stroke/fill
        for attr in ("stroke", "fill"):
            val = elem.get(attr)
            if val is None or val == "none":
                continue
            if val not in DRY_INK_COLORS:
                # Allow rgb()/hex outside palette only if it's explicitly transparent
                if val.lower() in ("transparent", ""):
                    continue
                return False
        # Stroke-width whitelist
        sw = elem.get("stroke-width")
        if sw:
            try:
                sw_f = float(sw)
                if sw_f not in {0.5, 0.8, 1.0, 1.5, 2.0, 2.5}:
                    # Tolerate small float drift
                    if not any(abs(sw_f - v) < 0.05 for v in (0.5, 0.8, 1.0, 1.5, 2.0, 2.5)):
                        return False
            except ValueError:
                return False

    if elem_count == 0 or elem_count > 30:
        return False
    return True


__all__ = ["enrich_scene", "enrich_shot", "needs_enrichment", "EnrichError"]
