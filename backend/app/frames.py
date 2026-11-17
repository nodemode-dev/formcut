"""Frames of a media file for the engine's own analysis and the source monitor, read by the timeline's decoder.

The OpenCV in the frozen Windows engine is built without videoio, so cv2.VideoCapture does not exist there, and every
route that read a video through it answered 500 (the Pro tab's source monitor for every clip). These read through
video_source: PyAV in the engine, or the ffmpeg pipe, the decoder the timeline already uses, so a file the timeline
shows is a file these read. Frames are eight-bit BGR, upright, as VideoCapture gave them.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np


def _source(path):
    from .video_source import _open

    return _open(str(path))


def size(path: Path | str) -> tuple[int, int]:
    """(width, height) as the frames come out (turned by the file's rotation); (0, 0) when it has no video."""
    from .video_source import VideoSource

    try:
        source = VideoSource(str(path))
    except (ValueError, OSError):
        return 0, 0
    return source.width, source.height


def count(path: Path | str) -> int:
    """The frames the file holds at its average rate (0 when it has no video)."""
    from .video_source import VideoSource

    try:
        return int(VideoSource(str(path)).frame_count)
    except (ValueError, OSError):
        return 0


def at(path: Path | str, seconds: float) -> np.ndarray | None:
    """The frame showing at `seconds`, or None when there is none."""
    try:
        source = _source(path)
    except (ValueError, OSError):
        return None
    try:
        source.seek(max(0, int(max(0.0, float(seconds)) * source.fps + 1e-7)))
        ok, frame = source.read()
        return np.ascontiguousarray(frame) if ok and frame is not None else None
    finally:
        source.release()


def each(path: Path | str, limit: int | None = None) -> Iterator[np.ndarray]:
    """Every frame from the first, in order (at most `limit`)."""
    try:
        source = _source(path)
    except (ValueError, OSError):
        return
    try:
        source.seek(0)
        read = 0
        while limit is None or read < limit:
            ok, frame = source.read()
            if not ok or frame is None:
                break
            read += 1
            yield np.ascontiguousarray(frame)
    finally:
        source.release()
