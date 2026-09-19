import io
import math
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field

from . import gpu, jobs
from .audio_render import render_audio
from .paths import DATA_DIR
from .render_document import validate_document
import hashlib
import json
import numpy as np
from .renderer import FrameRenderer
from .audio_render import processed_clip_audio, RATE
from .media import MEDIA_DIR, reversed_path
from .paths import DATA_DIR
from .frame_cache import FrameCache, ReadAhead
from .matte_cache import matte_key, sample_times, store as matte_store, progress as matte_progress
from . import jobs

router = APIRouter(prefix="/api/render", tags=["render"])
_lock = threading.RLock()
_sessions = {}
CLIP_AUDIO = DATA_DIR / "clip-audio"
OUTPUTS = DATA_DIR / "renders"


class RenderInput(BaseModel):
    project: dict
    width: int | None = Field(default=None, ge=16, le=7680)
    format: str = "mp4"
    quality: str = "high"


def checked(body: RenderInput) -> dict:
    try:
        return validate_document(body.project)
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/status")
def capabilities():
    return {"compositor": gpu.status(), "shared_preview_export": True, "formats": ["mp4", "webm"], "frame_format": "png"}


@router.post("/sessions", status_code=201)
def create_session(body: RenderInput):
    project = checked(body)
    renderer = FrameRenderer(project, body.width)
    session_id = uuid.uuid4().hex
    with _lock:
        while len(_sessions) >= 8:
            first = min(_sessions, key=lambda k: _sessions[k]["touched"])
            item = _sessions.pop(first)
            item["ahead"].stop()
            with item["lock"]:
                item["renderer"].close()
        lock = threading.RLock()
        cache = FrameCache(project)
        def render_locked(at: float):
            with lock:
                return renderer.frame(at)
        _sessions[session_id] = {"renderer": renderer, "lock": lock, "touched": time.monotonic(),
                                 "cache": cache, "ahead": ReadAhead(render_locked, cache, project["fps"])}
    return {"id": session_id, "width": renderer.width, "height": renderer.height, "duration": project["duration"]}


@router.post("/sessions/{session_id}/document")
def retarget_session(session_id: str, body: RenderInput):
    """Point a live session at an edited document; only touched frames drop."""
    project = checked(body)
    with _lock:
        item = _sessions.get(session_id)
        if not item:
            raise HTTPException(404, "Preview session expired")
    dropped = item["cache"].retarget(project)
    with item["lock"]:
        item["renderer"].close()
        item["renderer"] = FrameRenderer(project, body.width)
    return {"dropped": dropped, **item["cache"].stats()}


@router.get("/sessions/{session_id}/stats")
def session_stats(session_id: str):
    with _lock:
        item = _sessions.get(session_id)
        if not item:
            raise HTTPException(404, "Preview session expired")
    return item["cache"].stats()


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    with _lock:
        item = _sessions.pop(session_id, None)
    if item:
        item["ahead"].stop()
        with item["lock"]:
            item["renderer"].close()


@router.get("/sessions/{session_id}/frame")
def frame(session_id: str, time: float = 0):
    with _lock:
        item = _sessions.get(session_id)
        if not item:
            raise HTTPException(404, "Preview session expired")
        item["touched"] = __import__("time").monotonic()
    if not math.isfinite(time) or time < 0:
        raise HTTPException(422, "Invalid frame time")
    try:
        cache = item["cache"]
        pixels = cache.get(time)
        served = "hit"
        if pixels is None:
            served = "miss"
            with item["lock"]:
                pixels = item["renderer"].frame(time)
            cache.put(time, pixels)
        item["ahead"].seek(time)
        output = io.BytesIO()
        Image.fromarray(pixels).save(output, format="PNG", compress_level=1)
        return Response(output.getvalue(), media_type="image/png",
                        headers={"Cache-Control": "no-store", "x-formcut-frame": served})
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc


def export_workers() -> int:
    """Bounded by cores and by an override, so a small machine stays serial."""
    override = os.environ.get("FORMCUT_EXPORT_WORKERS")
    if override:
        try:
            return max(1, min(8, int(override)))
        except ValueError:
            pass
    return max(1, min(4, (os.cpu_count() or 1) - 1))


def _render_span(project: dict, fps: float, span: tuple[int, int], cancelled) -> list[bytes]:
    """Render one contiguous run of frames with a renderer of its own."""
    worker = FrameRenderer(project)
    try:
        out = []
        for index in range(span[0], span[1]):
            if cancelled():
                raise InterruptedError("Cancelled")
            out.append(worker.frame(index / fps).tobytes())
        return out
    finally:
        worker.close()


def export_media(project: dict, job_id: str, report, cancelled, format: str, quality: str) -> dict:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    path = OUTPUTS / (job_id + "." + format)
    audio = OUTPUTS / (job_id + ".wav")
    log = OUTPUTS / (job_id + ".log")
    renderer = FrameRenderer(project)
    process = None
    try:
        render_audio(project, audio, cancelled)
        report(0.1)
        fps = project["fps"]
        codec = ["-c:v", "libx264", "-preset", "veryfast", "-crf", {"high": "18", "medium": "23", "low": "28"}[quality], "-c:a", "aac"] if format == "mp4" else ["-c:v", "libvpx-vp9", "-b:v", "0", "-cpu-used", "5", "-crf", {"high": "24", "medium": "33", "low": "40"}[quality], "-c:a", "libopus"]
        count = math.ceil(project["duration"] * fps)
        command = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{renderer.width}x{renderer.height}", "-r", str(fps), "-i", "pipe:0", "-i", str(audio), "-map", "0:v", "-map", "1:a", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", *codec, "-pix_fmt", "yuv420p", "-t", str(project["duration"]), str(path)]
        with log.open("wb") as errors:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)
            # R5: render chunks on a bounded worker pool and feed the encoder in
            # frame order. Each worker keeps its own renderer, so decoders stay
            # sequential inside a chunk; one worker reproduces the old path.
            workers = export_workers()
            if workers > 1 and count > workers * 4:
                chunk = math.ceil(count / workers)
                spans = [(start, min(count, start + chunk)) for start in range(0, count, chunk)]
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    pending = [pool.submit(_render_span, project, fps, span, cancelled) for span in spans]
                    done = 0
                    for future in pending:
                        for payload in future.result():
                            if cancelled():
                                raise InterruptedError("Cancelled")
                            process.stdin.write(payload)
                            done += 1
                            report(0.1 + 0.85 * done / count)
            else:
                for i in range(count):
                    if cancelled():
                        raise InterruptedError("Cancelled")
                    process.stdin.write(renderer.frame(i / fps).tobytes())
                    report(0.1 + 0.85 * (i + 1) / count)
            process.stdin.close()
            process.wait(timeout=600)
        if process.returncode:
            raise ValueError(log.read_text(errors="replace")[-2000:])
        return {"file": str(path), "name": "formcut-export." + format, "media_type": "video/mp4" if format == "mp4" else "video/webm", "frames": count, "width": renderer.width, "height": renderer.height}
    except BaseException:
        if process and process.poll() is None:
            process.kill()
            process.wait()
        path.unlink(missing_ok=True)
        raise
    finally:
        renderer.close()
        audio.unlink(missing_ok=True)
        log.unlink(missing_ok=True)


@router.post("/export", status_code=202)
def export(body: RenderInput):
    project = checked(body)
    if body.format not in ("mp4", "webm") or body.quality not in ("high", "medium", "low"):
        raise HTTPException(422, "Unknown export format or quality")
    return jobs.submit("export", lambda job_id, report, cancelled: export_media(project, job_id, report, cancelled, body.format, body.quality))


@router.post("/audio", status_code=202)
def audio(body: RenderInput):
    project = checked(body)
    def operation(job_id, report, cancelled):
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        path = OUTPUTS / (job_id + ".wav")
        render_audio(project, path, cancelled)
        return {"file": str(path), "name": "formcut-preview.wav", "media_type": "audio/wav"}
    return jobs.submit("preview-audio", operation)

class ClipAudioInput(BaseModel):
    clip: dict


@router.post("/clip-audio")
def clip_audio(body: ClipAudioInput):
    """R2: one clip's processed sound, cached, for live mixing in the interface.

    The buffer carries speed and audio effects but not gain, fades or pan: the
    interface applies those as Web Audio automation so a volume change is heard
    at once, and the export applies the same curve from clip_envelope.
    """
    clip = body.clip
    media_id = str(clip.get("mediaId") or "")
    if not media_id:
        raise HTTPException(422, "Clip has no media")
    signature = hashlib.sha1(json.dumps({k: clip.get(k) for k in
        ("mediaId", "sourceIn", "duration", "extendOut", "speed", "speedCurve", "reversed", "audioEffects", "audioFx")},
        sort_keys=True, default=str).encode()).hexdigest()[:20]
    CLIP_AUDIO.mkdir(parents=True, exist_ok=True)
    path = CLIP_AUDIO / f"{signature}.f32"
    if not path.is_file():
        if clip.get("reversed"):
            source = reversed_path(media_id)
            if not source.is_file():
                raise HTTPException(409, "Reversed copy is not prepared yet")
        else:
            matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
            if not matches:
                raise HTTPException(404, "Media file is missing")
            source = matches[0]
        try:
            samples = processed_clip_audio(clip, source)
        except Exception as exc:
            raise HTTPException(422, str(exc)) from exc
        staging = path.with_suffix(".part")
        staging.write_bytes(np.ascontiguousarray(samples, dtype="<f4").tobytes())
        staging.replace(path)
    return Response(path.read_bytes(), media_type="application/octet-stream",
                    headers={"x-formcut-rate": str(RATE), "x-formcut-signature": signature,
                             "Cache-Control": "no-store"})


class MatteInput(BaseModel):
    clip: dict
    fps: float = 30.0


@router.post("/mattes", status_code=202)
def build_mattes(body: MatteInput):
    """BG3: compute a clip's mattes once, in the background, into the cache."""
    clip = body.clip
    media_id = str(clip.get("mediaId") or "")
    options = clip.get("cutout") or {}
    model = options.get("model", "object-cutout")
    if not media_id:
        raise HTTPException(422, "Clip has no media")
    key = matte_key(media_id, model, options)
    duration = float(clip.get("duration", 0)) + float(clip.get("extendOut", 0) or 0)
    times = sample_times(duration, body.fps)
    done = matte_progress(key, duration, body.fps)
    if done["ready"]:
        return {"status": "ready", **done}

    def operation(job_id, report, cancelled):
        from .segmentation import raw_alpha
        renderer = FrameRenderer({"title": "matte", "width": 640, "height": 360, "fps": body.fps,
                                  "duration": max(0.1, duration), "activeTimeline": 0,
                                  "timelines": [{"id": "m", "name": "m", "tracks": [{"id": "t", "name": "V",
                                      "clips": [{**clip, "start": 0, "cutout": None}]}]}]})
        try:
            for index, at in enumerate(times):
                if cancelled():
                    raise InterruptedError("Cancelled")
                frame = renderer.media_frame(clip, at)
                matte_store(key, at, raw_alpha(frame, model))
                report((index + 1) / len(times))
        finally:
            renderer.close()
        return {"status": "ready", **matte_progress(key, duration, body.fps)}

    return jobs.submit("mattes", operation)


@router.get("/mattes/{key}")
def matte_status(key: str, duration: float = 1.0, fps: float = 30.0):
    return matte_progress(key, duration, fps)
