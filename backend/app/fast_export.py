"""Export without Python in the frame loop, for timelines ffmpeg can draw alone.

The frame path composites every frame in NumPy and pipes it to the encoder,
which is right for effects, masks, text and shaders but costs the same for a
timeline that only cuts between clips. When every visible clip is plain video
and no two clips share a frame, each output frame is one source frame
letterboxed over black, which is a filtergraph. The source is sought, rate-
normalised and colour-converted exactly as `video_source` decodes it, and the
frame for output time t is the one the renderer picks, floor(source_time * rate
+ 1e-7), so the picture matches the frame path. Audio, codec and output
settings are the frame path's own.

A clip property that changes the picture and is not at its neutral value
refuses the plan, and so does any clip that is not video.
"""

from __future__ import annotations

import itertools
import math
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from PIL import ImageColor

from .media import MEDIA_DIR, needs_colour_work
from .render_document import flatten
from .renderer import DEFAULTS
from .timing import source_time
from .video_source import VideoSource

MOTION = ("scale", "posX", "posY", "rotation", "opacity")
ABSENT = (
    "effects",
    "effectId",
    "lutId",
    "shaderId",
    "mask",
    "cutout",
    "key",
    "stabilise",
    "colour",
    "colorGrade",
    "crop",
    "smoothSlow",
    "reversed",
    "speedCurve",
    "animations",
    "transitionIn",
    "transitionOut",
    "transitionLength",
    "extendOut",
    "pushOut",
    "fadeIn",
    "fadeOut",
    "rampIn",
    "rampOut",
    "words",
    "timelineId",
)
LIMIT = 64


@dataclass
class Segment:
    frames: int
    source: Path | None = None
    rate: float = 0.0
    width: int = 0
    height: int = 0
    seek: float = 0.0
    shift: float = 0.0
    span: float = 0.0


@dataclass
class Plan:
    width: int
    height: int
    fps: int
    count: int
    segments: list[Segment] = field(default_factory=list)

    @property
    def sources(self) -> list[Segment]:
        return [segment for segment in self.segments if segment.source is not None]


def _plain(clip: dict) -> str | None:
    """Why this clip needs the frame path, or None when ffmpeg can draw it."""
    if clip.get("kind") != "video":
        return f"a {clip.get('kind')} clip"
    if not clip.get("mediaId"):
        return "a clip without media"
    # X7: the graph feeds the file to ffmpeg untouched, which would skip the
    # tone map; PQ and HLG go to the frame path, whose decode pipe maps them,
    # and so does a wide-gamut or SD-tagged source the pipe converts.
    if needs_colour_work(str(clip["mediaId"])):
        return "footage the colour pipe converts"
    for key in ABSENT:
        if clip.get(key):
            return key
    if float(clip.get("speed") or 1) != 1:
        return "speed"
    transform = {**DEFAULTS, **(clip.get("transform") or {})}
    if transform != DEFAULTS:
        return "transform"
    if any(prop in (k.get("props") or {}) for k in clip.get("keyframes") or [] for prop in MOTION):
        return "keyframes"
    if any((clip.get("expressions") or {}).get(prop) for prop in MOTION):
        return "expressions"
    return None


def _background(project: dict) -> str | None:
    fill = project.get("background")
    if not fill:
        return None
    if isinstance(fill, str):
        fill = {"type": "colour", "colour": fill}
    if str(fill.get("type") or "colour") != "colour":
        return "background"
    try:
        return None if ImageColor.getrgb(str(fill.get("colour", "#000000")))[:3] == (0, 0, 0) else "background"
    except ValueError:
        return "background"


def _span(clip: dict, fps: int, count: int) -> tuple[int, int]:
    """The output frames i the renderer draws this clip on: 0 <= i/fps - start < duration."""
    start, duration = float(clip["start"]), float(clip["duration"])

    def first(offset: float) -> int:
        i = max(0, math.floor((start + offset) * fps) - 1)
        while i < count and i / fps - start < offset:
            i += 1
        return min(i, count)

    return first(0.0), first(duration)


def refusal(project: dict, count: int | None = None) -> str | None:
    """Why this project needs the frame path, or None when the native path can export it."""
    reason = _background(project)
    if reason:
        return reason
    fps = int(project["fps"])
    count = math.ceil(float(project["duration"]) * fps) if count is None else count
    visible = [c for c in flatten(project) if c["kind"] != "audio" and not c.get("trackHidden")]
    for clip in visible:
        reason = _plain(clip)
        if reason:
            return reason
    spans = sorted((_span(c, fps, count), c["id"]) for c in visible)
    spans = [s for s in spans if s[0][1] > s[0][0]]
    if len(spans) > LIMIT:
        return "more clips than one graph takes"
    for (a, _), (b, _) in itertools.pairwise(spans):
        if b[0] < a[1]:
            return "clips share a frame"
    return None


def plan(project: dict, count: int) -> Plan | None:
    """The native export for this project, or None when it needs the frame path."""
    if refusal(project, count):
        return None
    fps, width, height = int(project["fps"]), int(project["width"]), int(project["height"])
    visible = [c for c in flatten(project) if c["kind"] != "audio" and not c.get("trackHidden")]
    placed = sorted((_span(c, fps, count), c) for c in visible if _span(c, fps, count)[1] > _span(c, fps, count)[0])
    result = Plan(width, height, fps, count)
    cursor = 0
    for (first, end), clip in placed:
        if first > cursor:
            result.segments.append(Segment(first - cursor))
        paths = list(MEDIA_DIR.glob(f"{clip['mediaId']}.*"))
        if not paths:
            return None
        source = VideoSource(paths[0])
        rate = source.fps
        start = source_time(clip, first / fps - float(clip["start"]))
        index = max(0, int(start * rate + 1e-7))
        if source.frame_count:
            index = min(source.frame_count - 1, index)
        frames = end - first
        result.segments.append(
            Segment(
                frames,
                paths[0],
                rate,
                source.width,
                source.height,
                index / rate,
                start - index / rate + 1e-7 / rate,
                start + frames / fps - index / rate + 2 / rate,
            )
        )
        cursor = end
    if cursor < count:
        result.segments.append(Segment(count - cursor))
    return result


def _timebase(rate: float, fps: int) -> int:
    ticks = Fraction(rate).limit_denominator(1001000).numerator * fps
    return ticks * max(1, min(1000, (2**31 - 1) // ticks))


def inputs(plan: Plan) -> list[str]:
    args: list[str] = []
    for segment in plan.sources:
        args += ["-ss", str(segment.seek), "-t", f"{segment.span:.6f}", "-i", str(segment.source)]
    return args


def graph(plan: Plan, out_w: int, out_h: int) -> str:
    """One filtergraph: every segment at the canvas size, concatenated, then sized as the frame path sizes."""
    chains, labels, index = [], [], 0
    size = f"{plan.width}x{plan.height}"
    for number, segment in enumerate(plan.segments):
        label = f"s{number}"
        if segment.source is None:
            chains.append(f"color=c=black:s={size}:r={plan.fps},format=rgba,trim=end_frame={segment.frames},setsar=1[{label}]")
        else:
            fit = min(plan.width / segment.width, plan.height / segment.height)
            w, h = max(1, round(segment.width * fit)), max(1, round(segment.height * fit))
            ticks = _timebase(segment.rate, plan.fps)
            place = "" if (w, h) == (segment.width, segment.height) else f",scale={w}:{h}:flags=bilinear"
            chains.append(
                f"[{index}:v:0]fps={segment.rate},scale={segment.width}:{segment.height},format=bgr24,format=rgba,"
                f"settb=1/{ticks},setpts=PTS-{round(segment.shift * ticks)},tpad=stop_mode=clone:stop=-1,"
                f"fps={plan.fps}:round=up,trim=start=0,setpts=PTS-STARTPTS,trim=end_frame={segment.frames}"
                f"{place},pad={plan.width}:{plan.height}:{(plan.width - w) // 2}:{(plan.height - h) // 2}:color=black,"
                f"setsar=1[{label}]"
            )
            index += 1
        labels.append(f"[{label}]")
    chains.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0,scale={out_w}:{out_h},pad=ceil(iw/2)*2:ceil(ih/2)*2[out]")
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
    """Encode the plan with the frame path's audio and output settings."""
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
        graph(plan, out_w, out_h),
        "-map",
        "[out]",
        "-map",
        f"{len(plan.sources)}:a",
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
