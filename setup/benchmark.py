#!/usr/bin/env python3
"""Where formcut's render time actually goes.

The comparison that prompted this says the rendering row cannot be settled by
reading code, and that is right. This measures formcut's side of it: frame
throughput at several sizes, what each stage of the pipeline costs, what the
frame cache and proxies are worth, and how fast an export runs relative to real
time. It cannot measure another editor, so it is half a head-to-head, and the
half that can be run here.

Everything is rendered from generated content, so the numbers are comparable
between machines and between versions of formcut. Run it before and after a
change to the render path and the difference is the answer.

    python setup/benchmark.py            # the standard set
    python setup/benchmark.py --quick    # fewer frames, for a sanity check
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

TEXT = {"content": "FORMCUT", "size": 12, "color": "#ffcc55", "bold": True, "align": "center"}


def scene(width: int, height: int, *, effects: list | None = None, mask: bool = False, grade: bool = False, duration: float = 4.0) -> dict:
    clip: dict = {
        "id": "a",
        "kind": "text",
        "label": "t",
        "start": 0,
        "duration": duration,
        "textStyle": TEXT,
        "transform": {
            "scale": 80,
            "posX": 4,
            "posY": -3,
            "rotation": 6,
            "width": 100,
            "height": 100,
            "opacity": 95,
            "blendMode": "Normal",
            "flipH": False,
        },
    }
    if effects:
        clip["effects"] = effects
    if mask:
        clip["mask"] = {"shape": "star", "x": 8, "y": 8, "w": 84, "h": 84, "feather": 6}
    if grade:
        # Kelvin for temperature, and the panel's own units elsewhere.
        clip["colour"] = {"exposure": 0.2, "contrast": 12, "saturation": 15, "temperature": 7200, "highlights": -10, "shadows": 8}
    return {
        "title": "bench",
        "width": width,
        "height": height,
        "fps": 30,
        "duration": duration,
        "activeTimeline": 0,
        "timelines": [{"id": "x", "name": "x", "tracks": [{"id": "t", "name": "V", "clips": [clip]}]}],
    }


def time_frames(project: dict, count: int, width: int | None = None) -> tuple[float, float]:
    """Mean and worst milliseconds per frame, cold cache."""
    from app.renderer import FrameRenderer

    renderer = FrameRenderer(project, width) if width else FrameRenderer(project)
    try:
        renderer.frame(0.0)  # first frame pays for decoder setup; not counted
        samples = []
        for index in range(count):
            at = (index + 1) / (count + 1) * project["duration"]
            start = time.perf_counter()
            renderer.frame(at)
            samples.append((time.perf_counter() - start) * 1000)
    finally:
        renderer.close()
    return statistics.mean(samples), max(samples)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    count = 6 if args.quick else 20

    print("formcut render benchmark")
    print(f"frames per measurement: {count}\n")

    print("frame throughput by size, one text layer with a transform")
    sizes = [(640, 360), (1280, 720), (1920, 1080)] + ([] if args.quick else [(3840, 2160)])
    baseline: dict[tuple[int, int], float] = {}
    for width, height in sizes:
        mean, worst = time_frames(scene(width, height), count)
        baseline[(width, height)] = mean
        pixels = width * height
        print(f"  {width:>4}x{height:<4}  {mean:7.1f} ms   worst {worst:7.1f}   {1000 / mean:5.1f} fps   {pixels / mean / 1000:6.2f} Mpx/s")

    print("\nwhat each stage costs, at 1280x720")
    at_720 = baseline[(1280, 720)]
    stages = [
        ("transform only", scene(1280, 720)),
        ("plus a colour grade", scene(1280, 720, grade=True)),
        ("plus a star mask", scene(1280, 720, mask=True)),
        ("plus one blur", scene(1280, 720, effects=[{"id": "gaussian", "amount": 1, "params": {"radius": 8}}])),
        (
            "plus three effects",
            scene(
                1280,
                720,
                effects=[
                    {"id": "gaussian", "amount": 1, "params": {"radius": 8}},
                    {"id": "vignette", "amount": 1, "params": {}},
                    {"id": "grain", "amount": 1, "params": {}},
                ],
            ),
        ),
    ]
    for name, project in stages:
        try:
            mean, _ = time_frames(project, max(4, count // 2))
        except Exception as exc:  # noqa: BLE001 - a stage that cannot run is the finding
            print(f"  {name:<22} could not run: {str(exc)[:50]}")
            continue
        delta = mean - at_720
        print(f"  {name:<22} {mean:7.1f} ms   {'+' if delta >= 0 else ''}{delta:6.1f} ms over the baseline")

    print("\nwhat the frame cache is worth, at 1280x720")
    from app.frame_cache import FrameCache
    from app.renderer import FrameRenderer

    project = scene(1280, 720)
    renderer = FrameRenderer(project)
    cache = FrameCache(project, 64)
    try:
        moments = [i / 10 for i in range(1, 21)]
        start = time.perf_counter()
        for at in moments:
            cache.put(at, renderer.frame(at))
        cold = (time.perf_counter() - start) / len(moments) * 1000
        start = time.perf_counter()
        hits = sum(1 for at in moments if cache.get(at) is not None)
        warm = (time.perf_counter() - start) / len(moments) * 1000
    finally:
        renderer.close()
    print(f"  cold {cold:7.1f} ms per frame")
    print(f"  warm {warm:7.3f} ms per frame, {hits}/{len(moments)} hits, {cold / max(warm, 0.0001):.0f}x faster")

    print("\nexport, relative to real time")
    from app import jobs
    from app.render_api import RenderInput, export

    for width, height in [(640, 360)] if args.quick else [(640, 360), (1280, 720)]:
        project = scene(width, height, duration=3.0)
        started = export(RenderInput(project=project, format="mp4", quality="medium", codec="h264"))
        job_id = started["job_id"] if isinstance(started, dict) else started.job_id
        start = time.perf_counter()
        state: dict = {}
        for _ in range(900):
            state = jobs.status(job_id)
            if state.get("status") in ("done", "error", "failed"):
                break
            time.sleep(0.5)
        took = time.perf_counter() - start
        if state.get("status") != "done":
            print(f"  {width}x{height}: export failed: {str(state.get('error'))[:50]}")
            continue
        print(f"  {width:>4}x{height:<4}  {took:5.1f} s for 3.0 s of output   {3.0 / took:4.2f}x real time   {90 / took:5.1f} frames/s")

    print("\nNumbers move with the machine. Compare runs on one machine, not across them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
