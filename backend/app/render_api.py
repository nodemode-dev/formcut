import hashlib
import io
import json
import math
import os
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field

from . import fast_export, fast_layers, gif_export, gpu, jobs, openh264, webhooks
from .audio_render import RATE, processed_clip_audio, render_audio
from .encoders import CONTAINERS, addon_binary_for, estimate_bitrate, estimate_size, hardware_io, pixel_format, supports_ten_bit, tier_flags
from .encoders import choose as choose_encoder
from .encoders import status as encoder_status
from .frame_cache import FrameCache, ReadAhead
from .matte_cache import matte_key, sample_times
from .matte_cache import progress as matte_progress
from .matte_cache import store as matte_store
from .media import MEDIA_DIR, reversed_path
from .media import has_audio as media_has_audio
from .paths import DATA_DIR
from .render_document import validate_document
from .renderer import FrameRenderer

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
    codec: str | None = None
    tenBit: bool = False
    # Render every frame as the preview shows it, instead of the faster layered graph
    # whose colours can differ slightly (41 dB for a graded clip, measured).
    exact: bool = False
    size: str | None = None
    rate: str | None = None


def checked(body: RenderInput) -> dict:
    try:
        return validate_document(body.project)
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/status")
def capabilities():
    encoders = encoder_status()
    return {
        "compositor": gpu.status(),
        "shared_preview_export": True,
        "formats": ["mp4", "webm", "gif"],
        "frame_format": "png",
        "encoders": encoders,
        "tenBit": {codec: supports_ten_bit(codec) for codec in ("h264", "hevc", "av1", "vp9")},
        "sizes": list(SIZE_PRESETS),
        "rates": list(RATE_PRESETS),
        "codecs": encoders["containers"],
    }


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
            # Read-ahead feeds playback, which may use proxies.
            with lock:
                renderer.allow_proxy = True
                try:
                    return renderer.frame(at)
                finally:
                    renderer.allow_proxy = False

        _sessions[session_id] = {
            "renderer": renderer,
            "lock": lock,
            "touched": time.monotonic(),
            "cache": cache,
            "ahead": ReadAhead(render_locked, cache, project["fps"]),
        }
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
        # A still frame is the one a person judges the export by, so it is drawn
        # from the original; the tag keeps those frames apart from proxy frames.
        tag = "orig"
        pixels = cache.get(time, tag)
        served = "hit"
        if pixels is None:
            served = "miss"
            with item["lock"]:
                item["renderer"].allow_proxy = False
                pixels = item["renderer"].frame(time)
            cache.put(time, pixels, tag)
        item["ahead"].seek(time)
        output = io.BytesIO()
        Image.fromarray(pixels).save(output, format="PNG", compress_level=1)
        return Response(output.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store", "x-formcut-frame": served})
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


SIZE_PRESETS = {"720p": 720, "1080p": 1080, "1440p": 1440, "2160p": 2160}
# X4: rates stored as exact fractions; integer rates stay acceptable.
RATE_PRESETS = {
    "23.976": (24000, 1001),
    "24": (24, 1),
    "25": (25, 1),
    "29.97": (30000, 1001),
    "30": (30, 1),
    "50": (50, 1),
    "59.94": (60000, 1001),
    "60": (60, 1),
}


def resize_for(project: dict, size: str | None) -> tuple[int, int]:
    """A preset names the SHORT side; the timeline's aspect decides the rest."""
    width, height = int(project["width"]), int(project["height"])
    short = SIZE_PRESETS.get(size or "")
    if not short:
        return width, height
    if width <= height:
        out_w = short
        out_h = max(2, round(short * height / width))
    else:
        out_h = short
        out_w = max(2, round(short * width / height))
    return out_w - (out_w % 2), out_h - (out_h % 2)


def export_media(
    project: dict,
    job_id: str,
    report,
    cancelled,
    format: str,
    quality: str,
    codec_name: str | None = None,
    ten_bit: bool = False,
    size: str | None = None,
    rate: str | None = None,
    exact: bool = False,
) -> dict:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    path = OUTPUTS / (job_id + "." + format)
    audio = OUTPUTS / (job_id + ".wav")
    log = OUTPUTS / (job_id + ".log")
    renderer = FrameRenderer(project)
    process = None
    final, cisco = path, None
    try:
        render_audio(project, audio, cancelled)
        report(0.1)
        fps = project["fps"]
        # Phase 10: a GIF has no encoder to choose. Whichever path renders
        # writes the lossless intermediate, and finish() encodes it as a
        # two-pass palette GIF (gif_export.py), the tier deciding the palette.
        gif = format == "gif"
        # X2: choose the codec the caller asked for when this build can encode
        # it, else the container's default; hardware is preferred inside choose.
        wanted = "gif" if gif else codec_name or ("h264" if format == "mp4" else "vp9")
        encoder = None if gif else choose_encoder(wanted)
        # H.264 with no encoder on this computer: Cisco's OpenH264, fetched the
        # first time an export needs it, unless it is turned off (openh264.py).
        cisco = openh264.library(download=True) if not gif and not encoder and wanted == "h264" else None
        if cisco:
            encoder = "libopenh264"
        # Else the container's other codecs, best first. MPEG-4 Part 2 is used
        # only when asked for by name: players take it, but it looks its age.
        for fallback in CONTAINERS.get(format, ()):
            if encoder:
                break
            if fallback != "mpeg4":
                encoder, wanted = choose_encoder(fallback), fallback
        fell_back = None
        if not encoder and format == "mp4":
            # No MP4 encoder at all here: WebM, which formcut's ffmpeg writes on
            # every computer. The result says so, and the file is .webm.
            format, wanted, encoder, fell_back = "webm", "vp9", choose_encoder("vp9"), "webm"
            path = final = OUTPUTS / (job_id + ".webm")
        if not encoder and not gif:
            raise ValueError("This build has no working video encoder")
        speed = ["-preset", "veryfast"] if encoder in ("libx264", "libx265") else (["-cpu-used", "5"] if encoder == "libvpx-vp9" else [])
        pix = pixel_format(encoder or "", ten_bit)
        # VA-API takes frames in video memory: its device before the inputs and an
        # upload ending the filter chain, which the frame path's one chain can
        # take, so such exports go through the frame path.
        device, upload = hardware_io(encoder or "")
        out_w, out_h = resize_for(project, size)
        num, den = RATE_PRESETS.get(rate or "", (0, 0))
        out_rate = f"{num}/{den}" if num else str(fps)
        # `audio` is already the temporary wav path in this scope, so the audio
        # codec flags need their own name.
        audio_flags = ["-c:a", "aac"] if format == "mp4" else ["-c:a", "libopus"]
        # The colour-managed pipeline lands every source in BT.709 (tone-mapped
        # or converted at decode), so the file says so; an untagged file is
        # guessed at by players, and not always the same way.
        colour_tags = ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv"]
        codec = ["-c:v", encoder, *speed, *tier_flags(encoder, quality), *colour_tags, *audio_flags] if encoder else []
        count = math.ceil(project["duration"] * fps)
        if cisco or gif:
            # Whichever path renders writes a lossless intermediate, and finish()
            # encodes it through OpenH264 or the GIF palette: the same pixels any
            # encoder would get.
            path = OUTPUTS / (job_id + ".intermediate.mkv")
            codec, pix = ["-c:v", "ffv1", "-level", "3", "-c:a", "pcm_s16le"], "yuv420p"
            outer_report = report

            def report(fraction: float) -> None:
                outer_report(fraction * 0.6)

        def finish(result: dict) -> dict:
            if fell_back:
                result["fellBackTo"] = fell_back
            if gif:
                gif_export.encode(path, final, quality, lambda done: outer_report(0.6 + 0.4 * done), cancelled)
                path.unlink(missing_ok=True)
                return {**result, "file": str(final), "media_type": "image/gif", "codec": "gif", "encoder": "gif", "pixelFormat": "pal8"}
            if not cisco:
                return result
            bits = round(estimate_bitrate("h264", out_w, out_h, float(Fraction(out_rate)), quality) * 1000 * 1.3)
            openh264.encode_mp4(
                cisco, path, final, out_w, out_h, out_rate, bits, lambda done: outer_report(0.6 + 0.4 * done), cancelled, log
            )
            path.unlink(missing_ok=True)
            return {**result, "file": str(final), "encoder": "libopenh264", "pixelFormat": "yuv420p"}

        # An H.264 add-on the person installed runs from its own binary; the
        # bundled LGPL ffmpeg drives everything else.
        program = str(addon_binary_for(encoder) or "ffmpeg")
        native = None if os.environ.get("FORMCUT_EXPORT_PATH") == "frames" or upload else fast_export.plan(project, count)
        if native is not None:
            fast_export.run(
                native, program, audio, [*codec, "-pix_fmt", pix], out_w, out_h, out_rate, project["duration"], path, log, report, cancelled
            )
            return finish(
                {
                    "file": str(path),
                    "name": "formcut-export." + format,
                    "media_type": "video/mp4" if format == "mp4" else "video/webm",
                    "frames": count,
                    "width": out_w,
                    "height": out_h,
                    "codec": wanted,
                    "encoder": encoder,
                    "pixelFormat": pix,
                    "rate": out_rate,
                    "renderPath": "native",
                }
            )
        layered = (
            None if native is not None or os.environ.get("FORMCUT_EXPORT_PATH") == "frames" or upload else fast_layers.plan(project, count)
        )
        if layered is not None and exact and os.environ.get("FORMCUT_EXPORT_PATH") != "layered":
            # Exact colours: the frame path renders what the preview shows. The graph is
            # the default because it is the faster route: 1.7x to 1.9x on a 10-core Mac
            # with the Rust kernels, its colours identical or within 41 to 48 dB.
            # FORMCUT_EXPORT_PATH=layered keeps the graph regardless.
            layered = None
        if layered is not None:
            fast_layers.run(
                layered,
                program,
                audio,
                [*codec, "-pix_fmt", pix],
                out_w,
                out_h,
                out_rate,
                project["duration"],
                path,
                log,
                report,
                cancelled,
            )
            return finish(
                {
                    "file": str(path),
                    "name": "formcut-export." + format,
                    "media_type": "video/mp4" if format == "mp4" else "video/webm",
                    "frames": count,
                    "width": out_w,
                    "height": out_h,
                    "codec": wanted,
                    "encoder": encoder,
                    "pixelFormat": pix,
                    "rate": out_rate,
                    "renderPath": "layered",
                }
            )
        command = [
            program,
            "-v",
            "error",
            "-y",
            *device,
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-s",
            f"{renderer.width}x{renderer.height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-i",
            str(audio),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-vf",
            f"scale={out_w}:{out_h},pad=ceil(iw/2)*2:ceil(ih/2)*2" + (f",{upload}" if upload else ""),
            "-r",
            out_rate,
            *codec,
            *([] if upload else ["-pix_fmt", pix]),
            "-t",
            str(project["duration"]),
            str(path),
        ]
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
                    # The pipe takes the array's own memory, the bytes tobytes()
                    # made a copy of, in the same order: 5 ms a 1080p frame saved.
                    process.stdin.write(np.ascontiguousarray(renderer.frame(i / fps)))
                    report(0.1 + 0.85 * (i + 1) / count)
            process.stdin.close()
            process.wait(timeout=600)
        if process.returncode:
            raise ValueError(log.read_text(errors="replace")[-2000:])
        return finish(
            {
                "file": str(path),
                "name": "formcut-export." + format,
                "media_type": "video/mp4" if format == "mp4" else "video/webm",
                "frames": count,
                "width": out_w,
                "height": out_h,
                "codec": wanted,
                "encoder": encoder,
                "pixelFormat": pix,
                "rate": out_rate,
                "renderPath": "frames",
            }
        )
    except BaseException:
        if process and process.poll() is None:
            process.kill()
            process.wait()
        path.unlink(missing_ok=True)
        final.unlink(missing_ok=True)
        raise
    finally:
        renderer.close()
        audio.unlink(missing_ok=True)
        log.unlink(missing_ok=True)


@router.post("/export", status_code=202)
def export(body: RenderInput):
    project = checked(body)
    if body.format not in ("mp4", "webm", "gif") or body.quality not in ("high", "medium", "low"):
        raise HTTPException(422, "Unknown export format or quality")
    if body.size is not None and body.size not in SIZE_PRESETS:
        raise HTTPException(422, "Unknown export size")
    if body.rate is not None and body.rate not in RATE_PRESETS:
        raise HTTPException(422, "Unknown export rate")
    if body.codec is not None:
        allowed = encoder_status()["containers"].get(body.format, [])
        if body.codec not in allowed:
            raise HTTPException(422, f"{body.codec} is not available for {body.format} on this machine")

    def operation(job_id, report, cancelled):
        result = export_media(
            project, job_id, report, cancelled, body.format, body.quality, body.codec, body.tenBit, body.size, body.rate, body.exact
        )
        webhooks.announce_export(result, project)
        return result

    return jobs.submit("export", operation)


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
    signature = hashlib.sha1(
        json.dumps(
            {
                k: clip.get(k)
                for k in (
                    "mediaId",
                    "sourceIn",
                    "duration",
                    "extendOut",
                    "speed",
                    "speedCurve",
                    "reversed",
                    "audioEffects",
                    "audioFx",
                    "audioStream",
                )
            },
            sort_keys=True,
            default=str,
        ).encode(),
        usedforsecurity=False,
    ).hexdigest()[:20]
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
    return Response(
        path.read_bytes(),
        media_type="application/octet-stream",
        headers={"x-formcut-rate": str(RATE), "x-formcut-signature": signature, "Cache-Control": "no-store"},
    )


class MatteInput(BaseModel):
    clip: dict
    fps: float = 30.0
    # The canvas the clip is placed on, so a prompt made on the picture can be
    # carried back to the clip's own pixels. Without it prompts are used as sent.
    width: int | None = None
    height: int | None = None


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
    from .timing import source_time

    # Mattes are looked up by source time, so they are made at the clip's own
    # source times. Sampling from zero made a trimmed clip's mattes from the
    # wrong part of its file.
    times = [round(source_time(clip, local), 4) for local in sample_times(duration, body.fps)]
    done = matte_progress(key, duration, body.fps)
    if done["ready"]:
        return {"status": "ready", **done}

    def operation(job_id, report, cancelled):
        from .prompt_space import to_source
        from .segmentation import VideoMatter, prompts, raw_alpha

        matter = VideoMatter() if model == "video-matting" else None
        points, box = prompts(options)
        renderer = FrameRenderer(
            {
                "title": "matte",
                "width": 640,
                "height": 360,
                "fps": body.fps,
                "duration": max(0.1, duration),
                "activeTimeline": 0,
                "timelines": [
                    {"id": "m", "name": "m", "tracks": [{"id": "t", "name": "V", "clips": [{**clip, "start": 0, "cutout": None}]}]}
                ],
            }
        )
        from .model_manager import ready as model_ready
        from .sam_video import VideoTracker

        prompted = [*points, *([box] if box else [])]
        made = next((float(p["t"]) for p in prompted if isinstance(p.get("t"), (int, float)) and not isinstance(p.get("t"), bool)), 0.0)
        seed_at = source_time(clip, made)
        tracking = model == "click-select" and clip.get("kind") == "video" and bool(prompted) and model_ready("click-track")

        def placed(frame):
            if body.width and body.height and (points or box):
                return to_source(clip, (body.width, body.height), (frame.shape[1], frame.shape[0]), points, box)
            return points, box

        try:
            if tracking:
                # SAM 2.1 follows the subject: forward from the frame the prompt
                # was made on, then backward from it, each with its own tracker.
                seed = min(range(len(times)), key=lambda index: abs(times[index] - seed_at))
                done = 0
                for run, indices in enumerate((range(seed, len(times)), range(seed, -1, -1))):
                    tracker = None
                    for index in indices:
                        if cancelled():
                            raise InterruptedError("Cancelled")
                        frame = renderer.media_frame(clip, times[index])
                        if tracker is None:
                            tracker = VideoTracker(*placed(frame), len(times))
                        alpha = tracker(frame)
                        if run == 0 or index != seed:
                            matte_store(key, times[index], alpha)
                            done += 1
                            report(done / len(times))
            else:
                for index, at in enumerate(times):
                    if cancelled():
                        raise InterruptedError("Cancelled")
                    frame = renderer.media_frame(clip, at)
                    here, there = placed(frame)
                    matte_store(key, at, matter(frame) if matter else raw_alpha(frame, model, here, there))
                    report((index + 1) / len(times))
        finally:
            renderer.close()
        return {"status": "ready", **matte_progress(key, duration, body.fps)}

    return jobs.submit("mattes", operation)


@router.get("/mattes/{key}")
def matte_status(key: str, duration: float = 1.0, fps: float = 30.0):
    return matte_progress(key, duration, fps)


class EstimateInput(BaseModel):
    project: dict
    quality: str = "high"
    codec: str | None = None
    format: str = "mp4"
    size: str | None = None
    rate: str | None = None


@router.post("/sample")
def sample_frame(body: dict) -> dict:
    """Colour statistics of one rendered frame, for colour matching.

    The reference a person means is the frame they are looking at, so this
    renders that moment and returns the numbers rather than asking them to
    describe a look in words.
    """
    from .pixel_effects import reference_statistics

    project = validate_document(body.get("project") or {})
    renderer = FrameRenderer(project, 480)
    try:
        pixels = renderer.frame(max(0.0, float(body.get("time") or 0)))
    finally:
        renderer.close()
    return reference_statistics(pixels[:, :, :3].astype("float32") / 255)


@router.post("/estimate")
def estimate(body: EstimateInput):
    """X5: the export sheet's live size estimate, per tier."""
    project = checked(RenderInput(project=body.project, format=body.format, quality=body.quality))
    width, height = resize_for(project, body.size)
    num, den = RATE_PRESETS.get(body.rate or "", (0, 0))
    fps = (num / den) if num else float(project["fps"])
    # A video clip is only audible if its media actually carries sound; counting
    # every video clip as audible added 128 kbit/s that the export never spends.
    audible = any(
        clip.get("kind") in ("audio", "video") and not clip.get("muted") and clip.get("mediaId") and media_has_audio(str(clip["mediaId"]))
        for timeline in project["timelines"]
        for track in timeline["tracks"]
        for clip in track["clips"]
    )
    codec = body.codec or ("h264" if body.format == "mp4" else "gif" if body.format == "gif" else "vp9")
    if body.format == "gif":
        audible = False
    return {
        "tiers": {tier: estimate_size(codec, width, height, fps, tier, project["duration"], audible) for tier in ("high", "medium", "low")},
        "width": width,
        "height": height,
        "fps": fps,
        "codec": codec,
    }
