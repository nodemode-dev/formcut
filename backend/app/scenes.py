"""Scene detection (B5).

"Long video to short clips" is really one question asked many times: where did
the picture change enough to be a different shot? The measure here is the
distance between consecutive frames' colour histograms, which ignores ordinary
movement within a shot and jumps at a cut.

The analysis runs on small greyscale-plus-colour frames at a few samples per
second, so a long clip is cheap to scan, and it reads the proxy when one exists
for the same reason stabilisation does.
"""

from __future__ import annotations

import itertools
import subprocess

import cv2
import numpy as np

SAMPLE_FPS = 6.0
ANALYSIS_WIDTH = 240


def _frames(source, fps: float = SAMPLE_FPS):
    size = cv2.VideoCapture(str(source))
    width = int(size.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(size.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    size.release()
    if not width or not height:
        return
    out_w = ANALYSIS_WIDTH
    # Both sides use this number; letting ffmpeg round its own is how the
    # stabilisation pass ended up reading every frame a row out.
    out_h = max(2, int(round(height * ANALYSIS_WIDTH / width / 2) * 2))
    process = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            f"fps={fps},scale={out_w}:{out_h}",
            "-pix_fmt",
            "bgr24",
            "-f",
            "rawvideo",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    frame_bytes = out_w * out_h * 3
    try:
        while True:
            raw = process.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break
            yield np.frombuffer(raw, np.uint8).reshape(out_h, out_w, 3)
    finally:
        process.kill()


def _histogram(frame: np.ndarray) -> np.ndarray:
    hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3)
    return cv2.normalize(hist, hist).flatten()


def scenes(source, sensitivity: float = 0.5, minimum: float = 1.0) -> dict:
    """Cut points in seconds, with the score that found each one.

    `sensitivity` moves the threshold between missing soft cuts and calling a
    camera move a cut; `minimum` is the shortest shot worth reporting, so a
    dissolve does not arrive as five cuts in a row.
    """
    sensitivity = max(0.0, min(1.0, float(sensitivity)))
    threshold = 0.65 - 0.4 * sensitivity
    scores: list[float] = []
    previous = None
    for frame in _frames(source):
        current = _histogram(frame)
        if previous is not None:
            # Correlation is 1 for identical frames, so distance is what a cut
            # pushes up; Bhattacharyya would do as well and is slower.
            scores.append(1.0 - float(cv2.compareHist(previous, current, cv2.HISTCMP_CORREL)))
        previous = current
    cuts: list[dict] = []
    last = -minimum
    for index, score in enumerate(scores):
        at = (index + 1) / SAMPLE_FPS
        if score >= threshold and at - last >= minimum:
            cuts.append({"at": round(at, 3), "score": round(score, 4)})
            last = at
    duration = (len(scores) + 1) / SAMPLE_FPS
    segments = []
    edges = [0.0] + [cut["at"] for cut in cuts] + [round(duration, 3)]
    for start, end in itertools.pairwise(edges):
        if end - start >= minimum:
            segments.append({"start": round(start, 3), "duration": round(end - start, 3)})
    return {
        "cuts": cuts,
        "segments": segments,
        "duration": round(duration, 3),
        "threshold": round(threshold, 3),
        "peak": round(max(scores), 4) if scores else 0.0,
    }
