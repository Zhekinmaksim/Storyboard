"""HTML viewer for storyboard outputs.

A single-file static HTML page that renders alongside the pipeline outputs.
Side-by-side draft vs. final SVG, critique revision log, and a download
strip (SVG, PNG, scene JSON).

The viewer is intentionally self-contained — no external CSS/JS, no CDN.
Open viewer.html from disk and it works offline. This is part of the
"Editable, no black-box" pitch from the docx analysis.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from scripts.scene import Scene
from scripts.style import DRY_INK, FONTS


def build_viewer_html(out_dir: Path, draft: Scene, final: Scene) -> str:
    # Prefer animated SVGs for the visible WOW; fall back to static if not present.
    draft_svg = _read_text(out_dir / "draft.animated.svg") or _read_text(out_dir / "draft.svg")
    final_svg = _read_text(out_dir / "board.animated.svg") or _read_text(out_dir / "board.svg")
    revisions_data = _read_json(out_dir / "revisions" / "round_1.json")
    bible_data = _read_json(out_dir / "character_bible.json")

    revisions = revisions_data.get("revisions", []) if isinstance(revisions_data, dict) else []
    bible_entries = bible_data.get("entries", {}) if isinstance(bible_data, dict) else {}

    return _TEMPLATE.format(
        title=html.escape(final.title),
        scene_number=html.escape(final.scene_number),
        location=html.escape(final.location),
        director=html.escape(final.director),
        bg=DRY_INK["bg"],
        fg=DRY_INK["fg"],
        fg_dim=DRY_INK["fg_dim"],
        accent=DRY_INK["accent"],
        serif=FONTS["serif"],
        mono=FONTS["mono"],
        draft_svg=draft_svg,
        final_svg=final_svg,
        revisions_html=_revisions_html(revisions),
        bible_html=_bible_html(bible_entries),
        scene_json=html.escape(final.to_json()),
    )


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _revisions_html(revisions: list[dict]) -> str:
    if not revisions:
        return "<p class='empty'>No revisions — Kimi K2.5 found the draft coherent.</p>"
    rows = []
    for r in revisions:
        rows.append(
            f"<li><span class='label'>{html.escape(r.get('shot_label', ''))}</span>"
            f"<span class='field'>{html.escape(r.get('field', ''))}</span>"
            f"<span class='arrow'>→</span>"
            f"<span class='value'>{html.escape(r.get('new_value', ''))}</span>"
            f"<p class='reason'>{html.escape(r.get('reason', ''))}</p></li>"
        )
    return "<ul class='revisions'>" + "".join(rows) + "</ul>"


def _bible_html(entries: dict[str, dict]) -> str:
    if not entries:
        return "<p class='empty'>No characters yet.</p>"
    rows = []
    for role, e in entries.items():
        rows.append(
            f"<li><span class='label'>{html.escape(role)}</span>"
            f"<span class='value'>{html.escape(e.get('display_name', ''))}</span>"
            f"<p class='reason'>{html.escape(e.get('silhouette') or '(no silhouette)')}</p></li>"
        )
    return "<ul class='revisions'>" + "".join(rows) + "</ul>"


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} — storyboard</title>
<style>
  :root {{
    --bg: {bg};
    --fg: {fg};
    --fg-dim: {fg_dim};
    --accent: {accent};
    --serif: {serif};
    --mono: {mono};
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--fg); }}
  body {{ font-family: var(--serif); line-height: 1.5; padding: 32px 48px; max-width: 1600px; margin: 0 auto; }}
  h1 {{ font-family: var(--serif); font-weight: 500; font-size: 28px; margin: 0 0 4px; }}
  .meta {{ font-family: var(--mono); font-size: 12px; color: var(--fg-dim); letter-spacing: 0.05em; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--fg); }}
  h2 {{ font-family: var(--mono); font-weight: 500; font-size: 11px; letter-spacing: 0.15em; color: var(--fg-dim); text-transform: uppercase; margin: 32px 0 12px; }}
  .columns {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
  .col {{ background: var(--bg); border: 1px solid var(--fg); }}
  .col-header {{ font-family: var(--mono); font-size: 11px; letter-spacing: 0.15em; padding: 10px 14px; color: var(--fg-dim); border-bottom: 1px solid var(--fg-dim); display: flex; justify-content: space-between; }}
  .col-header .badge {{ background: var(--accent); color: var(--bg); padding: 1px 8px; border-radius: 2px; font-size: 9px; }}
  .svg-wrap {{ padding: 12px; }}
  .svg-wrap svg {{ display: block; width: 100%; height: auto; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .panel {{ border: 1px solid var(--fg); padding: 16px 20px; }}
  .panel h2 {{ margin-top: 0; }}
  ul.revisions {{ list-style: none; padding: 0; margin: 0; }}
  ul.revisions li {{ padding: 12px 0; border-bottom: 1px dashed var(--fg-dim); }}
  ul.revisions li:last-child {{ border-bottom: none; }}
  ul.revisions .label {{ display: inline-block; font-family: var(--mono); font-size: 12px; padding: 2px 8px; border: 1px solid var(--fg); margin-right: 8px; }}
  ul.revisions .field {{ font-family: var(--mono); font-size: 12px; color: var(--fg-dim); margin-right: 8px; }}
  ul.revisions .arrow {{ font-family: var(--mono); color: var(--accent); margin-right: 8px; }}
  ul.revisions .value {{ font-family: var(--mono); font-size: 13px; color: var(--accent); }}
  ul.revisions .reason {{ margin: 6px 0 0; padding-left: 4px; font-size: 13px; color: var(--fg-dim); font-style: italic; }}
  .empty {{ font-style: italic; color: var(--fg-dim); margin: 0; }}
  .actions {{ display: flex; gap: 12px; margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--fg); }}
  .actions button {{
    font-family: var(--mono); font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase;
    background: var(--bg); color: var(--fg); border: 1px solid var(--fg);
    padding: 10px 18px; cursor: pointer; transition: background 0.1s;
  }}
  .actions button:hover {{ background: var(--fg); color: var(--bg); }}
  .actions .primary {{ background: var(--accent); color: var(--bg); border-color: var(--accent); }}
  .actions .primary:hover {{ background: var(--fg); border-color: var(--fg); }}
  .scene-json {{ display: none; font-family: var(--mono); font-size: 11px; padding: 12px; background: rgba(31,29,26,0.04); border: 1px dashed var(--fg-dim); white-space: pre-wrap; max-height: 400px; overflow: auto; }}
  .scene-json.open {{ display: block; }}
  footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--fg-dim); font-family: var(--mono); font-size: 10px; color: var(--fg-dim); display: flex; justify-content: space-between; letter-spacing: 0.1em; }}
  footer a {{ color: var(--accent); text-decoration: none; }}
</style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">DIR. {director} · SCENE {scene_number} · {location} · STORYBOARD VIEWER</div>

  <h2>Draft vs. Critique</h2>
  <div class="columns">
    <div class="col">
      <div class="col-header"><span>DRAFT</span><span>before Kimi K2.5 critique</span></div>
      <div class="svg-wrap">{draft_svg}</div>
    </div>
    <div class="col">
      <div class="col-header"><span>BOARD <span class="badge">CRITIQUED</span></span><span>after 1 revision round</span></div>
      <div class="svg-wrap">{final_svg}</div>
    </div>
  </div>

  <div class="grid">
    <div class="panel">
      <h2>Kimi K2.5 Revisions</h2>
      {revisions_html}
    </div>
    <div class="panel">
      <h2>Character Bible</h2>
      {bible_html}
    </div>
  </div>

  <div class="actions">
    <button onclick="document.getElementById('json').classList.toggle('open')">Show Scene JSON</button>
    <button onclick="downloadFile('board.svg', document.querySelector('.col:nth-child(2) svg').outerHTML, 'image/svg+xml')">Download SVG</button>
    <button onclick="copyPrompt()">Copy revise prompt</button>
    <button class="primary" onclick="alert('On the CLI: storyboard finalize')">Approve as Final</button>
  </div>

  <pre class="scene-json" id="json">{scene_json}</pre>

  <footer>
    <span>generated by storyboard · powered by kimi k2.5 multimodal · dry ink palette</span>
    <span><a href="https://github.com/Zhekinmaksim/storyboard">github.com/Zhekinmaksim/storyboard</a></span>
  </footer>

<script>
function downloadFile(filename, content, mime) {{
  const blob = new Blob([content], {{type: mime}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}}
function copyPrompt() {{
  const ex = "storyboard revise scene.v2.json --frame 1F --note 'low angle, harder shadow'";
  navigator.clipboard.writeText(ex);
  alert('Copied: ' + ex);
}}
</script>
</body>
</html>
"""


__all__ = ["build_viewer_html"]
