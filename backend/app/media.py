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

from .paths import DATA_DIR
from . import jobs
from . import proxies
MEDIA_DIR = DATA_DIR / "media"
THUMB_DIR = DATA_DIR / "thumbs"
INDEX_FILE = DATA_DIR / "media.json"
_lock = threading.Lock()

router = APIRouter(prefix="/api/media", tags=["media"])

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".opus"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


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
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(path),
            ],
            capture_output=True, timeout=30,
        )
        return json.loads(out.stdout or b"{}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}


def _probe(path: Path, kind: str) -> dict:
    info = {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0}
    data = _ffprobe(path)
    fmt = data.get("format", {})
    try:
        info["duration"] = round(float(fmt.get("duration", 0.0)), 3)
    except (TypeError, ValueError):
        pass
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            info["width"] = int(stream.get("width") or 0)
            info["height"] = int(stream.get("height") or 0)
            rate = stream.get("avg_frame_rate") or "0/1"
            try:
                num, den = rate.split("/")
                info["fps"] = round(int(num) / int(den), 3) if int(den) else 0.0
            except (ValueError, ZeroDivisionError):
                pass
            break
    if kind == "image":
        info["duration"] = 5.0
    return info


def _thumbnail(src: Path, dest: Path, kind: str, duration: float) -> bool:
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    if kind == "audio":
        return False
    seek = ["-ss", str(min(1.0, max(duration - 0.1, 0.0)))] if kind == "video" else []
    cmd = [
        "ffmpeg", "-v", "quiet", "-y", *seek, "-i", str(src),
        "-frames:v", "1", "-vf", "scale=320:-2", str(dest),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
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
            ["ffmpeg", "-v", "error", "-y", "-i", str(source), "-f", "segment", "-segment_time", "0.5",
             "-reset_timestamps", "1", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k", str(work / "part_%05d.mp4")],
            capture_output=True, text=True, timeout=1800,
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
                ["ffmpeg", "-v", "error", "-y", "-i", str(part), *filters,
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
                 str(work / f"rev_{part.name}")],
                capture_output=True, text=True, timeout=1800,
            )
            if rev.returncode != 0:
                raise ValueError("Could not reverse a segment (memory or codec): " + rev.stderr[-300:])
        listing = work / "concat.txt"
        listing.write_text("".join(f"file '{work / ('rev_' + part.name)}'\n" for part in reversed(parts)), encoding="utf-8")
        joined = work / "joined.mp4"
        cat = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)],
            capture_output=True, text=True, timeout=600,
        )
        if cat.returncode != 0 or not joined.is_file():
            raise ValueError("Could not join the reversed segments: " + cat.stderr[-300:])
        shutil.move(str(joined), str(final))
    return final


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
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(matches[0]),
             "-frames:v", "1", str(out)],
            capture_output=True, text=True, timeout=120,
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
            ["ffmpeg", "-v", "error", "-y", "-i", str(matches[0]),
             "-vn", "-c:a", "aac", "-b:a", "192k", str(out)],
            capture_output=True, text=True, timeout=300,
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
        return {"opened": False, "path": str(path),
                "detail": "No file manager is available on this machine; the path is above."}
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
