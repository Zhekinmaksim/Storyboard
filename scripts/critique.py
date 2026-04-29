"""Multimodal critique pass: send rendered PNG + Scene JSON to Kimi K2.5,
get back a structured list of revisions.

Design notes:
- Schema is small and strict: list of revisions, each with shot_label,
  field_to_change, new_value, reason. The renderer applies revisions
  by mutating Scene fields directly.
- Anti-hallucination: every revision's shot_label is cross-checked
  against the Scene before being returned. Invalid labels are dropped
  with a stderr warning, never silently kept.
- The system prompt cites concrete film-grammar rules (180-line, eye-line,
  coverage, lens motivation, pacing) so the critique stays grounded
  rather than wandering into "make it more cinematic".
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass

from scripts.kimi_client import KimiError, kimi_vision
from scripts.scene import Scene


CRITIQUE_SYSTEM_PROMPT = """You are a senior cinematographer reviewing a storyboard draft. You see
the rendered storyboard image and the underlying shot metadata.

Apply ONLY these film-grammar rules. Do not invent aesthetic preferences.

1. 180-DEGREE LINE: across consecutive shots showing the same characters,
   screen direction must remain consistent. A character looking
   camera-right in one shot must continue looking camera-right in the
   next, unless an axis_status of NEW_AXIS or CROSSED_LINE is explicitly
   marked.

2. EYE-LINE CONTINUITY: in shot-reverse-shot dialogue coverage,
   character A looking CAMERA_RIGHT must be matched by character B
   looking CAMERA_LEFT (and vice versa). Mismatches break coverage.

3. COVERAGE: a dialogue scene needs at minimum (a) an establishing wide
   or two-shot, (b) close coverage of each speaker, (c) at least one
   reaction shot. Action scenes need an establishing wide and pacing
   close-ups.

4. LENS MOTIVATION: lens choice should track emotional intensity. Wider
   lenses for context, longer lenses for tension and isolation.
   Arbitrary lens swings without narrative reason are a flag.

5. PACING: action shots are 0.5-2 seconds. Dialogue shots are 2-5
   seconds. Establishing shots can be longer. Mismatch between content
   and duration is a flag.

OUTPUT FORMAT — strict JSON only, no markdown:

{
  "revisions": [
    {
      "shot_label": "1F",
      "field": "angle | lens | movement | duration | caption | eye_line.direction | eye_line.axis_status",
      "old_value": "<the current value, exactly as it appears in the metadata>",
      "new_value": "<the new value as a string>",
      "reason": "Short explanation citing one of the rules above"
    }
  ]
}

If the storyboard is correct, return {"revisions": []}.

DO NOT propose changes to fields not listed in the field enum above.
DO NOT propose revisions for shot labels that do not appear in the
provided Scene metadata. Be honest. Do not invent revisions when none
are needed.

ALWAYS include `old_value` matching the current scene metadata exactly.
If you cannot read the current value, omit the patch — do not guess."""


@dataclass
class Revision:
    shot_label: str
    field: str
    new_value: str
    reason: str
    old_value: str = ""   # If set, the patch is rejected if it doesn't match
                          # the current scene field — guards against critic
                          # operating on a stale view of the board.

    def to_dict(self) -> dict[str, str]:
        return {
            "shot_label": self.shot_label,
            "field": self.field,
            "new_value": self.new_value,
            "reason": self.reason,
            "old_value": self.old_value,
        }


# Allowed fields a critique can touch. Anything else is dropped with a warning.
ALLOWED_FIELDS = {
    "angle", "lens", "movement", "duration", "caption",
    "eye_line.direction", "eye_line.axis_status",
}


def critique_board(scene: Scene, png_bytes: bytes, *, use_cache: bool = True) -> list[Revision]:
    """Run one critique round. Returns validated revisions, possibly empty."""
    user_text = (
        "Critique this storyboard draft. The Scene metadata is below; "
        "use the rendered image plus this metadata to identify violations.\n\n"
        f"```json\n{scene.to_json()}\n```\n\n"
        "Return a JSON object with a 'revisions' array. Empty array if no issues."
    )
    try:
        raw = kimi_vision(
            user_text, png_bytes,
            system=CRITIQUE_SYSTEM_PROMPT,
            use_cache=use_cache,
            temperature=0.2,
            max_tokens=2000,
        )
    except KimiError as exc:
        print(f"[critique] Kimi vision call failed: {exc}", file=sys.stderr)
        return []

    cleaned = _strip_codeblock(raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        print(f"[critique] Kimi returned non-JSON; dropping: {exc}", file=sys.stderr)
        print(f"[critique] raw response: {raw[:400]}", file=sys.stderr)
        return []

    raw_revisions = data.get("revisions", []) if isinstance(data, dict) else []
    valid_labels = {s.label for s in scene.shots}
    shots_by_label = {s.label: s for s in scene.shots}
    out: list[Revision] = []
    for r in raw_revisions:
        if not isinstance(r, dict):
            continue
        label = r.get("shot_label", "")
        field = r.get("field", "")
        new_value = str(r.get("new_value", ""))
        old_value = str(r.get("old_value", ""))
        reason = r.get("reason", "")
        if label not in valid_labels:
            print(f"[critique] dropping hallucinated shot_label '{label}'", file=sys.stderr)
            continue
        if field not in ALLOWED_FIELDS:
            print(f"[critique] dropping unsupported field '{field}'", file=sys.stderr)
            continue
        if not new_value:
            continue

        # Optional: if Kimi returned old_value, verify it matches the
        # current scene field. Mismatched old_value means critic was
        # operating on a stale snapshot — reject the patch rather than
        # apply a guess.
        if old_value:
            shot = shots_by_label[label]
            current = _read_field(shot, field)
            if current is not None and old_value.strip() != str(current).strip():
                print(f"[critique] dropping patch on {label}.{field}: "
                      f"old_value mismatch (expected '{current}', "
                      f"got '{old_value}')", file=sys.stderr)
                continue

        out.append(Revision(
            shot_label=label,
            field=field,
            new_value=new_value,
            reason=reason,
            old_value=old_value,
        ))
    return out


def _read_field(shot, field: str):
    """Read a dotted field path from a Shot. Returns None on miss."""
    obj = shot
    for part in field.split("."):
        if obj is None:
            return None
        # Try attribute first, then dict
        if hasattr(obj, part):
            val = getattr(obj, part)
        elif isinstance(obj, dict) and part in obj:
            val = obj[part]
        else:
            return None
        obj = val
    return obj


_CODEBLOCK_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_codeblock(s: str) -> str:
    m = _CODEBLOCK_RE.match(s.strip())
    if m:
        return m.group(1)
    return s


def revisions_to_json(revisions: list[Revision]) -> str:
    return json.dumps({"revisions": [r.to_dict() for r in revisions]}, indent=2, ensure_ascii=False)


__all__ = [
    "critique_board", "Revision", "revisions_to_json",
    "CRITIQUE_SYSTEM_PROMPT", "ALLOWED_FIELDS",
]
