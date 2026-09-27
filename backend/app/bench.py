"""The frame-rate reading, TEST_PLAN 24: one command, both paths, real numbers.

    formcut-engine --bench [project.json] [--frames N] [--width W]
    python -m app.bench [project.json] [--frames N] [--width W]

Renders N frames of a project (the demo when none is given) twice, on the
CPU reference path and on the device path, and prints the adapter, the
frames per second of each, the ratio, how many layers stayed on the device
between their passes and the blend, and the largest pixel difference between
the two. The device path is only faster than NumPy on a real adapter, which
this file cannot supply; it makes the number a minute's work wherever one is.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


def _demo_project() -> dict:
    """The most recent project in the data directory, the demo when it is there; the app builds the demo, so the bench reads what it saved."""
    from .paths import DATA_DIR

    store = DATA_DIR / "projects.json"
    if not store.is_file():
        return _synthetic_project()
    data = json.loads(store.read_text(encoding="utf-8"))
    projects = data if isinstance(data, list) else data.get("projects", [])
    if not projects:
        return _synthetic_project()

    # the demo by name when it is there, else the longest saved project: a one-second test project would
    # bench empty frames past its end
    def clips_in(p):
        doc = p.get("document") or p
        return sum(len(t.get("clips") or []) for tl in doc.get("timelines") or [] for t in tl.get("tracks") or [])

    named = [p for p in projects if str(p.get("title", "")).lower().startswith("demo")]
    projects = sorted(named or projects, key=clips_in, reverse=True)
    demos = [p for p in projects if "demo" in str(p.get("title", p.get("name", ""))).lower()]
    return (demos or projects)[-1]


def _hdr_project(width: int = 1920, height: int = 1080, seconds: float = 4.0) -> dict:
    """A PQ timeline for the HDR scenarios: a ten-bit PQ clip made by ffmpeg once and ingested through the app's
    own media model (a moving gradient with light to full scale), over a lifted title, in a project whose output
    colour is PQ, so the frames run deep, the monitor rolls them off and the export keeps the light."""
    from .media import MEDIA_DIR, ingest_path

    clip = MEDIA_DIR / "bench-pq.mp4"
    if not clip.is_file():
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=white:s={width}x{height}:r=30:d={seconds},format=rgb48le,geq=r='(X+T*200)/W*65535':g='Y/H*65535':b='65535'",
                "-c:v",
                "libx265",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p10le",
                "-color_primaries",
                "bt2020",
                "-color_trc",
                "smpte2084",
                "-colorspace",
                "bt2020nc",
                "-x265-params",
                "log-level=0",
                str(clip),
            ],
            check=True,
        )
    record = ingest_path(clip, "bench-pq.mp4", {"source": "bench"})
    base = {
        "scale": 100,
        "posX": 0,
        "posY": 0,
        "rotation": 0,
        "width": 100,
        "height": 100,
        "opacity": 100,
        "blendMode": "Normal",
        "flipH": False,
    }
    return {
        "title": "bench-hdr",
        "width": width,
        "height": height,
        "fps": 30,
        "duration": seconds,
        "activeTimeline": 0,
        "outputColour": "pq",
        "timelines": [
            {
                "id": "t",
                "name": "t",
                "tracks": [
                    {
                        "id": "titles",
                        "name": "Titles",
                        "clips": [
                            {
                                "id": "t",
                                "kind": "text",
                                "label": "bench",
                                "start": 0,
                                "duration": seconds,
                                "transform": {**base, "posY": -30},
                                "textStyle": {"content": "formcut HDR bench", "size": 8, "color": "#ffffff"},
                            }
                        ],
                    },
                    {
                        "id": "video",
                        "name": "Video",
                        "clips": [
                            {
                                "id": "a",
                                "kind": "video",
                                "label": "a",
                                "mediaId": record["id"],
                                "start": 0,
                                "duration": seconds,
                                "transform": dict(base),
                                "effects": [{"id": "teal-amber", "amount": 0.6}],
                            }
                        ],
                    },
                ],
            }
        ],
    }


def _export_rate(doc: dict, width: int, frames: int) -> tuple[float, str]:
    """Frames a second through the real export (render_api.export_media): the encoder the export chooses on this
    machine (VideoToolbox, NVENC, QSV, AMF or the software one), the HDR two-pass with the light written into the
    stream for a deep project, the hold on a fast path, all of it; the file is discarded. The encoder's name comes
    back with the rate so the reading says what it measured."""
    import uuid

    from .render_api import OUTPUTS, export_media

    fps = float(doc.get("fps", 30) or 30)
    trimmed = json.loads(json.dumps(doc))
    trimmed["duration"] = frames / fps
    for timeline in trimmed.get("timelines") or []:
        for track in timeline.get("tracks") or []:
            for clip in track.get("clips") or []:
                clip["duration"] = min(float(clip.get("duration") or 0), trimmed["duration"])
    trimmed["width"], trimmed["height"] = width, round(width * doc["height"] / doc["width"] / 2) * 2
    job_id = "bench-" + uuid.uuid4().hex[:8]
    began = time.perf_counter()
    result = export_media(
        trimmed,
        job_id,
        lambda fraction: None,
        lambda: False,
        "mp4",
        "high",
        "hevc" if doc.get("outputColour") in ("hlg", "pq") else None,
        False,
        None,
        None,
        True,
    )
    took = time.perf_counter() - began
    for item in OUTPUTS.glob(job_id + "*"):
        item.unlink(missing_ok=True)
    encoder = str(result.get("encoder") or "")
    return (frames / took if took > 0 else 0.0), encoder


def _synthetic_project() -> dict:
    """A repeatable timeline for a machine that has never opened the app (a CI runner): the demo media
    seeded through the model the app uses, the two clips stacked with a grade, a mask and a title."""
    from .demo import seed_demo

    media = seed_demo()["media"]
    videos = [m for m in media if m.get("kind") == "video"]
    if not videos:
        raise SystemExit("the demo media did not seed; pass a project.json")
    base = {
        "scale": 100,
        "posX": 0,
        "posY": 0,
        "rotation": 0,
        "width": 100,
        "height": 100,
        "opacity": 100,
        "blendMode": "Normal",
        "flipH": False,
    }
    clips_a = [
        {
            "id": "a",
            "kind": "video",
            "label": "a",
            "mediaId": videos[0]["id"],
            "start": 0,
            "duration": 6,
            "transform": dict(base),
            "effects": [{"id": "teal-amber", "amount": 0.8}],
        }
    ]
    clips_b = []
    if len(videos) > 1:
        clips_b = [
            {
                "id": "b",
                "kind": "video",
                "label": "b",
                "mediaId": videos[1]["id"],
                "start": 0,
                "duration": 6,
                "transform": {**base, "scale": 45, "posX": 22, "posY": 18},
                "mask": {"shape": "ellipse", "x": 5, "y": 5, "w": 90, "h": 90, "feather": 4},
            }
        ]
    title = [
        {
            "id": "t",
            "kind": "text",
            "label": "bench",
            "start": 0,
            "duration": 6,
            "transform": {**base, "posY": -30},
            "textStyle": {"content": "formcut bench", "size": 8, "color": "#ffffff"},
        }
    ]
    return {
        "title": "bench",
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "activeTimeline": 0,
        "timelines": [
            {
                "id": "t",
                "name": "t",
                "tracks": [
                    {"id": "titles", "name": "Titles", "clips": title},
                    {"id": "over", "name": "Overlay", "clips": clips_b},
                    {"id": "video", "name": "Video", "clips": clips_a},
                ],
            }
        ],
    }


def _load(path: str | None) -> dict:
    data = _demo_project() if not path else json.loads(Path(path).read_text(encoding="utf-8"))
    doc = data.get("document") if isinstance(data.get("document"), dict) else data
    doc.setdefault("activeTimeline", 0)
    tracks = doc["timelines"][doc["activeTimeline"]]["tracks"]
    doc["duration"] = max([c["start"] + c["duration"] for t in tracks for c in t["clips"]] or [1.0])
    return doc


def _decode_floor(doc: dict, width: int, frames: int) -> float | None:
    """How fast the project's video sources decode on their own, sequentially, at this width: the ceiling either path could reach."""
    from .media import MEDIA_DIR
    from .video_source import VideoSource

    tracks = doc["timelines"][doc["activeTimeline"]]["tracks"]
    media_ids = {c["mediaId"] for t in tracks for c in t["clips"] if c.get("kind") == "video" and c.get("mediaId")}
    paths = [next(iter(MEDIA_DIR.glob(f"{m}.*")), None) for m in media_ids]
    paths = [p for p in paths if p]
    if not paths:
        return None
    total = 0.0
    for path in paths:
        source = VideoSource(str(path), width)
        source.seek(0)
        began = time.perf_counter()
        read = 0
        while read < frames:
            ok, _ = source.read()
            if not ok:
                break
            read += 1
        took = time.perf_counter() - began
        source.release()
        if read:
            total += took / read
    return len(paths) / total if total else None


def _run(doc: dict, width: int, frames: int, path: str):
    from . import gpu
    from .renderer import FrameRenderer

    os.environ["FORMCUT_COMPOSITE"] = path
    os.environ["FORMCUT_EFFECTS"] = path
    gpu._status = None
    gpu._stack_fuse = None
    renderer = FrameRenderer(doc, width)
    # Consecutive frames from one second in, as playback and export ask for
    # them; spreading the samples across the clip made every read skip a
    # run of frames through the pipe, which measured seeking, not rendering.
    fps = float(doc.get("fps", 30) or 30)
    # from the first instant footage is on screen (a saved demo may have been cut about), one second in at most
    tracks = doc["timelines"][doc.get("activeTimeline", 0)]["tracks"]
    starts = [float(c.get("start") or 0) for t in tracks for c in t.get("clips") or [] if c.get("kind") == "video"]
    first = min(starts) + 0.2 if starts else 0.0
    start = min(max(1.0, first), max(0.0, doc["duration"] - frames / fps))
    times = [start + i / fps for i in range(frames)]
    renderer.frame(times[0])  # warm: sessions, decoders, pipelines
    from . import gpu_frame as _warm_frame

    if _warm_frame._frame is not None and hasattr(_warm_frame._frame[1], "timings"):
        _warm_frame._frame[1].timings()  # the warm frame compiles kernels; it is not a frame's cost
    began = time.perf_counter()
    out = [renderer.frame(t) for t in times]
    took = time.perf_counter() - began
    resident = renderer.resident_layers
    renderer.close()
    return frames / took, out, resident


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="the frame-rate reading, CPU path against device path")
    parser.add_argument("project", nargs="?", help="a project.json; the demo when omitted")
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--hdr", action="store_true", help="bench a PQ timeline: deep frames, the export ten-bit HEVC with the light kept")
    parser.add_argument(
        "--export", action="store_true", help="also time the frame path's own encode loop (frames a second into the encoder)"
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="print the device path's twelve costliest functions by own time, for a reading that is slower than it should be",
    )
    parser.add_argument("--record", help="write the readings to this JSON table (a perf table with budgets)")
    parser.add_argument(
        "--budget",
        help="compare with a recorded table for this adapter and fail (exit 3) when a scenario is slower than the budget fraction of its record",
    )
    parser.add_argument("--budget-fraction", type=float, default=0.7, help="how much of the recorded rate a scenario must still reach")
    args = parser.parse_args(argv)
    os.environ.setdefault("FORMCUT_NO_WARM", "1")
    from . import gpu

    doc = _hdr_project(args.width, round(args.width * 9 / 16 / 2) * 2) if args.hdr else _load(args.project)
    status = gpu.status()
    from . import gpu_frame

    frame_path = gpu_frame.status()
    print(
        f"frame path:  {'rust, one command buffer a frame, on ' + frame_path['adapter'] if frame_path['available'] else 'python, one submit a pass (' + frame_path['reason'] + ')'}"
    )
    if not status.get("available"):
        print("no WebGPU adapter in this interpreter: " + str(status.get("reason", "wgpu is not importable")))
        print("this is not a reading. Run the bench with the engine's own Python, the one that has wgpu installed:")
        print("  cd backend && ../.venv/bin/python -m app.bench     (or the interpreter $FORMCUT_MCP names in the agent terminal)")
        print("  or: python3 -m pip install -r requirements.txt && python3 -m app.bench")
        return 2
    adapter = status.get("adapter", {})
    name = adapter.get("device", adapter.get("name", "none"))
    print(f"adapter: {name} ({adapter.get('adapter_type', 'unknown')}, {adapter.get('backend_type', '')})")
    print(f"project: {doc.get('title', 'demo')} at {args.width} wide, {args.frames} consecutive frames at {doc.get('fps', 30)} fps")
    floor = _decode_floor(doc, args.width, args.frames)
    if floor:
        print(f"decode floor: {floor:6.2f} fps   (the video sources read sequentially at this width, no rendering; both paths pay this)")
    cpu_fps, cpu_frames, _ = _run(doc, args.width, args.frames, "cpu")
    print(f"cpu path:    {cpu_fps:6.2f} fps")
    if args.profile:
        import cProfile
        import io
        import pstats

        profiler = cProfile.Profile()
        profiler.enable()
    dev_fps, dev_frames, resident = _run(doc, args.width, args.frames, "gpu")
    if args.profile:
        profiler.disable()
        from . import gpu_frame as _frame_path

        if _frame_path.available() and _frame_path._frame is not None:
            record, wait, copy_out = _frame_path._frame[1].timings()
            print(f"executor a frame: record and submit {record:.2f} ms, device {wait:.2f} ms, copy out {copy_out:.2f} ms")
        # what the sources really were: the decoder class, whether it ran deep and what dtype its frames had
        from .video_source import _hw_choice

        print(
            f"decoders: hardware choice per stream {[(k[0], k[3], v is not None) for k, v in _hw_choice.items()] or 'not measured'}; frames deep: {dev_frames[0].dtype.name if dev_frames else 'none'}"
        )
        text = io.StringIO()
        pstats.Stats(profiler, stream=text).sort_stats("tottime").print_stats(12)
        print("\n".join(line[:140] for line in text.getvalue().splitlines()[4:20]))
    fault = gpu.stack_fault()
    print(f"device path: {dev_fps:6.2f} fps   ({dev_fps / cpu_fps:.2f}x)   layers resident on the device: {resident}")
    if fault:
        print(f"stack fault: {fault}")
    # deep frames are compared in byte-equivalent counts, so the gate reads the same for an HDR timeline
    scale = 257 if cpu_frames and cpu_frames[0].dtype == np.uint16 else 1
    diffs = [
        np.abs(a[:, :, :3].astype(np.int64) - b[:, :, :3].astype(np.int64)) / scale for a, b in zip(cpu_frames, dev_frames, strict=True)
    ]
    mad = float(np.mean([d.mean() for d in diffs]))
    over = float(np.mean([(d > 1).mean() for d in diffs]) * 100)
    worst = max(round(float(d.max())) for d in diffs)
    print(f"difference between the paths: mean {mad:.4f} counts, {over:.3f}% of pixels over 1/255, largest {worst}/255")
    if adapter.get("adapter_type", "").lower() == "cpu":
        print("this adapter is a software rasteriser; the device path shares the CPU with NumPy here,")
        print("and the reading that matters is on a real GPU")
    # A perf table with budgets: every reading is a scenario keyed by the adapter, the width and the frame
    # count; --record writes them, --budget reads them back and fails when a scenario fell below the budget
    # fraction of its recorded rate on the same adapter, so a regression is caught by a machine before a person.
    scenario = f"{args.width}w-{args.frames}f" + ("-hdr" if args.hdr else "")
    readings = {
        "decode_floor": floor or 0.0,
        "cpu_fps": cpu_fps,
        "device_fps": dev_fps,
        "difference_mean": mad,
        "difference_max": int(worst),
    }
    if args.export:
        os.environ["FORMCUT_COMPOSITE"] = "gpu"
        os.environ["FORMCUT_EFFECTS"] = "gpu"
        gpu._status = None
        export_fps, encoder = _export_rate(doc, args.width, args.frames)
        readings["export_fps"] = export_fps
        readings["export_encoder"] = encoder
        what = f"the real export, {encoder}" + (", ten-bit PQ with the light written" if args.hdr else "")
        print(f"export:      {export_fps:6.2f} fps   ({what}, render and encode included)")
    if args.record:
        table = {}
        if os.path.exists(args.record):
            with open(args.record, encoding="utf-8") as handle:
                table = json.load(handle)
        table.setdefault(name, {})[scenario] = readings
        with open(args.record, "w", encoding="utf-8") as handle:
            json.dump(table, handle, indent=1)
        print(f"recorded {name} / {scenario} into {args.record}")
    if args.budget and os.path.exists(args.budget):
        with open(args.budget, encoding="utf-8") as handle:
            table = json.load(handle)
        recorded = table.get(name, {}).get(scenario)
        if recorded is None:
            print(f"no record for {name} / {scenario} in {args.budget}; nothing to hold against")
        else:
            failed = []
            for key in ("cpu_fps", "device_fps"):
                floor_rate = recorded[key] * args.budget_fraction
                state = "ok" if readings[key] >= floor_rate else "BELOW BUDGET"
                print(
                    f"budget {key}: {readings[key]:.2f} against {recorded[key]:.2f} recorded ({args.budget_fraction:.0%} = {floor_rate:.2f}) {state}"
                )
                if readings[key] < floor_rate:
                    failed.append(key)
            if readings["difference_max"] > max(8, recorded["difference_max"]):
                print(f"budget parity: largest {readings['difference_max']}/255 against {recorded['difference_max']} recorded BELOW BUDGET")
                failed.append("parity")
            if failed:
                print("perf budget failed: " + ", ".join(failed))
                return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
