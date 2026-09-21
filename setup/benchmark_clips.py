#!/usr/bin/env python3
"""formcut on real footage: scrub delay, three-layer playback, export time, peak memory.

benchmark.py measures generated scenes, which compare formcut with itself. This
takes clips, so the same files timed in another editor give a like-for-like
comparison:

    python setup/benchmark_clips.py a.mp4 [b.mp4 c.mp4] [--seconds 60] [--frames] [--json out.json]

- scrub: random seeks at preview size, as the editor's preview renders them;
  the delay from asking for a moment to having its pixels, median and p95
- playback: three layers, the first clip full frame and the others picture in
  picture, each graded, rendered in order at preview size, frames a second
- export: the first --seconds of the first clip at 1920x1080 and 3840x2160,
  by whichever route formcut takes; with --frames, also through the frame path
- peak memory: the engine's own, and the largest ffmpeg it started

Everything is written to a temporary data folder that is removed afterwards;
the clips are only read.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
DATA = tempfile.mkdtemp(prefix="formcut-benchmark-")
os.environ["FORMCUT_DATA_DIR"] = DATA
GRADE = {"exposure": 0.2, "contrast": 12, "saturation": 15, "temperature": 7200, "highlights": -10, "shadows": 8}


def peak_mb() -> dict:
    try:
        import resource
    except ImportError:
        return {}
    scale = 1 / 1048576 if sys.platform == "darwin" else 1 / 1024
    own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
    child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * scale
    return {"engine_mb": round(own, 1), "largest_ffmpeg_mb": round(child, 1)}


def document(width: int, height: int, fps: int, tracks: list[list[dict]]) -> dict:
    from app.render_document import validate_document

    rows = [{"id": f"t{i}", "name": f"V{i}", "clips": clips} for i, clips in enumerate(tracks)]
    project = {"title": "benchmark", "width": width, "height": height, "fps": fps, "activeTimeline": 0}
    return validate_document({**project, "timelines": [{"id": "b", "name": "b", "tracks": rows}]})


def clip(clip_id: str, media: dict, seconds: float, **extra) -> dict:
    return {
        "id": clip_id,
        "kind": "video",
        "label": clip_id,
        "mediaId": media["id"],
        "start": 0,
        "duration": seconds,
        "sourceIn": 0,
        **extra,
    }


def scrub(project: dict, width: int, count: int, length: float) -> dict:
    from app.renderer import FrameRenderer

    renderer = FrameRenderer(project, width)
    # Seeded so every run, and every editor, seeks to the same moments.
    moments = [random.Random(7 + i).uniform(0, length * 0.95) for i in range(count)]  # noqa: S311
    delays = []
    try:
        for at in moments:
            started = time.perf_counter()
            renderer.frame(at)
            delays.append((time.perf_counter() - started) * 1000)
    finally:
        renderer.close()
    ordered = sorted(delays)
    return {"seeks": count, "median_ms": round(statistics.median(ordered), 1), "p95_ms": round(ordered[int(0.95 * (len(ordered) - 1))], 1)}


def playback(project: dict, width: int, seconds: float) -> dict:
    from app.renderer import FrameRenderer

    renderer = FrameRenderer(project, width)
    frames = max(1, int(seconds * project["fps"]))
    started = time.perf_counter()
    try:
        for index in range(frames):
            renderer.frame(index / project["fps"])
    finally:
        renderer.close()
    return {"frames": frames, "fps": round(frames / (time.perf_counter() - started), 2)}


def export(project: dict, name: str, route: str) -> dict:
    from app.render_api import export_media

    os.environ["FORMCUT_EXPORT_PATH"] = "frames" if route == "frames" else ""
    started = time.perf_counter()
    result = export_media(project, name, lambda fraction: None, lambda: False, "mp4", "high")
    seconds = time.perf_counter() - started
    Path(result["file"]).unlink(missing_ok=True)
    return {
        "seconds": round(seconds, 1),
        "route": result.get("renderPath"),
        "encoder": result["encoder"],
        "x_realtime": round(project["duration"] / seconds, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("clips", nargs="+", type=Path)
    parser.add_argument("--seconds", type=float, default=60.0, help="how much of the first clip to export")
    parser.add_argument("--seeks", type=int, default=30)
    parser.add_argument("--preview", type=int, default=1280, help="preview width, as the editor renders it")
    parser.add_argument("--frames", action="store_true", help="also export through the frame path")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    missing = [str(path) for path in args.clips if not path.is_file()]
    if missing:
        print("not found: " + ", ".join(missing))
        return 2
    from app import media

    try:
        records = []
        for path in args.clips:
            copy = Path(DATA) / f"source{len(records)}{path.suffix}"
            shutil.copy2(path, copy)
            records.append(media.ingest_path(copy, path.name))
        first = records[0]
        length = min(args.seconds, float(first.get("duration") or args.seconds))
        fps = max(1, round(float(first.get("fps") or 30)))
        layers = [records[i % len(records)] for i in range(3)]
        report: dict = {
            "clips": [str(path) for path in args.clips],
            "source": {k: first.get(k) for k in ("width", "height", "fps", "duration")},
        }
        single = document(3840, 2160, fps, [[clip("a", first, length)]])
        report["scrub"] = scrub(single, args.preview, args.seeks, length)
        stacked = document(
            3840,
            2160,
            fps,
            [
                [clip("top", layers[2], length, colour=GRADE, transform={"scale": 40, "posX": 28, "posY": -28})],
                [clip("middle", layers[1], length, colour=GRADE, transform={"scale": 40, "posX": -28, "posY": 28})],
                [clip("bottom", layers[0], length, colour=GRADE)],
            ],
        )
        report["playback_three_layers_graded"] = playback(stacked, args.preview, min(10.0, length))
        for label, size in (("1080p", (1920, 1080)), ("4k", (3840, 2160))):
            project = document(*size, fps, [[clip("a", first, length)]])
            report[f"export_{label}"] = export(project, f"bench-{label}", "")
            if args.frames:
                report[f"export_{label}_frame_path"] = export(project, f"bench-{label}-frames", "frames")
        report["peak_memory"] = peak_mb()
    finally:
        shutil.rmtree(DATA, ignore_errors=True)
    text = json.dumps(report, indent=2)
    print(text)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
