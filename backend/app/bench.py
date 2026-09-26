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
import sys
import time
from pathlib import Path

import numpy as np


def _demo_project() -> dict:
    """The most recent project in the data directory, the demo when it is there; the app builds the demo, so the bench reads what it saved."""
    from .paths import DATA_DIR

    store = DATA_DIR / "projects.json"
    if not store.is_file():
        raise SystemExit(f"no projects at {store}; open the demo in formcut once, or pass a project.json")
    data = json.loads(store.read_text(encoding="utf-8"))
    projects = data if isinstance(data, list) else data.get("projects", [])
    if not projects:
        raise SystemExit("no saved project; open the demo in formcut once, or pass a project.json")
    demos = [p for p in projects if "demo" in str(p.get("title", p.get("name", ""))).lower()]
    return (demos or projects)[-1]


def _load(path: str | None) -> dict:
    data = _demo_project() if not path else json.loads(Path(path).read_text(encoding="utf-8"))
    doc = data.get("document") if isinstance(data.get("document"), dict) else data
    doc.setdefault("activeTimeline", 0)
    tracks = doc["timelines"][doc["activeTimeline"]]["tracks"]
    doc["duration"] = max([c["start"] + c["duration"] for t in tracks for c in t["clips"]] or [1.0])
    return doc


def _run(doc: dict, width: int, frames: int, path: str):
    from . import gpu
    from .renderer import FrameRenderer

    os.environ["FORMCUT_COMPOSITE"] = path
    os.environ["FORMCUT_EFFECTS"] = path
    gpu._status = None
    gpu._stack_fuse = None
    renderer = FrameRenderer(doc, width)
    times = [doc["duration"] * (i + 0.5) / frames for i in range(frames)]
    renderer.frame(times[0])  # warm: sessions, decoders, pipelines
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
    args = parser.parse_args(argv)
    os.environ.setdefault("FORMCUT_NO_WARM", "1")
    from . import gpu

    doc = _load(args.project)
    status = gpu.status()
    if not status.get("available"):
        print("no WebGPU adapter in this interpreter: " + str(status.get("reason", "wgpu is not importable")))
        print("this is not a reading. Run the bench with the engine's own Python, the one that has wgpu installed:")
        print("  cd backend && ../.venv/bin/python -m app.bench     (or the interpreter $FORMCUT_MCP names in the agent terminal)")
        print("  or: python3 -m pip install -r requirements.txt && python3 -m app.bench")
        return 2
    adapter = status.get("adapter", {})
    name = adapter.get("device", adapter.get("name", "none"))
    print(f"adapter: {name} ({adapter.get('adapter_type', 'unknown')}, {adapter.get('backend_type', '')})")
    print(f"project: {doc.get('title', 'demo')} at {args.width} wide, {args.frames} frames")
    cpu_fps, cpu_frames, _ = _run(doc, args.width, args.frames, "cpu")
    print(f"cpu path:    {cpu_fps:6.2f} fps")
    dev_fps, dev_frames, resident = _run(doc, args.width, args.frames, "gpu")
    fault = gpu.stack_fault()
    print(f"device path: {dev_fps:6.2f} fps   ({dev_fps / cpu_fps:.2f}x)   layers resident on the device: {resident}")
    if fault:
        print(f"stack fault: {fault}")
    diffs = [np.abs(a[:, :, :3].astype(int) - b[:, :, :3].astype(int)) for a, b in zip(cpu_frames, dev_frames, strict=True)]
    mad = float(np.mean([d.mean() for d in diffs]))
    over = float(np.mean([(d > 1).mean() for d in diffs]) * 100)
    worst = max(int(d.max()) for d in diffs)
    print(f"difference between the paths: mean {mad:.4f} counts, {over:.3f}% of pixels over 1/255, largest {worst}/255")
    if adapter.get("adapter_type", "").lower() == "cpu":
        print("this adapter is a software rasteriser; the device path shares the CPU with NumPy here,")
        print("and the reading that matters is on a real GPU")
    return 0


if __name__ == "__main__":
    sys.exit(main())
