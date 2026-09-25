"""Real-ESRGAN x4 upscaling, run on this machine with ONNX Runtime.

The model (Real-ESRGAN x4plus, BSD-3-Clause) takes RGB in 0 to 1 at any size and
returns it four times larger. A whole frame at once would need memory in
proportion to its area, so it runs in tiles: each tile is read with a margin of
context around it, and only the tile's own part of the result is kept, so the
seams fall inside context the model saw on both sides. Alpha, which the model
does not carry, is scaled with Lanczos. A factor below four is the x4 result
scaled down with Lanczos, which keeps the recovered detail.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np
from PIL import Image

from . import encoders
from .model_manager import ROOT as MODELS_ROOT

MODEL = "ai-upscale"
FILE = "realesrgan-x4plus.onnx"
SCALE = 4
TILE = 256  # source pixels per tile side
MARGIN = 16  # context read around each tile and discarded from its result

_session = None
_lock = threading.Lock()


def _run_model(batch: np.ndarray) -> np.ndarray:
    global _session
    with _lock:
        if _session is None:
            import onnxruntime as ort

            from .model_manager import providers

            _session = ort.InferenceSession(str(MODELS_ROOT / FILE), providers=providers())
        return _session.run(None, {"input": batch})[0]


def upscale_rgb(
    rgb: np.ndarray,
    run: Callable[[np.ndarray], np.ndarray] = _run_model,
    tile: int = TILE,
    margin: int = MARGIN,
    cancelled: Callable[[], bool] = lambda: False,
) -> np.ndarray:
    """An H x W x 3 uint8 picture, four times larger, built tile by tile."""
    height, width = rgb.shape[:2]
    out = np.zeros((height * SCALE, width * SCALE, 3), np.uint8)
    source = rgb.astype(np.float32) / 255.0
    for top in range(0, height, tile):
        for left in range(0, width, tile):
            if cancelled():
                raise InterruptedError("Cancelled")
            bottom, right = min(height, top + tile), min(width, left + tile)
            y0, x0 = max(0, top - margin), max(0, left - margin)
            y1, x1 = min(height, bottom + margin), min(width, right + margin)
            batch = source[y0:y1, x0:x1].transpose(2, 0, 1)[None]
            result = run(np.ascontiguousarray(batch))[0].transpose(1, 2, 0)
            keep = result[(top - y0) * SCALE : (bottom - y0) * SCALE, (left - x0) * SCALE : (right - x0) * SCALE]
            out[top * SCALE : bottom * SCALE, left * SCALE : right * SCALE] = (np.clip(keep, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    return out


def upscale_image(image: Image.Image, factor: float, run: Callable[[np.ndarray], np.ndarray] = _run_model) -> Image.Image:
    rgb = Image.fromarray(upscale_rgb(np.asarray(image.convert("RGB")), run))
    target = (max(1, round(image.width * factor)), max(1, round(image.height * factor)))
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        alpha = image.convert("RGBA").getchannel("A").resize(rgb.size, Image.Resampling.LANCZOS)
        rgb = Image.merge("RGBA", (*rgb.split(), alpha))
    return rgb if rgb.size == target else rgb.resize(target, Image.Resampling.LANCZOS)


def upscale_video(source: Path, out: Path, width: int, height: int, fps: float, factor: float, frames: int, report, cancelled) -> None:
    """Decode, upscale each frame, and encode with the source's sound."""
    program = shutil.which("ffmpeg") or "ffmpeg"
    target_w, target_h = int(width * factor) // 2 * 2, int(height * factor) // 2 * 2
    decode = [program, "-v", "error", "-nostdin", "-i", str(source), "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    encoder = _encoder_name()
    device, upload = encoders.hardware_io(encoder)
    chain = f"scale={target_w}:{target_h}:flags=lanczos" + (f",{upload}" if upload else "")
    encode = [program, "-v", "error", "-nostdin", "-y", *device, "-f", "rawvideo", "-pix_fmt", "rgb24"]
    encode += ["-s", f"{width * SCALE}x{height * SCALE}", "-r", f"{fps:.6f}", "-i", "-", "-i", str(source)]
    encode += ["-map", "0:v:0", "-map", "1:a?", "-vf", chain, "-c:v", encoder, *encoders.tier_flags(encoder, "high")]
    encode += ([] if upload else ["-pix_fmt", "yuv420p"]) + [
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out),
    ]
    size = width * height * 3
    with (
        subprocess.Popen(decode, stdout=subprocess.PIPE) as reader,
        subprocess.Popen(encode, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as writer,
    ):
        done = 0
        try:
            while True:
                raw = reader.stdout.read(size)
                if len(raw) < size:
                    break
                frame = np.frombuffer(raw, np.uint8).reshape(height, width, 3)
                writer.stdin.write(upscale_rgb(frame, cancelled=cancelled).tobytes())
                done += 1
                report(min(0.99, done / max(1, frames)))
        except BaseException:
            reader.kill()
            writer.kill()
            raise
        writer.stdin.close()
        errors = writer.stderr.read().decode(errors="replace")
    if writer.returncode:
        raise RuntimeError(f"ffmpeg could not write the upscaled clip: {errors.strip()[-400:]}")


def _encoder_name() -> str:
    from .upscale import _encoder

    return _encoder()
