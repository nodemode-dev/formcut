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
import math
import re
import subprocess
import threading
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
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
            done, faint, lost = 0, 0, None
            report(0.0, f"Tracking from frame {first}")
            for index, frame in frames:
                if cancelled():
                    break
                h, confidence = tracker.step(frame, exclude_at(index) if exclude_at else None)
                # a plane lost: twelve frames running with almost no confidence end the track there, what came
                # before it kept (Mocha drifts on; stopping says where it went wrong)
                faint = faint + 1 if confidence < 0.05 and settings.motion != "manual" else 0
                if faint >= 12:
                    way = 1 if last >= first else -1
                    lost = index - 11 * way  # the first of the twelve, in the order tracked
                    for drop in range(min(lost, index), max(lost, index) + 1):
                        data["frames"].pop(str(drop), None)
                        data["confidence"].pop(str(drop), None)
                    done -= 11
                    break
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
            out = {"layer": body.layer.id, "tracked": done, "from": first, "to": first + (done if last >= first else -done)}
            return {**out, "lost": lost} if lost is not None else out
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


@router.get("/media/{media_id}")
def media_frames(media_id: str) -> dict:
    """What the Track workspace needs of a media file: its frame rate, size and frame count."""
    _, fps, width, height, count = _video(media_id)
    return {"fps": fps, "width": width, "height": height, "frames": count}


@router.get("/frame/{media_id}")
def media_frame(media_id: str, index: int = 0, width: int = 0) -> Response:
    """One frame of a media file as a JPEG, at its own size or scaled down to width (the workspace's viewer)."""
    source, fps, full_w, full_h, count = _video(media_id)
    frame = next(_read(source, fps, full_w, full_h, max(0, min(count - 1, index)), 1), None)
    if frame is None:
        raise HTTPException(404, "that frame could not be read")
    if 0 < width < full_w:
        frame = cv2.resize(frame, (width, max(2, round(full_h * width / full_w))), interpolation=cv2.INTER_AREA)
    ok, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise HTTPException(500, "the frame could not be encoded")
    return Response(data.tobytes(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


class ApplyBody(BaseModel):
    project: dict
    tracked_clip: str  # the clip whose media the layer was tracked on
    layer_id: str
    target_clip: str  # the clip the result goes on
    kind: str = "corner-pin"  # "corner-pin" or "transform"


def _surface_on_canvas(project: dict, tracked: dict, layer: dict, data: dict) -> list[tuple[float, list[list[float]]]]:
    """The layer's surface on the canvas at every tracked frame inside the tracked clip: (timeline seconds, four
    corners in canvas pixels), through the tracked clip's own placement (fit, scale, position, turn, flips) and crop,
    the same placement the renderer gives it."""
    from types import SimpleNamespace

    from .renderer import FrameRenderer, crop_box, transform_at
    from .timing import timeline_time

    width, height = data["size"]
    fps = float(data["fps"])
    left, top, right, bottom = crop_box(tracked) or (0.0, 0.0, 0.0, 0.0)
    image = SimpleNamespace(shape=(round(height * (1 - top - bottom)), round(width * (1 - left - right))))
    canvas = SimpleNamespace(width=int(project["width"]), height=int(project["height"]))
    surface = np.array(layer["surface"], float) * [width, height]
    start, duration = float(tracked["start"]), float(tracked["duration"])
    source_in = float(tracked.get("sourceIn") or 0)
    out = []
    for index in sorted(data["frames"], key=int):
        seconds = int(index) / fps
        if seconds < source_in - 1e-6:
            continue
        local = timeline_time(tracked, seconds)
        if local < 0 or local > duration:
            continue
        corners = corners_of(_matrix(data["frames"][index]), surface) - [left * width, top * height]
        place = FrameRenderer._matrix(canvas, image, transform_at(tracked, local))
        on_canvas = corners @ np.asarray(place, float)[:, :2].T + np.asarray(place, float)[:, 2]
        out.append((start + local, on_canvas.tolist()))
    return out


@router.post("/apply")
def apply_track(body: ApplyBody) -> dict:
    """A layer's track put to use on a clip, as Mocha AE's exports are (P3): "corner-pin", the surface's four corners
    on the canvas at every tracked frame, timed for the target clip (its image's corners go onto them); or
    "transform", position, scale and rotation keyframes on the target clip, from the surface's centre, size and the
    turn of its top edge against the layer's reference frame. The result is returned for the page to put on the clip
    (one project command, with undo)."""
    from .render_document import flatten, validate_document
    from .renderer import DEFAULTS

    if body.kind not in ("corner-pin", "transform"):
        raise HTTPException(400, "kind is corner-pin or transform")
    try:
        project = validate_document(body.project)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    clips = {c["id"]: c for c in flatten(project)}
    tracked, target = clips.get(body.tracked_clip), clips.get(body.target_clip)
    if tracked is None or target is None:
        raise HTTPException(404, "the tracked clip or the target clip is not on the active timeline")
    layer = next((one for one in (tracked.get("planar") or {}).get("layers", []) if one.get("id") == body.layer_id), None)
    if layer is None or not layer.get("surface"):
        raise HTTPException(400, "that layer has no surface on the tracked clip: place its surface in the Track workspace")
    data = _load(body.layer_id)
    if not data or data.get("media") != tracked.get("mediaId"):
        raise HTTPException(409, "that layer has no track on this clip's media yet")
    samples = _surface_on_canvas(project, tracked, layer, data)
    width, height = int(project["width"]), int(project["height"])
    timed = [(t - float(target["start"]), c) for t, c in samples if -1e-6 <= t - float(target["start"]) <= float(target["duration"]) + 1e-6]
    if not timed:
        raise HTTPException(409, "no tracked frame falls inside the target clip's time on the timeline")
    if body.kind == "corner-pin":
        return {
            "cornerPin": {
                "times": [round(t, 6) for t, _ in timed],
                "points": [[round(v, 6) for x, y in c for v in (x / width, y / height)] for _, c in timed],
            },
            "frames": len(timed),
        }
    # transform: against the layer's reference, carried through the tracked clip's own placement at its first sample
    base = {**DEFAULTS, **(target.get("transform") or {})}
    # the reference: the surface on the layer's reference frame where the tracked clip shows it, else the first sample
    at_reference = _surface_on_canvas(
        project, tracked, layer, {**data, "frames": {str(data["reference"]): data["frames"][str(data["reference"])]}}
    )
    reference = np.array(at_reference[0][1] if at_reference else timed[0][1], float)
    size = lambda c: (np.linalg.norm(c[1] - c[0]) + np.linalg.norm(c[3] - c[0])) / 2  # noqa: E731
    angle = lambda c: math.degrees(math.atan2(c[1][1] - c[0][1], c[1][0] - c[0][0]))  # noqa: E731
    ref_size, ref_angle = size(reference), angle(reference)
    keyframes = []
    for t, listed in timed:
        c = np.array(listed, float)
        centre = c.mean(axis=0)
        keyframes.append(
            {
                "t": round(t, 6),
                "interp": "linear",
                "props": {
                    "posX": round((centre[0] / width - 0.5) * 100, 4),
                    "posY": round((centre[1] / height - 0.5) * 100, 4),
                    "scale": round(float(base["scale"]) * size(c) / max(1e-9, ref_size), 4),
                    "rotation": round(float(base["rotation"]) + angle(c) - ref_angle, 4),
                },
            }
        )
    return {"keyframes": keyframes, "frames": len(keyframes)}
