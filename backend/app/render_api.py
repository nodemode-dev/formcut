import io
import math
import subprocess
import threading
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
from .renderer import FrameRenderer

router = APIRouter(prefix="/api/render", tags=["render"])
_lock = threading.RLock()
_sessions = {}
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
            with item["lock"]:
                item["renderer"].close()
        _sessions[session_id] = {"renderer": renderer, "lock": threading.RLock(), "touched": time.monotonic()}
    return {"id": session_id, "width": renderer.width, "height": renderer.height, "duration": project["duration"]}


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    with _lock:
        item = _sessions.pop(session_id, None)
    if item:
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
        with item["lock"]:
            pixels = item["renderer"].frame(time)
            output = io.BytesIO()
            Image.fromarray(pixels).save(output, format="PNG", compress_level=1)
        return Response(output.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc


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
