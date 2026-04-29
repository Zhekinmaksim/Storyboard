"""Director memory — the learning loop.

When a user issues a targeted revision (e.g. "more Hitchcock — low angle,
harder shadow, killer as silhouette"), Hermes asks Kimi K2.5 to extract
a generalised *director rule* from that revision and persist it. On the
next scene, the rule is injected into the parse prompt so Hermes
applies the user's preferred style automatically — without being told
again.

This is the difference between "an AI that draws when asked" and
"an AI that learns how this director directs."

Storage: $STORYBOARD_OUTPUT_DIR/director_memory.json — flat list of
rules, lazy-write only when a new rule is added.

Schema:
  {
    "rules": [
      {
        "id": "rule_001",
        "preference": "For suspense and reveal moments, prefer low-angle framing, stronger cast shadows, and silhouettes for unseen threats.",
        "applies_to": ["suspense", "reveal", "danger", "killer entrance"],
        "source_revision": {
          "scene": "01",
          "frame": "1F",
          "note": "more Hitchcock — low angle, harder shadow, killer as silhouette"
        },
        "created_at": "2026-04-26T13:42:00Z"
      }
    ]
  }

The rule extraction is itself a Kimi call — we don't try to regex parse
"low angle, harder shadow" into structured fields. Kimi reads the user's
note alongside the original frame and returns a JSON rule. If the
extraction fails (Kimi returns malformed JSON), we fall back to storing
the raw note as a free-text rule, which is still useful for prompt
injection.
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.kimi_client import KimiError, kimi_text


def _output_dir(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        p = Path(base_dir).expanduser()
    else:
        raw = os.environ.get("STORYBOARD_OUTPUT_DIR", str(Path.home() / "storyboard-output"))
        p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class DirectorRule:
    id: str
    preference: str
    applies_to: list[str] = field(default_factory=list)
    source_revision: dict[str, str] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DirectorMemory:
    rules: list[DirectorRule] = field(default_factory=list)
    base_dir: Path | None = field(default=None, repr=False)

    @classmethod
    def load(cls, base_dir: Path | None = None) -> "DirectorMemory":
        path = _output_dir(base_dir) / "director_memory.json"
        if not path.exists():
            return cls(base_dir=base_dir)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls(base_dir=base_dir)
        rules = []
        for r in data.get("rules", []):
            rules.append(DirectorRule(
                id=r.get("id", _new_id()),
                preference=r.get("preference", ""),
                applies_to=r.get("applies_to", []),
                source_revision=r.get("source_revision", {}),
                created_at=r.get("created_at", ""),
            ))
        return cls(rules=rules, base_dir=base_dir)

    def save(self) -> Path:
        path = _output_dir(self.base_dir) / "director_memory.json"
        payload = {"rules": [r.to_dict() for r in self.rules]}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def add_rule(self, rule: DirectorRule) -> None:
        self.rules.append(rule)
        self.save()

    def hint_for_prompt(self, prose: str) -> str:
        """Build an addendum for the parse prompt that surfaces relevant
        rules. A rule is "relevant" if any of its applies_to tags appears
        in the prose (case-insensitive substring).
        """
        if not self.rules:
            return ""
        prose_l = prose.lower()
        matched: list[DirectorRule] = []
        for rule in self.rules:
            for tag in rule.applies_to:
                if tag.lower() in prose_l:
                    matched.append(rule)
                    break

        # No tag match → no rule applied. The website explicitly promises
        # "future scenes that match the tags" — silently applying the
        # most recent rule to unrelated scenes contradicts that and can
        # make a noir directing rule leak into a comedy scene.
        # CLI users who want the old behaviour can opt in:
        if not matched and self.rules and \
           os.environ.get("STORYBOARD_MEMORY_FALLBACK") == "1":
            matched = [self.rules[-1]]

        if not matched:
            return ""

        lines = [
            "\n\nDirector style rules learned from previous scenes (apply when the "
            "scene matches the listed contexts):"
        ]
        for r in matched:
            tags = ", ".join(r.applies_to) if r.applies_to else "general"
            lines.append(f'- "{r.preference}" (applies to: {tags})')
        return "\n".join(lines)


# =================== Rule extraction ===================

EXTRACT_SYSTEM_PROMPT = """You are a film director's continuity assistant. The director has
just made a targeted revision to a single storyboard frame. Your job is
to extract a GENERAL style rule from that revision so it can be applied
automatically to similar future frames.

Output ONLY a strict-JSON object:

{
  "preference": "<concise rule, 1-2 sentences, in director's voice>",
  "applies_to": ["<tag1>", "<tag2>", ...]
}

Tags are short keywords describing scene contexts where the rule
applies. Use lowercase phrases. Examples of good tags:
  "suspense", "reveal", "danger from above", "interior dialogue",
  "establishing shot", "killer entrance", "intimate close-up",
  "chase", "decision moment", "betrayal".

The preference should be GENERALISED — not "make frame 1F low angle"
but "for reveal moments, prefer low-angle framing".

CRITICAL CONSTRAINTS:
  - Memory rules describe STYLE only: framing, lighting, pacing,
    composition, lens motivation, blocking, emphasis.
  - Memory rules MUST NOT add or imply new plot facts: no specific
    characters, props, dialogue, story events, or named locations.
  - DO NOT name characters in the preference or tags.
  - DO NOT mention specific weapons, props, body parts, or items.
  - DO NOT echo the user's specific words like "knife" or "lotus";
    abstract them away to "weapon-reveal moments" or "intimate detail".
  - If the user revision is too specific to generalise safely,
    return preference="" — the system will fall back to a raw note.

Return only the JSON. No prose, no markdown fences."""


# Two categories of restricted vocabulary for memory rules.
#
# (1) PREFERENCE_TEXT_FORBIDDEN — plot facts that would leak into every
#     future matching scene. Named props, named characters, and specific
#     story events. These are forbidden in BOTH the preference text and
#     the applies_to tags — a tag like "knife reveal" still encodes a
#     prop into matching logic.
#
# (2) LOCATION_TAG_OK — locations and scene types that ARE legitimate
#     applies_to tags (you DO want a "stairwell" rule to apply to other
#     stairwell scenes), but should be filtered out of the preference
#     text itself (the rule should describe HOW to shoot a stairwell,
#     not say "stairwell").
_PREFERENCE_TEXT_FORBIDDEN = {
    # Named props
    "knife", "gun", "pistol", "lotus", "scarf", "rose", "ring",
    "phone", "key", "letter", "photograph", "mirror", "watch",
    # Named persons
    "marlowe", "mara", "sam", "spade", "moriarty", "holmes",
    # Specific events
    "murder", "suicide", "kidnap", "explosion",
}

# These are FINE as tags but NOT as preference text — they describe the
# scene context, not the directing intent.
_LOCATION_TAG_OK = {
    "alley", "stairwell", "kitchen", "warehouse", "rooftop",
    "garage", "basement", "hallway", "elevator", "bedroom",
    "bathroom", "office", "courtroom", "park", "forest",
}


def _has_plot_leak_in_preference(text: str) -> tuple[bool, str]:
    """Check if preference text encodes plot facts. Both the props/persons
    list AND location names — preferences should be ABOUT directing,
    not WHERE.
    """
    t = text.lower()
    forbidden = _PREFERENCE_TEXT_FORBIDDEN | _LOCATION_TAG_OK
    for term in forbidden:
        if term in t.split() or f" {term} " in f" {t} " or f" {term}." in t:
            return True, term
    return False, ""


def _has_plot_leak_in_tag(tag: str) -> tuple[bool, str]:
    """Check if a tag encodes a plot fact. Allows location names — only
    forbids props, named characters, and specific events."""
    t = tag.lower()
    for term in _PREFERENCE_TEXT_FORBIDDEN:
        if term in t.split() or f" {term} " in f" {t} " or f" {term}." in t:
            return True, term
    return False, ""


# Backcompat alias — internal callers in this module use the new helpers,
# but external code (or future callers) might still expect the old name.
_has_plot_leak = _has_plot_leak_in_preference
_PLOT_LEAK_TERMS = _PREFERENCE_TEXT_FORBIDDEN | _LOCATION_TAG_OK


def extract_rule(
    user_note: str,
    *,
    scene_number: str,
    frame_label: str,
    use_cache: bool = True,
) -> DirectorRule:
    """Ask Kimi to convert a user revision note into a structured rule.

    Falls back to a raw-note rule if Kimi returns invalid JSON.
    """
    user_prompt = (
        f"User revision note for shot {frame_label} in scene {scene_number}:\n\n"
        f"\"{user_note}\"\n\n"
        f"Extract a generalised director style rule. Return JSON only."
    )

    rule_id = _new_id()
    now = datetime.now(timezone.utc).isoformat()
    source = {"scene": scene_number, "frame": frame_label, "note": user_note}

    try:
        raw = kimi_text(
            user_prompt,
            system=EXTRACT_SYSTEM_PROMPT,
            use_cache=use_cache,
            temperature=0.4,
            max_tokens=500,
        )
    except KimiError as exc:
        print(f"[director_memory] Kimi extraction failed: {exc}", file=sys.stderr)
        return _fallback_rule(rule_id, user_note, source, now)

    cleaned = _strip_codeblock(raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[director_memory] Kimi returned non-JSON; using raw fallback. "
              f"Raw: {raw[:200]}", file=sys.stderr)
        return _fallback_rule(rule_id, user_note, source, now)

    preference = str(data.get("preference", "")).strip()
    applies_to = data.get("applies_to", [])
    if not isinstance(applies_to, list):
        applies_to = []
    applies_to = [str(t).strip().lower() for t in applies_to if t]

    if not preference:
        return _fallback_rule(rule_id, user_note, source, now)

    # Post-validation: reject rules that leak plot facts into style memory.
    # If Kimi accidentally returned a "preference" full of named props,
    # characters, or specific locations, the rule would contaminate
    # every future scene matching the tags. Better to fall back to a
    # clean raw-note rule scoped to this scene only.
    leak, term = _has_plot_leak_in_preference(preference)
    if leak:
        print(f"[director_memory] dropping rule with plot leak '{term}' in "
              f"preference; falling back to raw note", file=sys.stderr)
        return _fallback_rule(rule_id, user_note, source, now)

    # Tags are LESS strict — locations like "stairwell" and "kitchen"
    # are legitimate context tags (you DO want a rule to apply to other
    # stairwell scenes). Only filter out named props / named characters /
    # specific events from tags.
    safe_tags = []
    for tag in applies_to:
        tag_leak, _ = _has_plot_leak_in_tag(tag)
        if not tag_leak:
            safe_tags.append(tag)
    applies_to = safe_tags

    return DirectorRule(
        id=rule_id,
        preference=preference,
        applies_to=applies_to,
        source_revision=source,
        created_at=now,
    )


def _fallback_rule(rule_id: str, user_note: str, source: dict[str, str], now: str) -> DirectorRule:
    """When Kimi can't structure the note, store it as-is. Still useful
    because the raw note appears in the parse prompt addendum.
    """
    return DirectorRule(
        id=rule_id,
        preference=user_note,
        applies_to=[],  # no tag matching, but always surfaces as 'most recent'
        source_revision=source,
        created_at=now,
    )


_CODEBLOCK_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _strip_codeblock(s: str) -> str:
    m = _CODEBLOCK_RE.match(s.strip())
    if m:
        return m.group(1)
    return s


def _new_id() -> str:
    return f"rule_{uuid.uuid4().hex[:8]}"


__all__ = ["DirectorMemory", "DirectorRule", "extract_rule"]
