#!/usr/bin/env python3
"""Golden frames, and the preview-versus-export check.

formcut renders the preview and the export through one renderer. That is the
sturdiest thing about it and the easiest thing to lose: a shortcut taken in the
preview path, a filter applied in one place and not the other, and the two
drift apart without anything failing. Editors with separate paths show this as
a transition that previews as a dissolve and exports as a wipe.

So this checks two things on every push:

1. **Fixed projects render to fixed frames.** The scenes below are built from
   generated colour and text, never from media on disk, so they render the same
   on any machine. Each frame's hash is stored beside this script. A change in
   output is not assumed to be a regression, but it has to be looked at and the
   golden updated deliberately.

2. **The preview path and the export path agree.** The same moment is rendered
   through a preview-sized renderer and through the export renderer, scaled to
   match, and compared. They should be within rounding of each other.

Update the goldens on purpose, never to make the check pass:

    python setup/golden_frames.py --update
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

GOLDEN = Path(__file__).resolve().parent / "golden_frames.json"


def scene(name: str) -> dict:
    """Projects made only of generated content, so they render anywhere."""
    text = {"content": "FORMCUT", "size": 12, "color": "#ffcc55", "bold": True, "align": "center"}
    base = {"title": name, "width": 320, "height": 180, "fps": 30, "duration": 4, "activeTimeline": 0}
    if name == "title":
        clips = [{"id": "a", "kind": "text", "label": "t", "start": 0, "duration": 4, "textStyle": text}]
    elif name == "transform":
        clips = [{"id": "a", "kind": "text", "label": "t", "start": 0, "duration": 4, "textStyle": text,
                  "transform": {"scale": 60, "posX": 12, "posY": -8, "rotation": 15, "width": 100,
                                "height": 100, "opacity": 90, "blendMode": "Normal", "flipH": False}}]
    elif name == "keyframes":
        clips = [{"id": "a", "kind": "text", "label": "t", "start": 0, "duration": 4, "textStyle": text,
                  "keyframes": [{"t": 0, "props": {"scale": 40}, "interp": "ease"},
                                {"t": 4, "props": {"scale": 120}, "interp": "linear"}]}]
    elif name == "mask":
        clips = [{"id": "a", "kind": "text", "label": "t", "start": 0, "duration": 4, "textStyle": text,
                  "mask": {"shape": "star", "x": 10, "y": 10, "w": 80, "h": 80, "feather": 4}}]
    elif name == "background":
        return {**base, "background": {"type": "gradient", "from": "#101418", "to": "#2b3440"},
                "timelines": [{"id": "x", "name": "x", "tracks": [{"id": "t", "name": "V", "clips": [
                    {"id": "a", "kind": "text", "label": "t", "start": 0, "duration": 4, "textStyle": text,
                     "transform": {"scale": 45, "posX": 0, "posY": 0, "rotation": 0, "width": 100,
                                   "height": 100, "opacity": 100, "blendMode": "Normal", "flipH": False}}]}]}]}
    elif name == "transition":
        clips = [{"id": "a", "kind": "text", "label": "a", "start": 0, "duration": 2,
                  "textStyle": {**text, "content": "ONE"}},
                 {"id": "b", "kind": "text", "label": "b", "start": 2, "duration": 2,
                  "textStyle": {**text, "content": "TWO", "color": "#55aaff"},
                  "transitionIn": {"type": "wipe-left", "duration": 1.0}}]
    else:
        raise SystemExit(f"unknown scene: {name}")
    return {**base, "timelines": [{"id": "x", "name": "x", "tracks": [{"id": "t", "name": "V", "clips": clips}]}]}


SCENES = {
    "title": [0.5, 2.0],
    "transform": [1.0],
    "keyframes": [0.0, 2.0, 3.9],
    "mask": [1.0],
    "background": [1.0],
    # Either side of the transition and in the middle of it, which is exactly
    # where a preview that cheats and an export that does not would disagree.
    "transition": [1.9, 2.5, 3.1],
}


def frame_hash(pixels) -> str:
    return hashlib.sha256(pixels[:, :, :3].tobytes()).hexdigest()[:20]


def render_all() -> dict:
    from app.renderer import FrameRenderer
    out: dict[str, str] = {}
    for name, moments in SCENES.items():
        project = scene(name)
        renderer = FrameRenderer(project)
        try:
            for at in moments:
                out[f"{name}@{at}"] = frame_hash(renderer.frame(at))
        finally:
            renderer.close()
    return out


def parity() -> list[tuple[str, float, float]]:
    """The preview path against the export path, at the same moments."""
    import cv2
    import numpy as np

    from app.renderer import FrameRenderer
    results = []
    for name, moments in SCENES.items():
        project = scene(name)
        preview = FrameRenderer(project, 160)      # a decode limit: the preview path
        export = FrameRenderer(project)            # no limit: the export path
        try:
            for at in moments:
                small = preview.frame(at)[:, :, :3].astype(np.float32)
                large = export.frame(at)[:, :, :3].astype(np.float32)
                shrunk = cv2.resize(large, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_AREA)
                error = float(np.abs(small - shrunk).mean())
                worst = float(np.abs(small - shrunk).max())
                results.append((f"{name}@{at}", error, worst))
        finally:
            preview.close()
            export.close()
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="write the current output as the golden")
    args = parser.parse_args()

    current = render_all()

    if args.update:
        GOLDEN.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {len(current)} golden frames to {GOLDEN.name}")
        return 0

    if not GOLDEN.is_file():
        print(f"no goldens yet; run with --update to create {GOLDEN.name}", file=sys.stderr)
        return 2

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    drifted = [key for key, value in current.items() if golden.get(key) != value]
    missing = [key for key in golden if key not in current]

    print(f"{len(current) - len(drifted)} of {len(current)} frames match their golden")
    for key in drifted:
        print(f"  CHANGED {key}: golden {golden.get(key, 'none')} now {current[key]}")
    for key in missing:
        print(f"  MISSING {key}: the golden has it, this run did not render it")

    print()
    worst_mean = 0.0
    for key, error, worst in parity():
        worst_mean = max(worst_mean, error)
        print(f"  preview vs export {key:18s} mean {error:6.3f}  worst pixel {worst:6.1f}")
    # Both paths run the same code, so any real difference is resampling.
    ok_parity = worst_mean < 6.0
    print(f"\npreview and export agree: {ok_parity} (worst mean difference {worst_mean:.3f})")

    if drifted or missing or not ok_parity:
        print("\nIf a change is intended, look at it, then run with --update.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
