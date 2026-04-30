"""Public showcase server for hermes-story.art.

Single Python process, stdlib http.server only. Designed to run on
Fly.io as the API backend; the frontend lives on Vercel and calls
this server via CORS.

Endpoints:
  GET  /                         self-check page (proves Fly is alive)
  GET  /api/health               {status, jobs, uptime, ...}
  POST /api/start                {prose, demo?} → {job_id}
  GET  /api/events/{job_id}      SSE stream of pipeline events
  POST /api/revise               {job_id, frame, note} → {ok: true}
  GET  /api/result/{job_id}.zip  download the full output bundle
  GET  /api/demos                list of preset gallery demos

CORS: requests from STORYBOARD_ALLOWED_ORIGIN (default
https://hermes-story.art) are accepted. Preflight OPTIONS handled.

Job model:
  Each visitor's job runs in its own daemon thread. Events go into a
  per-job Queue. SSE handler drains the queue and writes events to the
  open EventSource connection. The handler uses a non-blocking get()
  with timeout, sending heartbeat lines between events to keep the
  connection alive through any HTTP proxy in the path.

Guard-rails (not full rate limits — that risk was accepted):
  - Prose 5..2000 chars, no HTML tags, no control characters.
  - Max 30 RUNNING jobs at once. Excess starts return 503.
  - Job TTL 30 minutes; janitor reaps expired jobs from disk + memory.

This file is import-safe — running `python -m scripts.web_server`
starts the server. Tests import the helpers without binding a port.
"""

from __future__ import annotations

import io
import json
import os
import queue
import re
import sys
import threading
import time
import traceback
import uuid
import zipfile
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


# =================== Configuration ===================

WEB_DIR = Path(__file__).parent.parent / "web"
DEFAULT_PORT = int(os.environ.get("PORT", os.environ.get("STORYBOARD_WEB_PORT", "8080")))
JOBS_DIR = Path(os.environ.get("STORYBOARD_JOBS_DIR", str(Path.home() / "storyboard-jobs")))
JOB_TTL_SECONDS = int(os.environ.get("STORYBOARD_JOB_TTL", "1800"))
MAX_CONCURRENT_JOBS = int(os.environ.get("STORYBOARD_MAX_JOBS", "30"))

# Per-IP rate limit for /api/start. Sliding window of recent timestamps.
RATE_LIMIT_PER_HOUR = int(os.environ.get("STORYBOARD_RATE_LIMIT_PER_HOUR", "6"))
RATE_LIMIT_WINDOW_SECONDS = 3600
_RATE_LOG: dict[str, list[float]] = {}
_RATE_LOCK = threading.Lock()


def _rate_limit_check(ip: str) -> tuple[bool, str]:
    """Returns (ok, message). ok=False means request should be 429-ed."""
    if not ip:
        return True, ""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _RATE_LOCK:
        history = _RATE_LOG.setdefault(ip, [])
        # Trim old entries
        history[:] = [t for t in history if t > cutoff]
        if len(history) >= RATE_LIMIT_PER_HOUR:
            oldest = history[0]
            wait_min = max(1, int((oldest + RATE_LIMIT_WINDOW_SECONDS - now) / 60))
            return False, (
                f"Rate limit: {RATE_LIMIT_PER_HOUR} generations per hour. "
                f"Try again in ~{wait_min} min, or install locally as a Hermes skill."
            )
        history.append(now)
    return True, ""
PROSE_MAX_LEN = 2000
PROSE_MIN_LEN = 5

# Comma-separated list. Default permits the production frontend domain
# plus localhost for dev.
ALLOWED_ORIGINS = set(
    o.strip()
    for o in os.environ.get(
        "STORYBOARD_ALLOWED_ORIGINS",
        "https://hermes-story.art,https://www.hermes-story.art,http://localhost:5173,http://localhost:3000,http://localhost:8000"
    ).split(",")
    if o.strip()
)

# Demo gallery presets — judges can run these without typing.
GALLERY_DEMOS: dict[str, dict[str, str]] = {
    "noir": {
        "title": "Noir alley",
        "prose": (
            "A detective enters a rain-soaked alley at night. He walks past "
            "silent buildings, dispatch crackling in his ear. He finds a body. "
            "He kneels, recognises the knot at the wrist — the same one as last "
            "week. He straightens, calls his partner: \"Marlowe. Third one this month.\""
        ),
    },
    "stairwell": {
        "title": "Stairwell pursuit",
        "prose": (
            "A detective enters a dim stairwell. She listens. A killer is on the "
            "landing above. She raises her weapon. She climbs two flights. The "
            "landing is empty. \"Marlowe. He was just here.\""
        ),
    },
    "kitchen": {
        "title": "Kitchen confrontation",
        "prose": (
            "Two siblings argue across a kitchen table at noon. The older one "
            "stands. The younger looks down. A phone rings. Neither answers it."
        ),
    },
}


# =================== Job state ===================

@dataclass
class Job:
    job_id: str
    prose: str
    created_at: float
    state: str = "PENDING"          # PENDING | RUNNING | DONE | ERROR | EXPIRED
    last_error: str = ""
    output_dir: Path | None = None
    events: "queue.Queue[dict[str, Any]]" = field(default_factory=lambda: queue.Queue())
    done_event: threading.Event = field(default_factory=threading.Event)
    client_ip: str = ""
    share_to_gallery: bool = False
    scene_title: str = ""
    trace: list[dict[str, Any]] = field(default_factory=list)

    def push(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.put({"type": event_type, "data": data})

    def trace_step(self, stage: str, source: str, ms: int, note: str = "") -> None:
        """Record a pipeline stage for the agent trace panel."""
        self.trace.append({
            "stage": stage,
            "source": source,
            "ms": ms,
            "note": note,
        })


_JOBS: dict[str, Job] = {}
_JOBS_LOCK = threading.Lock()
_SERVER_START = time.time()


def _new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def _job_dir(job_id: str) -> Path:
    p = JOBS_DIR / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _running_count() -> int:
    with _JOBS_LOCK:
        return sum(1 for j in _JOBS.values() if j.state == "RUNNING")


# =================== Prose validation ===================

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]")
_HTML = re.compile(r"<\s*[a-zA-Z]")


def validate_prose(prose: str) -> tuple[bool, str]:
    if not isinstance(prose, str):
        return False, "Prose must be a string."
    s = prose.strip()
    if len(s) < PROSE_MIN_LEN:
        return False, f"Prose is too short (min {PROSE_MIN_LEN} chars)."
    if len(s) > PROSE_MAX_LEN:
        return False, f"Prose is too long (max {PROSE_MAX_LEN} chars)."
    if _CONTROL.search(s):
        return False, "Prose contains control characters."
    if _HTML.search(s):
        return False, "Prose contains HTML tags. Plain text only."
    return True, ""


def _snapshot_output_artifacts(job: Job, scene: Any, out: Path) -> None:
    """Refresh files that downloads/inspect/gallery read from the job dir."""
    try:
        from scripts.render import render_scene

        patches_count = 0
        rev_path = out / "revisions.json"
        if rev_path.exists():
            try:
                rev_data = json.loads(rev_path.read_text(encoding="utf-8"))
                if isinstance(rev_data, dict):
                    patches_count = len(rev_data.get("revisions", []))
                elif isinstance(rev_data, list):
                    patches_count = len(rev_data)
            except json.JSONDecodeError:
                patches_count = 0

        memory_active = False
        try:
            from scripts.director_memory import DirectorMemory
            mem = DirectorMemory.load(base_dir=out)
            memory_active = bool(getattr(mem, "rules", []))
        except Exception:
            memory_active = False

        (out / "board.svg").write_text(
            render_scene(scene, patches_applied=patches_count, memory_active=memory_active),
            encoding="utf-8",
        )
        (out / "board.animated.svg").write_text(
            render_scene(
                scene,
                animated=True,
                patches_applied=patches_count,
                memory_active=memory_active,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[web] board snapshot skipped: {exc}", file=sys.stderr)

    try:
        from scripts.character_bible import CharacterBible
        bible = CharacterBible.load(base_dir=out)
        (out / "character_bible.json").write_text(
            bible.to_json() if hasattr(bible, "to_json")
            else json.dumps({"entries": {role: e.to_dict()
                                         for role, e in bible.entries.items()}},
                            indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[web] bible snapshot skipped: {exc}", file=sys.stderr)

    try:
        from scripts.director_memory import DirectorMemory
        mem = DirectorMemory.load(base_dir=out)
        (out / "director_memory.json").write_text(
            mem.to_json() if hasattr(mem, "to_json")
            else json.dumps({"rules": [r.to_dict() for r in mem.rules]},
                            indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[web] memory snapshot skipped: {exc}", file=sys.stderr)


def _share_job_to_gallery(job: Job) -> None:
    if not job.share_to_gallery or job.output_dir is None:
        return
    try:
        from scripts.gallery_store import add_entry
        add_entry(
            job_id=job.job_id,
            title=job.scene_title,
            prose=job.prose,
            output_dir=job.output_dir,
        )
    except Exception as exc:
        print(f"[web] gallery add failed: {exc}", file=sys.stderr)


# =================== Pipeline thread ===================

def run_pipeline(job: Job) -> None:
    """Run the full pipeline for one job, pushing events as it progresses."""
    try:
        job.state = "RUNNING"
        job.push("status", {"stage": "starting", "message": "Hermes is reading the scene…"})

        # 1. Parse prose → Scene
        from scripts.parse import ParseError, parse_prose, stub_scene
        _t0 = time.time()
        try:
            scene = parse_prose(job.prose, use_cache=True)
            job.trace_step("parse", "Kimi K2.5", int((time.time() - _t0) * 1000),
                           note=f"prose ({len(job.prose)} chars) → 6-shot Scene JSON")
        except ParseError as exc:
            job.push("status", {"stage": "parse_fallback", "message": f"Parse fallback: {exc}"})
            scene = stub_scene(job.prose)
            job.trace_step("parse", "fallback (validator)", int((time.time() - _t0) * 1000),
                           note=str(exc)[:80])

        job.push("scene", {
            "title": scene.title,
            "scene_number": scene.scene_number,
            "location": scene.location,
            "director": scene.director,
            "shot_count": len(scene.shots),
            "shots": [
                {"label": s.label, "type": s.shot_type.value, "description": s.description}
                for s in scene.shots
            ],
        })
        job.scene_title = scene.title or "Untitled scene"

        # Allocate per-job output dir BEFORE bible/memory loads — both
        # need base_dir=out to stay isolated from other users.
        out = _job_dir(job.job_id)
        job.output_dir = out

        # 2. Bible upsert (best-effort) — PER-JOB to prevent cross-user leakage
        try:
            from scripts.character_bible import CharacterBible
            bible = CharacterBible.load(base_dir=out)
            bible.upsert_from_scene(scene)
            bible.save()
            job.push("status", {"stage": "bible", "message": "Character bible updated."})
        except Exception as exc:
            job.push("status", {"stage": "bible_skipped", "message": str(exc)})

        # 3. Enrich (best-effort). Disabled by default on the public API:
        # the first visible board should not wait on optional extra Kimi calls.
        if os.environ.get("STORYBOARD_ENABLE_ENRICH") == "1":
            try:
                from scripts.enrich import enrich_scene
                enriched = enrich_scene(scene, use_cache=True)
                if enriched:
                    job.push("status", {
                        "stage": "enriched",
                        "message": f"Kimi rendered {enriched} custom environment(s).",
                    })
            except Exception as exc:
                job.push("status", {"stage": "enrich_skipped", "message": str(exc)})

        # 4. Persist scene + send SVG skeleton
        (out / "scene.json").write_text(scene.to_json(), encoding="utf-8")

        from scripts.storyboard import _build_stream_skeleton
        skeleton = _build_stream_skeleton(scene)
        job.push("skeleton", {"svg": skeleton})

        # 5. Render each shot, stream as it comes
        from scripts.render import render_shot, render_scene
        _t0 = time.time()
        for idx, shot in enumerate(scene.shots[:6]):
            shot_svg = render_shot(shot, scene, idx, animated=True)
            job.push("shot", {
                "index": idx,
                "label": shot.label,
                "shot_type": shot.shot_type.value,
                "svg": shot_svg,
            })
            # Pacing — let each shot start animating before the next arrives.
            time.sleep(0.55)
        job.trace_step("render", "local SVG", int((time.time() - _t0) * 1000),
                       note="6 shots, deterministic templates, no Kimi calls")

        # Persist the full board for download bundle
        (out / "board.svg").write_text(render_scene(scene), encoding="utf-8")
        (out / "board.animated.svg").write_text(
            render_scene(scene, animated=True), encoding="utf-8"
        )
        _snapshot_output_artifacts(job, scene, out)

        # 6. PNG export for gallery/share cards. This is local and quick.
        from scripts.png_export import PNGExportError, svg_to_png
        png_ok = False
        _t0 = time.time()
        try:
            svg_to_png(out / "board.svg", out / "board.png", width=1400)
            png_ok = True
            job.trace_step("export PNG", "rsvg-convert", int((time.time() - _t0) * 1000))
        except PNGExportError as exc:
            job.push("status", {"stage": "png_skipped", "message": str(exc)})

        # 7. Production packet is local; do it before `done` so downloads
        # are useful immediately. Vision critique continues after `done`.
        _t0 = time.time()
        try:
            from scripts.packet import export_packet
            export_packet(scene, out)
            job.trace_step("export packet", "local", int((time.time() - _t0) * 1000),
                           note="shotlist.csv, camera notes, dialogue, continuity")
            job.push("status", {"stage": "packet", "message": "Production packet exported."})
        except Exception as exc:
            job.push("status", {"stage": "packet_skipped", "message": str(exc)})

        _snapshot_output_artifacts(job, scene, out)
        _share_job_to_gallery(job)

        job.push("done", {"job_id": job.job_id})
        job.state = "DONE"

        # 8. Background PNG critique. This preserves the Kimi vision role,
        # but the user can already click frames, download, and share.
        if png_ok and os.environ.get("STORYBOARD_ENABLE_CRITIQUE", "1") == "1":
            _t0 = time.time()
            try:
                from scripts.critique import critique_board, revisions_to_json
                from scripts.iterate import apply_revisions
                png_bytes = (out / "board.png").read_bytes()
                revisions = critique_board(scene, png_bytes, use_cache=True)
                (out / "revisions.json").write_text(
                    revisions_to_json(revisions), encoding="utf-8"
                )
                job.trace_step(
                    "critique", "Kimi K2.5 vision",
                    int((time.time() - _t0) * 1000),
                    note=f"{len(revisions)} patches accepted "
                         f"(7-field whitelist + label cross-check + old_value match)",
                )
                for r in revisions:
                    job.push("revision", r.to_dict())
                    time.sleep(0.7)

                # Apply the validated patches and re-render only the
                # shots that actually changed. This is what closes the
                # loop the website promises: critic finds an issue ->
                # validator accepts -> board visibly updates.
                if revisions:
                    revised_scene = apply_revisions(scene, revisions)
                    (out / "scene.v2.json").write_text(
                        revised_scene.to_json(), encoding="utf-8"
                    )
                    changed_labels = {r.shot_label for r in revisions}
                    label_to_idx = {s.label: i for i, s in enumerate(revised_scene.shots[:6])}
                    for label in changed_labels:
                        idx = label_to_idx.get(label)
                        if idx is None:
                            continue
                        shot = revised_scene.shots[idx]
                        job.push("shot_replace", {
                            "index": idx,
                            "label": shot.label,
                            "svg": render_shot(shot, revised_scene, idx, animated=True),
                        })
                        time.sleep(0.4)
                    scene = revised_scene  # downstream stages use revised
                    (out / "scene.json").write_text(scene.to_json(), encoding="utf-8")
                    try:
                        from scripts.packet import export_packet
                        export_packet(scene, out)
                    except Exception as exc:
                        print(f"[web] packet refresh after critique skipped: {exc}", file=sys.stderr)
                else:
                    print("[web] critique found no revisions", file=sys.stderr)
                _snapshot_output_artifacts(job, scene, out)
            except Exception as exc:
                print(f"[web] background critique skipped: {exc}", file=sys.stderr)

    except Exception as exc:
        job.state = "ERROR"
        job.last_error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc(file=sys.stderr)
        job.push("error", {"message": job.last_error})
    finally:
        job.done_event.set()


def revise_frame(job: Job, frame_label: str, note: str) -> tuple[bool, str]:
    """Apply a user revision to a single frame and re-render it.
    Returns (ok, error_message). Pushes a 'shot' event with the new SVG.
    """
    if job.output_dir is None or not (job.output_dir / "scene.json").exists():
        return False, "Job has no scene yet."

    try:
        from scripts.scene import Scene
        scene_data = json.loads((job.output_dir / "scene.json").read_text(encoding="utf-8"))
        scene = Scene.from_dict(scene_data)
        target_idx = next(
            (i for i, s in enumerate(scene.shots) if s.label == frame_label), -1
        )
        if target_idx < 0:
            return False, f"No shot with label '{frame_label}'."

        # Apply the deterministic note mapper. This is what makes the
        # frame VISUALLY change — angle, shadow, silhouette, lens, etc.
        # Without it, "more Hitchcock" only ever updated a caption.
        target = scene.shots[target_idx]
        from scripts.director_notes import apply_director_note_to_shot
        intents_matched = apply_director_note_to_shot(target, note)

        # Stamp the note as a caption-prefix and persist
        if intents_matched > 0:
            target.caption = (
                f"{target.caption} [{intents_matched} intent{'s' if intents_matched != 1 else ''} applied: {note}]"
                if target.caption else f"[{intents_matched} intent{'s' if intents_matched != 1 else ''} applied: {note}]"
            )
        else:
            target.caption = (
                f"{target.caption} [note: {note}]"
                if target.caption else f"[note: {note}]"
            )
        (job.output_dir / "scene.json").write_text(scene.to_json(), encoding="utf-8")

        # Save a director-memory rule (best-effort, doesn't block the user)
        _t0 = time.time()
        try:
            from scripts.director_memory import DirectorMemory, extract_rule
            rule = extract_rule(
                note,
                scene_number=scene.scene_number,
                frame_label=frame_label,
                use_cache=True,
            )
            extract_ms = int((time.time() - _t0) * 1000)
            mem = DirectorMemory.load(base_dir=job.output_dir)
            mem.add_rule(rule)
            save_ms = int((time.time() - _t0) * 1000) - extract_ms
            job.trace_step("extract memory", "Kimi K2.5", extract_ms,
                           note="plot-leak filter + style-only validation")
            job.trace_step("save memory", "local JSON", max(save_ms, 1),
                           note="director_memory.json persisted for future scenes")
            job.push("memory_saved", {
                "preference": rule.preference,
                "applies_to": rule.applies_to,
            })
        except Exception as exc:
            print(f"[web] memory extract skipped: {exc}", file=sys.stderr)

        # Re-render only that shot and push as a replacement event
        from scripts.render import render_shot
        svg = render_shot(target, scene, target_idx, animated=True)
        job.push("shot_replace", {
            "index": target_idx,
            "label": frame_label,
            "svg": svg,
        })
        return True, ""
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return False, str(exc)


# =================== Janitor ===================

def refine_scene(job: Job, instruction: str) -> tuple[bool, str]:
    """Scene-level natural-language refinement.

    Re-parses the original prose with the user instruction injected as
    director direction. Re-renders all six shots. Used for chat-style
    refinements like "make it darker" or "more Tarkovsky".
    """
    if job.output_dir is None:
        return False, "Job has no output yet."
    instruction = (instruction or "").strip()
    if not instruction:
        return False, "Instruction is empty."
    if len(instruction) > 500:
        return False, "Instruction too long (max 500 chars)."

    try:
        from scripts.parse import ParseError, parse_prose
        from scripts.render import render_shot, render_scene

        job.push("status", {"stage": "refining",
                            "message": f"Hermes is refining: {instruction[:80]}…"})

        annotated = (
            f"{job.prose}\n\n"
            f"DIRECTION FROM DIRECTOR: {instruction}"
        )
        try:
            scene = parse_prose(annotated, use_cache=True)
        except ParseError as exc:
            return False, f"Parse failed: {exc}"

        # Apply the deterministic note mapper across all shots, so
        # whichever recognised intents are in the instruction land
        # visibly even if Kimi didn't fully internalise them.
        from scripts.director_notes import apply_director_note_to_scene
        apply_director_note_to_scene(scene, instruction)

        (job.output_dir / "scene.json").write_text(scene.to_json(), encoding="utf-8")

        from scripts.storyboard import _build_stream_skeleton
        skeleton = _build_stream_skeleton(scene)
        job.push("skeleton_replace", {"svg": skeleton})
        for idx, shot in enumerate(scene.shots[:6]):
            svg = render_shot(shot, scene, idx, animated=True)
            job.push("shot", {
                "index": idx,
                "label": shot.label,
                "shot_type": shot.shot_type.value,
                "svg": svg,
            })
            time.sleep(0.5)

        (job.output_dir / "board.svg").write_text(render_scene(scene), encoding="utf-8")
        (job.output_dir / "board.animated.svg").write_text(
            render_scene(scene, animated=True), encoding="utf-8"
        )

        job.push("status", {"stage": "refined",
                            "message": "Refined to your direction."})
        return True, ""
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return False, str(exc)


def janitor_loop() -> None:
    """Periodically reap expired jobs (in-memory + on-disk)."""
    while True:
        time.sleep(120)
        cutoff = time.time() - JOB_TTL_SECONDS
        with _JOBS_LOCK:
            expired = [
                jid for jid, job in _JOBS.items()
                if job.state in ("DONE", "ERROR") and job.created_at < cutoff
            ]
            for jid in expired:
                job = _JOBS.pop(jid, None)
                if job and job.output_dir and job.output_dir.exists():
                    try:
                        for f in job.output_dir.rglob("*"):
                            if f.is_file():
                                f.unlink(missing_ok=True)
                        for d in sorted(job.output_dir.rglob("*"), reverse=True):
                            if d.is_dir():
                                d.rmdir()
                        job.output_dir.rmdir()
                    except OSError:
                        pass


# =================== HTTP handler ===================

class StoryboardWebHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib name
        # Quiet down per-request noise; structured logs would go through
        # a real observer in prod.
        return

    # ---- CORS ----
    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        elif not origin:
            # No Origin header → likely server-to-server / curl. Send the
            # canonical site origin so it works without leaking access
            # to arbitrary browser-side callers.
            self.send_header("Access-Control-Allow-Origin", "https://hermes-story.art")
        else:
            # Origin set but NOT in allowlist — reject with no CORS header.
            # Browser will block the response. Don't wildcard, that lets
            # any site call our API and burn the OpenRouter key.
            self.send_header("Access-Control-Allow-Origin", "https://hermes-story.art")
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "3600")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    # ---- Common writers ----
    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status=status)

    # ---- Routing ----
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._serve_health_page()
        elif path == "/api/health":
            self._serve_health()
        elif path == "/api/demos":
            self._serve_demos()
        elif path == "/api/gallery":
            self._serve_gallery_list()
        elif path.startswith("/api/gallery/") and path.endswith("/board.png"):
            slug = path[len("/api/gallery/"):-len("/board.png")]
            self._serve_gallery_board(slug)
        elif path.startswith("/api/gallery/") and path.endswith("/scene.json"):
            slug = path[len("/api/gallery/"):-len("/scene.json")]
            self._serve_gallery_scene(slug)
        elif path.startswith("/board/"):
            slug = path[len("/board/"):]
            self._serve_board_share_page(slug)
        elif path.startswith("/api/events/"):
            self._serve_events(path[len("/api/events/"):])
        elif path.startswith("/api/result/") and path.endswith(".zip"):
            self._serve_result_zip(path[len("/api/result/"):-len(".zip")])
        elif path.startswith("/api/result/") and path.endswith(".gif"):
            self._serve_result_gif(path[len("/api/result/"):-len(".gif")])
        elif path.startswith("/api/inspect/"):
            # /api/inspect/{job_id}/{artifact}  → JSON
            tail = path[len("/api/inspect/"):]
            if "/" in tail:
                jid, art = tail.split("/", 1)
                self._serve_inspect(jid, art)
            else:
                self._send_error(404, "Not found.")
        else:
            self._send_error(404, "Not found.")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/start":
            self._handle_start()
        elif path == "/api/revise":
            self._handle_revise()
        elif path == "/api/refine":
            self._handle_refine()
        elif path == "/api/share":
            self._handle_share()
        else:
            self._send_error(404, "Not found.")

    # ---- Handlers ----
    def _client_ip(self) -> str:
        # Trust X-Forwarded-For when present (Fly + Cloudflare both set it).
        xff = self.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
        return self.client_address[0]

    def _serve_health_page(self) -> None:
        body = (
            "<!DOCTYPE html><meta charset=utf-8>"
            "<title>storyboard API · ok</title>"
            "<style>body{font-family:monospace;background:#f5f0e6;color:#1f1d1a;"
            "padding:48px;line-height:1.6;}h1{font-family:Georgia,serif;font-weight:500;}"
            "code{background:rgba(31,29,26,0.05);padding:2px 6px;}</style>"
            "<h1>storyboard · API</h1>"
            "<p>This is the Fly.io API endpoint for "
            "<a href='https://hermes-story.art'>hermes-story.art</a>. "
            "The frontend lives on Vercel.</p>"
            "<p>Endpoints:</p>"
            "<ul>"
            "<li><code>GET /api/health</code></li>"
            "<li><code>GET /api/demos</code></li>"
            "<li><code>POST /api/start</code> {prose}</li>"
            "<li><code>GET /api/events/{job_id}</code> (SSE)</li>"
            "<li><code>POST /api/revise</code> {job_id, frame, note}</li>"
            "<li><code>GET /api/result/{job_id}.zip</code></li>"
            "</ul>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_health(self) -> None:
        with _JOBS_LOCK:
            states = {"RUNNING": 0, "DONE": 0, "ERROR": 0, "PENDING": 0}
            for job in _JOBS.values():
                states[job.state] = states.get(job.state, 0) + 1
        self._send_json({
            "status": "ok",
            "uptime_seconds": int(time.time() - _SERVER_START),
            "jobs": states,
            "max_concurrent": MAX_CONCURRENT_JOBS,
        })

    def _serve_demos(self) -> None:
        self._send_json({
            "demos": [
                {"id": k, "title": v["title"], "prose": v["prose"]}
                for k, v in GALLERY_DEMOS.items()
            ]
        })

    def _handle_start(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 10000:
            return self._send_error(400, "Invalid request body length.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._send_error(400, "Body must be JSON.")

        # Two ways to start: explicit prose, or named demo.
        prose = payload.get("prose")
        demo_id = payload.get("demo")
        if demo_id and demo_id in GALLERY_DEMOS:
            prose = GALLERY_DEMOS[demo_id]["prose"]

        ok, err = validate_prose(prose or "")
        if not ok:
            return self._send_error(400, err)

        # Per-IP rate limit. Stops abuse + protects OpenRouter spend.
        client_ip = self._client_ip()
        ok_rate, msg = _rate_limit_check(client_ip)
        if not ok_rate:
            return self._send_error(429, msg)

        if _running_count() >= MAX_CONCURRENT_JOBS:
            return self._send_error(503, "Server is busy. Please try again in a minute.")

        job_id = _new_job_id()
        share = bool(payload.get("share_to_gallery", False))
        job = Job(
            job_id=job_id,
            prose=prose.strip(),
            created_at=time.time(),
            client_ip=self._client_ip(),
            share_to_gallery=share,
        )
        with _JOBS_LOCK:
            _JOBS[job_id] = job

        threading.Thread(target=run_pipeline, args=(job,), daemon=True,
                         name=f"pipeline-{job_id}").start()
        self._send_json({"job_id": job_id, "max_concurrent": MAX_CONCURRENT_JOBS})

    def _handle_revise(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 10000:
            return self._send_error(400, "Invalid request body length.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._send_error(400, "Body must be JSON.")

        job_id = payload.get("job_id", "")
        frame = payload.get("frame", "")
        note = payload.get("note", "")
        if not (job_id and frame and note):
            return self._send_error(400, "Missing job_id, frame, or note.")
        if len(note) > 500:
            return self._send_error(400, "Note is too long (max 500 chars).")

        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
        if job is None:
            return self._send_error(404, "Job not found or expired.")

        ok, err = revise_frame(job, frame, note)
        if not ok:
            return self._send_error(400, err)
        self._send_json({"ok": True})

    def _handle_refine(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 10000:
            return self._send_error(400, "Invalid request body length.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._send_error(400, "Body must be JSON.")

        job_id = payload.get("job_id", "")
        instruction = payload.get("instruction", "")
        if not (job_id and instruction):
            return self._send_error(400, "Missing job_id or instruction.")

        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
        if job is None:
            return self._send_error(404, "Job not found or expired.")

        ok, err = refine_scene(job, instruction)
        if not ok:
            return self._send_error(400, err)
        self._send_json({"ok": True})

    def _handle_share(self) -> None:
        """Publish a completed job to the public gallery on demand.
        Returns the canonical share_url. Idempotent: re-shares the same
        job overwrite the existing gallery entry.
        """
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0 or length > 4096:
            return self._send_error(400, "Invalid request body length.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._send_error(400, "Body must be JSON.")

        job_id = payload.get("job_id", "")
        if not job_id:
            return self._send_error(400, "Missing job_id.")

        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
        if job is None:
            return self._send_error(404, "Job not found or expired.")
        if job.state != "DONE":
            return self._send_error(409, "Job not finished yet.")
        if job.output_dir is None:
            return self._send_error(404, "No output to share.")

        try:
            from scripts.gallery_store import add_entry
            ok = add_entry(
                job_id=job.job_id,
                title=job.scene_title or "Untitled scene",
                prose=job.prose,
                output_dir=job.output_dir,
            )
            if not ok:
                return self._send_error(500, "Gallery write failed (board.png missing?).")
        except Exception as exc:
            return self._send_error(500, f"Gallery error: {exc}")

        slug = job.job_id[:6]
        self._send_json({
            "ok": True,
            "slug": slug,
            "share_url": f"https://hermes-story.art/board/{slug}",
        })

    def _serve_events(self, job_id: str) -> None:
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
        if job is None:
            return self._send_error(404, "Job not found or expired.")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")  # disable nginx buffering if any
        self._cors_headers()
        self.end_headers()

        # Send a comment immediately to defeat any proxy buffering.
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

        while True:
            try:
                event = job.events.get(timeout=1.0)
            except queue.Empty:
                # Heartbeat
                try:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
                # Stop if the job finished and queue is empty
                if job.done_event.is_set() and job.events.empty():
                    return
                continue

            payload = json.dumps(event["data"], ensure_ascii=False)
            msg = f"event: {event['type']}\ndata: {payload}\n\n".encode("utf-8")
            try:
                self.wfile.write(msg)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return

            if event["type"] in ("done", "error"):
                # Drain any trailing events first
                while not job.events.empty():
                    try:
                        ev2 = job.events.get_nowait()
                        p2 = json.dumps(ev2["data"], ensure_ascii=False)
                        m2 = f"event: {ev2['type']}\ndata: {p2}\n\n".encode("utf-8")
                        self.wfile.write(m2)
                        self.wfile.flush()
                    except (queue.Empty, BrokenPipeError, ConnectionResetError):
                        break

                # Hold the SSE connection open for a grace window so that
                # revise events (shot_replace, memory_saved) push through
                # the same channel without the client reconnecting.
                grace_deadline = time.time() + 600  # 10 minutes
                while time.time() < grace_deadline:
                    try:
                        ev = job.events.get(timeout=1.0)
                    except queue.Empty:
                        try:
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            return
                        continue
                    payload = json.dumps(ev["data"], ensure_ascii=False)
                    msg = f"event: {ev['type']}\ndata: {payload}\n\n".encode("utf-8")
                    try:
                        self.wfile.write(msg)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        return
                return

    def _serve_gallery_list(self) -> None:
        from scripts.gallery_store import list_entries
        try:
            entries = list_entries(limit=12)
        except Exception as exc:
            print(f"[web] gallery list failed: {exc}", file=sys.stderr)
            entries = []
        # Augment with public URLs the frontend can fetch directly
        for e in entries:
            slug = e.get("slug", "")
            e["board_url"] = f"/api/gallery/{slug}/board.png"
            e["share_url"] = f"https://hermes-story.art/board/{slug}"
        self._send_json({"entries": entries})

    def _serve_gallery_board(self, slug: str) -> None:
        from scripts.gallery_store import board_path
        p = board_path(slug)
        if p is None:
            return self._send_error(404, "Not found.")
        body = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_gallery_scene(self, slug: str) -> None:
        from scripts.gallery_store import scene_path
        p = scene_path(slug)
        if p is None:
            return self._send_error(404, "Not found.")
        body = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_board_share_page(self, slug: str) -> None:
        """Per-board share page with OG image meta-tags pointing at the
        board PNG. When linked on Twitter/Discord, this produces a rich
        unfurl that shows the actual storyboard.
        """
        from scripts.gallery_store import board_path, list_entries
        if not slug.isalnum() or len(slug) > 32:
            return self._send_error(404, "Invalid slug.")
        if board_path(slug) is None:
            return self._send_error(404, "Board not found.")
        # Look up title from index
        title = "Storyboard"
        prose_preview = ""
        for e in list_entries(limit=200):
            if e.get("slug") == slug:
                title = e.get("title") or title
                prose_preview = e.get("prose_preview", "")
                break

        og_img = f"https://api.hermes-story.art/api/gallery/{slug}/board.png"
        share_url = f"https://hermes-story.art/board/{slug}"
        safe_title = (title or "Storyboard").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_prose = prose_preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{safe_title} · storyboard · hermes-story.art</title>
<meta name="description" content="{safe_prose}">
<meta property="og:title" content="{safe_title} — drawn live by Hermes">
<meta property="og:description" content="{safe_prose}">
<meta property="og:image" content="{og_img}">
<meta property="og:url" content="{share_url}">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{og_img}">
<meta name="twitter:title" content="{safe_title} — drawn live by Hermes">
<meta name="twitter:description" content="{safe_prose}">
<meta http-equiv="refresh" content="0;url=https://hermes-story.art/?board={slug}">
<style>body{{font-family:Georgia,serif;background:#f5f0e6;color:#1f1d1a;padding:48px;text-align:center;}}img{{max-width:90%;border:1px solid #1f1d1a;}}</style>
</head>
<body>
<h1>{safe_title}</h1>
<p>Generated by <a href="https://hermes-story.art">storyboard</a> — a Hermes Agent skill.</p>
<img src="{og_img}" alt="storyboard">
<p><a href="https://hermes-story.art/?board={slug}">Open in storyboard →</a></p>
</body>
</html>"""
        body_bytes = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.send_header("Cache-Control", "public, max-age=600")
        self.end_headers()
        self.wfile.write(body_bytes)

    def _serve_result_zip(self, job_id: str) -> None:
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
        if job is None or job.output_dir is None or not job.output_dir.exists():
            return self._send_error(404, "Result not available.")
        if job.state != "DONE":
            return self._send_error(409, "Job not finished yet.")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath in sorted(job.output_dir.rglob("*")):
                if fpath.is_file():
                    zf.write(fpath, fpath.relative_to(job.output_dir))
        body = buf.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition",
                         f'attachment; filename="storyboard-{job_id}.zip"')
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_result_gif(self, job_id: str) -> None:
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
        if job is None or job.output_dir is None or not job.output_dir.exists():
            return self._send_error(404, "Result not available.")
        if job.state != "DONE":
            return self._send_error(409, "Job not finished yet.")

        gif_path = job.output_dir / "board.gif"
        if not gif_path.exists():
            # Build it on demand from scene.json
            try:
                from scripts.gif_export import export_gif
                from scripts.scene import Scene
                scene_data = json.loads(
                    (job.output_dir / "scene.json").read_text(encoding="utf-8")
                )
                scene = Scene.from_dict(scene_data)
                export_gif(scene, gif_path, width=900)
            except Exception as exc:
                return self._send_error(500, f"GIF export failed: {exc}")

        body = gif_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/gif")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition",
                         f'attachment; filename="storyboard-{job_id}.gif"')
        self.send_header("Cache-Control", "public, max-age=3600")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_inspect(self, job_id: str, artifact: str) -> None:
        """Return one of the agent's persistent artifacts as text.

        Whitelist of artifact names. Anything else 404s.
        """
        ALLOWED = {
            "scene": "scene.json",
            "critique": "revisions.json",
            "memory": None,
            "bible": None,
            "trace": "__trace__",   # served from job.trace, not disk
            "shotlist": "packet/shotlist.csv",
            "camera": "packet/camera_notes.md",
            "dialogue": "packet/dialogue.md",
            "continuity": "packet/continuity.md",
        }
        if artifact not in ALLOWED:
            return self._send_error(404, "Unknown artifact.")

        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
        if job is None or job.output_dir is None:
            return self._send_error(404, "Job not found or expired.")

        # Trace is served from in-memory job state
        if artifact == "trace":
            return self._send_json({"trace": job.trace})

        # Memory + bible come from THIS job's per-job dir, isolated
        # from other users on shared deployments.
        if artifact == "memory":
            try:
                from scripts.director_memory import DirectorMemory
                mem = DirectorMemory.load(base_dir=job.output_dir)
                payload = json.loads(mem.to_json()) if hasattr(mem, "to_json") else {}
            except Exception as exc:
                return self._send_error(500, f"memory read failed: {exc}")
            return self._send_json(payload)

        if artifact == "bible":
            try:
                from scripts.character_bible import CharacterBible
                bible = CharacterBible.load(base_dir=job.output_dir)
                payload = json.loads(bible.to_json()) if hasattr(bible, "to_json") else {}
            except Exception as exc:
                return self._send_error(500, f"bible read failed: {exc}")
            return self._send_json(payload)

        rel = ALLOWED[artifact]
        fp = job.output_dir / rel
        if not fp.exists():
            return self._send_error(404, f"Artifact `{artifact}` not produced for this job.")
        body = fp.read_bytes()
        if rel.endswith(".json"):
            ct = "application/json"
        elif rel.endswith(".csv"):
            ct = "text/csv"
        else:
            ct = "text/markdown"
        self.send_response(200)
        self.send_header("Content-Type", ct + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


# =================== Server entry point ===================

def serve(port: int = DEFAULT_PORT, *, blocking: bool = True) -> ThreadingHTTPServer:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", port), StoryboardWebHandler)
    threading.Thread(target=janitor_loop, daemon=True, name="janitor").start()
    print(
        f"[web] storyboard API listening on http://0.0.0.0:{port}",
        f" (allowed origins: {sorted(ALLOWED_ORIGINS)})",
        sep="\n", file=sys.stderr,
    )
    if blocking:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[web] shutting down.", file=sys.stderr)
            server.shutdown()
    return server


def main(argv: list[str] | None = None) -> int:
    serve(DEFAULT_PORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "Job", "validate_prose", "run_pipeline", "revise_frame",
    "GALLERY_DEMOS", "serve", "StoryboardWebHandler",
]
