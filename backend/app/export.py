import json
import math
import re
import subprocess
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .paths import DATA_DIR
MEDIA_DIR = DATA_DIR / "media"
EXPORT_DIR = DATA_DIR / "exports"

router = APIRouter(prefix="/api/export", tags=["export"])

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


class ExportTransform(BaseModel):
    scale: float = 100
    posX: float = 0
    posY: float = 0
    rotation: float = 0
    width: float = 100
    height: float = 100
    opacity: float = 100
    flipH: bool = False


class ExportText(BaseModel):
    content: str = "Title"
    size: float = 8.0
    color: str = "#ffffff"
    bold: bool = True
    align: str = "center"


AUDIO_FX: dict[str, str] = {
    # Server-side allowlist: clients send an id, never a filter string.
    # Leading aresample pins a known rate so the asetrate trick shifts by an
    # exact ratio regardless of the source's sample rate (bug found by FFT:
    # a 44.1 kHz source measured 1.361x against a hardcoded 48 kHz base).
    "pitch_up": "aresample=48000,asetrate=48000*1.25,aresample=48000,atempo=0.8",
    "pitch_down": "aresample=48000,asetrate=48000*0.8,aresample=48000,atempo=1.25",
    "echo": "aecho=0.8:0.6:60|120:0.4|0.2",
    "radio": "highpass=f=500,lowpass=f=2400,acompressor=threshold=0.1:ratio=4",
}


class ExportMask(BaseModel):
    shape: str = "rect"
    x: float = 0.0
    y: float = 0.0
    w: float = 100.0
    h: float = 100.0
    feather: float = 0.0


class ExportKey(BaseModel):
    color: str
    similarity: float = 0.25
    blend: float = 0.05


class ExportKeyframe(BaseModel):
    t: float
    props: dict[str, float] = {}
    interp: str = "linear"


class ExportClip(BaseModel):
    mediaId: str | None = None
    kind: str
    start: float
    duration: float
    transform: ExportTransform = ExportTransform()
    effect: str | None = None
    speed: float = 1.0
    fadeIn: float = 0.0
    fadeOut: float = 0.0
    text: ExportText | None = None
    rampIn: float = 0.0
    rampOut: float = 0.0
    extendOut: float = 0.0
    keyframes: list[ExportKeyframe] = []
    key: ExportKey | None = None
    muted: bool = False
    mask: ExportMask | None = None
    audioFx: str | None = None


def kf_points(clip: ExportClip, prop: str) -> list[tuple[float, float, str]]:
    pts = [(k.t, k.props[prop], k.interp) for k in clip.keyframes if prop in k.props]
    pts.sort(key=lambda p: p[0])
    return pts


def _progress(p: str, interp: str) -> str:
    """Ease the normalized progress expression; mirrors the stage sampler."""
    if interp == "easeIn":
        return f"({p})*({p})"
    if interp == "easeOut":
        return f"(1-(1-({p}))*(1-({p})))"
    if interp == "ease":
        return f"(({p})*({p})*(3-2*({p})))"
    return f"({p})"


def piecewise_expr(points: list[tuple[float, float, str]], t_var: str) -> str:
    """Nested if() expression over stream time; eased segments, hold steps."""
    expr = f"{points[-1][1]}"
    for (t0, v0, interp), (t1, v1, _i1) in reversed(list(zip(points, points[1:]))):
        if interp == "hold" or t1 == t0:
            seg = f"{v0}"
        else:
            prog = _progress(f"({t_var}-{t0})/({t1}-{t0})", interp)
            seg = f"({v0}+({v1}-{v0})*{prog})"
        expr = f"if(lt({t_var},{t1}),{seg},{expr})"
    return f"if(lt({t_var},{points[0][0]}),{points[0][1]},{expr})"


_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def drawtext_filter(text: ExportText, width: int, height: int, pos_y: float, textfile: Path) -> str:
    content = text.content.replace("\r\n", "\n").replace("\r", "\n")[:200] or "Title"
    textfile.write_text(content, encoding="utf-8")
    color = text.color if _COLOR_RE.match(text.color) else "#ffffff"
    size = int(max(1.0, min(50.0, text.size)) / 100 * height)
    if text.align == "left":
        x = f"{width}*0.05"
    elif text.align == "right":
        x = f"{width}*0.95-text_w"
    else:
        x = "(w-text_w)/2"
    y = f"(h-text_h)/2+{round(pos_y / 100 * height)}"
    style = ":".join([
        f"textfile={textfile}",
        f"fontcolor={color}",
        f"fontsize={size}",
        "font=Sans",
        f"borderw={max(1, size // 24)}",
        "bordercolor=black@0.6",
        f"x={x}",
        f"y={y}",
        "expansion=none",
    ])
    return f"drawtext={style}"


def clamp_speed(value: float) -> float:
    return min(4.0, max(0.25, value or 1.0))


def atempo_chain(speed: float) -> list[str]:
    filters: list[str] = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    if abs(remaining - 1.0) > 1e-6:
        filters.append(f"atempo={round(remaining, 6)}")
    return filters


ALLOWED_FILTERS = {"gblur", "boxblur", "eq", "hue", "negate", "colorbalance", "vignette"}
_ARGS_RE = re.compile(r"^[A-Za-z0-9_=:.\-]*$")


def validate_effect(effect: str | None) -> str | None:
    if not effect:
        return None
    segments = effect.split(",")
    for segment in segments:
        name, _, args = segment.partition("=")
        if name not in ALLOWED_FILTERS or not _ARGS_RE.match(args):
            return None
    return effect


class ExportRequest(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    duration: float
    format: str = "mp4"
    quality: str = "high"
    clips: list[ExportClip]


ENCODERS = {
    "mp4": {"ext": "mp4", "media": "video/mp4", "vcodec": "libx264", "acodec": "aac",
            "crf": {"high": "18", "medium": "23", "low": "28"}},
    "webm": {"ext": "webm", "media": "video/webm", "vcodec": "libvpx-vp9", "acodec": "libopus",
             "crf": {"high": "24", "medium": "33", "low": "40"}},
}


def _media_path(media_id: str) -> Path | None:
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    return matches[0] if matches else None


def _probe_streams(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(path)],
        capture_output=True, timeout=30,
    )
    data = json.loads(out.stdout or b"{}")
    info = {"width": 0, "height": 0, "audio": False, "video": False}
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and not info["video"]:
            info["video"] = True
            info["width"] = int(stream.get("width") or 0)
            info["height"] = int(stream.get("height") or 0)
        if stream.get("codec_type") == "audio":
            info["audio"] = True
    return info


def render_mask(mask: ExportMask, tw: int, th: int, dest: Path) -> None:
    """White shape on black at the clip's scaled size; gaussian blur = feather.
    Feather is percent of the smaller box dimension, matching the model docs."""
    from PIL import Image, ImageDraw, ImageFilter

    img = Image.new("L", (tw, th), 0)
    draw = ImageDraw.Draw(img)
    x0 = mask.x / 100 * tw
    y0 = mask.y / 100 * th
    x1 = (mask.x + mask.w) / 100 * tw
    y1 = (mask.y + mask.h) / 100 * th
    if mask.shape == "ellipse":
        draw.ellipse([x0, y0, x1, y1], fill=255)
    else:
        draw.rectangle([x0, y0, x1, y1], fill=255)
    radius = max(0.0, min(mask.feather, 50.0)) / 100 * min(tw, th)
    if radius > 0.2:
        img = img.filter(ImageFilter.GaussianBlur(radius))
    img.save(dest)


def _build_command(req: ExportRequest, out_path: Path) -> list[str] | str:
    W, H, fps, total = req.width, req.height, req.fps, req.duration
    args: list[str] = [
        "ffmpeg", "-v", "error", "-y", "-progress", "pipe:1",
        "-f", "lavfi", "-i", f"color=black:size={W}x{H}:rate={fps}:duration={total}",
    ]
    filters: list[str] = []
    audio_labels: list[str] = []
    base = "[0:v]"
    idx = 0
    next_input = 1
    clip_src: dict[int, int] = {}
    for clip in req.clips:
        if clip.kind == "text" and clip.text is not None:
            idx += 1
            args += [
                "-f", "lavfi", "-t", str(clip.duration),
                "-i", f"color=c=black@0.0:s={W}x{H}:r={fps},format=rgba",
            ]
            t_steps = [
                drawtext_filter(
                    clip.text, W, H, clip.transform.posY,
                    out_path.with_name(f"{out_path.stem}_t{idx}.txt"),
                ),
                "format=rgba",
            ]
            t_fin = min(max(clip.fadeIn, 0.0), clip.duration / 2)
            t_fout = min(max(clip.fadeOut, 0.0), clip.duration / 2)
            if t_fin > 0:
                t_steps.append(f"fade=t=in:st=0:d={t_fin}:alpha=1")
            if t_fout > 0:
                t_steps.append(f"fade=t=out:st={clip.duration - t_fout}:d={t_fout}:alpha=1")
            t_alpha = max(0.0, min(clip.transform.opacity / 100, 1.0))
            if t_alpha < 1.0:
                t_steps.append(f"colorchannelmixer=aa={t_alpha}")
            t_steps.append(f"setpts=PTS+{clip.start}/TB")
            src = next_input
            next_input += 1
            clip_src[idx] = src
            filters.append(f"[{src}:v]{','.join(t_steps)}[v{idx}]")
            nxt = f"[m{idx}]"
            filters.append(
                f"{base}[v{idx}]overlay=0:0:eof_action=pass:"
                f"enable='between(t,{clip.start},{clip.start + clip.duration})'{nxt}"
            )
            base = nxt
            continue
        path = _media_path(clip.mediaId)
        if path is None:
            continue
        info = _probe_streams(path)
        idx += 1
        if clip.kind == "image":
            args += ["-loop", "1", "-t", str(clip.duration), "-i", str(path)]
        else:
            args += ["-i", str(path)]
        src = next_input
        next_input += 1
        clip_src[idx] = src
        if clip.kind in ("video", "image") and info["video"]:
            sw = info["width"] or W
            sh = info["height"] or H
            fit = min(W / sw, H / sh)
            t = clip.transform
            tw = max(2, round(sw * fit * (t.scale / 100) * (t.width / 100) / 2) * 2)
            th = max(2, round(sh * fit * (t.scale / 100) * (t.height / 100) / 2) * 2)
            rot_pts = kf_points(clip, "rotation")
            rot = t.rotation % 360
            if rot_pts:
                angles = [v % 360 for (_t, v, _i) in rot_pts] + [rot]
            else:
                angles = [rot]
            bw = bh = 0
            for a in angles:
                rad = math.radians(a)
                bw = max(bw, round((abs(tw * math.cos(rad)) + abs(th * math.sin(rad))) / 2) * 2)
                bh = max(bh, round((abs(tw * math.sin(rad)) + abs(th * math.cos(rad))) / 2) * 2)
            bw, bh = max(2, bw), max(2, bh)
            x_pts = kf_points(clip, "posX")
            y_pts = kf_points(clip, "posY")
            tvar = f"(t-{clip.start})"
            if x_pts:
                px_pts = [(p[0], round((W - bw) / 2 + p[1] / 100 * W, 2), p[2]) for p in x_pts]
                x: object = f"'{piecewise_expr(px_pts, tvar)}'"
            else:
                x = round((W - bw) / 2 + (t.posX / 100) * W)
            if y_pts:
                py_pts = [(p[0], round((H - bh) / 2 + p[1] / 100 * H, 2), p[2]) for p in y_pts]
                y: object = f"'{piecewise_expr(py_pts, tvar)}'"
            else:
                y = round((H - bh) / 2 + (t.posY / 100) * H)
            alpha = max(0.0, min(t.opacity / 100, 1.0))
            effect = validate_effect(clip.effect)
            speed = clamp_speed(clip.speed)
            fade_in = min(max(clip.fadeIn, 0.0), clip.duration / 2)
            fade_out = min(max(clip.fadeOut, 0.0), clip.duration / 2)
            ramp_in = min(max(clip.rampIn, 0.0), clip.duration)
            ramp_out = min(max(clip.rampOut, 0.0), clip.duration)
            extend = max(clip.extendOut, 0.0)
            steps = []
            if clip.kind == "video":
                steps.append(f"trim=duration={(clip.duration + extend) * speed}")
                if speed != 1.0:
                    steps.append(f"setpts=(PTS-STARTPTS)/{speed}")
                else:
                    steps.append("setpts=PTS-STARTPTS")
            steps.append(f"scale={tw}:{th}")
            if t.flipH:
                steps.append("hflip")
            if effect:
                steps.append(effect)
            if clip.key and re.fullmatch(r"#[0-9a-fA-F]{6}", clip.key.color):
                sim = min(max(clip.key.similarity, 0.01), 1.0)
                kblend = min(max(clip.key.blend, 0.0), 1.0)
                steps.append(f"chromakey=0x{clip.key.color[1:]}:{sim}:{kblend}")
            steps.append("format=rgba")
            op_pts = kf_points(clip, "opacity")
            if op_pts:
                frac = [(pt, val / 100.0, itp) for (pt, val, itp) in op_pts]
                a_expr = piecewise_expr(frac, "T")
                steps.append(f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*({a_expr})'")
            if fade_in > 0:
                steps.append(f"fade=t=in:st=0:d={fade_in}:alpha=1")
            if fade_out > 0:
                steps.append(f"fade=t=out:st={clip.duration - fade_out}:d={fade_out}:alpha=1")
            if ramp_in > 0:
                steps.append(f"fade=t=in:st=0:d={ramp_in}:alpha=1")
            if ramp_out > 0:
                steps.append(f"fade=t=out:st={clip.duration - ramp_out}:d={ramp_out}:alpha=1")
            if extend > 0:
                steps.append(f"fade=t=out:st={clip.duration}:d={extend}:alpha=1")
            if alpha < 1.0:
                steps.append(f"colorchannelmixer=aa={alpha}")
            if rot_pts:
                deg = piecewise_expr(rot_pts, "t")
                steps.append(f"rotate=a='({deg})*PI/180':ow={bw}:oh={bh}:c=black@0")
            elif rot:
                steps.append(f"rotate={math.radians(rot)}:ow={bw}:oh={bh}:c=black@0")
            if clip.kind == "image":
                steps.append(f"fps={fps}")
            steps.append(f"setpts=PTS+{clip.start}/TB")
            if clip.mask is not None:
                mask_png = out_path.with_name(f"{out_path.stem}_m{idx}.png")
                render_mask(clip.mask, tw, th, mask_png)
                args += ["-loop", "1", "-t", str(clip.duration + extend), "-i", str(mask_png)]
                msrc = next_input
                next_input += 1
                cut = steps.index("format=rgba") + 1
                pre, post = steps[:cut], steps[cut:]
                post_chain = ("," + ",".join(post)) if post else ""
                filters.append(
                    f"[{src}:v]{','.join(pre)}[pm{idx}];"
                    f"[{msrc}:v]format=gray[mg{idx}];"
                    f"[pm{idx}][mg{idx}]alphamerge{post_chain}[v{idx}]"
                )
            else:
                filters.append(f"[{src}:v]{','.join(steps)}[v{idx}]")
            end = clip.start + clip.duration + extend
            filters.append(
                f"{base}[v{idx}]overlay=x={x}:y={y}:eof_action=pass:"
                f"enable='between(t,{clip.start},{end})'[b{idx}]"
            )
            base = f"[b{idx}]"
        if info["audio"] and clip.kind in ("video", "audio"):
            ms = round(clip.start * 1000)
            if clip.muted:
                continue
            a_speed = clamp_speed(clip.speed)
            a_fin = min(max(clip.fadeIn, 0.0), clip.duration / 2)
            a_fout = min(max(clip.fadeOut, 0.0), clip.duration / 2)
            a_rin = min(max(clip.rampIn, 0.0), clip.duration)
            a_rout = min(max(clip.rampOut, 0.0), clip.duration)
            a_ext = max(clip.extendOut, 0.0)
            a_steps = [f"atrim=duration={(clip.duration + a_ext) * a_speed}", "asetpts=PTS-STARTPTS"]
            a_steps += atempo_chain(a_speed)
            if clip.audioFx in AUDIO_FX:
                a_steps.append(AUDIO_FX[clip.audioFx])
            if a_fin > 0:
                a_steps.append(f"afade=t=in:st=0:d={a_fin}")
            if a_fout > 0:
                a_steps.append(f"afade=t=out:st={clip.duration - a_fout}:d={a_fout}")
            if a_rin > 0:
                a_steps.append(f"afade=t=in:st=0:d={a_rin}")
            if a_rout > 0:
                a_steps.append(f"afade=t=out:st={clip.duration - a_rout}:d={a_rout}")
            if a_ext > 0:
                a_steps.append(f"afade=t=out:st={clip.duration}:d={a_ext}")
            a_steps.append(f"adelay={ms}:all=1")
            filters.append(f"[{clip_src[idx]}:a]{','.join(a_steps)}[a{idx}]")
            audio_labels.append(f"[a{idx}]")
    if idx == 0:
        return "no exportable clips"
    filters.append(f"{base}format=yuv420p[vout]")
    if audio_labels:
        filters.append(
            f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:normalize=0,"
            f"apad,atrim=duration={total}[aout]"
        )
    else:
        args += ["-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=48000:cl=stereo"]
        filters.append(f"[{next_input}:a]anull[aout]")
    enc = ENCODERS.get(req.format, ENCODERS["mp4"])
    crf = enc["crf"].get(req.quality, enc["crf"]["high"])
    video_args = ["-c:v", enc["vcodec"], "-crf", crf, "-pix_fmt", "yuv420p"]
    if enc["vcodec"] == "libx264":
        video_args += ["-preset", "veryfast"]
    if enc["vcodec"] == "libvpx-vp9":
        video_args += ["-b:v", "0", "-row-mt", "1", "-cpu-used", "5"]
    args += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "[aout]",
        *video_args,
        "-c:a", enc["acodec"], "-t", str(total), str(out_path),
    ]
    return args


def _run_job(job_id: str, req: ExportRequest) -> None:
    enc = ENCODERS.get(req.format, ENCODERS["mp4"])
    out_path = EXPORT_DIR / f"{job_id}.{enc['ext']}"
    err_path = EXPORT_DIR / f"{job_id}.log"
    cmd = _build_command(req, out_path)
    if isinstance(cmd, str):
        with _jobs_lock:
            _jobs[job_id].update(status="error", error=cmd)
        return
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
    try:
        with err_path.open("w") as err_file:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err_file, text=True)
            for line in proc.stdout or []:
                if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
                    try:
                        us = int(line.split("=", 1)[1])
                    except ValueError:
                        continue
                    pct = min(0.99, (us / 1_000_000) / max(req.duration, 0.001))
                    with _jobs_lock:
                        _jobs[job_id]["progress"] = round(pct, 3)
            proc.wait(timeout=600)
        if proc.returncode != 0 or not out_path.exists():
            err = err_path.read_text()[-400:] if err_path.exists() else ""
            for tf in EXPORT_DIR.glob(f"{out_path.stem}_t*.txt"):
                tf.unlink(missing_ok=True)
            with _jobs_lock:
                _jobs[job_id].update(status="error", error=err or "ffmpeg failed")
            return
        err_path.unlink(missing_ok=True)
        for tf in EXPORT_DIR.glob(f"{out_path.stem}_t*.txt"):
            tf.unlink(missing_ok=True)
        with _jobs_lock:
            _jobs[job_id].update(status="done", progress=1.0, format=req.format)
    except (OSError, subprocess.SubprocessError) as exc:
        with _jobs_lock:
            _jobs[job_id].update(status="error", error=str(exc))


@router.post("", status_code=202)
def start_export(req: ExportRequest) -> dict:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        finished = [k for k, v in _jobs.items() if v.get("status") in ("done", "error")]
        for old in finished[:-49] if len(finished) > 49 else []:
            _jobs.pop(old, None)
        _jobs[job_id] = {"status": "queued", "progress": 0.0}
    threading.Thread(target=_run_job, args=(job_id, req), daemon=True).start()
    return {"job_id": job_id}


@router.get("/{job_id}")
def export_status(job_id: str) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return {"job_id": job_id, **job}


@router.get("/{job_id}/file")
def export_file(job_id: str) -> FileResponse:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None or job.get("status") != "done":
        raise HTTPException(status_code=404, detail="export not ready")
    enc = ENCODERS.get(job.get("format", "mp4"), ENCODERS["mp4"])
    return FileResponse(EXPORT_DIR / f"{job_id}.{enc['ext']}", media_type=enc["media"],
                        filename=f"formcut-export.{enc['ext']}")
