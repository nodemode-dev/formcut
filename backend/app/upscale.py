"""Upscale a clip or still in the bin into a new, larger one.

Algorithmic methods run here. ffmpeg's scaler does video with Lanczos, which keeps
the most detail of the classic filters, with Lanczos followed by a light unsharp
mask, or with bicubic; Pillow does stills with the same filters. Video is encoded
with the best MP4 encoder this machine has, as exports are.

Topaz runs in Topaz Labs' cloud through its Video API, with the person's own key
and credits. Creating a request is free and returns an estimate, so that step is
its own route and the interface can show the credits before anything is billed.
Accepting reserves the credits and returns presigned upload URLs; the file goes
up in equal byte ranges, one PUT a part, and the parts' ETags complete the
upload. The status route reports progress and, when done, a signed link that
lives about a day, so the result is downloaded at once.

The original is never replaced: the result is a new item beside it in the bin.
"""

from __future__ import annotations

import hashlib
import math
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from PIL import Image, ImageFilter, ImageOps
from pydantic import BaseModel, Field

from . import ai_upscale, encoders, jobs, media, model_manager, providers

router = APIRouter(prefix="/api/media", tags=["upscale"])

ALGORITHMS = {"lanczos": "lanczos", "sharp": "lanczos", "bicubic": "bicubic"}
LABELS = {"lanczos": "Lanczos", "sharp": "sharpened", "bicubic": "bicubic", "ai": "AI"}
LIMIT = 4096  # longest side written here; beyond it most machines have no encoder
MODEL = re.compile(r"^[a-z]{2,8}-\d{1,3}$")
POLL = 5.0  # seconds between Topaz status queries


class UpscaleBody(BaseModel):
    method: str = "lanczos"
    factor: float = Field(2.0, gt=1.0, le=4.0)
    model: str = "prob-4"
    request_id: str | None = None


class TopazError(RuntimeError):
    """Topaz refused, failed, or could not be reached; the message says which."""


def _even(value: float) -> int:
    return max(2, round(value / 2) * 2)


def _source(media_id: str) -> tuple[dict, Path]:
    item = media._find(media_id)
    if item.get("kind") not in ("video", "image"):
        raise HTTPException(422, "only video and stills can be upscaled")
    matches = sorted(media.MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(404, "file missing")
    if not item.get("width") or not item.get("height"):
        raise HTTPException(422, "the source has no picture size")
    return item, matches[0]


def _fits(item: dict, factor: float) -> None:
    longest = max(item["width"], item["height"]) * factor
    if longest > LIMIT:
        raise HTTPException(422, f"{factor:g}x would make the long side {round(longest)} pixels; the limit here is {LIMIT}")


def _named(item: dict, factor: float, label: str, suffix: str) -> str:
    stem = Path(item["name"]).stem or item["name"]
    return f"{stem} {factor:g}x {label}{suffix}"


def _still(source: Path, out: Path, factor: float, method: str) -> None:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        image = image.convert("RGBA" if "A" in image.getbands() or image.mode == "P" else "RGB")
        resample = Image.Resampling.BICUBIC if method == "bicubic" else Image.Resampling.LANCZOS
        large = image.resize((_even(image.width * factor), _even(image.height * factor)), resample)
    if method == "sharp":
        large = large.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=0))
    large.save(out, "PNG")


def _encoder() -> str:
    return next(filter(None, (encoders.choose(codec) for codec in encoders.CONTAINERS["mp4"])), "mpeg4")


def _video(source: Path, out: Path, factor: float, method: str, seconds: float, report, cancelled) -> None:
    # Sizes come from the decoded frames, which ffmpeg has already turned upright,
    # so a phone clip flagged as rotated is not stretched.
    chain = f"scale=trunc(iw*{factor}/2)*2:trunc(ih*{factor}/2)*2:flags={ALGORITHMS[method]}+accurate_rnd+full_chroma_int"
    if method == "sharp":
        chain += ",unsharp=5:5:0.6"
    encoder = _encoder()
    device, upload = encoders.hardware_io(encoder)
    if upload:
        chain += f",{upload}"
    program = shutil.which("ffmpeg") or "ffmpeg"
    command = [program, "-v", "error", "-nostdin", "-y", *device, "-i", str(source), "-map", "0:v:0", "-map", "0:a?", "-vf", chain]
    pixels = [] if upload else ["-pix_fmt", "yuv420p"]
    command += ["-c:v", encoder, *encoders.tier_flags(encoder, "high"), *pixels, "-c:a", "aac", "-b:a", "192k"]
    command += ["-movflags", "+faststart", "-progress", "pipe:1", str(out)]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        for line in process.stdout:
            if cancelled():
                process.kill()
                raise InterruptedError
            key, _, value = line.strip().partition("=")
            if key == "out_time_us" and value.isdigit() and seconds > 0:
                report(int(value) / 1e6 / seconds)
        errors = process.stderr.read()
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg could not upscale this clip: {errors.strip()[-400:]}")


def _algorithmic(item: dict, source: Path, body: UpscaleBody):
    def operation(job_id: str, report, cancelled) -> dict:
        with tempfile.TemporaryDirectory(prefix="formcut-upscale-") as scratch:
            suffix = ".png" if item["kind"] == "image" else ".mp4"
            out = Path(scratch) / f"upscaled{suffix}"
            if item["kind"] == "image":
                _still(source, out, body.factor, body.method)
            else:
                _video(source, out, body.factor, body.method, float(item.get("duration") or 0), report, cancelled)
            extra = {"upscaledFrom": item["id"], "upscale": {"method": body.method, "factor": body.factor}}
            return {"media": media.ingest_path(out, _named(item, body.factor, LABELS[body.method], suffix), extra)}

    return operation


def _ai(item: dict, source: Path, body: UpscaleBody):
    """Real-ESRGAN on this machine: a still at once, a clip frame by frame."""

    def operation(job_id: str, report, cancelled) -> dict:
        with tempfile.TemporaryDirectory(prefix="formcut-upscale-") as scratch:
            suffix = ".png" if item["kind"] == "image" else ".mp4"
            out = Path(scratch) / f"upscaled{suffix}"
            if item["kind"] == "image":
                with Image.open(source) as image:
                    ai_upscale.upscale_image(ImageOps.exif_transpose(image), body.factor).save(out)
            else:
                fps = float(item.get("fps") or 30.0)
                frames = round(fps * float(item.get("duration") or 0))
                ai_upscale.upscale_video(source, out, int(item["width"]), int(item["height"]), fps, body.factor, frames, report, cancelled)
            extra = {"upscaledFrom": item["id"], "upscale": {"method": "ai", "model": ai_upscale.MODEL, "factor": body.factor}}
            return {"media": media.ingest_path(out, _named(item, body.factor, LABELS["ai"], suffix), extra)}

    return operation


# Topaz ---------------------------------------------------------------------------


def _topaz(method: str, path: str, **kwargs) -> dict:
    key = providers.key_for("topaz")
    if not key:
        raise TopazError("No Topaz key. Add one in Settings, or set TOPAZ_API_KEY.")
    headers = {"X-API-Key": key, "accept": "application/json"}
    try:
        response = httpx.request(method, f"{providers.base_for('topaz')}{path}", headers=headers, timeout=60.0, **kwargs)
    except httpx.HTTPError as error:
        raise TopazError(f"Could not reach Topaz: {error.__class__.__name__}") from error
    if response.status_code >= 400:
        try:
            detail = response.json().get("message") or response.text
        except ValueError:
            detail = response.text
        raise TopazError(f"Topaz answered HTTP {response.status_code}: {str(detail)[:300]}")
    return response.json() if response.content else {}


def _request_body(item: dict, source: Path, factor: float, model: str) -> dict:
    rate = float(item.get("fps") or 30.0)
    seconds = float(item.get("duration") or 0.0)
    size = {"width": item["width"], "height": item["height"]}
    target = {"width": _even(item["width"] * factor), "height": _even(item["height"] * factor)}
    return {
        "source": {
            "resolution": size,
            "container": source.suffix.lstrip(".").lower() or "mp4",
            "size": source.stat().st_size,
            "duration": seconds,
            "frameRate": rate,
            "frameCount": max(1, round(seconds * rate)),
        },
        "output": {
            "resolution": target,
            "frameRate": rate,
            "audioCodec": "AAC",
            "audioTransfer": "Copy",
            "dynamicCompressionLevel": "High",
            "container": "mp4",
        },
        "filters": [{"model": model, "videoType": "Progressive", "auto": "Auto"}],
    }


def _upload(source: Path, urls: list[str], report, cancelled) -> tuple[list[dict], str]:
    """Equal byte ranges, one PUT a part, retried on the same URL; the key never goes to storage."""
    size = source.stat().st_size
    part = math.ceil(size / len(urls))
    digest = hashlib.md5(usedforsecurity=False)
    results = []
    with source.open("rb") as handle, httpx.Client(timeout=600.0) as client:
        for number, url in enumerate(urls, start=1):
            chunk = handle.read(part)
            if not chunk:
                break
            digest.update(chunk)
            for attempt in range(3):
                if cancelled():
                    raise InterruptedError
                try:
                    response = client.put(url, content=chunk)
                except httpx.HTTPError as error:
                    if attempt == 2:
                        raise TopazError(f"Upload of part {number} failed: {error.__class__.__name__}") from error
                    continue
                if response.status_code < 300:
                    break
                if attempt == 2:
                    raise TopazError(f"Upload of part {number} failed: HTTP {response.status_code}")
            results.append({"partNum": number, "eTag": response.headers.get("ETag", "").strip('"')})
            report(0.4 * number / len(urls))
    return results, digest.hexdigest()


def _topaz_job(item: dict, source: Path, body: UpscaleBody):
    def operation(job_id: str, report, cancelled) -> dict:
        request_id = body.request_id
        accepted = _topaz("PATCH", f"/video/{request_id}/accept")
        parts, md5 = _upload(source, accepted["urls"], report, cancelled)
        _topaz("PATCH", f"/video/{request_id}/complete-upload/", json={"uploadResults": parts, "md5Hash": md5})
        while True:
            if cancelled():
                raise InterruptedError
            state = _topaz("GET", f"/video/{request_id}/status")
            report(0.4 + 0.55 * min(100.0, float(state.get("progress") or 0)) / 100)
            if state.get("status") == "complete":
                link = (state.get("download") or {}).get("url")
                if not link:
                    raise TopazError("Topaz finished but sent no download link")
                break
            if state.get("status") in ("failed", "canceled", "canceling"):
                raise TopazError(f"Topaz reported {state['status']}: {state.get('message') or 'no reason given'}")
            time.sleep(POLL)
        with tempfile.TemporaryDirectory(prefix="formcut-topaz-") as scratch:
            out = Path(scratch) / "topaz.mp4"
            try:
                with httpx.stream("GET", link, timeout=600.0) as response:
                    response.raise_for_status()
                    with out.open("wb") as handle:
                        for chunk in response.iter_bytes(1 << 20):
                            handle.write(chunk)
            except httpx.HTTPError as error:
                raise TopazError(f"Could not download the result: {error.__class__.__name__}") from error
            extra = {
                "upscaledFrom": item["id"],
                "upscale": {"method": "topaz", "factor": body.factor, "model": body.model, "request": request_id},
            }
            return {"media": media.ingest_path(out, _named(item, body.factor, f"Topaz {body.model}", ".mp4"), extra)}

    return operation


# Routes --------------------------------------------------------------------------


@router.post("/{media_id}/upscale/estimate")
def estimate(media_id: str, body: UpscaleBody) -> dict:
    """Create the Topaz request, which is free, and return its estimate before any credit is spent."""
    item, source = _source(media_id)
    if item["kind"] != "video":
        raise HTTPException(422, "Topaz upscales video; stills use the methods here")
    if not MODEL.match(body.model):
        raise HTTPException(422, f"{body.model!r} is not a Topaz model name")
    try:
        reply = _topaz("POST", "/video/", json=_request_body(item, source, body.factor, body.model))
    except TopazError as error:
        raise HTTPException(502, str(error)) from error
    estimates = reply.get("estimates") or {}
    target = {"width": _even(item["width"] * body.factor), "height": _even(item["height"] * body.factor)}
    return {"request_id": reply.get("requestId"), "credits": estimates.get("cost"), "seconds": estimates.get("time"), **target}


@router.post("/{media_id}/upscale")
def upscale(media_id: str, body: UpscaleBody) -> dict:
    """Start the upscale as a job; the result arrives in the bin as a new item."""
    item, source = _source(media_id)
    if body.method == "topaz":
        if not body.request_id:
            raise HTTPException(422, "ask for an estimate first; its request id starts the Topaz job")
        return jobs.submit("upscale", _topaz_job(item, source, body))
    if body.method == "ai":
        if not model_manager.ready(ai_upscale.MODEL):
            raise HTTPException(409, "AI upscaling needs its model (64 MB) downloaded first")
        _fits(item, body.factor)
        return jobs.submit("upscale", _ai(item, source, body))
    if body.method not in ALGORITHMS:
        raise HTTPException(422, f"unknown method {body.method!r}")
    _fits(item, body.factor)
    return jobs.submit("upscale", _algorithmic(item, source, body))
