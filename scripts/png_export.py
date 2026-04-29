"""SVG → PNG export, used to feed the multimodal critique pass.

Strategy:
1. Try the system's `rsvg-convert` (librsvg2-bin on Ubuntu, librsvg on
   macOS) — fastest, faithful, what CI uses.
2. Fall back to `cairosvg` if installed — pure-Python, slower, slight
   font differences.
3. Raise PNGExportError with a clear install hint if neither is found.

We intentionally do NOT try Inkscape headless because it spawns
slowly (~5s) which kills demo recording responsiveness.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class PNGExportError(RuntimeError):
    pass


def svg_to_png(svg_path: Path, png_path: Path, *, width: int = 1400) -> Path:
    """Render an SVG file to PNG. Returns the PNG path on success."""
    rsvg = shutil.which("rsvg-convert")
    if rsvg:
        cmd = [rsvg, "-w", str(width), "-o", str(png_path), str(svg_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            return png_path
        except subprocess.CalledProcessError as exc:
            raise PNGExportError(
                f"rsvg-convert failed: {exc.stderr.decode(errors='replace')}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise PNGExportError("rsvg-convert timed out after 30s") from exc

    # cairosvg fallback
    try:
        import cairosvg  # type: ignore[import-untyped]
    except ImportError:
        raise PNGExportError(
            "Neither rsvg-convert nor cairosvg is available. "
            "Install one of:\n"
            "  Ubuntu: sudo apt install librsvg2-bin\n"
            "  macOS:  brew install librsvg\n"
            "  Python: pip install cairosvg"
        ) from None

    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        output_width=width,
    )
    return png_path


def svg_string_to_png_bytes(svg: str, *, width: int = 1400) -> bytes:
    """Convenience: render an SVG string directly to PNG bytes via temp file."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as svg_f:
        svg_f.write(svg)
        svg_p = Path(svg_f.name)
    png_p = svg_p.with_suffix(".png")
    try:
        svg_to_png(svg_p, png_p, width=width)
        return png_p.read_bytes()
    finally:
        svg_p.unlink(missing_ok=True)
        png_p.unlink(missing_ok=True)


__all__ = ["svg_to_png", "svg_string_to_png_bytes", "PNGExportError"]
