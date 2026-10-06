import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field

from . import alpha_export, encoders, fast_export, fast_layers, gif_export, gpu, jobs, openh264, webhooks
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
from .renderer import FrameRenderer, rolloff_for_display

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
    transparent: bool = False  # no background, alpha kept: format mov (ProRes 4444), webm (VP9 alpha) or png (a zip)
    audioBitrate: int | None = Field(default=None, ge=64, le=512)  # kbps; the encoder's default when unset
    loudness: float | None = Field(default=None, ge=-40, le=-5)  # integrated LUFS target; the mix as made when unset
    truePeak: float = Field(default=-1.0, ge=-9, le=0)  # dBTP the loudness gain never pushes past


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
                    # step 4 of the HDR working space: a deep frame is rolled off for the SDR monitor here,
                    # after the whole frame is composed, so the edit happens in the transfer and only the
                    # picture shown is SDR
                    return rolloff_for_display(renderer.frame(at), renderer.transfer)
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


def forget_media(media_id: str) -> None:
    """A relinked media item: each preview session's renderer forgets where its file was and what it drew from it."""
    with _lock:
        items = list(_sessions.values())
    for item in items:
        renderer = item.get("renderer")
        known = getattr(renderer, "_media_known", None)
        if isinstance(known, dict):
            known.pop(media_id, None)
        cache = item["cache"]
        with cache.lock:
            cache.frames.clear()


def release_frames() -> int:
    """The preview's cached frames let go, for a local image model that needs the memory more (up to 240 frames a
    session, over a gigabyte at 1080p): the preview draws them again when they are asked for. Returns the bytes."""
    import gc

    freed = 0
    with _lock:
        items = list(_sessions.values())
    for item in items:
        cache = item["cache"]
        with cache.lock:
            freed += sum(int(getattr(frame, "nbytes", 0)) for frame in cache.frames.values())
            cache.frames.clear()
    gc.collect()
    return freed


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


_LIGHT_TABLES: dict[str, np.ndarray] = {}


def _frame_tags(colour_tags: list) -> str:
    """A setparams filter that tags the frames with the export's own colour (primaries, transfer, matrix, range),
    so the encoder's tags match the frames' and FFmpeg's colour negotiation (7.1 and later) inserts no scaler."""
    names = {"-color_primaries": "color_primaries", "-color_trc": "color_trc", "-colorspace": "colorspace", "-color_range": "range"}
    pairs = [f"{names[flag]}={value}" for flag, value in zip(colour_tags[::2], colour_tags[1::2], strict=False) if flag in names]
    return "setparams=" + ":".join(pairs) if pairs else "null"


def _box(kind: bytes, payload: bytes) -> bytes:
    return (8 + len(payload)).to_bytes(4, "big") + kind + payload


def write_light_boxes(path: Path, max_cll: int, max_fall: int) -> bool:
    """Write MaxCLL and MaxFALL into an MP4 or MOV the encoder could not tag: a clli box (the content light
    levels) and an mdcv box (the mastering display, the BT.2020 primaries and D65 the x265 path declares, peak
    at the measured light) appended to the video sample entry. The boxes above it grow by their size and, when
    the movie box sits before the media data (a fast-start file), every chunk offset moves by the same amount.
    Returns whether the boxes were written; a file already carrying them, or not laid out as expected, is left
    as it was."""
    data = bytearray(path.read_bytes())
    extra = _box(
        b"mdcv",
        b"".join(v.to_bytes(2, "big") for v in (13250, 34500, 7500, 3000, 34000, 16000, 15635, 16450))
        + (max(max_cll, 1) * 10000).to_bytes(4, "big")
        + (50).to_bytes(4, "big"),
    )
    extra += _box(b"clli", max(0, min(max_cll, 65535)).to_bytes(2, "big") + max(0, min(max_fall, 65535)).to_bytes(2, "big"))

    def children(start: int, end: int):
        at = start
        while at + 8 <= end:
            size = int.from_bytes(data[at : at + 4], "big")
            kind = bytes(data[at + 4 : at + 8])
            head = 8
            if size == 1:
                size, head = int.from_bytes(data[at + 8 : at + 16], "big"), 16
            elif size == 0:
                size = end - at
            if size < head or at + size > end:
                return
            yield at, size, kind, head
            at += size

    top = list(children(0, len(data)))
    moov = next((b for b in top if b[2] == b"moov"), None)
    mdat = next((b for b in top if b[2] == b"mdat"), None)
    if moov is None or moov[3] != 8:
        return False
    chain, entry = None, None
    for trak in children(moov[0] + 8, moov[0] + moov[1]):
        if trak[2] != b"trak":
            continue
        path_boxes = [moov, trak]
        node = trak
        for want in (b"mdia", b"minf", b"stbl", b"stsd"):
            node = next((b for b in children(node[0] + node[3], node[0] + node[1]) if b[2] == want), None)
            if node is None:
                break
            path_boxes.append(node)
        if node is None:
            continue
        # stsd: version and flags, an entry count, then the sample entries; a visual one carries 78 bytes of
        # fields before its own children
        for sample in children(node[0] + 16, node[0] + node[1]):
            if sample[2] in (b"hvc1", b"hev1", b"av01", b"avc1", b"avc3", b"vp09", b"dvh1", b"dvhe"):
                inner = list(children(sample[0] + 8 + 78, sample[0] + sample[1]))
                if any(b[2] in (b"clli", b"mdcv") for b in inner):
                    return False
                chain, entry = path_boxes, sample
                break
        if entry is not None:
            break
    if entry is None or any(b[3] != 8 for b in [*chain, entry]):
        return False
    grow = len(extra)
    insert_at = entry[0] + entry[1]
    for at, size, _kind, _head in [*chain, entry]:
        data[at : at + 4] = (size + grow).to_bytes(4, "big")
    data[insert_at:insert_at] = extra
    if mdat is not None and mdat[0] > moov[0]:
        # a fast-start file: the media data moved down by the boxes' size, so every chunk offset does too
        def shift(start: int, end: int):
            for at, size, kind, head in children(start, end):
                if kind in (b"trak", b"mdia", b"minf", b"stbl", b"edts"):
                    shift(at + head, at + size)
                elif kind in (b"stco", b"co64"):
                    wide = kind == b"co64"
                    n = int.from_bytes(data[at + head + 4 : at + head + 8], "big")
                    for k in range(n):
                        pos = at + head + 8 + k * (8 if wide else 4)
                        width = 8 if wide else 4
                        value = int.from_bytes(data[pos : pos + width], "big") + grow
                        data[pos : pos + width] = value.to_bytes(width, "big")

        shift(moov[0] + 8, moov[0] + moov[1] + grow)
    temporary = path.with_suffix(path.suffix + ".light")
    temporary.write_bytes(bytes(data))
    os.replace(temporary, path)
    return True


def _timing(stamps: dict, count: int) -> dict:
    """The export in parts, milliseconds: until the first frame reached the encoder, the frames after it (and
    their steady rate), the encoder's finish. A short export is mostly start-up; the steady rate is the one
    that decides a long one."""
    if "first" not in stamps:
        return {}
    first = (stamps["first"] - stamps["began"]) * 1000
    frames = (stamps.get("last", stamps["first"]) - stamps["first"]) * 1000
    finish = (stamps.get("done", stamps.get("last", stamps["first"])) - stamps.get("last", stamps["first"])) * 1000
    steady = (count - 1) / (frames / 1000) if count > 1 and frames > 0 else 0.0
    each = max(1, count)
    return {
        "startupMs": round(first, 1),
        "framesMs": round(frames, 1),
        "finishMs": round(finish, 1),
        "steadyFps": round(steady, 2),
        # a frame's wait on each side of the loop: on the renderer for the next frame, on the pipe to the encoder
        "renderWaitMs": round(stamps.get("render_wait", 0.0) * 1000 / each, 2),
        "writeMs": round(stamps.get("write", 0.0) * 1000 / each, 2),
    }


def _light_table(transfer: str) -> np.ndarray:
    """Nits for every sixteen-bit code value of the transfer, once."""
    table = _LIGHT_TABLES.get(transfer)
    if table is None:
        from .gpu import _to_linear

        codes = np.arange(65536, dtype=np.float64) / 65535
        table = (_to_linear(codes, transfer) * (10000.0 if transfer == "pq" else 1000.0)).astype(np.float32)
        _LIGHT_TABLES[transfer] = table
    return table


def _to_planes(frame: np.ndarray, layout: str = "yuv420p10le") -> np.ndarray:
    """A deep RGBA frame as yuv420p10le planes on the CPU, for the frame the device did not pack: the BT.2020
    matrix in limited range, chroma the mean of each 2x2 block, the same arithmetic as the device's pack."""
    rgb = frame[:, :, :3].astype(np.float32) / 65535
    y = 0.2627 * rgb[:, :, 0] + 0.6780 * rgb[:, :, 1] + 0.0593 * rgb[:, :, 2]
    cb = (rgb[:, :, 2] - y) / 1.8814
    cr = (rgb[:, :, 0] - y) / 1.4746
    h, w = y.shape
    cb2 = cb.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))
    cr2 = cr.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))
    code = lambda v, offset, span: np.clip(np.round((offset + span * v) * 4), 0, 1023).astype(np.uint16)  # noqa: E731
    if layout == "p010le":
        chroma = np.stack([code(cb2, 128, 224), code(cr2, 128, 224)], axis=-1)
        return np.concatenate([(code(y, 16, 219) << 6).ravel(), (chroma << 6).ravel()]).view(np.uint8)
    return np.concatenate([code(y, 16, 219).ravel(), code(cb2, 128, 224).ravel(), code(cr2, 128, 224).ravel()]).view(np.uint8)


def _light_of(frame: np.ndarray, transfer: str, stride: int = 2) -> tuple[float, float]:
    """The frame's brightest pixel and its average, in nits, from the deep signal: MaxCLL and MaxFALL's inputs.
    The transfer is monotonic, so the brightest channel's code is the brightest channel's light, and one table
    lookup on the per-pixel code maximum replaces a pow over every channel of every pixel (a hundred
    milliseconds a frame at 1080p, which the M5 reading showed)."""
    codes = frame[:, :, :3].max(axis=2)
    table = _light_table(transfer)
    peak = float(table[int(codes.max())])  # the brightest code is the brightest pixel, exactly
    average = float(table[codes[::stride, ::stride]].mean())  # the frame average from every other pixel each way
    return peak, average


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


def measure_loudness(path: Path) -> dict | None:
    """A file's EBU R128 loudness: integrated (LUFS), range (LU) and true peak (dBTP), by ffmpeg's ebur128 filter;
    None where it has no audio or cannot be read."""
    run = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    summary = run.stderr[run.stderr.rfind("Summary:") :]
    found = {}
    for key, label in (("integrated", "I:"), ("range", "LRA:"), ("true_peak", "Peak:")):
        at = summary.find(label)
        if at < 0:
            return None
        try:
            found[key] = float(summary[at + len(label) :].split()[0])
        except (ValueError, IndexError):
            return None
    return found if found["integrated"] > -70 else None


def loudness_gain(path: Path, target: float, ceiling: float = -1.0) -> float | None:
    """The one gain (dB) that brings a mix to the target integrated loudness without its true peak passing the
    ceiling: plain gain, the mix's dynamics as edited (no compression or limiting). None where it cannot be measured."""
    measured = measure_loudness(path)
    if measured is None:
        return None
    return min(target - measured["integrated"], ceiling - measured["true_peak"])


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
    audio_kbps: int | None = None,
    loudness: float | None = None,
    true_peak: float = -1.0,
) -> dict:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    stamps = {"began": time.perf_counter()}  # the export timed in parts: start-up, the frames, the finish
    # A rate other than the project's, beyond the 0.2% of a retime such as 24 to 23.976 (the same frames, stamped
    # slower), is sampled from the timeline at that rate. Rendered at the project's rate and handed to the encoder at
    # another, frames were duplicated: the Posh :15 from a 24 fps project exported at 30 repeated every fifth frame.
    wanted_num, wanted_den = RATE_PRESETS.get(rate or "", (0, 0))
    if wanted_num:
        target = wanted_num / wanted_den
        if abs(target - float(project["fps"])) / float(project["fps"]) > 0.002:
            project = {**project, "fps": round(target) if abs(target - round(target)) < 1e-6 else target}
    path = OUTPUTS / (job_id + "." + format)
    audio = OUTPUTS / (job_id + ".wav")
    log = OUTPUTS / (job_id + ".log")
    # finished frames, kept losslessly while the job runs: a job resumed after the engine stopped (closed, crashed,
    # the machine slept) reads them back instead of rendering them again; removed when the job ends any other way
    frames_cache = OUTPUTS / (job_id + ".frames")
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
        if audio_kbps:
            audio_flags += ["-b:a", f"{int(audio_kbps)}k"]
        if loudness is not None:
            gain = loudness_gain(audio, loudness, true_peak)
            if gain is not None:
                audio_flags += ["-af", f"volume={gain:.2f}dB"]
        # The colour-managed pipeline lands every source in BT.709 (tone-mapped
        # or converted at decode), so the file says so; an untagged file is
        # guessed at by players, and not always the same way.
        colour_tags = ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv"]
        # An HDR output: the project's outputColour asks for HLG or PQ. The
        # working space is BT.709; the export applies the inverse transform
        # (BT.709 to BT.2020 primaries, the HLG or PQ transfer) with zscale,
        # in ten bits, and tags the file as what it is. Both encoders that
        # carry ten bits are asked for it; an encoder that cannot keeps 709.
        output_colour = str(project.get("outputColour") or "bt709").lower()
        hdr_filter = ""
        if output_colour in ("hlg", "pq") and encoder in (
            "libx265",
            "libsvtav1",
            "libaom-av1",
            "libvpx-vp9",
            "hevc_videotoolbox",
            "hevc_nvenc",
            "hevc_qsv",
            "hevc_amf",
        ):
            ten_bit = True
            transfer = "arib-std-b67" if output_colour == "hlg" else "smpte2084"
            # The frames arrive as untagged RGB; the colorspace filter names
            # them BT.709 in ten bits first, which is the input zscale accepts.
            # Step 5 of the HDR working space: the renderer works in the transfer, so the frames arrive
            # already PQ or HLG at sixteen bits (rgba64) and need only the BT.2020 matrix on the way to
            # ten-bit 4:2:0; nothing is tone-mapped or transformed. The primaries are declared BT.2020 as
            # the deep source's are; an SDR source lifted into the space carries its BT.709 primaries into
            # the wider gamut unconverted, a known approximation until a primaries pass joins the lift.
            hdr_filter = "scale=out_color_matrix=bt2020nc:out_range=tv,format=yuv420p10le"
            colour_tags = ["-color_primaries", "bt2020", "-color_trc", transfer, "-colorspace", "bt2020nc", "-color_range", "tv"]
            pix = pixel_format(encoder or "", True)
        codec = ["-c:v", encoder, *speed, *tier_flags(encoder, quality, out_w, out_h, fps), *colour_tags, *audio_flags] if encoder else []
        if encoder and encoder.endswith("_videotoolbox") and not hdr_filter:
            # VideoToolbox writes the matrix into the stream but not the primaries or the transfer (the owner's
            # exports read "unknown"): the bitstream's own colour description says BT.709 throughout
            codec += [
                "-bsf:v",
                f"{'hevc' if 'hevc' in encoder else 'h264'}_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1",
            ]
        # an HDR timeline exported through a codec that cannot carry HDR (H.264, say) renders as SDR: the frames
        # would otherwise leave the renderer PQ- or HLG-encoded and be tagged BT.709, a washed-out picture
        render_project = project if hdr_filter or output_colour not in ("hlg", "pq") else {**project, "outputColour": "bt709"}
        if render_project is not project:
            renderer.close()
            renderer = FrameRenderer(render_project)
        count = math.ceil(project["duration"] * fps)
        # An HDR export writes a lossless sixteen-bit intermediate first: MaxCLL and MaxFALL are measured
        # while the frames are rendered and the encoder needs them before it starts, so the final
        # ten-bit encode is a second pass over the intermediate with the measured light in its
        # parameters (x265's max-cll and master-display, SVT-AV1's content-light) and in the container.
        # The two-pass buys the light in the stream only where the encoder can write it (x265 and SVT-AV1);
        # a hardware encoder (VideoToolbox, NVENC, QSV, AMF) cannot take the SEI from ffmpeg at all, so an
        # HDR export through one is a single pass straight into it, render-bound, with the measured light in
        # the result and the job log. The M5 reading showed the two-pass costing the export two thirds of
        # its rate for a stream that could not carry the values anyway.
        hdr_deep = bool(hdr_filter) and encoder in ("libx265", "libsvtav1")
        hdr_final = [*codec] if hdr_deep else []
        hdr_pix = pix
        hdr_filter_final = hdr_filter
        if hdr_deep:
            # the intermediate is lossless in the final layout (ten-bit 4:2:0 with the BT.2020 matrix), a
            # quarter the samples of sixteen-bit RGB, so the second pass only adds the light
            hdr_filter = hdr_filter_final
            hdr_filter_final = ""
            path = OUTPUTS / (job_id + ".intermediate.mkv")
            codec, pix = (
                ["-c:v", "ffv1", "-level", "3", "-slices", "24", "-slicecrc", "0", "-threads", "0", "-c:a", "pcm_s16le"],
                "yuv420p10le",
            )
            outer_report = report

            def report(fraction: float) -> None:
                outer_report(fraction * 0.6)

        if cisco or gif:
            # Whichever path renders writes a lossless intermediate, and finish()
            # encodes it through OpenH264 or the GIF palette: the same pixels any
            # encoder would get.
            path = OUTPUTS / (job_id + ".intermediate.mkv")
            codec, pix = ["-c:v", "ffv1", "-level", "3", "-c:a", "pcm_s16le"], "yuv420p"
            outer_report = report

            def report(fraction: float) -> None:
                outer_report(fraction * 0.6)

        def note(line: str) -> None:
            with open(log, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")

        def held_to_frame_path(file_path, label: str) -> bool:
            """R25: the fast path is held to the frame path per export. One frame in the middle of the finished
            file is decoded and compared with the frame renderer's own frame at that instant; the encoder's loss
            is cancelled (the renderer's frame goes once through the same encoder), and a mean over three counts or a
            99th percentile over 48 means
            the graph and the renderer disagree on this project, so the export is redone through the frame path."""
            try:
                import cv2

                from .renderer import FrameRenderer

                # the frame path renders frame k at k / rate; the file's frame k is read by index, not by a seek,
                # and decoded through the file's own colour tags into full-range RGB as the renderer's frame is
                index = max(0, int(count) // 2)
                middle = index / float(out_rate)
                probe = subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        str(file_path),
                        "-vf",
                        f"select=eq(n\\,{index}),scale=in_range=tv:out_range=pc",
                        "-vsync",
                        "0",
                        "-frames:v",
                        "1",
                        "-pix_fmt",
                        "rgba",
                        "-f",
                        "rawvideo",
                        "pipe:1",
                    ],
                    capture_output=True,
                    check=False,
                )
                if probe.returncode or len(probe.stdout) != out_w * out_h * 4:
                    note(f"{label}: the check frame could not be read; keeping the export")
                    return False
                got = np.frombuffer(probe.stdout, np.uint8).reshape(out_h, out_w, 4)[:, :, :3].astype(np.int16)
                renderer = FrameRenderer(render_project, out_w)
                try:
                    want = renderer.frame(middle)
                finally:
                    renderer.close()
                if want.shape[1] != out_w or want.shape[0] != out_h:
                    want = cv2.resize(want, (out_w, out_h), interpolation=cv2.INTER_AREA)
                # the encoder's own loss cancels: the renderer's frame is sent once through the same encoder
                # and read back the same way, and the file's frame is compared with that
                baseline = subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgba",
                        "-s",
                        f"{out_w}x{out_h}",
                        "-r",
                        str(out_rate),
                        "-i",
                        "pipe:0",
                        *codec,
                        "-pix_fmt",
                        pix,
                        "-frames:v",
                        "1",
                        "-f",
                        "matroska",
                        "pipe:1",
                    ],
                    input=np.ascontiguousarray(want).tobytes(),
                    capture_output=True,
                    check=False,
                )
                back = subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        "pipe:0",
                        "-vf",
                        "scale=in_range=tv:out_range=pc",
                        "-frames:v",
                        "1",
                        "-pix_fmt",
                        "rgba",
                        "-f",
                        "rawvideo",
                        "pipe:1",
                    ],
                    input=baseline.stdout,
                    capture_output=True,
                    check=False,
                )
                reference = want[:, :, :3].astype(np.int16)
                if not back.returncode and len(back.stdout) == out_w * out_h * 4:
                    reference = np.frombuffer(back.stdout, np.uint8).reshape(out_h, out_w, 4)[:, :, :3].astype(np.int16)
                diff = np.abs(reference - got)
                mean, p99 = float(diff.mean()), float(np.percentile(diff, 99))
                mse = float((diff.astype(np.float64) ** 2).mean())
                psnr = 99.0 if mse <= 0 else 10 * np.log10(255.0**2 / mse)
                note(f"{label} held to the frame path: mean {mean:.2f} counts, 99th percentile {p99:.0f}, {psnr:.1f} dB")
                if os.environ.get("FORMCUT_HOLD_TRACE"):
                    print(f"[hold] {label}: mean {mean:.2f} p99 {p99:.0f} max {int(diff.max())} psnr {psnr:.1f}", flush=True)
                # calibrated on the synthetic bars the fast-export tests cut, the harshest content for a
                # scaler: mean 1.2 counts, 99th percentile 18 to 22, with the encoder's loss cancelled; a graph
                # that dropped an effect, a colour tag or a layer lands far beyond this
                if label == "layered":
                    # the layered graph bakes the grade into a 33-point cube and is approximate by design;
                    # its standard has always been the tests' own: 30 dB against the frame path
                    return psnr < 30.0
                return mean > 3.0 or p99 > 48
            except (OSError, ValueError, RuntimeError) as exc:
                note(f"{label}: the check failed ({exc}); keeping the export")
                return False

        def finish(result: dict) -> dict:
            if fell_back:
                result["fellBackTo"] = fell_back
            # an HDR file (tagged PQ or HLG, not an SDR file made from a deep timeline) carries its measured light
            # in the container as the ISO BMFF boxes a player reads it from (clli and mdcv on the video sample
            # entry); a hardware encoder cannot take it as SEI from ffmpeg, so there the boxes are all it has
            hdr_output = any(t in colour_tags for t in ("smpte2084", "arib-std-b67")) and result.get("maxCll") is not None
            if hdr_output and not hdr_deep and str(result.get("file", "")).endswith((".mp4", ".mov")):
                written = write_light_boxes(Path(result["file"]), int(result.get("maxCll") or 0), int(result.get("maxFall") or 0))
                result["lightWritten"] = "container" if written else "result only"
            if hdr_deep:
                cll, fall = int(result.get("maxCll") or 0), int(result.get("maxFall") or 0)
                params = [*hdr_final]
                encoder_name = params[1] if len(params) > 1 else ""
                if encoder_name == "libx265":
                    params += [
                        "-x265-params",
                        f"max-cll={cll},{fall}:master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L({max(cll, 1) * 10000},50)",
                    ]
                elif encoder_name == "libsvtav1":
                    params += [
                        "-svtav1-params",
                        f"content-light={cll},{fall}:mastering-display=G(0.265,0.690)B(0.150,0.060)R(0.680,0.320)WP(0.3127,0.3290)L({max(cll, 1)},0.005)",
                    ]
                second = [
                    program,
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(path),
                    # the intermediate's frames are the final layout already; tagged here so no scaler is put in
                    "-vf",
                    _frame_tags(colour_tags),
                    *params,
                    "-pix_fmt",
                    hdr_pix,
                    "-c:a",
                    "copy" if format == "mp4" else "libopus",
                    "-metadata:s:v",
                    f"MaxCLL={cll}",
                    "-metadata:s:v",
                    f"MaxFALL={fall}",
                    str(final),
                ]
                done = subprocess.run(second, capture_output=True, text=True, check=False)
                if done.returncode:
                    raise RuntimeError("HDR encode failed: " + done.stderr[-400:])
                path.unlink(missing_ok=True)
                boxed = str(final).endswith((".mp4", ".mov")) and write_light_boxes(Path(final), cll, fall)
                in_stream = encoder_name in ("libx265", "libsvtav1")
                outer_report(1.0)
                return {
                    **result,
                    "file": str(final),
                    "pixelFormat": hdr_pix,
                    "hdrMetadataWritten": in_stream,
                    "lightWritten": " and ".join(where for where, yes in (("stream", in_stream), ("container", boxed)) if yes)
                    or "result only",
                }
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
        # An HDR output needs the frame path: the two graphs feed the file to
        # the encoder untouched and would tag Rec.709 pixels as HLG or PQ.
        fractional = not float(project["fps"]).is_integer()  # the graph's timebase takes whole rates; the frame path any
        frames_only = os.environ.get("FORMCUT_EXPORT_PATH") == "frames" or upload or hdr_filter or fractional
        native = None if frames_only else fast_export.plan(project, count)
        if native is not None:
            fast_export.run(
                native, program, audio, [*codec, "-pix_fmt", pix], out_w, out_h, out_rate, project["duration"], path, log, report, cancelled
            )
            if held_to_frame_path(path, "native"):
                native = None
                layered = None
                note("the native graph disagreed with the frame path on this project; exporting through the frame path")
        if native is not None:
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
            None
            if native is not None or os.environ.get("FORMCUT_EXPORT_PATH") == "frames" or upload or hdr_filter
            else fast_layers.plan(project, count)
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
            if held_to_frame_path(path, "layered"):
                layered = None
                note("the layered graph disagreed with the frame path on this project; exporting through the frame path")
        if layered is not None:
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
        # A deep frame comes off the device as ten-bit 4:2:0 planes with the light measured there, so the
        # pipe carries three bytes a pixel instead of eight and ffmpeg converts nothing; the M5 export sat
        # at 18 fps against a 41 fps render with the conversion in ffmpeg's single thread.
        planar = bool(renderer.deep and gpu.stack_active() and out_w % 4 == 0 and out_h % 2 == 0)
        # the Rust executor packs P010 for VideoToolbox, which takes it without a conversion; otherwise ten-bit planar
        from . import gpu_frame

        layout = "p010le" if planar and str(encoder or "").endswith("_videotoolbox") and gpu_frame.available() else "yuv420p10le"
        same_size = renderer.width == out_w and renderer.height == out_h
        command = [
            program,
            "-v",
            "error",
            "-y",
            *device,
            "-f",
            "rawvideo",
            "-pix_fmt",
            (layout if planar else "rgba64le") if renderer.deep else "rgba",
            "-s",
            f"{renderer.width}x{renderer.height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-filter_threads",
            str(max(2, min(8, (os.cpu_count() or 2) // 2))),
            "-i",
            str(audio),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-vf",
            # Planes already in BT.2020 are tagged as what they are: with only the output tagged, FFmpeg 7.1 and
            # later negotiate the colour and put a scaler in that converts the "unspecified" frames to BT.2020,
            # which altered every pixel and held the M5's export near 87 fps against 190 without the tags.
            (
                (_frame_tags(colour_tags) if colour_tags else "null")
                if planar and same_size
                else f"scale={out_w}:{out_h},pad=ceil(iw/2)*2:ceil(ih/2)*2"
            )
            + (f",{hdr_filter}" if hdr_filter and not planar else "")
            + (f",{upload}" if upload else ""),
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
            # The pool suits the CPU path, where renderers on separate cores add up. On the device path they
            # all queue for one GPU lock and one decoder each seeks into the same clip, and the M5 export read
            # 18 fps against a 41 fps render; there the frame path renders one frame ahead on a thread while
            # the encoder takes the last (the render and the pipe write overlap, the GPU never idles for the
            # write), which is the same shape the decoder's own prefetch has.
            from . import gpu_frame as _executor

            if gpu.stack_active() or _executor.available():
                # the frame executor and its recorder serve one renderer at a time; a pool of renderers on it
                # would share its pictures across threads (the M5's export after a fault took the pool and broke)
                workers = 1
            if workers > 1 and count > workers * 4:
                chunk = math.ceil(count / workers)
                spans = [(start, min(count, start + chunk)) for start in range(0, count, chunk)]
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    pending = [pool.submit(_render_span, render_project, fps, span, cancelled) for span in spans]
                    done = 0
                    max_cll, max_fall = 0.0, 0.0
                    for future in pending:
                        for payload in future.result():
                            if cancelled():
                                raise InterruptedError("Cancelled")
                            process.stdin.write(payload)
                            if renderer.deep:
                                frame_view = np.frombuffer(payload, np.uint16).reshape(renderer.height, renderer.width, 4)
                                peak, average = _light_of(frame_view, renderer.transfer)
                                max_cll = max(max_cll, peak)
                                max_fall = max(max_fall, average)
                            done += 1
                            report(0.1 + 0.85 * done / count)
            else:
                max_cll, max_fall = 0.0, 0.0

                frames_cache.mkdir(parents=True, exist_ok=True)

                def produce(i: int):
                    if planar:
                        got = renderer.frame_planes(i / fps, layout)
                        if got is not None:
                            return got
                    kept = frames_cache / f"{i:06d}.png"
                    picture = cv2.imread(str(kept), cv2.IMREAD_UNCHANGED) if kept.exists() else None
                    if picture is None:
                        picture = np.ascontiguousarray(renderer.frame(i / fps))
                        # written then renamed, so a frame cut off mid-write is never read back
                        partial = frames_cache / f"{i:06d}.part.png"
                        cv2.imwrite(str(partial), picture, [cv2.IMWRITE_PNG_COMPRESSION, 1])
                        partial.replace(kept)
                    picture = np.ascontiguousarray(picture)
                    if planar:
                        # the device did not pack this frame (nothing on screen, say): converted here as ffmpeg would
                        picture = _to_planes(picture, layout)
                    light = _light_of(picture, renderer.transfer) if renderer.deep and not planar else None
                    return picture, light

                stamps["loop"] = time.perf_counter()
                stamps["render_wait"] = stamps["write"] = 0.0
                # The renderer works up to three frames ahead of the pipe (one thread, in order), so a frame the
                # encoder takes slowly does not stop the next from rendering; the time this loop waits on each
                # side is kept, so the export's parts say which side holds it back.
                depth = 3
                with ThreadPoolExecutor(max_workers=1) as ahead:
                    pending = [ahead.submit(produce, j) for j in range(min(depth, count))]
                    for i in range(count):
                        if cancelled():
                            raise InterruptedError("Cancelled")
                        waited = time.perf_counter()
                        written, light = pending.pop(0).result()
                        stamps["render_wait"] += time.perf_counter() - waited
                        if i + depth < count:
                            pending.append(ahead.submit(produce, i + depth))
                        if light is not None:
                            max_cll = max(max_cll, light[0])
                            max_fall = max(max_fall, light[1])
                        # The pipe takes the array's own memory, the bytes tobytes()
                        # made a copy of, in the same order: 5 ms a 1080p frame saved.
                        began_write = time.perf_counter()
                        process.stdin.write(written)
                        stamps["write"] += time.perf_counter() - began_write
                        stamps.setdefault("first", time.perf_counter())
                        stamps["last"] = time.perf_counter()
                        report(0.1 + 0.85 * (i + 1) / count)
            process.stdin.close()
            process.wait(timeout=600)
            stamps["done"] = time.perf_counter()
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
                "timing": _timing(stamps, count),
                "encoderCommand": [str(part) for part in command],
                "workingSpace": renderer.transfer if renderer.deep else "bt709",
                "maxCll": round(max_cll) if renderer.deep else None,
                "maxFall": round(max_fall) if renderer.deep else None,
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
        shutil.rmtree(frames_cache, ignore_errors=True)


@router.post("/export", status_code=202)
def export(body: RenderInput):
    project = checked(body)
    if body.transparent:
        if body.format not in alpha_export.FORMATS:
            raise HTTPException(422, "A transparent export is mov (ProRes 4444), webm (VP9 with alpha) or png (a zip of frames)")
    elif body.format not in ("mp4", "webm", "gif") or body.quality not in ("high", "medium", "low"):
        raise HTTPException(422, "Unknown export format or quality")
    if body.size is not None and body.size not in SIZE_PRESETS:
        raise HTTPException(422, "Unknown export size")
    if body.rate is not None and body.rate not in RATE_PRESETS:
        raise HTTPException(422, "Unknown export rate")
    if body.codec is not None:
        allowed = encoder_status()["containers"].get(body.format, [])
        if body.codec not in allowed:
            raise HTTPException(422, f"{body.codec} is not available for {body.format} on this machine")

    return jobs.submit("export", _export_operation(body, project), recipe=body.model_dump())


def _export_operation(body: RenderInput, project: dict):
    def operation(job_id, report, cancelled):
        if body.transparent:
            num, den = RATE_PRESETS.get(body.rate or "", (0, 0))
            fps = num / den if num else float(project["fps"])
            return alpha_export.export_transparent(project, job_id, report, cancelled, body.format, fps, OUTPUTS)
        sound = {"audio_kbps": body.audioBitrate, "loudness": body.loudness, "true_peak": body.truePeak}
        picture = (body.format, body.quality, body.codec, body.tenBit, body.size, body.rate, body.exact)
        result = export_media(project, job_id, report, cancelled, *picture, **sound)
        webhooks.announce_export(result, project)
        return result

    return operation


def _resume_export(recipe: dict):
    body = RenderInput(**recipe)
    return _export_operation(body, checked(body))


jobs.RESUMERS["export"] = _resume_export


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
        pixels = rolloff_for_display(renderer.frame(max(0.0, float(body.get("time") or 0))), renderer.transfer)
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
        "tiers": {
            tier: estimate_size(
                codec, width, height, fps, tier, project["duration"], audible, encoders.choose(codec) if body.format != "gif" else None
            )
            for tier in ("high", "medium", "low")
        },
        "width": width,
        "height": height,
        "fps": fps,
        "codec": codec,
    }
