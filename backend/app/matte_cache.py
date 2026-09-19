"""Matte cache for background removal (BG3).

Inference during rendering is what makes removal slow and makes preview and
export disagree: every frame pays for a model run, and a frame cache keyed on
pixels can miss. Here a job computes mattes once, at ten samples per source
second (every frame for clips under ten seconds), stores them as 8-bit PNGs
keyed by media, source time and model, and the renderer only ever reads and
interpolates them. A clip whose mattes are not ready renders unmatted rather
than stalling the pipeline.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading

import cv2
import numpy as np

from .paths import DATA_DIR

MATTES = DATA_DIR / "mattes"
_lock = threading.RLock()


def matte_key(media_id: str, model: str, options: dict | None = None) -> str:
    """Identity of a matte set: the media, the model and the matte-shaping options.

    Stroke edits and threshold changes shape the matte, so they belong in the
    key; feather does not, because it is applied when the matte is read.
    """
    shaping = {
        "threshold": (options or {}).get("threshold", 0.5),
        "strokes": (options or {}).get("strokes", []),
    }
    digest = hashlib.sha1(json.dumps(shaping, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return f"{media_id}-{model}-{digest}"


def sample_times(duration: float, fps: float) -> list[float]:
    """Ten samples per source second, or every frame under ten seconds."""
    if duration <= 10:
        step = 1.0 / max(1.0, fps)
    else:
        step = 0.1
    count = max(1, int(math.ceil(duration / step)))
    return [round(index * step, 4) for index in range(count + 1)]


def _path(key: str, at: float):
    return MATTES / key / f"{round(at * 1000):09d}.png"


def store(key: str, at: float, alpha: np.ndarray) -> None:
    """Write one matte as an 8-bit PNG."""
    target = _path(key, at)
    target.parent.mkdir(parents=True, exist_ok=True)
    # The staging name keeps the .png suffix: OpenCV picks its writer from the
    # extension, so a .part suffix would leave it with no writer at all.
    staging = target.with_name(target.stem + ".part.png")
    cv2.imwrite(str(staging), np.clip(alpha * 255.0, 0, 255).astype(np.uint8))
    staging.replace(target)


def available(key: str) -> list[float]:
    """Source times with a stored matte, ascending."""
    folder = MATTES / key
    if not folder.is_dir():
        return []
    times = []
    for item in folder.glob("*.png"):
        if item.name.endswith(".part.png"):
            continue
        try:
            times.append(int(item.stem) / 1000.0)
        except ValueError:
            continue
    return sorted(times)


def progress(key: str, duration: float, fps: float) -> dict:
    """How much of a clip's matte set exists, for the clip's progress display."""
    wanted = len(sample_times(duration, fps))
    have = len(available(key))
    return {"key": key, "wanted": wanted, "have": have, "ready": have >= wanted, "fraction": min(1.0, have / max(1, wanted))}


def read(key: str, at: float, size: tuple[int, int] | None = None) -> np.ndarray | None:
    """The matte at a source time, interpolated between the two nearest samples."""
    with _lock:
        times = available(key)
    if not times:
        return None
    if at <= times[0]:
        lower = upper = times[0]
        blend = 0.0
    elif at >= times[-1]:
        lower = upper = times[-1]
        blend = 0.0
    else:
        index = max(0, min(len(times) - 2, int(np.searchsorted(times, at) - 1)))
        lower, upper = times[index], times[index + 1]
        blend = 0.0 if upper <= lower else (at - lower) / (upper - lower)
    first = cv2.imread(str(_path(key, lower)), cv2.IMREAD_GRAYSCALE)
    if first is None:
        return None
    alpha = first.astype(np.float32) / 255.0
    if blend > 0:
        second = cv2.imread(str(_path(key, upper)), cv2.IMREAD_GRAYSCALE)
        if second is not None:
            alpha = alpha * (1 - blend) + (second.astype(np.float32) / 255.0) * blend
    if size and (alpha.shape[1], alpha.shape[0]) != size:
        alpha = cv2.resize(alpha, size, interpolation=cv2.INTER_LINEAR)
    return alpha


def clear(key: str) -> int:
    """Drop a matte set; returns how many files went."""
    folder = MATTES / key
    if not folder.is_dir():
        return 0
    gone = 0
    for item in folder.glob("*.png"):
        item.unlink(missing_ok=True)
        gone += 1
    folder.rmdir()
    return gone
