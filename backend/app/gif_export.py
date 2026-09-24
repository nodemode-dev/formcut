"""GIF export (comparison v2, phase 10).

A GIF is drawn from the same lossless intermediate every other special export
uses, so its frames are exactly the frames any codec would have received. The
encode is ffmpeg's two-pass palette: palettegen reads the whole picture and
builds one palette, paletteuse maps every frame through it with dithering,
which is what keeps a 256-colour file from banding. The quality tier decides
the palette size and the dither: fewer colours and an ordered dither make the
low tier markedly smaller.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

TIERS: dict[str, tuple[int, str]] = {
    "high": (256, "sierra2_4a"),
    "medium": (128, "sierra2_4a"),
    "low": (64, "bayer:bayer_scale=3"),
}


def encode(intermediate: Path, output: Path, quality: str, report, cancelled) -> None:
    """The intermediate's picture as a looping GIF at the tier's palette."""
    colors, dither = TIERS.get(quality, TIERS["high"])
    palette = output.with_suffix(".palette.png")
    try:
        first = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(intermediate),
                "-map",
                "0:v:0",
                "-vf",
                f"palettegen=max_colors={colors}",
                str(palette),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=1800,
        )
        if first.returncode != 0 or not palette.is_file():
            raise ValueError("Could not build the GIF palette: " + first.stderr[-300:])
        report(0.35)
        if cancelled():
            raise InterruptedError("Cancelled")
        second = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(intermediate),
                "-i",
                str(palette),
                "-lavfi",
                f"[0:v][1:v]paletteuse=dither={dither}",
                "-loop",
                "0",
                str(output),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=1800,
        )
        if second.returncode != 0 or not output.is_file():
            raise ValueError("Could not encode the GIF: " + second.stderr[-300:])
        report(1.0)
    finally:
        palette.unlink(missing_ok=True)
