"""Transparent export: the timeline with no background, alpha and all, for mockups laid over other designs.

formcut's compositor works on an opaque canvas (the blend writes full alpha), and stays that way: changing every path
it has (wgpu-py, the Rust executor, the CPU reference, deep and YUV) to carry alpha would put preview and export parity
at risk. Instead each frame is rendered twice, over black (the empty canvas) and over white (the project's background
set to white). The compositor mixes in linear light, so over black a pixel is a * F and over white a * F + (1 - a);
their difference gives the alpha, and the black render divided by it the colour. Exact for normal blending; a
non-normal blend mode over nothing has no transparent meaning and comes out as its result over black.
"""

import math
import subprocess
import zipfile
from pathlib import Path

import cv2
import numpy as np

from .renderer import FrameRenderer

FORMATS = {
    "mov": {
        "ext": "mov",
        "media_type": "video/quicktime",
        "codec": "prores",
        "encoder": "prores_ks",
        "pix": "yuva444p10le",
        "args": ["-profile:v", "4444", "-vendor", "apl0", "-alpha_bits", "16"],
    },
    "webm": {
        "ext": "webm",
        "media_type": "video/webm",
        "codec": "vp9",
        "encoder": "libvpx-vp9",
        "pix": "yuva420p",
        "args": ["-b:v", "0", "-crf", "28", "-row-mt", "1", "-cpu-used", "5", "-auto-alt-ref", "0"],
    },
    "png": {"ext": "zip", "media_type": "application/zip", "codec": "png", "encoder": "png", "pix": "rgba"},
}
_DECODE = np.array([(i / 255) / 12.92 if i / 255 <= 0.04045 else ((i / 255 + 0.055) / 1.055) ** 2.4 for i in range(256)], np.float32)


def _bytes(frame) -> np.ndarray:
    picture = np.asarray(frame)
    if picture.dtype == np.uint16:
        picture = (picture >> 8).astype(np.uint8)
    return picture


def unmatte(black: np.ndarray, white: np.ndarray) -> np.ndarray:
    """A straight-alpha RGBA picture from the same frame over black and over white (sRGB bytes)."""
    b = _DECODE[_bytes(black)[:, :, :3]]
    w = _DECODE[_bytes(white)[:, :, :3]]
    alpha = np.clip(1.0 - (w - b).mean(axis=2), 0.0, 1.0)
    colour = np.clip(b / np.maximum(alpha, 1.0 / 255)[:, :, None], 0.0, 1.0)
    encoded = np.where(colour <= 0.0031308, colour * 12.92, 1.055 * np.power(colour, 1 / 2.4) - 0.055)
    out = np.empty((*alpha.shape, 4), np.uint8)
    out[:, :, :3] = np.where(alpha[:, :, None] > 0, np.round(encoded * 255), 0).astype(np.uint8)
    out[:, :, 3] = np.round(alpha * 255).astype(np.uint8)
    return out


def export_transparent(project: dict, job_id: str, report, cancelled, fmt: str, fps: float, outputs: Path) -> dict:
    """Renders the project with no background into a format that carries alpha; returns the job's result."""
    spec = FORMATS.get(fmt)
    if spec is None:
        raise ValueError("A transparent export is mov (ProRes 4444), webm (VP9 with alpha) or png (a zip of frames)")
    over_black = FrameRenderer({**project, "background": None})
    over_white = FrameRenderer({**project, "background": "#ffffff"})
    process = None
    final = outputs / f"{job_id}.{spec['ext']}"
    try:
        if over_black.deep:
            raise ValueError("A transparent export is SDR; this project's timeline is HDR")
        width, height = over_black.width, over_black.height
        count = max(1, math.ceil(float(project["duration"]) * fps))
        outputs.mkdir(parents=True, exist_ok=True)
        archive = zipfile.ZipFile(final, "w", zipfile.ZIP_STORED) if fmt == "png" else None
        if archive is None:
            command = [
                "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}",
                "-r", f"{fps:.6g}", "-i", "-", "-c:v", spec["encoder"], *spec["args"], "-pix_fmt", spec["pix"], str(final),
            ]  # fmt: skip
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        report(0.02)
        for index in range(count):
            if cancelled():
                raise RuntimeError("Export cancelled")
            at = index / fps
            picture = unmatte(over_black.frame(at), over_white.frame(at))
            if archive is not None:
                ok, png = cv2.imencode(".png", cv2.cvtColor(picture, cv2.COLOR_RGBA2BGRA))
                if not ok:
                    raise RuntimeError("A frame could not be written as PNG")
                archive.writestr(f"frame_{index:06d}.png", png.tobytes())
            else:
                process.stdin.write(picture.tobytes())
            report(0.02 + 0.96 * (index + 1) / count)
        if archive is not None:
            archive.close()
        else:
            process.stdin.close()
            if process.wait() != 0:
                raise RuntimeError(f"The {spec['encoder']} encoder failed: {process.stderr.read().decode(errors='replace')[-400:]}")
        report(1.0)
        return {
            "file": str(final),
            "media_type": spec["media_type"],
            "codec": spec["codec"],
            "encoder": spec["encoder"],
            "pixelFormat": spec["pix"],
            "width": width,
            "height": height,
            "fps": fps,
            "frames": count,
            "transparent": True,
        }
    except BaseException:
        if process and process.poll() is None:
            process.kill()
            process.wait()
        final.unlink(missing_ok=True)
        raise
    finally:
        over_black.close()
        over_white.close()
