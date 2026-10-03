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
from fastapi.responses import PlainTextResponse, Response
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
    kind: str = "polygon"  # or "xspline": each point's tension from a corner (0) to a smooth curve (1)
    tension: list[float] | None = None
    feather: list[float] | None = None  # each point's own feather, media pixels (the matte's)
    keys: dict[str, list[list[float]]] | None = None  # frame -> points (a roto layer's keyframes)
    handles: list[list[float]] | None = None  # a Bezier shape's in and out handles per point: ix, iy, ox, oy
    off: dict[str, list[int]] | None = None


class Layer(BaseModel):
    id: str
    shapes: list[Shape] = Field(min_length=1, max_length=64)
    reference: float = Field(ge=0)  # source seconds: the frame the shapes are drawn on
    settings: dict = Field(default_factory=dict)
    link: str | None = None  # Link to Track: the layer whose track carries these shapes (its own, without)


class TrackBody(BaseModel):
    media_id: str
    layer: Layer
    start: float = Field(ge=0)  # source seconds: a frame the layer has a track for (its reference first)
    stop: float = Field(ge=0)  # source seconds: as far as to track, before start to track backwards
    above: list[Layer] = Field(default_factory=list, max_length=32)  # layers in front, excluding what they cover


def _settings(raw: dict) -> Settings:
    raw = {k: v for k, v in raw.items() if k not in ("screen", "matte")}  # read by the job itself (track_layer)
    allowed = set(Settings.__dataclass_fields__)
    unknown = set(raw) - allowed
    if unknown:
        raise HTTPException(400, f"unknown track settings: {', '.join(sorted(unknown))}")
    settings = Settings(**raw)
    if settings.motion not in ("large", "small", "manual") or settings.channel not in ("luminance", "auto", "max"):
        raise HTTPException(400, "motion is large, small or manual; channel is luminance, auto or max")
    return settings


def _signature(layer: Layer, media_id: str) -> str:
    """What a track depends on: the media, the shapes, the reference frame and the settings."""
    # (a point's feather is the matte's, not the tracker's: softening an edge does not start a track afresh)
    shapes = [{k: v for k, v in s.model_dump().items() if k != "feather"} for s in layer.shapes]
    raw = json.dumps([media_id, shapes, round(layer.reference, 6), layer.settings], sort_keys=True)
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


def _raster(layer: Layer, size: tuple[int, int], h: np.ndarray | None = None, frame: int = 0) -> np.ndarray:
    """The layer's matte on a frame: its shapes as they are on that frame (keyframes, X-Splines; planar_shapes)
    carried by h, add then subtract, solid (the tracker's area takes no feather)."""
    from .planar_shapes import layer_matte

    width, height = size
    shapes = [{**s.model_dump(), "feather": None} for s in layer.shapes]
    carry = (lambda pts: corners_of(h, pts * [width, height])) if h is not None else (lambda pts: pts * [width, height])
    return (layer_matte(shapes, frame, carry, (width, height), lambda pts: pts) > 0.5).astype(np.uint8) * 255


def _matrix(values) -> np.ndarray:
    return np.array(values, float).reshape(3, 3)


def _matte_outside(frame: np.ndarray, spec: dict, size: tuple[int, int]) -> np.ndarray:
    """Where an imported matte keeps the tracker out: its dark half by brightness (its light half, inverted), 255."""
    if (frame.shape[1], frame.shape[0]) != size:
        frame = cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)
    inside = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) > 127
    if spec.get("invert"):
        inside = ~inside
    return np.where(inside, 0, 255).astype(np.uint8)


def _exclusion(above: list[Layer], media_id: str, size: tuple[int, int]):
    """A function of the frame: what the layers in front cover there, each carried by its own track where it has one
    (and where it is drawn where it has none), grown a few pixels."""
    tracks = []
    for layer in above:
        # a linked layer rides its carrier's track; its own must still match its shapes to be believed
        data = _load(layer.link or layer.id)
        tracks.append((layer, data if layer.link or data.get("signature") == _signature(layer, media_id) else {}))
    if not tracks:
        return None
    grow = np.ones((7, 7), np.uint8)

    def at(index: int) -> np.ndarray | None:
        out = None
        for layer, data in tracks:
            follow = data.get("adjusted") or data.get("frames") or {}
            values = follow.get(str(index))
            matte = _raster(layer, size, _matrix(values) if values else None, index)
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
    imported = body.layer.settings.get("matte") if isinstance(body.layer.settings.get("matte"), dict) else None
    matte_info = _video(str(imported["media"])) if imported and imported.get("media") else None
    matte_source, matte_size = (matte_info[0], (matte_info[2], matte_info[3])) if matte_info else (None, (width, height))
    lock = _locks.setdefault(body.layer.id, threading.Lock())

    def operation(job_id, report, cancelled):
        if not lock.acquire(blocking=False):
            raise RuntimeError("this layer is being tracked already")
        try:
            total = abs(last - first)
            frames = _frames(source, fps, width, height, first, last)
            _, frame = next(frames)
            matte = _raster(body.layer, (width, height), start_h, first)
            mattes = _frames(matte_source, fps, matte_size[0], matte_size[1], first, last) if matte_source else None
            if mattes is not None:
                _, first_matte = next(mattes)
                matte = cv2.bitwise_and(matte, cv2.bitwise_not(_matte_outside(first_matte, imported, (width, height))))
            if (matte > 0).sum() < 64:
                raise ValueError("the layer's shapes cover almost nothing on the frame tracked from")
            # Track by a green or blue screen's edges (settings screen: "green" or "blue"): each frame's keyed screen
            # (planar_green.green_quad, its sides' lines crossed) against the frame tracked from's, a homography from
            # four points; a frame where it is not found holds the last, with no confidence (P8: on the owner's three
            # phone shots this is what a planar track of a shiny, near-textureless screen cannot match)
            screen = body.layer.settings.get("screen")
            if screen not in (None, "", "green", "blue"):
                raise ValueError("screen is green or blue")
            if screen:
                from .planar_green import green_quad

                start_quad = green_quad(frame, screen)
                if start_quad is None:
                    raise ValueError(f"no {screen} screen found on the frame tracked from")
                last_h = np.eye(3)

                class _Screen:
                    def __init__(self):
                        self.at = first
                        self.read = {first: start_quad}  # frame -> the screen's corners where it could be read

                    def step(self, picture, exclude=None):
                        nonlocal last_h
                        found = green_quad(picture, screen)
                        if found is None:
                            return last_h, 0.0
                        self.read[self.at] = found
                        last_h = cv2.getPerspectiveTransform(start_quad.astype(np.float32), found.astype(np.float32)).astype(float)
                        return last_h, 1.0

                tracker = _Screen()
            else:
                tracker = PlanarTracker(frame, matte, settings)
            done, faint, lost = 0, 0, None
            report(0.0, f"Tracking from frame {first}")
            for index, frame in frames:
                if cancelled():
                    break
                if screen:
                    tracker.at = index
                kept_out = exclude_at(index) if exclude_at else None
                if mattes is not None:
                    _, matte_frame = next(mattes, (None, None))
                    if matte_frame is not None:
                        outside = _matte_outside(matte_frame, imported, (width, height))
                        kept_out = outside if kept_out is None else cv2.bitwise_or(kept_out, outside)
                h, confidence = tracker.step(frame, kept_out)
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
            if screen:
                # frames where the screen could not be read (a finger over it, a flare) are filled from the frames
                # either side that could, the corners run linearly between them (gaps up to a second), confidence
                # 0.5 to say they were filled: on the owner's clip 3 a touch hid the screen on nine frames
                read = tracker.read
                order = sorted(read)
                for gap in [
                    int(i) for i, c in data["confidence"].items() if c == 0.0 and int(i) in range(min(first, last), max(first, last) + 1)
                ]:
                    before = [f for f in order if f < gap]
                    after = [f for f in order if f > gap]
                    if not before or not after or after[0] - before[-1] > round(fps):
                        continue
                    a, b = before[-1], after[0]
                    corners = read[a] + (read[b] - read[a]) * ((gap - a) / (b - a))
                    rel = cv2.getPerspectiveTransform(start_quad.astype(np.float32), corners.astype(np.float32)).astype(float)
                    full = rel @ start_h
                    data["frames"][str(gap)] = (full / full[2, 2]).ravel().round(9).tolist()
                    data["confidence"][str(gap)] = 0.5
            _readjust(data)  # the reference points' corrections carried onto the frames just tracked
            write_json(path_of, data)
            out = {"layer": body.layer.id, "tracked": done, "from": first, "to": first + (done if last >= first else -done)}
            return {**out, "lost": lost} if lost is not None else out
        finally:
            lock.release()

    STORE.mkdir(parents=True, exist_ok=True)
    write_json(path_of, data)
    return jobs.submit("planar-track", operation)


@router.get("/export/{layer_id}", response_class=PlainTextResponse)
def export_track(layer_id: str, surface: str, format: str = "nuke") -> str:
    """A layer's corner pin for other hosts, in pixels of the tracked media: a Nuke CornerPin2D node to paste (y up from
    the bottom, to1 to to4 lower left, lower right, upper right, upper left), CSV, or JSON (Mocha Pro's exports)."""
    track = read_track(layer_id, surface)
    width, height = track["size"]
    rows = list(zip(track["frames"], track["corners"], strict=True))
    if format == "csv":
        head = "frame,top_left_x,top_left_y,top_right_x,top_right_y,bottom_right_x,bottom_right_y,bottom_left_x,bottom_left_y"
        body = [",".join([str(f)] + [f"{c[0] * width:.3f},{c[1] * height:.3f}" for c in quad]) for f, quad in rows]
        return "\n".join([head, *body]) + "\n"
    if format == "json":
        frames = [{"frame": f, "corners": [[round(c[0] * width, 3), round(c[1] * height, 3)] for c in quad]} for f, quad in rows]
        return json.dumps(
            {"fps": track["fps"], "width": width, "height": height, "origin": "top left", "order": "tl tr br bl", "frames": frames},
            indent=1,
        )
    if format != "nuke":
        raise HTTPException(400, "format is nuke, csv or json")

    def curve(k: int, axis: int) -> str:
        keys = [f"x{f} {quad[k][0] * width if axis == 0 else height - quad[k][1] * height:.3f}" for f, quad in rows]
        return "{curve " + " ".join(keys) + "}"

    pins = "\n".join(f" to{n + 1} {{{curve(k, 0)} {curve(k, 1)}}}" for n, k in enumerate((3, 2, 1, 0)))
    return f"CornerPin2D {{\n{pins}\n from1 {{0 0}}\n from2 {{{width} 0}}\n from3 {{{width} {height}}}\n from4 {{0 {height}}}\n name CornerPin2D_formcut\n}}\n"


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
    adjusted = data.get("adjusted") or {}
    if adjusted:
        out["adjusted"] = [adjusted.get(i, data["frames"][i]) for i in order]
        out["adjust"] = data.get("adjust") or []
    if surface:
        values = [float(v) for v in surface.split(",")]
        if len(values) != 8:
            raise HTTPException(400, "a surface is four corners: eight numbers")
        width, height = data["size"]
        corners = np.array(values, float).reshape(4, 2) * [width, height]
        follow = data.get("adjusted") or data["frames"]  # the adjusted track where there is one, as Mocha links to it
        out["corners"] = [
            (corners_of(_matrix(follow.get(i, data["frames"][i])), corners) / [width, height]).round(6).tolist() for i in order
        ]
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
    data = _load(str(layer.get("link") or body.layer_id))  # a linked layer applies by its carrier's track
    if not data or data.get("media") != tracked.get("mediaId"):
        raise HTTPException(409, "that layer has no track on this clip's media yet")
    if data.get("adjusted"):
        data = {**data, "frames": data["adjusted"]}  # the adjusted track where there is one
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


# ---- AdjustTrack (P4): reference points that remove drift, as Mocha's AdjustTrack does ----


def _interpolate(keys: dict[int, np.ndarray], frame: int) -> np.ndarray:
    """A point's correction at a frame: linear between its keyed frames, held before the first and after the last."""
    order = sorted(keys)
    if frame <= order[0]:
        return keys[order[0]]
    if frame >= order[-1]:
        return keys[order[-1]]
    import bisect

    at = bisect.bisect_right(order, frame)
    a, b = order[at - 1], order[at]
    f = (frame - a) / (b - a)
    return keys[a] + (keys[b] - keys[a]) * f


def adjusted_track(frames: dict, points: list[dict], size: tuple[int, int]) -> dict[str, list]:
    """The adjusted track: on every tracked frame, the raw homography corrected by the reference points.

    A point has a master frame and its place there (home, in the frame's unit square): the raw track carries it to
    every other frame. Where the person put it on a frame (keys: frame -> place), its correction is that place less
    where the track carried it; the master frame's correction is nothing; between keyed frames the corrections run
    linearly and they hold beyond. On each frame the points' carried places and corrected places give a correcting
    transform (four or more points: a homography, least squares past four; three: affine; two: a similarity; one:
    a shift), composed in front of the raw track. Points whose master frame has no track are left out."""
    width, height = size
    raw = {int(i): _matrix(v) for i, v in frames.items()}
    usable = []
    for point in points:
        master = int(point["master"])
        if master not in raw:
            continue
        home = np.array(point["home"], float) * [width, height]
        back = np.linalg.inv(raw[master])
        keys = {master: np.zeros(2)}
        for key, place in (point.get("keys") or {}).items():
            frame = int(key)
            if frame in raw and frame != master:
                carried = corners_of(raw[frame] @ back, home[None])[0]
                keys[frame] = np.array(place, float) * [width, height] - carried
        usable.append((home, back, keys))
    out = {}
    for frame, h in raw.items():
        src, dst = [], []
        for home, back, keys in usable:
            carried = corners_of(h @ back, home[None])[0]
            src.append(carried)
            dst.append(carried + _interpolate(keys, frame))
        correction = np.eye(3)
        if src and np.abs(np.array(dst) - np.array(src)).max() > 1e-6:
            a, b = np.float32(src), np.float32(dst)
            if len(a) >= 4:
                found, _ = cv2.findHomography(a, b, 0)
                correction = found if found is not None else correction
            elif len(a) == 3:
                correction = np.vstack([cv2.getAffineTransform(a, b), [0, 0, 1]])
            elif len(a) == 2:
                found, _ = cv2.estimateAffinePartial2D(a, b, method=cv2.LMEDS)
                correction = np.vstack([found, [0, 0, 1]]) if found is not None else correction
            else:
                correction = np.array([[1, 0, b[0][0] - a[0][0]], [0, 1, b[0][1] - a[0][1]], [0, 0, 1]], float)
        adjusted = correction @ h
        out[str(frame)] = (adjusted / adjusted[2, 2]).ravel().round(9).tolist()
    return out


class AdjustPoint(BaseModel):
    master: int = Field(ge=0)
    home: list[float] = Field(min_length=2, max_length=2)  # its place on the master frame, unit square
    keys: dict[str, list[float]] = Field(default_factory=dict)  # frame -> its place there, unit square


class AdjustBody(BaseModel):
    points: list[AdjustPoint] = Field(default_factory=list, max_length=64)


def _readjust(data: dict) -> None:
    """The adjusted track kept with the raw one, from the layer's reference points (none: no adjusted track)."""
    spec = data.get("adjust") or []
    if spec:
        data["adjusted"] = adjusted_track(data["frames"], spec, tuple(data["size"]))
    else:
        data.pop("adjusted", None)


@router.post("/adjust/{layer_id}")
def adjust_track(layer_id: str, body: AdjustBody) -> dict:
    """A layer's reference points set (all of them, as the workspace holds them) and its adjusted track made from
    them; the corner pin, the Transform keys, the tracked matte and the workspace then follow the adjusted track."""
    path = _path(layer_id)
    data = _load(layer_id)
    if not data:
        raise HTTPException(404, "no track for that layer")
    data["adjust"] = [p.model_dump() for p in body.points]
    _readjust(data)
    write_json(path, data)
    keyed = sum(len(p.keys) for p in body.points)
    return {"layer": layer_id, "points": len(body.points), "keys": keyed, "frames": len(data.get("adjusted") or {})}


class NudgeBody(BaseModel):
    media_id: str
    layer_id: str
    master: int = Field(ge=0)
    home: list[float] = Field(min_length=2, max_length=2)
    frame: int = Field(ge=0)
    patch: int = Field(default=21, ge=7, le=101)  # the search region's size, pixels (Mocha's Search Region Size)
    motion: int = Field(default=16, ge=1, le=200)  # how far it may have gone, pixels (Mocha's Maximum Motion)


@router.post("/nudge")
def auto_nudge(body: NudgeBody) -> dict:
    """Mocha's Auto nudge: where a reference point's feature is on a frame. The master frame is warped into the
    frame's geometry by the track, so a plane that has turned or tilted still matches; the patch around the point's
    place there is searched for within the maximum motion, to a fraction of a pixel. Returns its place (unit square)
    and the match's score (1 is perfect)."""
    data = _load(body.layer_id)
    if not data or str(body.master) not in data["frames"] or str(body.frame) not in data["frames"]:
        raise HTTPException(409, "the point's master frame and this frame both need a track")
    source, fps, width, height, _ = _video(body.media_id)
    frames = data.get("adjusted") or data["frames"]
    relate = _matrix(frames[str(body.frame)]) @ np.linalg.inv(_matrix(frames[str(body.master)]))
    master = next(_read(source, fps, width, height, body.master, 1), None)
    current = next(_read(source, fps, width, height, body.frame, 1), None)
    if master is None or current is None:
        raise HTTPException(404, "a frame could not be read")
    home = np.array(body.home, float) * [width, height]
    guess = corners_of(relate, home[None])[0]
    half, reach = body.patch // 2, body.motion
    gx, gy = round(guess[0]), round(guess[1])
    x0, y0 = gx - half - reach, gy - half - reach
    x1, y1 = gx + half + reach + 1, gy + half + reach + 1
    if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
        raise HTTPException(409, "the point is too near the edge of the frame to search around it")
    grey = lambda img: cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # noqa: E731
    warped = cv2.warpPerspective(grey(master), relate, (width, height), flags=cv2.INTER_LINEAR)
    template = warped[gy - half : gy + half + 1, gx - half : gx + half + 1]
    region = grey(current)[y0:y1, x0:x1]
    scores = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
    _, best, _, (bx, by) = cv2.minMaxLoc(scores)

    def subpixel(values: np.ndarray, at: int) -> float:
        if 0 < at < len(values) - 1:
            a, b, c = values[at - 1], values[at], values[at + 1]
            denom = a - 2 * b + c
            return 0.5 * (a - c) / denom if abs(denom) > 1e-9 else 0.0
        return 0.0

    dx = bx + subpixel(scores[by, :], bx) - reach
    dy = by + subpixel(scores[:, bx], by) - reach
    place = [(gx + dx) / width, (gy + dy) / height]
    return {"at": [round(float(v), 6) for v in place], "score": round(float(best), 3)}


# ---- click to spline (P6): an object outlined by SAM 2.1 as a shape to edit ----


class SegmentBody(BaseModel):
    media_id: str
    frame: int = Field(ge=0)
    points: list[dict] = Field(min_length=1, max_length=16)  # {x, y} in the frame's unit square; keep: false excludes
    detail: int = Field(default=24, ge=6, le=96)  # how many points the outline may have


@router.post("/segment")
def segment(body: SegmentBody) -> dict:
    """Click to spline: the object at the clicked points outlined by SAM 2.1 (formcut's click-select model, the one its
    cutout uses) on one frame of the media, its largest region traced and simplified into a shape's points (the
    frame's unit square), as editable as a drawn one. Refused plainly when the model is not downloaded yet."""
    from .segmentation import cutout_ready, outline, raw_alpha

    if not cutout_ready("click-select"):
        raise HTTPException(409, "click-select (SAM 2 Hiera Tiny) is not downloaded yet: get it from the model manager")
    source, fps, width, height, count = _video(body.media_id)
    frame = next(_read(source, fps, width, height, min(body.frame, count - 1), 1), None)
    if frame is None:
        raise HTTPException(404, "that frame could not be read")
    clicks = [{"x": float(p.get("x", 0)), "y": float(p.get("y", 0)), "keep": p.get("keep", True) is not False} for p in body.points]
    alpha = raw_alpha(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), "click-select", points=clicks)
    traced = outline(alpha, body.detail)
    if len(traced) < 3:
        raise HTTPException(422, "nothing was found at that point: click inside the object")
    return {"points": [[p["x"], p["y"]] for p in traced], "area": round(float((alpha > 0.5).mean()), 4)}


class AssistBody(BaseModel):
    media_id: str
    points: list[list[float]] = Field(min_length=3, max_length=4000)  # the shape's outline on frame, unit square
    frame: int = Field(ge=0)
    stop: int = Field(ge=0)


def _smooth_closed(values: np.ndarray, median: int = 7, sigma: float = 3.0) -> np.ndarray:
    """Per-point values along a closed path: a running median, then a Gaussian, each wrapping round."""
    half = median // 2
    wrapped = np.concatenate([values[-half:], values, values[:half]])
    cleaned = np.median(np.lib.stride_tricks.sliding_window_view(wrapped, median, axis=0), axis=-1)
    reach = int(3 * sigma)
    taps = np.exp(-0.5 * (np.arange(-reach, reach + 1) / sigma) ** 2)
    taps /= taps.sum()
    padded = np.concatenate([cleaned[-reach:], cleaned, cleaned[:reach]])
    return np.stack([np.convolve(padded[:, k], taps, mode="valid") for k in range(values.shape[1])], -1)


def _normals_in(pts: np.ndarray) -> np.ndarray:
    """Each point's unit normal towards the inside of the closed path."""
    tangent = np.roll(pts, -1, 0) - np.roll(pts, 1, 0)
    tangent /= np.maximum(np.linalg.norm(tangent, axis=1, keepdims=True), 1e-9)
    inward = np.stack([-tangent[:, 1], tangent[:, 0]], -1)
    return -inward if float(((pts.mean(0) - pts) * inward).sum()) < 0 else inward


def _snap_to_edges(frame: np.ndarray, pts: np.ndarray, reach: float = 4.0) -> np.ndarray:
    """Points (pixels) moved along their normals to the strongest edge within reach, where one stands out, the
    moves cleaned and smoothed along the closed path."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    edge = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    inward = _normals_in(pts)
    steps = np.arange(-reach, reach + 0.01, 0.5)
    along = (pts[:, None, :] - inward[:, None, :] * steps[None, :, None]).astype(np.float32)
    profiles = cv2.remap(edge, along[:, :, 0], along[:, :, 1], cv2.INTER_LINEAR)
    strong = profiles.max(axis=1) > 1.5 * profiles.mean(axis=1)
    snap = np.where(strong, steps[profiles.argmax(axis=1)], 0.0)
    return pts - inward * _smooth_closed(snap[:, None])


class SnapBody(BaseModel):
    media_id: str
    frame: int = Field(ge=0)
    points: list[list[float]] = Field(min_length=3, max_length=4000)  # unit square
    reach: float = Field(default=6.0, gt=0, le=40)


@router.post("/snap")
def snap_points(body: SnapBody) -> dict:
    """A shape's points snapped to the edges on a frame (Mocha Pro's edge snapping and magnetic drawing)."""
    source, fps, width, height, count = _video(body.media_id)
    frame = next(_read(source, fps, width, height, min(body.frame, count - 1), 1), None)
    if frame is None:
        raise HTTPException(422, "that frame could not be read")
    pts = _snap_to_edges(frame, np.array(body.points, np.float64) * [width, height], body.reach)
    return {"points": (pts / [width, height]).round(6).tolist()}


class BrushBody(BaseModel):
    width: int = Field(gt=0, le=16384)
    height: int = Field(gt=0, le=16384)
    strokes: list[list[list[float]]] = Field(min_length=1, max_length=200)  # each a list of points, unit square
    radius: float = Field(gt=0, le=2000)  # pixels


@router.post("/brush")
def brush_outline(body: BrushBody) -> dict:
    """The outline of the area painted by brush strokes (Mocha Pro's Area Brush): the strokes drawn thick at the
    picture's size, the largest painted area's edge traced and simplified to within a pixel, in the unit square."""
    canvas = np.zeros((body.height, body.width), np.uint8)
    thickness = max(1, round(body.radius * 2))
    for stroke in body.strokes:
        pts = np.round(np.array(stroke, np.float64) * [body.width, body.height]).astype(np.int32)
        if len(pts) == 1:
            cv2.circle(canvas, tuple(int(v) for v in pts[0]), max(1, round(body.radius)), 255, -1, cv2.LINE_AA)
        else:
            cv2.polylines(canvas, [pts], False, 255, thickness, cv2.LINE_AA)
    found, _ = cv2.findContours((canvas > 127).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not found:
        raise HTTPException(422, "nothing was painted")
    outline = cv2.approxPolyDP(max(found, key=cv2.contourArea), 1.0, True).reshape(-1, 2).astype(np.float64)
    if len(outline) < 3:
        raise HTTPException(422, "the painted area is too small")
    return {"points": (outline / [body.width, body.height]).round(6).tolist()}


@router.post("/assist")
def matte_assist(body: AssistBody) -> dict:
    """A shape carried through the shot as vector keys (Mocha Pro's Matte Assist): each frame, dense optical flow
    from the frame before, read a few pixels inside the outline (the object's own motion, not its edge's mix with
    what is behind), cleaned and smoothed along the closed path, moves every point. Keys in the frame's unit square."""
    source, fps, width, height, count = _video(body.media_id)
    last = max(0, min(body.stop, count - 1))
    pts = np.array(body.points, np.float64) * [width, height]
    scale = min(1.0, 640 / max(width, height))
    frames = _frames(source, fps, width, height, body.frame, last)
    _, before = next(frames)

    def small(image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else gray

    previous = small(before)
    keys = {str(body.frame): (pts / [width, height]).round(6).tolist()}
    for index, frame in frames:
        current = small(frame)
        flow = cv2.calcOpticalFlowFarneback(previous, current, None, 0.5, 4, 21, 5, 7, 1.5, 0)
        inward = _normals_in(pts)
        probe = ((pts + inward * 4.0) * scale).astype(np.float32)
        sampled = [cv2.remap(flow[:, :, k], probe[:, None, 0], probe[:, None, 1], cv2.INTER_LINEAR).ravel() for k in (0, 1)]
        moves = np.stack(sampled, -1) / scale
        pts = _snap_to_edges(frame, pts + _smooth_closed(moves))
        keys[str(index)] = (pts / [width, height]).round(6).tolist()
        previous = current
    return {"keys": keys}


class FacesBody(BaseModel):
    media_id: str
    frame: int = Field(ge=0)


@router.post("/faces")
def faces_on(body: FacesBody) -> dict:
    """Faces on a frame, frontal and in profile either way (OpenCV's own detectors, offline), overlapping finds
    merged, each a box (x, y, w, h) in the frame's unit square: Mocha Pro's face detection."""
    source, fps, width, height, count = _video(body.media_id)
    frame = next(_read(source, fps, width, height, min(body.frame, count - 1), 1), None)
    if frame is None:
        raise HTTPException(422, "that frame could not be read")
    gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    smallest = (max(24, width // 40),) * 2
    found: list[tuple[int, int, int, int]] = []
    for name, mirrored in (
        ("haarcascade_frontalface_default.xml", False),
        ("haarcascade_profileface.xml", False),
        ("haarcascade_profileface.xml", True),
    ):
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + name)
        image = cv2.flip(gray, 1) if mirrored else gray
        for x, y, w, h in cascade.detectMultiScale(image, 1.1, 5, minSize=smallest):
            found.append((width - int(x) - int(w) if mirrored else int(x), int(y), int(w), int(h)))
    kept: list[tuple[int, int, int, int]] = []
    for box in sorted(found, key=lambda b: b[2] * b[3], reverse=True):
        x, y, w, h = box
        overlaps = any(
            max(0, min(x + w, kx + kw) - max(x, kx)) * max(0, min(y + h, ky + kh) - max(y, ky)) > 0.3 * min(w * h, kw * kh)
            for kx, ky, kw, kh in kept
        )
        if not overlaps:
            kept.append(box)
    return {"faces": [[round(x / width, 5), round(y / height, 5), round(w / width, 5), round(h / height, 5)] for x, y, w, h in kept]}
