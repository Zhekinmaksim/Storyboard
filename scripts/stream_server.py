"""Local HTTP server with Server-Sent Events for live storyboard rendering.

When `storyboard full --stream` runs:
  1. Server starts on http://localhost:7777
  2. Viewer.html (served at /) connects to /events via EventSource
  3. As the pipeline produces each shot, it pushes an SSE event:
       event: shot
       data: {"index": 0, "label": "1A", "svg": "<g>...</g>"}
  4. Viewer appends the shot SVG to the live board, animations play
     automatically because the SVG carries SMIL begin='Xs' offsets.
  5. After the last shot, server pushes:
       event: done
       data: {"revisions": [...]}
     and viewer fades in the revisions panel.

This is the WOW moment: the user types a prompt, hits enter, watches
the board self-draw shot-by-shot in their browser, then sees Kimi's
critique appear in real time.

The server uses only the stdlib (http.server + threading + queue) — no
fastapi/uvicorn dependency, no async runtime to manage. One thread
serves HTTP, one thread runs the pipeline, they communicate via Queue.
"""

from __future__ import annotations

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


# Singleton event queue. The pipeline thread pushes events; the SSE
# handler drains them and writes to the open EventSource connection.
_event_queue: "queue.Queue[dict[str, Any]]" = queue.Queue()
_pipeline_done = threading.Event()


def push_event(event_type: str, data: dict[str, Any]) -> None:
    """Pipeline calls this to send an event to the live viewer."""
    _event_queue.put({"type": event_type, "data": data})


def signal_done() -> None:
    _pipeline_done.set()
    _event_queue.put({"type": "done", "data": {}})


class StreamHandler(BaseHTTPRequestHandler):
    """Serves the streaming viewer at / and SSE events at /events."""

    output_dir: Path = Path.home() / "storyboard-output"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib name
        # Quiet down per-request logging; the pipeline is the show.
        return

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._serve_viewer()
        elif self.path == "/events":
            self._serve_events()
        elif self.path.startswith("/static/"):
            self._serve_static(self.path[len("/static/"):])
        else:
            self.send_error(404, "Not Found")

    def _serve_viewer(self) -> None:
        html = build_streaming_viewer_html()
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            while True:
                try:
                    event = _event_queue.get(timeout=1.0)
                except queue.Empty:
                    # Heartbeat to keep the connection alive
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    if _pipeline_done.is_set() and _event_queue.empty():
                        break
                    continue

                payload = json.dumps(event["data"], ensure_ascii=False)
                msg = f"event: {event['type']}\ndata: {payload}\n\n"
                try:
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break

                if event["type"] == "done":
                    break
        except Exception:
            return

    def _serve_static(self, name: str) -> None:
        # Sanitize: no traversal, only flat names
        if "/" in name or ".." in name:
            self.send_error(403)
            return
        path = self.output_dir / name
        if not path.exists():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        ext = path.suffix.lower()
        ct = {
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".json": "application/json",
            ".html": "text/html",
        }.get(ext, "application/octet-stream")
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_server(output_dir: Path, *, port: int = 7777) -> ThreadingHTTPServer:
    StreamHandler.output_dir = output_dir
    server = ThreadingHTTPServer(("127.0.0.1", port), StreamHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def build_streaming_viewer_html() -> str:
    """The live viewer. Subscribes to /events, appends shots as they
    arrive, plays the SMIL animations automatically.
    """
    from scripts.style import DRY_INK, FONTS
    return _STREAMING_TEMPLATE.format(
        bg=DRY_INK["bg"], fg=DRY_INK["fg"], fg_dim=DRY_INK["fg_dim"],
        accent=DRY_INK["accent"], serif=FONTS["serif"], mono=FONTS["mono"],
    )


_STREAMING_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>storyboard — live</title>
<style>
  :root {{
    --bg: {bg}; --fg: {fg}; --fg-dim: {fg_dim}; --accent: {accent};
    --serif: {serif}; --mono: {mono};
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--fg); }}
  body {{ font-family: var(--serif); padding: 32px 48px; max-width: 1600px; margin: 0 auto; }}
  h1 {{ font-weight: 500; font-size: 28px; margin: 0 0 4px; }}
  .meta {{ font-family: var(--mono); font-size: 12px; color: var(--fg-dim);
           letter-spacing: 0.05em; margin-bottom: 24px; padding-bottom: 16px;
           border-bottom: 1px solid var(--fg); }}
  .status {{ font-family: var(--mono); font-size: 11px; color: var(--accent);
             letter-spacing: 0.15em; padding: 8px 14px; margin-bottom: 16px;
             border: 1px dashed var(--accent); display: inline-block; }}
  .status.idle {{ color: var(--fg-dim); border-color: var(--fg-dim); }}
  .status.done {{ color: #2c5a3a; border-color: #2c5a3a; }}
  .board-wrap {{ background: var(--bg); border: 1px solid var(--fg); padding: 0; }}
  .board {{ width: 100%; height: auto; display: block; }}
  .board svg {{ display: block; width: 100%; height: auto; }}
  .panel {{ margin-top: 24px; border: 1px solid var(--fg); padding: 16px 20px; opacity: 0; transition: opacity 0.6s; }}
  .panel.visible {{ opacity: 1; }}
  .panel h2 {{ font-family: var(--mono); font-weight: 500; font-size: 11px;
               letter-spacing: 0.15em; color: var(--fg-dim); text-transform: uppercase;
               margin: 0 0 12px; }}
  .revisions {{ list-style: none; padding: 0; margin: 0; }}
  .revisions li {{ padding: 12px 0; border-bottom: 1px dashed var(--fg-dim); }}
  .revisions li:last-child {{ border-bottom: none; }}
  .revisions .label {{ font-family: var(--mono); font-size: 12px; padding: 2px 8px;
                       border: 1px solid var(--fg); margin-right: 8px; display: inline-block; }}
  .revisions .field {{ font-family: var(--mono); font-size: 12px; color: var(--fg-dim); margin-right: 8px; }}
  .revisions .arrow {{ font-family: var(--mono); color: var(--accent); margin-right: 8px; }}
  .revisions .value {{ font-family: var(--mono); font-size: 13px; color: var(--accent); }}
  .revisions .reason {{ margin: 6px 0 0; font-size: 13px; color: var(--fg-dim); font-style: italic; }}
  footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--fg-dim);
            font-family: var(--mono); font-size: 10px; color: var(--fg-dim);
            display: flex; justify-content: space-between; letter-spacing: 0.1em; }}
  footer a {{ color: var(--accent); text-decoration: none; }}
  /* Highlight pulse when Kimi flags a frame */
  .kimi-flag {{ animation: pulse 1.4s ease-in-out 2; }}
  @keyframes pulse {{
    0%, 100% {{ filter: drop-shadow(0 0 0 transparent); }}
    50% {{ filter: drop-shadow(0 0 12px var(--accent)); }}
  }}
</style>
</head>
<body>
  <h1 id="title">storyboard</h1>
  <div class="meta" id="meta">awaiting prose…</div>
  <div class="status idle" id="status">CONNECTING…</div>

  <div class="board-wrap">
    <div class="board" id="board"></div>
  </div>

  <div class="panel" id="critique-panel">
    <h2>Kimi K2.5 Critique</h2>
    <ul class="revisions" id="revisions"></ul>
  </div>

  <footer>
    <span>generated by storyboard · live · powered by Kimi K2.5</span>
    <span><a href="https://github.com/Zhekinmaksim/storyboard">github.com/Zhekinmaksim/storyboard</a></span>
  </footer>

<script>
  const status = document.getElementById('status');
  const board = document.getElementById('board');
  const meta = document.getElementById('meta');
  const titleEl = document.getElementById('title');
  const critiquePanel = document.getElementById('critique-panel');
  const revisionsEl = document.getElementById('revisions');

  function setStatus(text, cls) {{
    status.textContent = text;
    status.className = 'status ' + (cls || '');
  }}

  let svgRoot = null;

  const es = new EventSource('/events');

  es.addEventListener('open', () => setStatus('CONNECTED — WAITING FOR PIPELINE', 'idle'));

  es.addEventListener('scene', (e) => {{
    const data = JSON.parse(e.data);
    titleEl.textContent = data.title || 'storyboard';
    meta.textContent = `DIR. ${{(data.director || '').toUpperCase()}} · SCENE ${{data.scene_number || '01'}} · ${{(data.location || '').toUpperCase()}}`;
    // Initialize the SVG container with the scene-level chrome
    board.innerHTML = data.svg_skeleton;
    svgRoot = board.querySelector('svg');
    setStatus('PARSING…', '');
  }});

  es.addEventListener('shot', (e) => {{
    const data = JSON.parse(e.data);
    setStatus(`RENDERING SHOT ${{data.label}} (${{data.index + 1}}/6)`, '');
    if (svgRoot) {{
      // Insert the shot's <g> just before the footer/end
      const wrapper = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      wrapper.innerHTML = data.svg;
      // Move all children of wrapper into svgRoot
      while (wrapper.firstChild) {{
        svgRoot.appendChild(wrapper.firstChild);
      }}
    }}
  }});

  es.addEventListener('critique_start', (e) => {{
    setStatus('KIMI K2.5 CRITIQUING…', '');
  }});

  es.addEventListener('revision', (e) => {{
    const r = JSON.parse(e.data);
    critiquePanel.classList.add('visible');
    const li = document.createElement('li');
    li.innerHTML = `<span class="label">${{r.shot_label}}</span>` +
                   `<span class="field">${{r.field}}</span>` +
                   `<span class="arrow">→</span>` +
                   `<span class="value">${{r.new_value}}</span>` +
                   `<p class="reason">${{r.reason}}</p>`;
    revisionsEl.appendChild(li);

    // Pulse the flagged frame
    if (svgRoot) {{
      const target = svgRoot.querySelector(`g[data-shot-label='${{r.shot_label}}']`);
      if (target) {{
        target.classList.add('kimi-flag');
        setTimeout(() => target.classList.remove('kimi-flag'), 3000);
      }}
    }}
  }});

  es.addEventListener('done', (e) => {{
    setStatus('DONE — REVIEW & APPROVE', 'done');
    es.close();
  }});

  es.onerror = () => {{
    setStatus('CONNECTION LOST', 'idle');
  }};
</script>
</body>
</html>
"""


__all__ = ["start_server", "push_event", "signal_done", "build_streaming_viewer_html"]
