import contextlib
import json
import mimetypes
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import jobs, proxies, scenes, stabilise
from .paths import DATA_DIR

MEDIA_DIR = DATA_DIR / "media"
THUMB_DIR = DATA_DIR / "thumbs"
INDEX_FILE = DATA_DIR / "media.json"
_lock = threading.Lock()

router = APIRouter(prefix="/api/media", tags=["media"])

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".opus"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".heic", ".heif", ".avif", ".tif", ".tiff"}

# X6: phones save HEIC by default. Pillow 11.3 decodes AVIF and TIFF itself;
# HEIC and HEIF come through pi-heif (decoders only, recorded in Licences),
# registered once here so every Image.open in the engine takes them. Absent
# the plugin, those two refuse at import with the plain unsupported message.
try:
    from pi_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    IMAGE_EXT = IMAGE_EXT - {".heic", ".heif"}


def _read() -> list[dict]:
    if not INDEX_FILE.exists():
        return []
    return json.loads(INDEX_FILE.read_text())


def _write(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(items, indent=2))


def _kind(ext: str) -> str | None:
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in IMAGE_EXT:
        return "image"
    return None


def _ffprobe(path: Path) -> dict:
    """Stream and format facts.

    Routed through tools.probe, which uses ffprobe when the bundle carries one
    and reads ffmpeg's own report when it does not: an LGPL build configured
    with --disable-programs --enable-ffmpeg ships ffmpeg alone.
    """
    from .tools import probe

    try:
        return probe(path)
    except Exception:
        return {}


def _probe(path: Path, kind: str) -> dict:
    info = {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0}
    data = _ffprobe(path)
    fmt = data.get("format", {})
    with contextlib.suppress(TypeError, ValueError):
        info["duration"] = round(float(fmt.get("duration", 0.0)), 3)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"] = int(stream.get("width") or 0)
            info["height"] = int(stream.get("height") or 0)
            # X7: PQ and HLG footage is tone-mapped to SDR in the decode pipe;
            # the record carries the transfer so every path can ask cheaply.
            if stream.get("color_transfer") in ("smpte2084", "arib-std-b67"):
                info["transfer"] = stream["color_transfer"]
            rate = stream.get("avg_frame_rate") or "0/1"
            try:
                num, den = rate.split("/")
                info["fps"] = round(int(num) / int(den), 3) if int(den) else 0.0
            except (ValueError, ZeroDivisionError):
                pass
            break
    # X8: screen recordings keep the microphone and the desktop sound as
    # separate streams. More than one earns an inventory on the record, so the
    # inspector can offer the choice without probing again.
    sounds = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if len(sounds) > 1:
        info["audioStreams"] = [
            {
                "index": n,
                "channels": int(s.get("channels") or 0),
                "language": (s.get("tags") or {}).get("language") or "",
                "title": (s.get("tags") or {}).get("title") or "",
            }
            for n, s in enumerate(sounds)
        ]
    if kind == "image":
        info["duration"] = 5.0
        # ffprobe cannot read every image the engine can (HEIC among them);
        # the size comes from the decoder that will actually draw it.
        if not info["width"]:
            try:
                from PIL import Image, ImageOps

                with Image.open(path) as picture:
                    info["width"], info["height"] = ImageOps.exif_transpose(picture).size
            except Exception:
                pass
    return info


def _thumbnail(src: Path, dest: Path, kind: str, duration: float) -> bool:
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    if kind == "audio":
        return False
    seek = ["-ss", str(min(1.0, max(duration - 0.1, 0.0)))] if kind == "video" else []
    cmd = [
        "ffmpeg",
        "-v",
        "quiet",
        "-y",
        *seek,
        "-i",
        str(src),
        "-frames:v",
        "1",
        "-vf",
        "scale=320:-2",
        str(dest),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    if not dest.exists() and kind == "image":
        # The same reach as _probe: ffmpeg cannot read every image the engine
        # decodes, so the thumbnail falls back to the decoder that can.
        try:
            from PIL import Image, ImageOps

            with Image.open(src) as picture:
                small = ImageOps.exif_transpose(picture).convert("RGB")
                small.thumbnail((320, 320 * 4))
                small.save(dest, "JPEG", quality=85)
        except Exception:
            return False
    return dest.exists()


@router.get("")
def list_media() -> list[dict]:
    with _lock:
        return _read()


def ingest_path(src: Path, name: str, extra: dict | None = None) -> dict:
    ext = src.suffix.lower()
    kind = _kind(ext)
    if kind is None:
        raise HTTPException(status_code=415, detail=f"unsupported file type {ext or 'none'}")
    media_id = uuid.uuid4().hex
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    stored = MEDIA_DIR / f"{media_id}{ext}"
    shutil.move(str(src), stored)
    info = _probe(stored, kind)
    has_thumb = _thumbnail(stored, THUMB_DIR / f"{media_id}.jpg", kind, info["duration"])
    item = {
        "id": media_id,
        "name": name,
        "kind": kind,
        "size": stored.stat().st_size,
        "thumb": has_thumb,
        **info,
        **(extra or {}),
    }
    # P3: heavy footage earns a proxy as it arrives, so the first scrub is
    # already cheap rather than the first scrub paying for the build.
    if proxies.wants_proxy(item):
        proxies.enqueue(media_id, stored)
    with _lock:
        items = _read()
        items.append(item)
        _write(items)
    return item


@router.post("", status_code=201)
def import_media(file: UploadFile) -> dict:
    name = file.filename or "untitled"
    ext = Path(name).suffix.lower()
    if _kind(ext) is None:
        raise HTTPException(status_code=415, detail=f"unsupported file type {ext or 'none'}")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MEDIA_DIR / f"upload_{uuid.uuid4().hex}{ext}"
    with tmp.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    return ingest_path(tmp, name)


def _find(media_id: str) -> dict:
    with _lock:
        found = next((m for m in _read() if m["id"] == media_id), None)
    if found is None:
        raise HTTPException(status_code=404, detail="media not found")
    return found


@router.get("/{media_id}/thumb")
def get_thumb(media_id: str) -> FileResponse:
    _find(media_id)
    path = THUMB_DIR / f"{media_id}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no thumbnail")
    return FileResponse(path, media_type="image/jpeg")


@router.get("/{media_id}/file")
def get_file(media_id: str) -> FileResponse:
    item = _find(media_id)
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="file missing")
    media_type = mimetypes.guess_type(item["name"])[0] or "application/octet-stream"
    return FileResponse(matches[0], media_type=media_type, filename=item["name"])


class FreezeBody(BaseModel):
    time: float


REVERSED_DIR = DATA_DIR / "reversed"


def reversed_path(media_id: str) -> Path:
    return REVERSED_DIR / f"{media_id}.mp4"


def build_reversed(media_id: str, source: Path, report, cancelled) -> Path:
    """Segment the source, reverse each piece, and concatenate the pieces backwards.

    Reversing whole files buffers every frame in memory; half-second chunks bound
    that even for 4K sources (a 4 s 1080p chunk was OOM-killed on a 4 GB machine),
    and concatenation of the reversed chunks in reverse order is stream copy.
    """
    import tempfile

    REVERSED_DIR.mkdir(parents=True, exist_ok=True)
    final = reversed_path(media_id)
    if final.is_file() and final.stat().st_size > 0:
        return final
    with tempfile.TemporaryDirectory(dir=REVERSED_DIR) as folder:
        work = Path(folder)
        seg = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(source),
                "-f",
                "segment",
                "-segment_time",
                "0.5",
                "-reset_timestamps",
                "1",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(work / "part_%05d.mp4"),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=1800,
        )
        if seg.returncode != 0:
            raise ValueError("Could not segment the source: " + seg.stderr[-300:])
        parts = sorted(work.glob("part_*.mp4"))
        if not parts:
            raise ValueError("The source produced no segments")
        for index, part in enumerate(parts):
            if cancelled():
                raise InterruptedError("Cancelled")
            report(index / len(parts))
            has_audio = any(s.get("codec_type") == "audio" for s in _ffprobe(part).get("streams", []))
            filters = ["-vf", "reverse"] + (["-af", "areverse"] if has_audio else [])
            rev = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(part),
                    *filters,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "18",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    str(work / f"rev_{part.name}"),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=1800,
            )
            if rev.returncode != 0:
                raise ValueError("Could not reverse a segment (memory or codec): " + rev.stderr[-300:])
        listing = work / "concat.txt"
        listing.write_text("".join(f"file '{work / ('rev_' + part.name)}'\n" for part in reversed(parts)), encoding="utf-8")
        joined = work / "joined.mp4"
        cat = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)],
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        if cat.returncode != 0 or not joined.is_file():
            raise ValueError("Could not join the reversed segments: " + cat.stderr[-300:])
        shutil.move(str(joined), str(final))
    return final


@router.post("/voiceover", status_code=201)
async def upload_voiceover(file: UploadFile, name: str = "Voiceover") -> dict:
    """B7: a recording made in the browser, converted and ingested.

    Browsers record Opus in a WebM container, which is fine to play and poor to
    edit: seeking it is slow and the container carries no sample count. It is
    converted to wav on the way in, so a voiceover behaves like any other audio
    in the timeline from the moment it lands.
    """
    raw = await file.read()
    if len(raw) > 200_000_000:
        raise HTTPException(status_code=413, detail="recording is too large")
    if not raw:
        raise HTTPException(status_code=422, detail="the recording is empty")
    staging = MEDIA_DIR.parent / f"voiceover-{uuid.uuid4().hex}"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_bytes(raw)
    converted = staging.with_suffix(".wav")
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(staging), "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(converted)],
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
        if result.returncode != 0 or not converted.is_file():
            raise HTTPException(status_code=422, detail=f"could not read the recording: {result.stderr[-200:]}")
        return ingest_path(converted, name, extra={"source": "voiceover"})
    finally:
        staging.unlink(missing_ok=True)
        converted.unlink(missing_ok=True)


@router.post("/capture", status_code=201)
async def upload_capture(file: UploadFile, name: str = "Capture") -> dict:
    """A screen or camera recording made in the browser, remuxed and ingested.

    MediaRecorder streams its container as it goes, so the file it hands back
    has no duration and no cues: ffprobe reports N/A and every seek is a scan.
    The streams are copied unchanged into a fresh container of the same kind
    (WebM from Chromium and Firefox, MP4 from Safari), which writes both; a
    stream the named container refuses lands in Matroska instead.
    """
    raw = await file.read()
    if len(raw) > 2_000_000_000:
        raise HTTPException(status_code=413, detail="recording is too large")
    if not raw:
        raise HTTPException(status_code=422, detail="the recording is empty")
    ext = Path(file.filename or "").suffix.lower() or ".webm"
    if ext not in VIDEO_EXT:
        ext = ".webm"
    staging = MEDIA_DIR.parent / f"capture-{uuid.uuid4().hex}{ext}"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_bytes(raw)
    remuxed = staging.with_name(staging.stem + "-remux" + ext)
    try:
        for target in (remuxed, remuxed.with_suffix(".mkv")):
            result = subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-i", str(staging), "-c", "copy", "-movflags", "+faststart", str(target)],
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )
            if result.returncode == 0 and target.is_file() and target.stat().st_size:
                return ingest_path(target, name, extra={"source": "capture"})
            target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"could not read the recording: {result.stderr[-200:]}")
    finally:
        staging.unlink(missing_ok=True)
        remuxed.unlink(missing_ok=True)
        remuxed.with_suffix(".mkv").unlink(missing_ok=True)


@router.post("/{media_id}/subject")
def subject_outline(media_id: str, body: dict) -> dict:
    """An auto mask for the subject, returned as an editable path."""
    from .render_document import validate_document
    from .renderer import FrameRenderer
    from .segmentation import cutout_alpha, outline

    _find(media_id)
    project = validate_document(body.get("project") or {})
    model = str(body.get("model") or "person-cutout")
    renderer = FrameRenderer(project, 640)
    try:
        pixels = renderer.frame(max(0.0, float(body.get("time") or 0)))
    finally:
        renderer.close()
    rgb = pixels[:, :, :3].astype("float32") / 255
    try:
        alpha = cutout_alpha(rgb, {"model": model, "threshold": 0.0, "feather": 1.0, "strokes": []})
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"{model} is not ready: {exc}") from exc
    points = outline(alpha)
    if not points:
        raise HTTPException(status_code=422, detail="nothing recognisable to mask in this frame")
    return {"points": points, "model": model}


def _samples(media_id: str):
    """Mono samples for a media item, through the bundled ffmpeg."""
    import subprocess

    import numpy as np

    from .tools import ffmpeg

    source = _find(media_id)
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="media file is missing")
    out = subprocess.run(
        [ffmpeg(), "-v", "error", "-i", str(matches[0]), "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"],
        capture_output=True,
        check=False,
        timeout=600,
    )
    if out.returncode != 0 or not out.stdout:
        raise HTTPException(status_code=422, detail="this item has no audio to read")
    _ = source
    return np.frombuffer(out.stdout, np.int16).astype("float32") / 32768.0


def _frame_series(project: dict, start: float, duration: float, fps: float = 6.0, cap: int = 240):
    """A run of rendered frames, for anything that follows motion."""
    from .renderer import FrameRenderer

    count = max(2, min(cap, int(duration * fps)))
    renderer = FrameRenderer(project, 480)
    try:
        return [renderer.frame(start + index / fps) for index in range(count)], fps
    finally:
        renderer.close()


@router.post("/{media_id}/track")
def media_track(media_id: str, body: dict) -> dict:
    """Carry a mask forward across a clip, as keyframed anchors."""
    from .render_document import validate_document
    from .subject import track_points

    _find(media_id)
    project = validate_document(body.get("project") or {})
    points = body.get("points") or []
    if len(points) < 3:
        raise HTTPException(status_code=422, detail="a mask needs at least three points to follow")
    start = float(body.get("start") or 0)
    duration = max(0.1, float(body.get("duration") or 2))
    frames, fps = _frame_series(project, start, duration)
    path = track_points(frames, points)
    return {"path": [{"t": round(entry["t"] / fps, 3), "points": entry["points"]} for entry in path], "fps": fps, "frames": len(path)}


@router.post("/{media_id}/reframe")
def media_reframe(media_id: str, body: dict) -> dict:
    """Where a crop of a given shape should sit over time."""
    from .render_document import validate_document
    from .subject import reframe

    _find(media_id)
    project = validate_document(body.get("project") or {})
    frames, fps = _frame_series(project, float(body.get("start") or 0), max(0.1, float(body.get("duration") or 4)))
    result = reframe(frames, float(body.get("aspect") or 9 / 16), float(body.get("smoothing") or 0.8))
    result["crops"] = [{**crop, "t": round(crop["t"] / fps, 3)} for crop in result["crops"]]
    return result


@router.post("/fillers")
def media_fillers(body: dict) -> dict:
    """Filler words in a transcript, as ranges to review before anything is cut."""
    from .subject import fillers

    return fillers(body.get("segments") or [], str(body.get("language") or "en"), body.get("extra") or [])


@router.get("/{media_id}/beats")
def media_beats(media_id: str, sensitivity: float = 0.5) -> dict:
    """Where the beats are, so an edit can be cut to them."""
    from .rhythm import beats

    return beats(_samples(media_id), 48000, sensitivity)


@router.post("/{media_id}/ducking")
def media_ducking(media_id: str, body: dict) -> dict:
    """The envelope music should follow under this speech, as keyframes."""
    from .rhythm import ducking

    return ducking(
        _samples(media_id),
        48000,
        depth=float(body.get("depth", 0.25)),
        attack=float(body.get("attack", 0.15)),
        release=float(body.get("release", 0.4)),
    )


@router.post("/{media_id}/cutout-preview")
def cutout_preview(media_id: str, body: dict) -> dict:
    """Run the cutout once and report what it found.

    This exists so the interface can say something true before anything is
    applied: whether the model is there, how long it took, how much of the frame
    it kept, and how many separate things it found, which is what tells a person
    whether they need to point at one.
    """
    import time as _time

    from .render_document import validate_document
    from .renderer import FrameRenderer
    from .segmentation import cutout_ready as model_ready
    from .segmentation import pick_region, raw_alpha, region_count

    _find(media_id)
    model = str(body.get("model") or "person-cutout")
    if not model_ready(model):
        raise HTTPException(status_code=409, detail=f"{model} is not downloaded yet")
    project = validate_document(body.get("project") or {})
    renderer = FrameRenderer(project, 640)
    started = _time.perf_counter()
    try:
        frame = renderer.frame(max(0.0, float(body.get("time") or 0)))
    finally:
        renderer.close()
    point = body.get("point")
    if model == "click-select":
        from .segmentation import prompts

        points, box = prompts(body)
        if not points and box is None:
            raise HTTPException(status_code=422, detail="Point at what to keep first")
        alpha = raw_alpha(frame[:, :, :3], model, points, box)
        found = region_count(alpha)
    else:
        alpha = raw_alpha(frame[:, :, :3], model)
        found = region_count(alpha)
        if isinstance(point, dict):
            alpha = pick_region(alpha, float(point.get("x", 0.5)), float(point.get("y", 0.5)))
    kept = float((alpha > 0.5).mean())
    return {
        "model": model,
        "regions": found,
        "kept": round(kept, 4),
        "seconds": round(_time.perf_counter() - started, 2),
        "empty": kept < 0.002,
    }


@router.get("/{media_id}/scenes")
def media_scenes(media_id: str, sensitivity: float = 0.5, minimum: float = 1.0) -> dict:
    """B5: where the shots change, so a long clip can become short ones."""
    record = _find(media_id)
    if record["kind"] != "video":
        raise HTTPException(status_code=400, detail="only video media has scenes")
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="media file missing")
    stand_in = proxies.proxy_path(media_id)
    source = stand_in if proxies.status(media_id, matches[0]).get("state") == "ready" else matches[0]
    return scenes.scenes(source, sensitivity, minimum)


@router.get("/{media_id}/motion")
def motion_status(media_id: str) -> dict:
    _find(media_id)
    return stabilise.status(media_id)


@router.post("/{media_id}/motion", status_code=202)
def analyse_motion(media_id: str) -> dict:
    record = _find(media_id)
    if record["kind"] != "video":
        raise HTTPException(status_code=400, detail="only video media can be stabilised")
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="media file missing")
    # A proxy is the right thing to measure: the movement is the same and the
    # decode is a fraction of the cost.
    stand_in = proxies.proxy_path(media_id)
    source = stand_in if proxies.status(media_id, matches[0]).get("state") == "ready" else matches[0]
    return stabilise.analyse(media_id, source, float(record.get("fps") or 30))


@router.get("/{media_id}/proxy")
def proxy_status(media_id: str) -> dict:
    _find(media_id)
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    return proxies.status(media_id, matches[0] if matches else None)


@router.post("/{media_id}/proxy", status_code=202)
def build_media_proxy(media_id: str, size: int = proxies.DEFAULT_LONG_SIDE) -> dict:
    record = _find(media_id)
    if record["kind"] != "video":
        raise HTTPException(status_code=400, detail="only video media can have a proxy")
    if size not in proxies.ALLOWED_SIZES:
        raise HTTPException(status_code=422, detail="unknown proxy size")
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="media file missing")
    return proxies.enqueue(media_id, matches[0], size)


@router.delete("/{media_id}/proxy", status_code=204)
def delete_media_proxy(media_id: str) -> None:
    _find(media_id)
    proxies.remove(media_id)


@router.post("/{media_id}/reverse", status_code=202)
def reverse_media(media_id: str) -> dict:
    record = _find(media_id)
    if record["kind"] != "video":
        raise HTTPException(status_code=400, detail="only video media can be reversed")
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="media file missing")
    if reversed_path(media_id).is_file():
        return {"status": "ready", "media_id": media_id}

    def operation(job_id, report, cancelled):
        # P8: reversing re-encodes every frame, so it reads the proxy when one
        # is ready; the reversed copy is a preview artefact either way.
        stand_in = proxies.proxy_path(media_id)
        source = stand_in if proxies.status(media_id, matches[0]).get("state") == "ready" else matches[0]
        build_reversed(media_id, source, report, cancelled)
        return {"media_id": media_id, "status": "ready"}

    return jobs.submit("reverse-media", operation)


@router.post("/{media_id}/freeze", status_code=201)
def freeze_frame(media_id: str, body: FreezeBody) -> dict:
    record = _find(media_id)
    if record["kind"] != "video":
        raise HTTPException(status_code=400, detail="only video media has frames to freeze")
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="media file missing")
    at = float(body.time)
    if not 0 <= at <= 86400:
        raise HTTPException(status_code=422, detail="Invalid frame time")
    out = MEDIA_DIR / f"freeze_{uuid.uuid4().hex}.png"
    try:
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(matches[0]), "-frames:v", "1", str(out)],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="No frame at that time")
    base = Path(record["name"]).stem
    return ingest_path(out, f"{base} frame {at:.2f}s.png", extra={"source": "freeze", "from": media_id, "at": at})


@router.post("/{media_id}/detach", status_code=201)
def detach_audio(media_id: str) -> dict:
    record = _find(media_id)
    if record["kind"] != "video":
        raise HTTPException(status_code=400, detail="only video media has audio to detach")
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="media file missing")
    out = MEDIA_DIR / f"detach_{uuid.uuid4().hex}.m4a"
    try:
        proc = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(matches[0]), "-vn", "-c:a", "aac", "-b:a", "192k", str(out)],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if proc.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="This video has no audio track to detach")
    base = Path(record["name"]).stem
    return ingest_path(out, f"{base} audio.m4a", extra={"source": "detach", "from": media_id})


class RenameBody(BaseModel):
    name: str


@router.patch("/{media_id}")
def rename_media(media_id: str, body: RenameBody) -> dict:
    """Rename the library entry. The stored file keeps its id-based name, so a
    rename cannot break a project that references this media."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="the name is empty")
    with _lock:
        items = _read()
        found = next((m for m in items if m["id"] == media_id), None)
        if found is None:
            raise HTTPException(status_code=404, detail="media not found")
        found["name"] = name[:120]
        _write(items)
    return found


@router.post("/{media_id}/reveal")
def reveal_media(media_id: str) -> dict:
    """Show the file in the platform's file manager.

    A desktop convenience that cannot work everywhere: a headless machine has no
    file manager, so the answer says so rather than pretending it opened.
    """
    _find(media_id)
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="file missing")
    path = matches[0]
    if sys.platform == "darwin":
        command = ["open", "-R", str(path)]
    elif sys.platform == "win32":
        command = ["explorer", f"/select,{path}"]
    else:
        command = ["xdg-open", str(path.parent)]
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return {"opened": False, "path": str(path), "detail": "No file manager is available on this machine; the path is above."}
    return {"opened": True, "path": str(path)}


@router.delete("/{media_id}", status_code=204)
def delete_media(media_id: str):
    _find(media_id)
    with _lock:
        items = [m for m in _read() if m["id"] != media_id]
        _write(items)
    for path in MEDIA_DIR.glob(f"{media_id}.*"):
        path.unlink(missing_ok=True)
    (THUMB_DIR / f"{media_id}.jpg").unlink(missing_ok=True)
    proxies.remove(media_id)


_audio_streams: dict[str, bool] = {}
_hdr_media: dict[str, bool] = {}


def is_hdr(media_id: str) -> bool:
    """Whether a media file's video is PQ or HLG (X7): the record answers for
    anything ingested since the transfer was recorded; older and SDR records
    probe once and remember, as has_audio does."""
    with _lock:
        record = next((m for m in _read() if m["id"] == media_id), None)
    if record is not None and "transfer" in record:
        return True
    if media_id in _hdr_media:
        return _hdr_media[media_id]
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    found = False
    if matches:
        try:
            found = any(
                s.get("codec_type") == "video" and s.get("color_transfer") in ("smpte2084", "arib-std-b67")
                for s in _ffprobe(matches[0]).get("streams", [])
            )
        except Exception:
            found = False
    _hdr_media[media_id] = found
    return found


def has_audio(media_id: str) -> bool:
    """Whether a media file carries an audio stream; probed once and cached."""
    if media_id in _audio_streams:
        return _audio_streams[media_id]
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    found = False
    if matches:
        try:
            found = any(s.get("codec_type") == "audio" for s in _ffprobe(matches[0]).get("streams", []))
        except Exception:
            found = False
    _audio_streams[media_id] = found
    return found
