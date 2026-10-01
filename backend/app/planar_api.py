"""The planar tracker's API (P1 of DEV_PLAN_planar_tracking.md).

A layer: its shapes (polygons in the frame's unit square, each adding to or cutting from the tracked area), the frame
they are drawn on (its reference, in source seconds) and its track settings (planar.Settings, as Mocha names them).
POST /api/planar/track tracks it over a media file as a job, forwards or backwards from any frame it already has a
track for (its reference first), as far as asked: a frame at a time is a track of one. Layers in front exclude what
they cover on each frame, carried by their own tracks (or where they are drawn, untracked). Each frame's homography
from the layer's reference, and its confidence, are kept in the layer's store as they come, so a stopped job keeps
what it did and the next one can carry on from there; GET reads them back (with a surface's corners per frame, when
asked), DELETE clears all or a range. A layer whose shapes or settings change starts a fresh track.

Frames are read at full size from the media by ffmpeg, a range at a time (backwards in chunks read forwards).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import threading
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import jobs
from .durable import read_json, write_json
from .paths import DATA_DIR
from .planar import Settings, corners_of

router = APIRouter(prefix="/api/planar", tags=["track"])
STORE = DATA_DIR / "planar-tracks"
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_locks: dict[str, threading.Lock] = {}


class Shape(BaseModel):
    points: list[list[float]] = Field(min_length=3, max_length=4000)  # x, y in the frame's unit square
    mode: str = "add"  # "add" or "subtract"


class Layer(BaseModel):
    id: str
    shapes: list[Shape] = Field(min_length=1, max_length=64)
    reference: float = Field(ge=0)  # source seconds: the frame the shapes are drawn on
    settings: dict = Field(default_factory=dict)


class TrackBody(BaseModel):
    media_id: str
    layer: Layer
    start: float = Field(ge=0)  # source seconds: a frame the layer has a track for (its reference first)
    stop: float = Field(ge=0)  # source seconds: as far as to track, before start to track backwards
    above: list[Layer] = Field(default_factory=list, max_length=32)  # layers in front, excluding what they cover


def _settings(raw: dict) -> Settings:
    allowed = set(Settings.__dataclass_fields__)
    unknown = set(raw) - allowed
    if unknown:
        raise HTTPException(400, f"unknown track settings: {', '.join(sorted(unknown))}")
    settings = Settings(**raw)
    if settings.motion not in ("large", "small", "manual") or settings.channel not in ("luminance", "auto"):
        raise HTTPException(400, "motion is large, small or manual; channel is luminance or auto")
    return settings


def _signature(layer: Layer, media_id: str) -> str:
    """What a track depends on: the media, the shapes, the reference frame and the settings."""
    raw = json.dumps([media_id, [s.model_dump() for s in layer.shapes], round(layer.reference, 6), layer.settings], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _path(layer_id: str) -> Path:
    if not _ID.match(layer_id):
        raise HTTPException(400, "a layer id is letters, digits, - and _")
    return STORE / f"{layer_id}.json"


def _load(layer_id: str) -> dict:
    data = read_json(_path(layer_id), None)
    return data if isinstance(data, dict) else {}


def _video(media_id: str) -> tuple[Path, float, int, int, int]:
    """The media's file, frame rate, size and frame count."""
    from .media import _ffprobe, media_path

    path = media_path(media_id)
    if path is None or not Path(path).is_file():
        raise HTTPException(404, "that media is not in the library, or its file is missing")
    probe = _ffprobe(Path(path))
    stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
    if stream is None:
        raise HTTPException(400, "that media has no video")
    top, _, bottom = str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "30/1").partition("/")
    fps = float(top) / float(bottom or 1) if float(bottom or 1) else 30.0
    if not fps or fps != fps:
        fps = 30.0
    duration = float(probe.get("format", {}).get("duration") or stream.get("duration") or 0)
    count = int(stream.get("nb_frames") or 0) or max(1, round(duration * fps))
    return Path(path), fps, int(stream["width"]), int(stream["height"]), count


def _read(path: Path, fps: float, width: int, height: int, first: int, count: int):
    """count frames from frame first, at full size, BGR."""
    from .tools import ffmpeg

    start = max(0.0, (first - 0.5) / fps)  # half a frame early: the first frame out is the one at or after it
    command = [
        ffmpeg(),
        "-v",
        "error",
        "-ss",
        f"{start:.6f}",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-an",
        "-frames:v",
        str(count),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-",
    ]
    size = width * height * 3
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        for _ in range(count):
            raw = process.stdout.read(size)
            if len(raw) < size:
                break
            yield np.frombuffer(raw, np.uint8).reshape(height, width, 3)
        process.stdout.close()
        process.kill()


def _frames(path: Path, fps: float, width: int, height: int, start: int, stop: int):
    """(index, frame) from start to stop inclusive, either way; backwards a chunk at a time, each read forwards."""
    if stop >= start:
        for offset, frame in enumerate(_read(path, fps, width, height, start, stop - start + 1)):
            yield start + offset, frame
        return
    chunk = 48
    upper = start
    while upper >= stop:
        lower = max(stop, upper - chunk + 1)
        block = list(_read(path, fps, width, height, lower, upper - lower + 1))
        for offset in range(len(block) - 1, -1, -1):
            yield lower + offset, block[offset]
        upper = lower - 1


def _raster(layer: Layer, size: tuple[int, int], h: np.ndarray | None = None) -> np.ndarray:
    """The layer's matte on a frame: its shapes (drawn on its reference) carried by h, add then subtract."""
    width, height = size
    matte = np.zeros((height, width), np.uint8)
    for wanted in ("add", "subtract"):
        for shape in layer.shapes:
            if (shape.mode == "subtract") != (wanted == "subtract"):
                continue
            pts = np.array(shape.points, float) * [width, height]
            if h is not None:
                pts = corners_of(h, pts)
            cv2.fillPoly(matte, [np.round(pts).astype(np.int32)], 0 if wanted == "subtract" else 255)
    return matte


def _matrix(values) -> np.ndarray:
    return np.array(values, float).reshape(3, 3)


def _exclusion(above: list[Layer], media_id: str, size: tuple[int, int]):
    """A function of the frame: what the layers in front cover there, each carried by its own track where it has one
    (and where it is drawn where it has none), grown a few pixels."""
    tracks = []
    for layer in above:
        data = _load(layer.id)
        tracks.append((layer, data if data.get("signature") == _signature(layer, media_id) else {}))
    if not tracks:
        return None
    grow = np.ones((7, 7), np.uint8)

    def at(index: int) -> np.ndarray | None:
        out = None
        for layer, data in tracks:
            values = (data.get("frames") or {}).get(str(index))
            matte = _raster(layer, size, _matrix(values) if values else None)
            out = matte if out is None else cv2.bitwise_or(out, matte)
        return None if out is None else cv2.dilate(out, grow)

    return at


@router.post("/track", status_code=202)
def track_layer(body: TrackBody) -> dict:
    """A layer tracked over a media file as a job: forwards or backwards from start (a frame it has a track for) to
    stop. The job's progress counts frames; each frame is kept as it comes."""
    from .planar import PlanarTracker

    path_of = _path(body.layer.id)
    settings = _settings(body.layer.settings)
    for layer in body.above:
        _path(layer.id)
    source, fps, width, height, count = _video(body.media_id)
    reference = min(count - 1, round(body.layer.reference * fps))
    first, last = min(count - 1, round(body.start * fps)), min(count - 1, round(body.stop * fps))
    signature = _signature(body.layer, body.media_id)
    data = _load(body.layer.id)
    if data.get("signature") != signature:
        data = {
            "signature": signature,
            "media": body.media_id,
            "fps": fps,
            "size": [width, height],
            "reference": reference,
            "frames": {},
            "confidence": {},
        }
    data["frames"].setdefault(str(reference), np.eye(3).ravel().round(9).tolist())
    data["confidence"].setdefault(str(reference), 1.0)
    if str(first) not in data["frames"]:
        raise HTTPException(409, "track from the layer's reference frame, or from a frame it already has a track for")
    start_h = _matrix(data["frames"][str(first)])
    exclude_at = _exclusion(body.above, body.media_id, (width, height))
    lock = _locks.setdefault(body.layer.id, threading.Lock())

    def operation(job_id, report, cancelled):
        if not lock.acquire(blocking=False):
            raise RuntimeError("this layer is being tracked already")
        try:
            total = abs(last - first)
            frames = _frames(source, fps, width, height, first, last)
            _, frame = next(frames)
            matte = _raster(body.layer, (width, height), start_h)
            if (matte > 0).sum() < 64:
                raise ValueError("the layer's shapes cover almost nothing on the frame tracked from")
            tracker = PlanarTracker(frame, matte, settings)
            done = 0
            for index, frame in frames:
                if cancelled():
                    break
                h, confidence = tracker.step(frame, exclude_at(index) if exclude_at else None)
                full = h @ start_h  # reference to frame: the frame tracked from, then on from it
                full = full / full[2, 2]
                data["frames"][str(index)] = full.ravel().round(9).tolist()
                data["confidence"][str(index)] = round(confidence, 3)
                done += 1
                if done % 12 == 0:
                    write_json(path_of, data)
                report(
                    done / max(1, total),
                    f"Frame {index} of {count}, confidence {confidence:.2f}",
                    frame=index,
                    confidence=round(confidence, 3),
                )
            write_json(path_of, data)
            return {"layer": body.layer.id, "tracked": done, "from": first, "to": first + (done if last >= first else -done)}
        finally:
            lock.release()

    STORE.mkdir(parents=True, exist_ok=True)
    write_json(path_of, data)
    return jobs.submit("planar-track", operation)


@router.get("/track/{layer_id}")
def read_track(layer_id: str, surface: str = "") -> dict:
    """A layer's track: frame indices, homographies from its reference (row-major, nine numbers), confidences; with
    surface (eight numbers, its four corners in the reference frame's unit square), the corners on every frame."""
    data = _load(layer_id)
    if not data:
        raise HTTPException(404, "no track for that layer")
    order = sorted(data["frames"], key=int)
    out = {
        "layer": layer_id,
        "media": data["media"],
        "fps": data["fps"],
        "size": data["size"],
        "reference": data["reference"],
        "frames": [int(i) for i in order],
        "matrices": [data["frames"][i] for i in order],
        "confidence": [data["confidence"].get(i, 0.0) for i in order],
    }
    if surface:
        values = [float(v) for v in surface.split(",")]
        if len(values) != 8:
            raise HTTPException(400, "a surface is four corners: eight numbers")
        width, height = data["size"]
        corners = np.array(values, float).reshape(4, 2) * [width, height]
        out["corners"] = [(corners_of(_matrix(data["frames"][i]), corners) / [width, height]).round(6).tolist() for i in order]
    return out


@router.delete("/track/{layer_id}")
def clear_track(layer_id: str, start: int | None = None, stop: int | None = None) -> dict:
    """All of a layer's track, or the frames from start to stop (its reference kept)."""
    path = _path(layer_id)
    data = _load(layer_id)
    if not data:
        return {"cleared": 0}
    if start is None and stop is None:
        path.unlink(missing_ok=True)
        return {"cleared": len(data["frames"])}
    lo, hi = min(start or 0, stop if stop is not None else 10**9), max(start or 0, stop if stop is not None else 10**9)
    gone = [i for i in data["frames"] if lo <= int(i) <= hi and int(i) != data["reference"]]
    for i in gone:
        data["frames"].pop(i, None)
        data["confidence"].pop(i, None)
    write_json(path, data)
    return {"cleared": len(gone)}
