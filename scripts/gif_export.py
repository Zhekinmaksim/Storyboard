"""Animated GIF export for storyboards.

Strategy: render the scene N times, each with a progressively larger
prefix of shots visible. Frame N has shots 1..N rendered, frames before
that show only the header and earlier shots. This produces a "board
fills in" animation when played as a GIF — the same wow as live-drawing
in a browser, but as a portable, shareable file.

Pipeline:
  1. For each step k in 1..6: build a Scene clone with shots[:k],
     render to PNG via librsvg.
  2. Stack PNGs via ImageMagick convert into an animated GIF.

Falls back gracefully: if imagemagick or rsvg fail, raises GifExportError
and the API surface returns a clean error to the user.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from scripts.scene import Scene
from scripts.render import render_scene


class GifExportError(RuntimeError):
    pass


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def export_gif(
    scene: Scene,
    out_path: Path,
    *,
    width: int = 900,
    delay_cs: int = 70,   # 0.7s per progressive frame
    final_hold_cs: int = 240,  # 2.4s hold on the complete board
) -> Path:
    """Build an animated GIF showing the board fill in stroke-by-stroke.

    Returns out_path on success. Raises GifExportError on any failure.
    """
    if not _have("convert"):
        raise GifExportError("ImageMagick `convert` not installed.")

    use_rsvg = _have("rsvg-convert")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = len(scene.shots)
    if n == 0:
        raise GifExportError("Scene has no shots.")
    n = min(n, 6)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        png_paths: list[Path] = []

        for k in range(1, n + 1):
            partial = Scene(
                title=scene.title,
                scene_number=scene.scene_number,
                location=scene.location,
                director=scene.director,
                shots=scene.shots[:k],
                notes=getattr(scene, "notes", ""),
            )
            svg_path = td_path / f"step-{k:02d}.svg"
            png_path = td_path / f"step-{k:02d}.png"
            svg_path.write_text(render_scene(partial), encoding="utf-8")

            if use_rsvg:
                res = subprocess.run(
                    ["rsvg-convert", "-w", str(width), "-o", str(png_path), str(svg_path)],
                    check=False, capture_output=True,
                )
            else:
                # ImageMagick can rasterise SVG directly via MagickCore
                res = subprocess.run(
                    ["convert", "-density", "150", "-background", "#f5f0e6",
                     str(svg_path), "-resize", f"{width}x", str(png_path)],
                    check=False, capture_output=True,
                )
            if res.returncode != 0:
                raise GifExportError(
                    f"raster step {k}: {res.stderr.decode('utf-8', 'ignore')[:200]}"
                )
            png_paths.append(png_path)

        # Build the GIF: per-frame delay for progressives, longer hold on last
        cmd: list[str] = ["convert", "-loop", "0"]
        for i, p in enumerate(png_paths):
            d = final_hold_cs if i == len(png_paths) - 1 else delay_cs
            cmd += ["-delay", str(d), str(p)]
        cmd += [
            "-layers", "OptimizePlus",
            "-colors", "32",
            str(out_path),
        ]
        res = subprocess.run(cmd, check=False, capture_output=True)
        if res.returncode != 0:
            raise GifExportError(
                f"convert failed: {res.stderr.decode('utf-8', 'ignore')[:200]}"
            )

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise GifExportError("GIF was not produced.")
    return out_path
