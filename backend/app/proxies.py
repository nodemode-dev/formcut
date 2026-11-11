"""Proxy media for preview (P1 to P4).

A proxy is a small, quick-to-decode copy of a heavy clip, used only while
editing. Exports keep reading the originals, so nothing a proxy does can reach
the delivered file.

The shape follows the reverse feature already in `media.py`: a derived file
under the data directory, built by a job that reports progress and can be
cancelled. Two things are added on top. A sidecar records what the proxy was
built from, so a replaced or re-encoded source is detected rather than silently
previewed from a stale copy. And proxies get a worker of their own that stands
aside while an export runs, because a background build that slows the export it
is meant to support would be worse than no proxy at all.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from queue import Queue

from .paths import DATA_DIR

PROXY_DIR = DATA_DIR / "proxies"
FORMAT_VERSION = 1

# The document's rule, kept here so the interface and the engine agree on it.
AUTO_LONG_SIDE = 1920
AUTO_CODECS = {"hevc", "h265", "prores", "dnxhd", "dnxhr", "av1", "vp9"}
AUTO_BITRATE = 50_000_000
DEFAULT_LONG_SIDE = 1280
ALLOWED_SIZES = (960, 1280, 1920)


def proxy_path(media_id: str) -> Path:
    return PROXY_DIR / f"{media_id}.mp4"


def sidecar_path(media_id: str) -> Path:
    return PROXY_DIR / f"{media_id}.json"


def source_stamp(source: Path) -> dict:
    stat = source.stat()
    return {"size": stat.st_size, "mtime": round(stat.st_mtime, 3)}


def status(media_id: str, source: Path | None = None) -> dict:
    """Where a proxy stands: missing, stale, building, failed or ready."""
    with _lock:
        if media_id in _building:
            return {"state": "building", "progress": _building[media_id]}
        if media_id in _failed:
            return {"state": "failed", "error": _failed[media_id]}
        if media_id in _queued:
            return {"state": "queued", "progress": 0.0}
    path, side = proxy_path(media_id), sidecar_path(media_id)
    if not path.is_file() or not side.is_file():
        return {"state": "missing"}
    try:
        record = json.loads(side.read_text(encoding="utf-8"))
    except ValueError:
        return {"state": "stale"}
    if record.get("version") != FORMAT_VERSION:
        return {"state": "stale"}
    if source is not None and source.is_file() and record.get("source") != source_stamp(source):
        # The source was replaced or re-encoded, so the proxy no longer stands
        # for it. Saying stale is better than previewing the wrong footage.
        return {"state": "stale"}
    return {"state": "ready", **{k: record[k] for k in ("width", "height", "fps", "encoder") if k in record}}


def wants_proxy(info: dict) -> bool:
    """Whether the document's rule says this media earns a proxy."""
    if info.get("kind") != "video":
        return False
    long_side = max(int(info.get("width") or 0), int(info.get("height") or 0))
    if long_side > AUTO_LONG_SIDE:
        return True
    if str(info.get("codec") or "").lower() in AUTO_CODECS:
        return True
    return int(info.get("bitrate") or 0) > AUTO_BITRATE


def build_proxy(media_id: str, source: Path, report, cancelled, long_side: int = DEFAULT_LONG_SIDE) -> Path:
    """Encode the proxy, then write its sidecar."""
    from .media import _ffprobe

    PROXY_DIR.mkdir(parents=True, exist_ok=True)
    probe = _ffprobe(source)
    stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
    rate = str(stream.get("avg_frame_rate") or "30/1")
    if rate in ("0/0", "0"):
        rate = "30/1"
    target = proxy_path(media_id)
    staging = target.with_name(f"{media_id}.part.mp4")
    report(0.05)
    from .encoders import detect

    encoder = "libx264" if "libx264" in (detect().get("h264") or []) else "mpeg4"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"scale=w={long_side}:h={long_side}:force_original_aspect_ratio=decrease:force_divisible_by=2",
        # The frame rate is pinned to the source's average because VideoSource
        # turns a time into a frame number with avg_frame_rate; if the proxy ran
        # at another rate, frame n would land at a different moment in each file.
        "-r",
        rate,
        "-c:v",
        encoder,
        *(["-preset", "veryfast", "-tune", "fastdecode", "-crf", "23"] if encoder == "libx264" else ["-q:v", "3"]),
        "-g",
        "1",
        "-pix_fmt",
        "yuv420p",
        "-metadata:s:v:0",
        "rotate=0",
        "-movflags",
        "+faststart",
        str(staging),
    ]
    with tempfile.TemporaryFile("w+") as log:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=log, text=True)
        while process.poll() is None:
            if cancelled():
                process.kill()
                staging.unlink(missing_ok=True)
                raise InterruptedError("Cancelled")
            time.sleep(0.2)
        if process.returncode != 0:
            log.seek(0)
            error = log.read()[-300:]
            staging.unlink(missing_ok=True)
            raise ValueError(f"Could not build a proxy: {error}")
    staging.replace(target)
    made = _ffprobe(target)
    out = next((s for s in made.get("streams", []) if s.get("codec_type") == "video"), {})
    sidecar_path(media_id).write_text(
        json.dumps(
            {
                "version": FORMAT_VERSION,
                "source": source_stamp(source),
                "width": int(out.get("width") or 0),
                "height": int(out.get("height") or 0),
                "fps": rate,
                "encoder": encoder,
                "longSide": long_side,
            }
        ),
        encoding="utf-8",
    )
    report(1.0)
    return target


# One worker, and it stands aside for exports.
_lock = threading.RLock()
_queued: dict[str, int] = {}
_building: dict[str, float] = {}
_failed: dict[str, str] = {}
_work: Queue[tuple[str, Path, int]] = Queue()
_export_running = threading.Event()
_started = False


def exports_started() -> None:
    _export_running.set()


def exports_finished() -> None:
    _export_running.clear()


def enqueue(media_id: str, source: Path, long_side: int = DEFAULT_LONG_SIDE) -> dict:
    with _lock:
        _failed.pop(media_id, None)
        if media_id in _building or media_id in _queued:
            return status(media_id, source)
        _queued[media_id] = long_side
    _work.put((media_id, source, long_side))
    _ensure_worker()
    return {"state": "queued", "progress": 0.0}


def _ensure_worker() -> None:
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_run, name="proxy-worker", daemon=True).start()


def _run() -> None:
    while True:
        media_id, source, long_side = _work.get()
        # An export always wins: the build waits rather than competing for the
        # cores the export needs.
        while _export_running.is_set():
            time.sleep(0.5)
        with _lock:
            _queued.pop(media_id, None)
            _building[media_id] = 0.0
        try:
            # The progress callback binds this iteration's id rather than the
            # loop variable: without the default argument a later build would
            # report its progress against whichever media the loop had reached.
            build_proxy(media_id, source, lambda value, which=media_id: _progress(which, value), lambda: False, long_side)
        except Exception as exc:
            with _lock:
                _failed[media_id] = str(exc)[:200]
        finally:
            with _lock:
                _building.pop(media_id, None)
            _work.task_done()


def _progress(media_id: str, value: float) -> None:
    with _lock:
        if media_id in _building:
            _building[media_id] = max(0.0, min(1.0, float(value)))


def remove(media_id: str) -> bool:
    gone = False
    for path in (proxy_path(media_id), sidecar_path(media_id)):
        if path.is_file():
            path.unlink(missing_ok=True)
            gone = True
    with _lock:
        _failed.pop(media_id, None)
    return gone


def usable(media_id: str, source: Path, decode_limit: int | None) -> Path | None:
    """The proxy to read for a preview, or None to read the original.

    A proxy is only used when the renderer is previewing (it has a decode
    limit), the proxy is ready and current, and its long side is at least that
    limit, so a preview never upscales from a proxy.
    """
    if not decode_limit:
        return None
    state = status(media_id, source)
    if state.get("state") != "ready":
        return None
    if max(int(state.get("width") or 0), int(state.get("height") or 0)) < decode_limit:
        return None
    path = proxy_path(media_id)
    return path if path.is_file() else None
