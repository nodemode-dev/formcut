"""The planar tracker's benchmark: synthetic shots whose true corners are known.

    backend/venv/bin/python -m app.planar_bench --size 1920x1080 --frames 600 [--scenario strong]

A textured plane is moved through a path (drift, zoom, turn, keystone) over a background, then the shot is spoiled as
a scenario asks: noise, motion blur along the motion, light change, an occluder crossing the plane, low texture. The
tracker follows the plane from the first frame's drawn region; each frame's error is the mean distance of the tracked
corners from the true ones. A scenario passes at P0's bar (DEV_PLAN_planar_tracking.md, section 7): unoccluded mean
under 0.5 px and worst under 1.5 px at 1080p, the same with an occluder excluded, and no drift (the last frames as
good as the first).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from .planar import Settings, corners_of, track


@dataclass
class Scenario:
    name: str
    frames: int = 120
    width: int = 640
    height: int = 360
    path: str = "moderate"  # "moderate" or "strong" (wide perspective, scale to 3x, fast turns)
    noise: float = 5.0
    blur: bool = False  # motion blur along each frame's motion
    light: bool = False  # gain and offset drifting over the shot
    occluder: bool = False
    exclude: bool = False  # the occluder given to the tracker as an exclusion matte (a layer in front)
    texture: str = "detailed"  # or "low"
    shape: float = 0.92  # the drawn shape's size against the plane: inside its edges (under 1), or taking them in
    settings: dict = field(default_factory=lambda: {"perspective": True})
    seed: int = 7


SCENARIOS = {
    "moderate": Scenario("moderate"),
    "occluded": Scenario("occluded", occluder=True),
    "excluded": Scenario("excluded", occluder=True, exclude=True),
    "strong": Scenario("strong", path="strong"),
    "blur-light": Scenario("blur-light", blur=True, light=True),
    "low-texture": Scenario("low-texture", texture="low", settings={"perspective": True, "channel": "auto"}),
    "similarity": Scenario("similarity", path="flat", settings={}),
    "translation": Scenario("translation", path="slide", settings={"scale": False, "rotation": False}),
}


def _texture(rng: np.random.Generator, kind: str) -> np.ndarray:
    h, w = 720, 960
    if kind == "low":
        # a soft, low-contrast surface: a gradient with faint grain and a few faint marks (a wall, a sky-lit board)
        base = np.tile(np.linspace(90, 150, w, dtype=np.float32), (h, 1))
        base += cv2.GaussianBlur(rng.normal(0, 18, (h, w)).astype(np.float32), (0, 0), 5)
        for _ in range(12):
            cv2.circle(
                base, (int(rng.integers(0, w)), int(rng.integers(0, h))), int(rng.integers(20, 70)), float(rng.integers(100, 140)), -1
            )
        img = np.clip(cv2.GaussianBlur(base, (0, 0), 2), 0, 255).astype(np.uint8)
        return cv2.merge([img, (img * 0.9).astype(np.uint8), (img * 0.8).astype(np.uint8)])
    img = cv2.GaussianBlur((rng.random((h, w)) * 255).astype(np.uint8), (0, 0), 2.2)
    for _ in range(60):
        cv2.circle(img, (int(rng.integers(0, w)), int(rng.integers(0, h))), int(rng.integers(8, 50)), int(rng.integers(0, 255)), -1)
    for i, word in enumerate(("FORMCUT", "PLANAR", "TRACK")):
        cv2.putText(img, word, (60, 200 + i * 200), cv2.FONT_HERSHEY_SIMPLEX, 5, 255 - i * 80, 12)
    colour = cv2.applyColorMap(img, cv2.COLORMAP_TWILIGHT)
    return cv2.addWeighted(colour, 0.6, cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), 0.4, 0)


def _corners(t: float, s: Scenario) -> np.ndarray:
    """The plane's true corners at time t (frames), in pixels."""
    u = s.width / 640.0  # paths are written for 640 x 360 and scale with the frame
    if s.path == "slide":
        cx, cy, size, turn, tilt, lean = 320 + 150 * np.sin(t * 0.03), 180 + 70 * np.sin(t * 0.021 + 1), 0.42, 0.0, 0.0, 0.0
    elif s.path == "flat":
        cx, cy = 320 + 120 * np.sin(t * 0.03), 180 + 50 * np.sin(t * 0.02 + 1)
        size, turn, tilt, lean = 0.32 + 0.12 * np.sin(t * 0.025), 0.6 * np.sin(t * 0.017), 0.0, 0.0
    elif s.path == "strong":
        cx, cy = 320 + 130 * np.sin(t * 0.031), 180 + 60 * np.sin(t * 0.023 + 1)
        size = 0.2 * 3.0 ** (0.5 + 0.5 * np.sin(t * 0.02))  # 0.2 to 0.6: three times
        turn, tilt, lean = 0.9 * np.sin(t * 0.016), 0.55 * np.sin(t * 0.027), 0.35 * np.sin(t * 0.019 + 2)
    else:
        cx, cy = 320 + 90 * np.sin(t * 0.04), 180 + 40 * np.sin(t * 0.03 + 1)
        size, turn, tilt, lean = 0.36 + 0.12 * np.sin(t * 0.025), 0.35 * np.sin(t * 0.02), 0.25 * np.sin(t * 0.035), 0.0
    base = np.array([[-240.0, -180.0], [240.0, -180.0], [240.0, 180.0], [-240.0, 180.0]]) * size
    # keystone (the plane turning away about its vertical axis) and lean (about its horizontal axis)
    base[:, 1] *= 1 + tilt * np.array([-1, 1, 1, -1]) * 0.8
    base[:, 0] *= 1 + lean * np.array([-1, -1, 1, 1]) * 0.8
    rot = np.array([[np.cos(turn), -np.sin(turn)], [np.sin(turn), np.cos(turn)]])
    return ((base @ rot.T + [cx, cy]) * u).astype(np.float64)


def _occluder(t: int, s: Scenario) -> tuple[int, int, int, int] | None:
    start, span = int(s.frames * 0.35), int(s.frames * 0.25)
    if not s.occluder or not start <= t < start + span:
        return None
    u = s.width / 640.0
    x = int((140 + (t - start) * 300 / max(1, span)) * u)
    return x, int(70 * u), x + int(80 * u), int(300 * u)


def shot(s: Scenario) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray | None]]:
    """The frames, the true corners per frame, and the occluder's matte per frame (or None)."""
    rng = np.random.default_rng(s.seed)
    tex = _texture(rng, s.texture)
    th, tw = tex.shape[:2]
    src = np.float32([[0, 0], [tw, 0], [tw, th], [0, th]])
    bg = cv2.GaussianBlur((rng.random((s.height, s.width, 3)) * 255).astype(np.uint8), (0, 0), 6 * s.width / 640)
    frames, truth, mattes = [], [], []
    for t in range(s.frames):
        c = _corners(t, s)
        h = cv2.getPerspectiveTransform(src, c.astype(np.float32))
        f = bg.copy()
        warped = cv2.warpPerspective(tex, h, (s.width, s.height), flags=cv2.INTER_LINEAR)
        inside = cv2.warpPerspective(np.full((th, tw), 255, np.uint8), h, (s.width, s.height)) > 127
        f[inside] = warped[inside]
        if s.blur:
            # motion blur along this frame's motion: the average of the plane over the shutter
            d = c.mean(0) - _corners(t - 1, s).mean(0)
            length = max(1, round(float(np.linalg.norm(d))))
            if length > 1:
                # centred on the frame's moment, as a shutter is: from half the motion before to half after
                kernel = np.zeros((length * 2 + 1, length * 2 + 1), np.float32)
                cv2.line(
                    kernel,
                    (round(length - d[0] / 2), round(length - d[1] / 2)),
                    (round(length + d[0] / 2), round(length + d[1] / 2)),
                    1,
                    1,
                )
                f = cv2.filter2D(f, -1, kernel / kernel.sum())
        box = _occluder(t, s)
        matte = None
        if box:
            cv2.rectangle(f, box[:2], box[2:], (40, 45, 50), -1)
            matte = np.zeros((s.height, s.width), np.uint8)
            cv2.rectangle(matte, (box[0] - 6, box[1] - 6), (box[2] + 6, box[3] + 6), 255, -1)
        if s.light:
            gain, offset = 1 + 0.35 * np.sin(t * 0.05), 20 * np.sin(t * 0.031)
            f = np.clip(f.astype(np.float32) * gain + offset, 0, 255)
        f = cv2.GaussianBlur(np.asarray(f, np.float32), (0, 0), 0.7)
        f = np.clip(f + rng.normal(0, s.noise, f.shape), 0, 255).astype(np.uint8)
        frames.append(f)
        truth.append(c)
        mattes.append(matte)
    return frames, truth, mattes


def run(s: Scenario, backwards: bool = False) -> dict:
    """The scenario tracked from its first frame (or its last, backwards), scored."""
    frames, truth, mattes = shot(s)
    start, stop = (len(frames) - 1, 0) if backwards else (0, len(frames) - 1)
    c0 = truth[start]
    drawn = np.zeros((s.height, s.width), np.uint8)
    centre = c0.mean(0)
    cv2.fillPoly(drawn, [((c0 - centre) * s.shape + centre).astype(np.int32)], 255)  # inside the edges, or around them
    t0 = time.perf_counter()
    found = track(
        lambda i: frames[i],
        start,
        stop,
        drawn,
        Settings(**s.settings),
        exclude=(lambda i: mattes[i]) if s.exclude else None,
    )
    seconds = time.perf_counter() - t0
    errors, occluded, confidence = [], [], []
    for i, (h, conf) in found.items():
        if i == start:
            continue
        e = float(np.linalg.norm(corners_of(h, c0) - truth[i], axis=1).mean())
        (occluded if mattes[i] is not None else errors).append(e)
        confidence.append(conf)
    every = errors + occluded
    tail = [float(np.linalg.norm(corners_of(found[i][0], c0) - truth[i], axis=1).mean()) for i in sorted(found)[-10:] if i != start]
    head = [float(np.linalg.norm(corners_of(found[i][0], c0) - truth[i], axis=1).mean()) for i in sorted(found)[1:11] if i != start]
    return {
        "scenario": s.name + (" (backwards)" if backwards else ""),
        "size": f"{s.width}x{s.height}",
        "frames": s.frames,
        "mean": round(float(np.mean(every)), 3),
        "unoccludedMean": round(float(np.mean(errors)), 3) if errors else None,
        "unoccludedWorst": round(float(np.max(errors)), 3) if errors else None,
        "occludedMean": round(float(np.mean(occluded)), 3) if occluded else None,
        "occludedWorst": round(float(np.max(occluded)), 3) if occluded else None,
        "first10": round(float(np.mean(head)), 3),
        "last10": round(float(np.mean(tail)), 3),
        "lowestConfidence": round(float(min(confidence)), 3) if confidence else None,
        "msPerFrame": round(seconds * 1000 / max(1, len(found) - 1), 1),
    }


def passes(r: dict) -> bool:
    """P0's bar as the plan writes it, in pixels at the size run: unoccluded mean under 0.5 and worst under 1.5, the same
    through an occluder that is excluded, and no drift (the last frames within three times the first, or under the
    mean bar). Run at 1080p, the size the bar is written for, for the verdict that counts. (Scaling the bar down with
    the frame was tried and dropped: sub-pixel error does not shrink with the frame, and the scaled bar failed shots
    that pass at 1080p.)"""
    mean_limit, worst_limit = 0.5, 1.5
    ok = r["unoccludedMean"] is None or (r["unoccludedMean"] < mean_limit and r["unoccludedWorst"] < worst_limit)
    if r["occludedMean"] is not None and "excluded" in r["scenario"]:
        ok = ok and r["occludedMean"] < mean_limit and r["occludedWorst"] < worst_limit
    return ok and r["last10"] < max(mean_limit, r["first10"] * 3 + 0.1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="formcut's planar tracker on synthetic shots with known corners")
    parser.add_argument("--size", default="1920x1080")
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--scenario", action="append", choices=sorted(SCENARIOS), help="one or more; all by default")
    parser.add_argument("--backwards", action="store_true", help="track from the last frame to the first")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    width, height = (int(v) for v in args.size.lower().split("x"))
    results, failed = [], 0
    for name in args.scenario or list(SCENARIOS):
        base = SCENARIOS[name]
        s = Scenario(**{**base.__dict__, "width": width, "height": height, "frames": args.frames})
        r = run(s, backwards=args.backwards)
        r["passes"] = passes(r)
        failed += not r["passes"]
        results.append(r)
        if not args.json:
            print(
                f"{r['scenario']:22} {r['size']:>9} {r['frames']:>4} frames | mean {r['mean']:.3f} px, unoccluded worst {r['unoccludedWorst']} px,"
                f" occluded mean {r['occludedMean']} | first 10 {r['first10']:.3f}, last 10 {r['last10']:.3f} | {r['msPerFrame']} ms a frame"
                f" | {'passes' if r['passes'] else 'FAILS'}",
                flush=True,
            )
    if args.json:
        print(json.dumps(results, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
