"""Stabilisation (CapCut breadth).

Camera shake is a property of a clip over time, not of a single frame, so it
cannot be an ordinary effect: a frame on its own does not know which way the
camera was drifting. The shape here is the one the matte cache already uses.
A pass measures the movement between consecutive frames once and stores it;
the renderer then reads a correction per frame and applies it, running no
analysis at render time at all.

The measurement is feature tracking between neighbouring frames, which gives a
translation and a rotation. Those are accumulated into a camera path, the path
is smoothed, and the correction for a frame is the difference between where the
camera was and where a steady version of it would have been. A crop hides the
edges the correction exposes.
"""
from __future__ import annotations

import json
import math
import subprocess
import threading

import cv2
import numpy as np

from .paths import DATA_DIR

MOTION_DIR = DATA_DIR / "motion"
FORMAT_VERSION = 1
ANALYSIS_WIDTH = 480
_lock = threading.RLock()
_running: dict[str, float] = {}


def motion_path(media_id: str):
    return MOTION_DIR / f"{media_id}.json"


def status(media_id: str) -> dict:
    with _lock:
        if media_id in _running:
            return {"state": "analysing", "progress": _running[media_id]}
    path = motion_path(media_id)
    if not path.is_file():
        return {"state": "missing"}
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {"state": "stale"}
    if record.get("version") != FORMAT_VERSION:
        return {"state": "stale"}
    return {"state": "ready", "frames": len(record.get("path", [])), "fps": record.get("fps")}


def _frames(source, fps: float):
    """Decoded frames at the analysis size, as greyscale.

    The height is computed here and given to ffmpeg rather than left to `-2`.
    Letting each side round on its own is how this went wrong the first time:
    the two disagreed by two pixels, every frame was reshaped off by a row, and
    the motion measured from it was close to noise.
    """
    size = cv2.VideoCapture(str(source))
    width = int(size.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(size.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    size.release()
    if not width or not height:
        return
    out_w = ANALYSIS_WIDTH
    out_h = max(2, int(round(height * ANALYSIS_WIDTH / width / 2) * 2))
    probe = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(source), "-map", "0:v:0", "-an",
         "-vf", f"fps={fps},scale={out_w}:{out_h}", "-pix_fmt", "gray",
         "-f", "rawvideo", "pipe:1"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    frame_bytes = out_w * out_h
    try:
        while True:
            raw = probe.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break
            yield np.frombuffer(raw, np.uint8).reshape(out_h, out_w)
    finally:
        probe.kill()


def measure(media_id: str, source, fps: float, report=lambda p: None, cancelled=lambda: False) -> dict:
    """Walk the clip once and record how the camera moved."""
    MOTION_DIR.mkdir(parents=True, exist_ok=True)
    previous = None
    previous_points = None
    steps: list[list[float]] = []
    for index, frame in enumerate(_frames(source, fps)):
        if cancelled():
            raise InterruptedError("Cancelled")
        if previous is None:
            previous = frame
            previous_points = cv2.goodFeaturesToTrack(frame, 220, 0.01, 24)
            continue
        dx = dy = da = 0.0
        if previous_points is not None and len(previous_points):
            moved, ok, _ = cv2.calcOpticalFlowPyrLK(previous, frame, previous_points, None)
            if moved is not None and ok is not None:
                good_old = previous_points[ok.flatten() == 1]
                good_new = moved[ok.flatten() == 1]
                if len(good_old) >= 8:
                    matrix, _ = cv2.estimateAffinePartial2D(good_old, good_new)
                    if matrix is not None:
                        dx, dy = float(matrix[0, 2]), float(matrix[1, 2])
                        da = float(math.atan2(matrix[1, 0], matrix[0, 0]))
        steps.append([dx, dy, da])
        previous = frame
        previous_points = cv2.goodFeaturesToTrack(frame, 220, 0.01, 24)
        if index % 15 == 0:
            report(min(0.95, index / 900))
            with _lock:
                if media_id in _running:
                    _running[media_id] = min(0.95, index / 900)
    record = {"version": FORMAT_VERSION, "fps": fps, "width": ANALYSIS_WIDTH, "path": steps}
    motion_path(media_id).write_text(json.dumps(record), encoding="utf-8")
    report(1.0)
    return record


def analyse(media_id: str, source, fps: float) -> dict:
    with _lock:
        if media_id in _running:
            return {"state": "analysing", "progress": _running[media_id]}
        _running[media_id] = 0.0

    def run() -> None:
        try:
            measure(media_id, source, fps)
        except Exception:
            motion_path(media_id).unlink(missing_ok=True)
        finally:
            with _lock:
                _running.pop(media_id, None)

    threading.Thread(target=run, name=f"motion-{media_id[:8]}", daemon=True).start()
    return {"state": "analysing", "progress": 0.0}


def _smooth(values: np.ndarray, window: int) -> np.ndarray:
    if window < 2 or len(values) < 2:
        return values
    pad = window // 2
    padded = np.pad(values, (pad, pad), mode="edge")
    kernel = np.ones(window) / window
    return np.convolve(padded, kernel, mode="valid")[: len(values)]


def correction(media_id: str, frame_index: int, smoothing: float = 0.6) -> tuple[float, float, float] | None:
    """How far to move a frame back toward a steady camera."""
    path = motion_path(media_id)
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    steps = np.array(record.get("path") or [], dtype=np.float64)
    if steps.ndim != 2 or len(steps) < 2:
        return None
    # The camera path is the running total of the steps; a steady camera is that
    # path smoothed. The correction is the gap between them.
    trajectory = np.cumsum(steps, axis=0)
    window = max(3, int(5 + 55 * max(0.0, min(1.0, smoothing))))
    steady = np.stack([_smooth(trajectory[:, c], window) for c in range(3)], axis=1)
    gap = steady - trajectory
    index = max(0, min(len(gap) - 1, frame_index))
    scale = 1.0
    return float(gap[index][0]) * scale, float(gap[index][1]) * scale, float(gap[index][2])


def apply(image: np.ndarray, media_id: str, frame_index: int, params: dict) -> np.ndarray:
    """Move a frame by its correction, then crop the exposed edges away."""
    found = correction(media_id, frame_index, float(params.get("smoothing", 0.6)))
    if found is None:
        return image
    dx, dy, da = found
    h, w = image.shape[:2]
    # The path was measured at the analysis width, so the correction scales with
    # however large the frame being rendered is.
    factor = w / float(ANALYSIS_WIDTH)
    dx *= factor
    dy *= factor
    zoom = 1.0 + max(0.0, min(0.3, float(params.get("crop", 0.06))))
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), math.degrees(da), zoom)
    matrix[0, 2] += dx
    matrix[1, 2] += dy
    return cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
