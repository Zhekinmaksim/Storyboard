"""Main CLI for the storyboard skill.

Subcommands:
  full      end-to-end: prose → board → 1 critique round → approval gate
  parse     prose → Scene JSON
  render    Scene JSON → SVG
  critique  Scene + PNG → revisions JSON
  iterate   Scene + revisions → new Scene
  revise    re-render a single frame after a user note
  view      open the HTML viewer for the latest board
  bible     show or edit the character bible

The full pipeline is hard-capped at ONE auto-critique round. After that,
control returns to the user for explicit approval or targeted edits.
This is the hybrid loop: model-driven draft + critique, human-in-loop
finalize.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path

from scripts.character_bible import CharacterBible
from scripts.critique import Revision, critique_board, revisions_to_json
from scripts.iterate import apply_revisions
from scripts.parse import ParseError, parse_prose, stub_scene
from scripts.png_export import PNGExportError, svg_to_png
from scripts.render import render_scene
from scripts.scene import Scene


def _output_dir() -> Path:
    raw = os.environ.get("STORYBOARD_OUTPUT_DIR", str(Path.home() / "storyboard-output"))
    p = Path(raw).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    (p / "revisions").mkdir(exist_ok=True)
    return p


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    print(f"  → {path}", file=sys.stderr)


# =================== subcommands ===================

def cmd_parse(args: argparse.Namespace) -> int:
    try:
        scene = parse_prose(args.prose, use_cache=not args.no_cache)
    except ParseError as exc:
        if args.fallback:
            print(f"[parse] using stub fallback: {exc}", file=sys.stderr)
            scene = stub_scene(args.prose)
        else:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    output = scene.to_json()
    if args.output:
        _write(Path(args.output), output)
    else:
        print(output)
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    scene_data = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    scene = Scene.from_dict(scene_data)
    svg = render_scene(scene)
    if args.output:
        _write(Path(args.output), svg)
    else:
        sys.stdout.write(svg)
    return 0


def cmd_critique(args: argparse.Namespace) -> int:
    scene_data = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    scene = Scene.from_dict(scene_data)
    png_bytes = Path(args.png).read_bytes()
    revisions = critique_board(scene, png_bytes, use_cache=not args.no_cache)
    out = revisions_to_json(revisions)
    if args.output:
        _write(Path(args.output), out)
    else:
        print(out)
    return 0


def cmd_iterate(args: argparse.Namespace) -> int:
    scene_data = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    scene = Scene.from_dict(scene_data)
    rev_data = json.loads(Path(args.revisions).read_text(encoding="utf-8"))
    revisions = [
        Revision(
            shot_label=r["shot_label"],
            field=r["field"],
            new_value=r["new_value"],
            reason=r.get("reason", ""),
        )
        for r in rev_data.get("revisions", [])
    ]
    new_scene = apply_revisions(scene, revisions)
    out = new_scene.to_json()
    if args.output:
        _write(Path(args.output), out)
    else:
        print(out)
    return 0


def cmd_full(args: argparse.Namespace) -> int:
    """End-to-end: prose → draft → 1 critique round → approval gate.

    With --stream, opens a local viewer at http://localhost:7777 and
    pushes each shot live as it renders. WOW mode for demos.
    """
    out = _output_dir()

    # Streaming server boots first so the viewer can connect before
    # we start producing events.
    server = None
    if args.stream:
        from scripts.stream_server import start_server
        server = start_server(out, port=7777)
        print("[stream] viewer at http://localhost:7777", file=sys.stderr)
        print("[stream] open it in Firefox now; demo starts in 3 seconds.", file=sys.stderr)
        import time as _time
        _time.sleep(3)

    print("[1/7] parsing prose...", file=sys.stderr)
    try:
        scene = parse_prose(args.prose, use_cache=not args.no_cache)
    except ParseError as exc:
        print(f"  parse failed, using stub: {exc}", file=sys.stderr)
        scene = stub_scene(args.prose)

    # Character bible round-trip
    print("[2/7] loading character bible...", file=sys.stderr)
    bible = CharacterBible.load()
    added = bible.upsert_from_scene(scene)
    if added:
        print(f"  bible: added {len(added)} new role(s): {', '.join(added)}", file=sys.stderr)
    bible.save()

    # Kimi-as-environment-renderer for shots that don't fit templates
    print("[3/7] enriching non-template environments via Kimi K2.5...", file=sys.stderr)
    if not args.skip_enrich:
        from scripts.enrich import enrich_scene
        enriched = enrich_scene(scene, use_cache=not args.no_cache)
        if enriched:
            print(f"  enriched {enriched} shot(s) with custom SVG", file=sys.stderr)
        else:
            print("  no enrichment needed (all shots use templates)", file=sys.stderr)
    else:
        print("  skipped (--skip-enrich)", file=sys.stderr)

    _write(out / "scene.json", scene.to_json())
    print("[4/7] rendering draft SVG (static + animated)...", file=sys.stderr)

    # If streaming, push the scene skeleton then per-shot SVGs as we go
    if args.stream:
        from scripts.stream_server import push_event
        from scripts.render import render_shot
        # Send a minimal skeleton: SVG container with header and footer placeholders,
        # so per-shot <g> elements can be inserted.
        skeleton = _build_stream_skeleton(scene)
        push_event("scene", {
            "title": scene.title,
            "scene_number": scene.scene_number,
            "location": scene.location,
            "director": scene.director,
            "svg_skeleton": skeleton,
        })
        for idx, shot in enumerate(scene.shots[:6]):
            shot_svg = render_shot(shot, scene, idx, animated=True)
            push_event("shot", {
                "index": idx,
                "label": shot.label,
                "svg": shot_svg,
            })
            import time as _time
            _time.sleep(0.6)  # let each shot start its animation before the next arrives

    draft_svg = render_scene(scene)                          # for PNG critique
    draft_animated = render_scene(scene, animated=True)      # for viewer wow
    _write(out / "draft.svg", draft_svg)
    _write(out / "draft.animated.svg", draft_animated)

    print("[5/7] exporting PNG for critique...", file=sys.stderr)
    try:
        svg_to_png(out / "draft.svg", out / "draft.png", width=1400)
    except PNGExportError as exc:
        print(f"  PNG export failed; skipping critique: {exc}", file=sys.stderr)
        _write_viewer(out, scene, scene)
        print("\nDraft saved without critique. Open viewer.html to review.", file=sys.stderr)
        return 0

    print("[6/7] auto-critique (1 round)...", file=sys.stderr)
    if args.stream:
        from scripts.stream_server import push_event
        push_event("critique_start", {})
    png_bytes = (out / "draft.png").read_bytes()
    revisions = critique_board(scene, png_bytes, use_cache=not args.no_cache)
    _write(out / "revisions" / "round_1.json", revisions_to_json(revisions))

    if args.stream:
        from scripts.stream_server import push_event
        for r in revisions:
            push_event("revision", r.to_dict())
            import time as _time
            _time.sleep(0.8)

    if revisions:
        print(f"  {len(revisions)} revision(s) suggested:", file=sys.stderr)
        for r in revisions:
            print(f"    {r.shot_label} · {r.field} → {r.new_value}  ({r.reason})", file=sys.stderr)
        revised_scene = apply_revisions(scene, revisions)
        _write(out / "scene.v2.json", revised_scene.to_json())
        revised_svg = render_scene(revised_scene)
        revised_animated = render_scene(revised_scene, animated=True)
        _write(out / "board.svg", revised_svg)
        _write(out / "board.animated.svg", revised_animated)
        try:
            svg_to_png(out / "board.svg", out / "board.png", width=1400)
        except PNGExportError as exc:
            print(f"  PNG re-export failed: {exc}", file=sys.stderr)
        _write_viewer(out, scene, revised_scene)
    else:
        print("  no revisions; draft is already coherent", file=sys.stderr)
        revised_scene = scene
        _write(out / "board.svg", draft_svg)
        _write(out / "board.animated.svg", draft_animated)
        try:
            svg_to_png(out / "board.svg", out / "board.png", width=1400)
        except PNGExportError:
            pass
        _write_viewer(out, scene, scene)

    print("[7/7] approval gate", file=sys.stderr)

    # Production packet — export the ancillary documents (shotlist,
    # camera notes, dialogue, continuity). Written even before approval
    # so judges/users see a complete pre-production bundle.
    try:
        from scripts.packet import export_packet
        packet_files = export_packet(revised_scene, out)
        print(f"  production packet: {len(packet_files)} files in {out/'packet'}/",
              file=sys.stderr)
    except Exception as exc:
        print(f"  packet export skipped: {exc}", file=sys.stderr)

    if args.stream:
        from scripts.stream_server import signal_done
        signal_done()
        print("[stream] viewer received all events; server will exit when you Ctrl+C.", file=sys.stderr)
    print("\n──────────────────────────────────────────────────────────", file=sys.stderr)
    print(f"Draft + 1 critique round complete. Outputs in: {out}", file=sys.stderr)
    print("Open viewer.html to review side-by-side.", file=sys.stderr)
    print("To request a targeted change:", file=sys.stderr)
    print(f"  storyboard revise {out/'scene.v2.json'} --frame <label> --note '...'", file=sys.stderr)
    print("To accept as final:", file=sys.stderr)
    print("  storyboard finalize", file=sys.stderr)
    print("──────────────────────────────────────────────────────────", file=sys.stderr)

    if args.open:
        webbrowser.open(f"file://{(out / 'viewer.html').resolve()}")

    if args.stream and server is not None:
        # Keep the server alive so the viewer can stay open. User Ctrl+Cs to exit.
        try:
            print("\n[stream] press Ctrl+C to stop the server.", file=sys.stderr)
            import time as _time
            while True:
                _time.sleep(60)
        except KeyboardInterrupt:
            print("\n[stream] shutting down.", file=sys.stderr)
            server.shutdown()

    return 0


def cmd_revise(args: argparse.Namespace) -> int:
    """Re-render a specific frame given a user note, extract a director
    rule from the note, and persist it to director_memory so future
    scenes inherit the style automatically.
    """
    scene_data = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    scene = Scene.from_dict(scene_data)
    target = next((s for s in scene.shots if s.label == args.frame), None)
    if target is None:
        print(f"error: no shot with label '{args.frame}'", file=sys.stderr)
        return 2

    # Stamp the note into the caption so the change is visible in the
    # frame metadata; this is the immediate, mechanical effect.
    target.caption = (
        f"{target.caption} [revised: {args.note}]"
        if target.caption else f"[revised: {args.note}]"
    )

    out = _output_dir()
    new_scene_path = out / "scene.revised.json"
    new_svg_path = out / "board.svg"
    _write(new_scene_path, scene.to_json())
    _write(new_svg_path, render_scene(scene))
    log_path = out / "revisions" / f"user_note_{args.frame}.txt"
    log_path.write_text(args.note, encoding="utf-8")

    # Extract a director rule and save it to memory. This is the
    # learning loop: the user revises one frame, Hermes generalises
    # the preference, future scenes apply it without being asked.
    if not args.no_memory:
        try:
            from scripts.director_memory import DirectorMemory, extract_rule
            rule = extract_rule(
                args.note,
                scene_number=scene.scene_number,
                frame_label=args.frame,
                use_cache=not getattr(args, "no_cache", False),
            )
            memory = DirectorMemory.load()
            memory.add_rule(rule)
            print(f"[memory] saved director rule: {rule.preference[:80]}",
                  file=sys.stderr)
            tags = ", ".join(rule.applies_to) if rule.applies_to else "(no tags)"
            print(f"[memory] applies_to: {tags}", file=sys.stderr)
        except Exception as exc:
            print(f"[memory] rule extraction skipped: {exc}", file=sys.stderr)

    print(f"frame {args.frame} updated. Re-render saved.", file=sys.stderr)
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    out = _output_dir()
    viewer = out / "viewer.html"
    if not viewer.exists():
        print(f"no viewer.html in {out}; run `storyboard full ...` first", file=sys.stderr)
        return 2
    webbrowser.open(f"file://{viewer.resolve()}")
    return 0


def cmd_bible(args: argparse.Namespace) -> int:
    bible = CharacterBible.load()
    if args.show:
        print(json.dumps({"entries": {k: v.to_dict() for k, v in bible.entries.items()}},
                         indent=2, ensure_ascii=False))
        return 0
    if args.set_silhouette:
        role, _, silhouette = args.set_silhouette.partition("=")
        role = role.strip().lower()
        if role not in bible.entries:
            print(f"role '{role}' not in bible", file=sys.stderr)
            return 2
        bible.entries[role].silhouette = silhouette.strip()
        bible.save()
        print(f"updated silhouette for '{role}'", file=sys.stderr)
        return 0
    print("nothing to do; pass --show or --set-silhouette role=value", file=sys.stderr)
    return 1


def cmd_memory(args: argparse.Namespace) -> int:
    """Inspect or clear the director memory."""
    from scripts.director_memory import DirectorMemory
    memory = DirectorMemory.load()
    if args.clear:
        memory.rules = []
        memory.save()
        print("director memory cleared.", file=sys.stderr)
        return 0
    if args.show or not args.clear:
        if not memory.rules:
            print("(director memory is empty — no rules learned yet)")
            return 0
        print(json.dumps(
            {"rules": [r.to_dict() for r in memory.rules]},
            indent=2, ensure_ascii=False,
        ))
        return 0
    return 0


def cmd_packet(args: argparse.Namespace) -> int:
    """Export the production packet (shotlist, camera notes, dialogue,
    continuity) for a given Scene JSON. Files are written to
    $STORYBOARD_OUTPUT_DIR/packet/.
    """
    from scripts.packet import export_packet
    scene_data = json.loads(Path(args.scene).read_text(encoding="utf-8"))
    scene = Scene.from_dict(scene_data)
    out = _output_dir()
    written = export_packet(scene, out)
    print(f"production packet exported to {out / 'packet'}/", file=sys.stderr)
    for name, path in written.items():
        print(f"  {name}: {path.stat().st_size} bytes", file=sys.stderr)
    return 0


def _write_viewer(out: Path, draft_scene: Scene, final_scene: Scene) -> None:
    """Generate the HTML viewer with side-by-side draft/critique view."""
    from scripts.viewer import build_viewer_html  # lazy import to keep CLI startup fast
    html = build_viewer_html(out, draft_scene, final_scene)
    _write(out / "viewer.html", html)


# =================== argparse plumbing ===================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="storyboard", description=__doc__.strip().splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("full", help="end-to-end pipeline with approval gate")
    sp.add_argument("prose", help="prose scene description")
    sp.add_argument("--no-cache", action="store_true", help="bypass Kimi response cache")
    sp.add_argument("--open", action="store_true", help="auto-open viewer in browser")
    sp.add_argument("--skip-enrich", action="store_true",
                    help="skip Kimi env-rendering, use templates only (faster, more deterministic)")
    sp.add_argument("--stream", action="store_true",
                    help="start the streaming server so the viewer renders shots live as they arrive")
    sp.set_defaults(func=cmd_full)

    sp = sub.add_parser("parse", help="prose to Scene JSON")
    sp.add_argument("prose")
    sp.add_argument("--output", "-o", help="write to file instead of stdout")
    sp.add_argument("--no-cache", action="store_true")
    sp.add_argument("--fallback", action="store_true", help="emit stub Scene if Kimi fails")
    sp.set_defaults(func=cmd_parse)

    sp = sub.add_parser("render", help="Scene JSON to SVG")
    sp.add_argument("scene")
    sp.add_argument("--output", "-o")
    sp.set_defaults(func=cmd_render)

    sp = sub.add_parser("critique", help="multimodal critique pass")
    sp.add_argument("scene")
    sp.add_argument("png")
    sp.add_argument("--output", "-o")
    sp.add_argument("--no-cache", action="store_true")
    sp.set_defaults(func=cmd_critique)

    sp = sub.add_parser("iterate", help="apply revisions JSON to scene")
    sp.add_argument("scene")
    sp.add_argument("revisions")
    sp.add_argument("--output", "-o")
    sp.set_defaults(func=cmd_iterate)

    sp = sub.add_parser("revise", help="re-render a single frame from a user note; learns the style rule")
    sp.add_argument("scene")
    sp.add_argument("--frame", required=True, help="shot label, e.g. 1F")
    sp.add_argument("--note", required=True, help="director note for the frame")
    sp.add_argument("--no-memory", action="store_true",
                    help="don't extract or persist a director rule from this revision")
    sp.add_argument("--no-cache", action="store_true",
                    help="bypass Kimi response cache")
    sp.set_defaults(func=cmd_revise)

    sp = sub.add_parser("view", help="open the HTML viewer for the last board")
    sp.set_defaults(func=cmd_view)

    sp = sub.add_parser("bible", help="show or edit the character bible")
    sp.add_argument("--show", action="store_true")
    sp.add_argument("--set-silhouette", help="role=silhouette description")
    sp.set_defaults(func=cmd_bible)

    sp = sub.add_parser("memory", help="show or clear the director memory (style rules)")
    sp.add_argument("--show", action="store_true", default=True)
    sp.add_argument("--clear", action="store_true",
                    help="erase all learned director rules")
    sp.set_defaults(func=cmd_memory)

    sp = sub.add_parser("packet", help="export production packet (shotlist, camera notes, dialogue, continuity)")
    sp.add_argument("scene", help="path to scene JSON file")
    sp.set_defaults(func=cmd_packet)

    return p


def _build_stream_skeleton(scene: Scene) -> str:
    """Build the SVG container with header + background + footer rule, but
    no shot frames. Frames are appended live by the streaming viewer.

    The header animates in immediately so the page doesn't look frozen
    while waiting for shot 1A.
    """
    from scripts.render import _background, _defs, _footer, _header, _svg_open
    from scripts.style import PAGE
    w, h = PAGE["width"], PAGE["height"]
    parts = [
        _svg_open(w, h),
        _defs(),
        _background(w, h),
        _header(scene, w, animated=True),
        # Footer can render — counts will be correct since scene.shots is final
        _footer(scene, w, h, animated=True, total_shots=len(scene.shots)),
        # Note: no </svg> here — viewer appends shots before closing
    ]
    return "".join(parts) + "</svg>"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
