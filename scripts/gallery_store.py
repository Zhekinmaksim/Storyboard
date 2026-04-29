"""Public gallery store for hermes-story.art.

Users can opt their generated boards into a public gallery. Stored as a
single JSONL file plus per-board PNG copies. Bounded to MAX_GALLERY
entries (oldest evicted).

Privacy:
  - Opt-in only — `share_to_gallery: true` in /api/start request.
  - We persist: anonymised slug (first 6 chars of job_id), title,
    truncated prose preview (200 chars), board.png path, scene.json
    path, created_at timestamp.
  - We do NOT persist: client IP, user-provided email, full prose if
    longer than 200 chars (truncated).
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Any

GALLERY_DIR = Path(os.environ.get("STORYBOARD_GALLERY_DIR",
                                   str(Path.home() / "storyboard-gallery")))
GALLERY_INDEX = GALLERY_DIR / "index.jsonl"
GALLERY_BOARDS = GALLERY_DIR / "boards"
MAX_GALLERY = int(os.environ.get("STORYBOARD_MAX_GALLERY", "60"))

_LOCK = threading.Lock()


def ensure_dirs() -> None:
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    GALLERY_BOARDS.mkdir(parents=True, exist_ok=True)
    if not GALLERY_INDEX.exists():
        GALLERY_INDEX.touch()


def _read_all() -> list[dict[str, Any]]:
    if not GALLERY_INDEX.exists():
        return []
    items: list[dict[str, Any]] = []
    with GALLERY_INDEX.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def _write_all(items: list[dict[str, Any]]) -> None:
    tmp = GALLERY_INDEX.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    tmp.replace(GALLERY_INDEX)


def add_entry(
    job_id: str,
    title: str,
    prose: str,
    output_dir: Path,
) -> bool:
    """Persist a job to the gallery. Returns True on success."""
    ensure_dirs()
    slug = job_id[:6]
    board_src = output_dir / "board.png"
    scene_src = output_dir / "scene.json"
    if not board_src.exists() or not scene_src.exists():
        return False

    with _LOCK:
        items = _read_all()
        # Evict oldest if past cap
        while len(items) >= MAX_GALLERY:
            old = items.pop(0)
            old_board = GALLERY_BOARDS / f"{old['slug']}.png"
            old_scene = GALLERY_BOARDS / f"{old['slug']}.json"
            for p in (old_board, old_scene):
                p.unlink(missing_ok=True)

        # Copy artefacts under a stable name
        dst_board = GALLERY_BOARDS / f"{slug}.png"
        dst_scene = GALLERY_BOARDS / f"{slug}.json"
        shutil.copyfile(board_src, dst_board)
        shutil.copyfile(scene_src, dst_scene)

        entry = {
            "slug": slug,
            "title": title or "Untitled",
            "prose_preview": (prose[:200] + "…") if len(prose) > 200 else prose,
            "created_at": int(time.time()),
        }
        items.append(entry)
        _write_all(items)
    return True


def list_entries(limit: int = 12) -> list[dict[str, Any]]:
    """Return the most-recent N entries, newest first."""
    if not GALLERY_INDEX.exists():
        return []
    items = _read_all()
    items.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return items[:limit]


def board_path(slug: str) -> Path | None:
    """Resolve a slug to its board.png path, if it exists in gallery."""
    if not slug or len(slug) > 32 or not slug.isalnum():
        return None
    p = GALLERY_BOARDS / f"{slug}.png"
    return p if p.exists() else None


def scene_path(slug: str) -> Path | None:
    if not slug or len(slug) > 32 or not slug.isalnum():
        return None
    p = GALLERY_BOARDS / f"{slug}.json"
    return p if p.exists() else None
