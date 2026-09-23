"""Export layered, placed, faded and graded timelines without Python in the frame loop.

The native cut path takes plain video one clip at a time. This takes more:
video and still images on several tracks at once, overlapping, each scaled,
stretched, moved, flipped and rotated where the renderer places it, at an
opacity, fading in and out, crossfading or dipping into the next clip, graded
by the colour panel or a LUT, over a solid background. ffmpeg composites the
clips in the renderer's order, bottom track first.

The grade is not rewritten as ffmpeg filters. The renderer's own colour panel
and LUT code is run over a 33-point cube of colours, and ffmpeg applies that
cube, so the grade is formcut's, interpolated. Frames are chosen as the cut
path chooses them, sought and rate-normalised as the decoder does. Blend
modes, effects, masks, text, transitions other than crossfade and dip, and
keyframed motion keep the frame path.
"""

from __future__ import annotations

import math
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageOps

from . import fast_export
from .media import MEDIA_DIR
from .render_document import flatten
from .renderer import DEFAULTS
from .timing import source_time
from .video_source import VideoSource

ALLOWED = {
    "colour",
    "colorGrade",
    "lutId",
    "fadeIn",
    "fadeOut",
    "rampIn",
    "rampOut",
    "extendOut",
    "transitionIn",
    "transitionOut",
    "transitionLength",
}
# The renderer draws these two as alpha ramps alone: a crossfade ramps the
# incoming clip in over the outgoing one, which keeps playing; a dip ramps one
# out and the other in through the background.
TRANSITIONS = ("crossfade", "dip")
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
    still: bool = False
    angle: float = 0.0
    turned_w: int = 0
    turned_h: int = 0


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
    if clip.get("kind") not in ("video", "image"):
        return f"a {clip.get('kind')} clip"
    if not clip.get("mediaId"):
        return "a clip without media"
    for key in fast_export.ABSENT:
        if key not in ALLOWED and clip.get(key):
            return key
    for key in ("transitionIn", "transitionOut"):
        kind = (clip.get(key) or {}).get("type")
        if kind and kind not in TRANSITIONS:
            return "transition"
    if float(clip.get("speed") or 1) != 1:
        return "speed"
    transform = {**DEFAULTS, **(clip.get("transform") or {})}
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
    from .color_grade import active as grade_active
    from .pixel_effects import colour_active

    if not colour_active(clip.get("colour")) and not grade_active(clip.get("colorGrade")) and not clip.get("lutId"):
        return None
    return {
        "colour": clip.get("colour"),
        "colorGrade": clip.get("colorGrade"),
        "lutId": clip.get("lutId"),
        "lutIntensity": clip.get("lutIntensity", 1),
    }


def plan(project: dict, count: int) -> Plan | None:
    """The layered native export for this project, or None when it needs the frame path."""
    if refusal(project):
        return None
    fps, width, height = int(project["fps"]), int(project["width"]), int(project["height"])
    result = Plan(width, height, fps, count, _background(project) or (0, 0, 0))
    for clip in sorted(_visible(project), key=lambda c: (-c["trackIndex"], c["start"])):
        # An outgoing crossfade keeps drawing through its extension, as the renderer draws it.
        drawn = {**clip, "duration": float(clip["duration"]) + float(clip.get("extendOut") or 0)}
        first, end = fast_export._span(drawn, fps, count)
        transform = {**DEFAULTS, **(clip.get("transform") or {})}
        opacity = max(0.0, min(1.0, float(transform["opacity"]) / 100))
        if end <= first or opacity <= 0:
            continue
        paths = list(MEDIA_DIR.glob(f"{clip['mediaId']}.*"))
        if not paths:
            return None
        frames = end - first
        lead = first / fps - float(clip["start"])
        still = clip["kind"] == "image"
        if still:
            with Image.open(paths[0]) as picture:
                source_w, source_h = ImageOps.exif_transpose(picture).size
            rate, seek, shift, span = float(fps), 0.0, 0.0, frames / fps
        else:
            source = VideoSource(paths[0])
            rate, source_w, source_h = source.fps, source.width, source.height
            start = source_time(clip, lead)
            index = max(0, int(start * rate + 1e-7))
            if source.frame_count:
                index = min(source.frame_count - 1, index)
            seek, shift, span = index / rate, start - index / rate + 1e-7 / rate, start + frames / fps - index / rate + 2 / rate
        fit = min(width / source_w, height / source_h)
        drawn_w = abs(fit * float(transform["scale"]) / 100 * float(transform["width"]) / 100) * source_w
        drawn_h = abs(fit * float(transform["scale"]) / 100 * float(transform["height"]) / 100) * source_h
        if round(drawn_w) < 1 or round(drawn_h) < 1:
            continue
        # A rotated layer is placed by the box around it, centred where the clip's centre falls.
        angle = math.radians(float(transform["rotation"]) % 360)
        turned_w = abs(drawn_w * math.cos(angle)) + abs(drawn_h * math.sin(angle))
        turned_h = abs(drawn_w * math.sin(angle)) + abs(drawn_h * math.cos(angle))
        cx, cy = width * (0.5 + float(transform["posX"]) / 100), height * (0.5 + float(transform["posY"]) / 100)
        result.layers.append(
            Layer(
                paths[0],
                rate,
                source_w,
                source_h,
                seek,
                shift,
                span,
                first,
                frames,
                lead,
                float(clip["duration"]),
                round(cx - turned_w / 2),
                round(cy - turned_h / 2),
                round(drawn_w),
                round(drawn_h),
                bool(transform["flipH"]),
                bool(transform.get("flipV")),
                opacity,
                max(float(clip.get("fadeIn") or 0), float(clip.get("rampIn") or 0)),
                max(float(clip.get("fadeOut") or 0), float(clip.get("rampOut") or 0)),
                _grade(clip),
                still,
                angle,
                max(1, round(turned_w)),
                max(1, round(turned_h)),
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
    from .color_grade import apply as apply_color_grade

    graded = apply_color_grade(apply_colour_panel(image, grade.get("colour")), grade.get("colorGrade"))
    if grade.get("lutId"):
        graded = apply_lut(graded, str(grade["lutId"]), float(grade.get("lutIntensity", 1)))
    values = graded[:, :, :3].reshape(-1, 3).astype(np.float64) / 255
    path.write_text(f"LUT_3D_SIZE {CUBE}\n" + "".join(f"{r:.6f} {g:.6f} {b:.6f}\n" for r, g, b in values), encoding="ascii")
    return path


def _still(source: Path, path: Path) -> Path:
    """The still as the renderer decodes it: upright by its EXIF orientation, alpha kept."""
    with Image.open(source) as picture:
        ImageOps.exif_transpose(picture).convert("RGBA").save(path)
    return path


def inputs(plan: Plan, stills: dict[int, Path] | None = None) -> list[str]:
    args: list[str] = []
    for number, layer in enumerate(plan.layers):
        if layer.still:
            args += ["-loop", "1", "-framerate", str(plan.fps), "-t", f"{layer.span + 2 / plan.fps:.6f}"]
            args += ["-i", str((stills or {})[number])]
        else:
            args += ["-ss", str(layer.seek), "-t", f"{layer.span:.6f}", "-i", str(layer.source)]
    return args


def filter_path(path: Path) -> str:
    """A file path as a filter option value, for both levels of ffmpeg's parsing.

    A filter graph is unescaped twice: the graph parser removes quotes, then the
    filter's option parser splits on ':'. A Windows path's drive colon (C:/...)
    ended the option there, and every graded clip on the layered path failed to
    export on Windows. The colon is escaped for the option parser, and the whole
    value quoted so the graph parser keeps that backslash.
    """
    text = path.as_posix().replace(":", "\\:")
    return "'" + text.replace("'", "'\\''") + "'"


def graph(plan: Plan, cubes: dict[int, Path], out_w: int, out_h: int) -> str:
    """The background, then each layer overlaid in the renderer's order, then sized as the frame path sizes."""
    red, green, blue = plan.background
    chains = [
        f"color=c=0x{red:02x}{green:02x}{blue:02x}:s={plan.width}x{plan.height}:r={plan.fps},format=rgba,trim=end_frame={plan.count},setsar=1[base0]"
    ]
    for number, layer in enumerate(plan.layers):
        if layer.still:
            steps = [f"[{number}:v:0]format=rgba,trim=end_frame={layer.frames},setpts=PTS-STARTPTS"]
        else:
            ticks = fast_export._timebase(layer.rate, plan.fps)
            steps = [
                f"[{number}:v:0]fps={layer.rate},scale={layer.width}:{layer.height},format=bgr24,format=rgba",
                f"settb=1/{ticks},setpts=PTS-{round(layer.shift * ticks)},tpad=stop_mode=clone:stop=-1",
                f"fps={plan.fps}:round=up,trim=start=0,setpts=PTS-STARTPTS,trim=end_frame={layer.frames}",
            ]
        if number in cubes:
            steps.append(f"lut3d=file={filter_path(cubes[number])}:interp=trilinear")
        if (layer.w, layer.h) != (layer.width, layer.height):
            steps.append(f"scale={layer.w}:{layer.h}:flags=bilinear")
        if layer.flip_h:
            steps.append("hflip")
        if layer.flip_v:
            steps.append("vflip")
        if layer.angle:
            steps.append(f"rotate=a={layer.angle:.8f}:ow={layer.turned_w}:oh={layer.turned_h}:c=none:bilinear=1")
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
        stills = {
            number: _still(layer.source, Path(folder) / f"still{number}.png") for number, layer in enumerate(plan.layers) if layer.still
        }
        command = [
            program,
            "-v",
            "error",
            "-y",
            "-nostdin",
            *inputs(plan, stills),
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
