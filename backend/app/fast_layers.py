"""Export layered, placed, faded and graded timelines without Python in the frame loop.

The native cut path takes plain video one clip at a time. This takes more:
video on several tracks at once, overlapping, each scaled, stretched, moved and
flipped where the renderer places it, at an opacity, fading in and out, graded
by the colour panel or a LUT, over a solid background. ffmpeg composites the
clips in the renderer's order, bottom track first.

The grade is not rewritten as ffmpeg filters. The renderer's own colour panel
and LUT code is run over a 33-point cube of colours, and ffmpeg applies that
cube, so the grade is formcut's, interpolated. Frames are chosen as the cut
path chooses them, sought and rate-normalised as the decoder does. Rotation,
blend modes, effects, masks, text, images, transitions and keyframed motion
keep the frame path.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import ImageColor

from . import fast_export
from .media import MEDIA_DIR
from .render_document import flatten
from .renderer import DEFAULTS
from .timing import source_time
from .video_source import VideoSource

ALLOWED = {"colour", "lutId", "fadeIn", "fadeOut"}
LIMIT = 32
CUBE = 33


@dataclass
class Layer:
    source: Path
    rate: float
    width: int
    height: int
    seek: float
    shift: float
    span: float
    first: int
    frames: int
    lead: float
    duration: float
    x: int
    y: int
    w: int
    h: int
    flip_h: bool
    flip_v: bool
    opacity: float
    fade_in: float
    fade_out: float
    grade: dict | None


@dataclass
class Plan:
    width: int
    height: int
    fps: int
    count: int
    background: tuple[int, int, int]
    layers: list[Layer] = field(default_factory=list)


def _refuse(clip: dict) -> str | None:
    """Why this clip needs the frame path, or None when it can be layered here."""
    if clip.get("kind") != "video":
        return f"a {clip.get('kind')} clip"
    if not clip.get("mediaId"):
        return "a clip without media"
    for key in fast_export.ABSENT:
        if key not in ALLOWED and clip.get(key):
            return key
    if float(clip.get("speed") or 1) != 1:
        return "speed"
    transform = {**DEFAULTS, **(clip.get("transform") or {})}
    if float(transform["rotation"]) % 360:
        return "rotation"
    if str(transform["blendMode"]) != "Normal":
        return "blendMode"
    if any(prop in (k.get("props") or {}) for k in clip.get("keyframes") or [] for prop in fast_export.MOTION):
        return "keyframes"
    if any((clip.get("expressions") or {}).get(prop) for prop in fast_export.MOTION):
        return "expressions"
    return None


def _background(project: dict) -> tuple[int, int, int] | None:
    fill = project.get("background")
    if not fill:
        return (0, 0, 0)
    if isinstance(fill, str):
        fill = {"type": "colour", "colour": fill}
    if str(fill.get("type") or "colour") != "colour":
        return None
    try:
        red, green, blue = ImageColor.getrgb(str(fill.get("colour", "#000000")))[:3]
    except ValueError:
        return None
    return red, green, blue


def _visible(project: dict) -> list[dict]:
    return [c for c in flatten(project) if c["kind"] != "audio" and not c.get("trackHidden")]


def refusal(project: dict) -> str | None:
    """Why this project needs the frame path, or None when it can be layered natively."""
    if _background(project) is None:
        return "background"
    visible = _visible(project)
    for clip in visible:
        reason = _refuse(clip)
        if reason:
            return reason
    if len(visible) > LIMIT:
        return "more layers than one graph takes"
    return None


def _grade(clip: dict) -> dict | None:
    from .pixel_effects import colour_active

    if not colour_active(clip.get("colour")) and not clip.get("lutId"):
        return None
    return {"colour": clip.get("colour"), "lutId": clip.get("lutId"), "lutIntensity": clip.get("lutIntensity", 1)}


def plan(project: dict, count: int) -> Plan | None:
    """The layered native export for this project, or None when it needs the frame path."""
    if refusal(project):
        return None
    fps, width, height = int(project["fps"]), int(project["width"]), int(project["height"])
    result = Plan(width, height, fps, count, _background(project) or (0, 0, 0))
    for clip in sorted(_visible(project), key=lambda c: (-c["trackIndex"], c["start"])):
        first, end = fast_export._span(clip, fps, count)
        transform = {**DEFAULTS, **(clip.get("transform") or {})}
        opacity = max(0.0, min(1.0, float(transform["opacity"]) / 100))
        if end <= first or opacity <= 0:
            continue
        paths = list(MEDIA_DIR.glob(f"{clip['mediaId']}.*"))
        if not paths:
            return None
        source = VideoSource(paths[0])
        rate = source.fps
        lead = first / fps - float(clip["start"])
        start = source_time(clip, lead)
        index = max(0, int(start * rate + 1e-7))
        if source.frame_count:
            index = min(source.frame_count - 1, index)
        frames = end - first
        fit = min(width / source.width, height / source.height)
        drawn_w = abs(fit * float(transform["scale"]) / 100 * float(transform["width"]) / 100) * source.width
        drawn_h = abs(fit * float(transform["scale"]) / 100 * float(transform["height"]) / 100) * source.height
        if round(drawn_w) < 1 or round(drawn_h) < 1:
            continue
        cx, cy = width * (0.5 + float(transform["posX"]) / 100), height * (0.5 + float(transform["posY"]) / 100)
        result.layers.append(
            Layer(
                paths[0],
                rate,
                source.width,
                source.height,
                index / rate,
                start - index / rate + 1e-7 / rate,
                start + frames / fps - index / rate + 2 / rate,
                first,
                frames,
                lead,
                float(clip["duration"]),
                round(cx - drawn_w / 2),
                round(cy - drawn_h / 2),
                round(drawn_w),
                round(drawn_h),
                bool(transform["flipH"]),
                bool(transform.get("flipV")),
                opacity,
                float(clip.get("fadeIn") or 0),
                float(clip.get("fadeOut") or 0),
                _grade(clip),
            )
        )
    return result


def bake(grade: dict, path: Path) -> Path:
    """Run the renderer's own grade over a cube of colours and write it as a .cube LUT."""
    from .assets import apply_lut
    from .pixel_effects import apply_colour_panel

    steps = np.round(np.linspace(0, 255, CUBE)).astype(np.uint8)
    blue, green, red = np.meshgrid(steps, steps, steps, indexing="ij")
    image = np.stack([red, green, blue, np.full_like(red, 255)], axis=-1).reshape(CUBE * CUBE, CUBE, 4)
    graded = apply_colour_panel(image, grade.get("colour"))
    if grade.get("lutId"):
        graded = apply_lut(graded, str(grade["lutId"]), float(grade.get("lutIntensity", 1)))
    values = graded[:, :, :3].reshape(-1, 3).astype(np.float64) / 255
    path.write_text(f"LUT_3D_SIZE {CUBE}\n" + "".join(f"{r:.6f} {g:.6f} {b:.6f}\n" for r, g, b in values), encoding="ascii")
    return path


def inputs(plan: Plan) -> list[str]:
    args: list[str] = []
    for layer in plan.layers:
        args += ["-ss", str(layer.seek), "-t", f"{layer.span:.6f}", "-i", str(layer.source)]
    return args


def graph(plan: Plan, cubes: dict[int, Path], out_w: int, out_h: int) -> str:
    """The background, then each layer overlaid in the renderer's order, then sized as the frame path sizes."""
    red, green, blue = plan.background
    chains = [
        f"color=c=0x{red:02x}{green:02x}{blue:02x}:s={plan.width}x{plan.height}:r={plan.fps},format=rgba,trim=end_frame={plan.count},setsar=1[base0]"
    ]
    for number, layer in enumerate(plan.layers):
        ticks = fast_export._timebase(layer.rate, plan.fps)
        steps = [
            f"[{number}:v:0]fps={layer.rate},scale={layer.width}:{layer.height},format=bgr24,format=rgba",
            f"settb=1/{ticks},setpts=PTS-{round(layer.shift * ticks)},tpad=stop_mode=clone:stop=-1",
            f"fps={plan.fps}:round=up,trim=start=0,setpts=PTS-STARTPTS,trim=end_frame={layer.frames}",
        ]
        if number in cubes:
            steps.append(f"lut3d=file='{cubes[number].as_posix()}':interp=trilinear")
        if (layer.w, layer.h) != (layer.width, layer.height):
            steps.append(f"scale={layer.w}:{layer.h}:flags=bilinear")
        if layer.flip_h:
            steps.append("hflip")
        if layer.flip_v:
            steps.append("vflip")
        if layer.opacity < 1:
            steps.append(f"colorchannelmixer=aa={layer.opacity:.6f}")
        if layer.fade_in > 0 or layer.fade_out > 0:
            # The fades run on the clip's own time, as the renderer's do.
            steps.append(f"setpts=PTS-STARTPTS+{layer.lead:.6f}/TB")
            if layer.fade_in > 0:
                steps.append(f"fade=t=in:st=0:d={layer.fade_in:.6f}:alpha=1")
            if layer.fade_out > 0:
                steps.append(f"fade=t=out:st={max(0.0, layer.duration - layer.fade_out):.6f}:d={layer.fade_out:.6f}:alpha=1")
        steps.append(f"setpts=PTS-STARTPTS+{layer.first}/({plan.fps}*TB)")
        chains.append(",".join(steps) + f"[layer{number}]")
        chains.append(
            f"[base{number}][layer{number}]overlay=x={layer.x}:y={layer.y}:format=rgb:eof_action=pass:repeatlast=0[base{number + 1}]"
        )
    chains.append(f"[base{len(plan.layers)}]scale={out_w}:{out_h},pad=ceil(iw/2)*2:ceil(ih/2)*2[out]")
    return ";".join(chains)


def run(
    plan: Plan,
    program: str,
    audio: Path,
    codec: list[str],
    out_w: int,
    out_h: int,
    out_rate: str,
    duration: float,
    path: Path,
    log: Path,
    report,
    cancelled,
) -> None:
    """Encode the layered plan with the frame path's audio and output settings."""
    with tempfile.TemporaryDirectory(prefix="formcut-grades-") as folder:
        cubes = {number: bake(layer.grade, Path(folder) / f"grade{number}.cube") for number, layer in enumerate(plan.layers) if layer.grade}
        command = [
            program,
            "-v",
            "error",
            "-y",
            "-nostdin",
            *inputs(plan),
            "-i",
            str(audio),
            "-filter_complex",
            graph(plan, cubes, out_w, out_h),
            "-map",
            "[out]",
            "-map",
            f"{len(plan.layers)}:a",
            "-r",
            out_rate,
            *codec,
            "-t",
            str(duration),
            "-progress",
            "pipe:1",
            "-nostats",
            str(path),
        ]
        with log.open("wb") as errors:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, text=True)
            try:
                for line in process.stdout:
                    if cancelled():
                        raise InterruptedError("Cancelled")
                    if line.startswith("frame=") and line[6:].strip().isdigit():
                        report(0.1 + 0.85 * min(1.0, int(line[6:]) / max(1, plan.count)))
                process.wait(timeout=600)
            except BaseException:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                raise
    if process.returncode:
        raise ValueError(log.read_text(errors="replace")[-2000:])
