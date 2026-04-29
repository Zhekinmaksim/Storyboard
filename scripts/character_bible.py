"""Minimal character bible — persists role → (display name + silhouette tag)
across scenes so the agent looks like it 'remembers' characters between
sessions, even though the renderer is stateless.

v0.1 scope (deliberately small):
- role: the canonical key, e.g. 'detective', 'partner', 'victim'
- display_name: 'Mara Holloway', 'Marlowe' — what shows up in director notes
- silhouette: short adjective string — 'narrow shoulders, long coat', 'broad,
  tactical vest'. The renderer DOES use these tags for visual variation:
  long-coat figures get a visible coat-tail, silhouette-only figures get a
  threat halo, square-headed figures look more brutalist, etc. The bible
  also feeds Kimi via prepare_bible_hint() so character continuity holds
  across sessions, not just within one scene.

Storage: $STORYBOARD_OUTPUT_DIR/character_bible.json by default, OR per
job dir when CharacterBible.load(base_dir=job_dir) is used (web pipeline
does this so different users don't share characters on a public host).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from scripts.scene import Scene


def _output_dir(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        p = Path(base_dir).expanduser()
    else:
        raw = os.environ.get("STORYBOARD_OUTPUT_DIR", str(Path.home() / "storyboard-output"))
        p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class CharacterEntry:
    role: str
    display_name: str = ""
    silhouette: str = ""        # 1-line description; max ~80 chars
    first_seen_scene: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class CharacterBible:
    entries: dict[str, CharacterEntry] = field(default_factory=dict)
    base_dir: Path | None = field(default=None, repr=False)

    @classmethod
    def load(cls, base_dir: Path | None = None) -> "CharacterBible":
        path = _output_dir(base_dir) / "character_bible.json"
        if not path.exists():
            return cls(base_dir=base_dir)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls(base_dir=base_dir)
        entries = {
            role: CharacterEntry(**fields)
            for role, fields in data.get("entries", {}).items()
        }
        return cls(entries=entries, base_dir=base_dir)

    def save(self) -> Path:
        path = _output_dir(self.base_dir) / "character_bible.json"
        payload = {"entries": {role: e.to_dict() for role, e in self.entries.items()}}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def upsert_from_scene(self, scene: Scene) -> list[str]:
        """Add any new roles to the bible. Returns list of newly added roles."""
        added: list[str] = []
        for shot in scene.shots:
            for fig in shot.figures:
                role = fig.role.strip().lower()
                if not role or role in self.entries:
                    continue
                self.entries[role] = CharacterEntry(
                    role=role,
                    display_name=role.title(),
                    silhouette=_silhouette_from_state(fig.state),
                    first_seen_scene=scene.scene_number,
                )
                added.append(role)
        return added

    def hint_for_prompt(self, prose: str) -> str:
        """Build a short addendum for the parse prompt listing relevant
        roles and silhouettes. Only roles whose name appears in the prose
        are included, so we don't pollute every scene with unrelated
        characters.
        """
        prose_l = prose.lower()
        hits: list[str] = []
        for role, entry in self.entries.items():
            if role in prose_l or (entry.display_name and entry.display_name.lower() in prose_l):
                hits.append(f'- "{role}": {entry.silhouette or "(no silhouette set)"}'
                            f' [first seen: scene {entry.first_seen_scene}]')
        if not hits:
            return ""
        return (
            "\n\nKnown characters from previous scenes (preserve their identity "
            "and visual silhouette in figure roles and states):\n"
            + "\n".join(hits)
        )


def _silhouette_from_state(state: str | None) -> str:
    """Best-effort silhouette description from a state tag."""
    if not state:
        return ""
    base = "schematic figure"
    state_words = state.lower()
    parts = [base]
    if "wet" in state_words or "rain" in state_words:
        parts.append("dripping coat outline")
    if "wounded" in state_words or "blood" in state_words:
        parts.append("favouring one side")
    if "tense" in state_words or "alert" in state_words:
        parts.append("tight stance")
    return ", ".join(parts)


__all__ = ["CharacterBible", "CharacterEntry"]
