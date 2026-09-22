#!/usr/bin/env python3
"""Which export route layered projects should take, measured on this machine.

formcut exports a project by one of three routes: a native cut when nothing
needs compositing, the layered ffmpeg graph for stacked, faded or graded
video, and the frame path, which renders every frame through formcut's own
renderer and is exact by construction. Which of the last two is faster
depends on the machine: the frame path's Rust kernels use every core, and the
graph leans on ffmpeg's filters. One core cannot settle it, so this runs four
scenes by each route and reports the time and how far each route is from the
exact frame path (PSNR; identical files report inf).

    python setup/benchmark_routes.py                        # 3 s of 1920x1080
    python setup/benchmark_routes.py --seconds 10 --json routes.json

The scenes are generated, so results compare between machines. Everything is
written to a temporary data folder that is removed afterwards.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRADE = {"exposure": 0.2, "contrast": 12, "saturation": 15, "temperature": 7200}
ROUTES = {"auto": "", "layered": "layered", "frames": "frames"}


def psnr(ffmpeg: str, first: str, second: str) -> str:
    out = subprocess.run(
        [ffmpeg, "-i", first, "-i", second, "-lavfi", "[0:v][1:v]psnr", "-f", "null", "-"], capture_output=True, text=True, check=False
    ).stderr
    return out.split("average:")[1].split()[0] if "average:" in out else "?"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seconds", type=float, default=3.0, help="length of each scene")
    parser.add_argument("--size", default="1920x1080", help="canvas size, WIDTHxHEIGHT")
    parser.add_argument("--json", type=Path, help="also write the results here")
    args = parser.parse_args()
    width, height = (int(part) for part in args.size.lower().split("x"))
    data = tempfile.mkdtemp(prefix="formcut-routes-")
    os.environ["FORMCUT_DATA_DIR"] = data
    try:
        return run(args, data, width, height)
    finally:
        os.environ.pop("FORMCUT_EXPORT_PATH", None)
        shutil.rmtree(data, ignore_errors=True)


def run(args: argparse.Namespace, data: str, width: int, height: int) -> int:
    fps, seconds = 30, args.seconds
    sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "tests")]
    from app import media, tools
    from app.render_api import export_media
    from app.render_document import validate_document
    from conftest import make_project

    ffmpeg = tools.ffmpeg()
    source = os.path.join(data, "clip.mp4")
    length = seconds * 2 + 3
    # MPEG-4 Part 2 and AAC are in every ffmpeg formcut runs, the LGPL builds included.
    lavfi = ["-f", "lavfi", "-i", f"testsrc2=size={width}x{height}:rate={fps}:duration={length}", "-f", "lavfi", "-i", f"sine=d={length}"]
    subprocess.run([ffmpeg, "-v", "error", "-y", *lavfi, "-c:v", "mpeg4", "-q:v", "2", "-c:a", "aac", "-shortest", source], check=True)
    clip_id = media.ingest_path(Path(source), "clip.mp4")["id"]

    def video(cid: str, start: float, duration: float, **extra) -> dict:
        clip = {"id": cid, "kind": "video", "label": cid, "mediaId": clip_id, "start": start, "duration": duration}
        return {**clip, "sourceIn": 0.0, **extra}

    def stacked(*tracks: list) -> dict:
        project = make_project(width=width, height=height, fps=fps, duration=seconds, clips=tracks[0])
        project["timelines"][0]["tracks"] += [{"id": f"t{i}", "name": "V", "clips": c} for i, c in enumerate(tracks[1:], 1)]
        return project

    half, part = seconds / 2, seconds * 0.4
    scenes = {
        "cut only": stacked([video("a", 0, half), {**video("b", half, seconds - half), "sourceIn": seconds}]),
        "graded clip": stacked([video("a", 0, seconds, colour=GRADE)]),
        "faded picture in picture": stacked(
            [video("a", 0, seconds)], [video("p", 0.2, seconds - 0.4, transform={"scale": 40, "x": 25, "y": -20}, fadeIn=0.5, fadeOut=0.5)]
        ),
        "overlapping clips with fades": stacked(
            [video("a", 0, seconds - part, fadeOut=part)], [{**video("b", seconds - 2 * part, 2 * part, fadeIn=part), "sourceIn": seconds}]
        ),
    }

    machine = {
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cores": os.cpu_count(),
        "size": f"{width}x{height}",
        "seconds": seconds,
    }
    print(f"formcut export routes on {machine['platform']}, {machine['cores']} cores, {seconds:g} s at {width}x{height}\n")
    results = []
    # The first export in a process detects the encoders (a test encode each)
    # and fills caches; one discarded export keeps that off the first scene.
    os.environ["FORMCUT_EXPORT_PATH"] = ""
    export_media(validate_document(scenes["cut only"]), "warm-up", lambda f: None, lambda: False, "mp4", "high", codec_name="h264")
    for name, project in scenes.items():
        runs = {}
        for route, value in ROUTES.items():
            os.environ["FORMCUT_EXPORT_PATH"] = value
            started = time.perf_counter()
            done = export_media(
                validate_document(project),
                f"{name.replace(' ', '-')}-{route}",
                lambda f: None,
                lambda: False,
                "mp4",
                "high",
                codec_name="h264",
            )
            runs[route] = {
                "seconds": round(time.perf_counter() - started, 2),
                "path": done["renderPath"],
                "encoder": done.get("encoder"),
                "file": done["file"],
            }
        exact = runs["frames"]["file"]
        for route in ("auto", "layered"):
            runs[route]["psnr_vs_frames"] = psnr(ffmpeg, exact, runs[route]["file"])
        ratio = runs["frames"]["seconds"] / max(runs["layered"]["seconds"], 0.01)
        results.append(
            {
                "scene": name,
                "frames_over_layered": round(ratio, 2),
                **{k: {x: y for x, y in v.items() if x != "file"} for k, v in runs.items()},
            }
        )
        print(
            f"{name:30s} auto takes {runs['auto']['path']:7s} {runs['auto']['seconds']:6.1f} s | layered route {runs['layered']['path']:7s}"
            f" {runs['layered']['seconds']:6.1f} s, PSNR {runs['layered']['psnr_vs_frames']} dB | frames {runs['frames']['seconds']:6.1f} s"
            f" | frames/layered {ratio:4.2f}x",
            flush=True,
        )

    encoder = results[0]["auto"]["encoder"] if results else None
    print(f"\nencoder: {encoder}. Under 1.00x the frame path, exact by construction, was also the faster route.")
    if args.json:
        args.json.write_text(json.dumps({"machine": {**machine, "encoder": encoder}, "scenes": results}, indent=2) + "\n", encoding="utf-8")
        print(f"written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
