"""The planar tracker on real footage: a green screen measured against formcut's track of it (P8 of the plan).

A screen keyed green on a flat device is a plane whose four corners can be measured on every frame without any
tracker: the green is keyed (greenness: green less the larger of red and blue, the map upsampled twice so the edge
falls between pixels), its outline taken, and each side's straight middle fitted with a line (the rounded corners and
a notch left out: the hull bridges the notch, and only points near the hull's side, away from its ends, are used);
the four lines' crossings are the screen's corners, the sharp corners its rounded ones stand for. formcut's planar
tracker then follows the screen from the first frame (its search area the measured screen grown to take in the bezel)
and every frame's carried corners are scored against the measurement. The measurement's own jitter (its corners
against a moving average of themselves) is reported too: below it, the comparison cannot see.

    backend/venv/bin/python -m app.planar_green shot.mp4 [shot2.mp4 ...] [--margin 0.08] [--frames N] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import cv2
import numpy as np

from .planar import PlanarTracker, Settings, corners_of

GREEN_LEVEL = 60  # greenness (0-255) above which a pixel is the screen


def _greenness(frame: np.ndarray, screen: str = "green") -> np.ndarray:
    """How much a pixel is the screen's colour: green (or blue) less the larger of the other two (BGR frames)."""
    b, g, r = (frame[:, :, i].astype(np.float32) for i in range(3))
    return b - np.maximum(r, g) if screen == "blue" else g - np.maximum(r, b)


def _ordered(points: np.ndarray) -> np.ndarray:
    """Four corners in a fixed order: the one nearest the image's top left first, then round as the image runs."""
    centre = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - centre[1], points[:, 0] - centre[0])
    ring = points[np.argsort(angles)]
    start = int(np.argmin(ring.sum(axis=1)))
    return np.roll(ring, -start, axis=0)


def green_quad(frame: np.ndarray, screen: str = "green") -> np.ndarray | None:
    """The green (or blue) screen's four corners on a frame (sharp corners, sub-pixel), or None where it cannot be
    found."""
    green = _greenness(frame, screen)
    big = cv2.resize(green, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    # the edge at half of the screen's own local level, not at a fixed one: where a reflection washes the green out,
    # a fixed level cuts the softened edge further in, and the measured screen shrinks with the glare (on the owner's
    # upright phone, 2 to 4 px on its side under the reflection, mistaken at first for the tracker's error)
    plateau = cv2.dilate(big, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    mask = ((big > 0.5 * np.maximum(plateau, 2 * GREEN_LEVEL)) & (big > GREEN_LEVEL / 3)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    found, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not found:
        return None
    outline = max(found, key=cv2.contourArea)
    if cv2.contourArea(outline) < 4000:
        return None
    hull = cv2.convexHull(outline)
    peri = cv2.arcLength(hull, True)
    rough = None
    for share in (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1):
        approx = cv2.approxPolyDP(hull, share * peri, True)
        if len(approx) == 4:
            rough = _ordered(approx.reshape(4, 2).astype(float))
            break
    if rough is None:
        return None
    pts = outline.reshape(-1, 2).astype(float)
    # only the outline that lies on the hull: a notch (the hull bridges it) is not the screen's edge, and on a notched
    # side it fills the middle a line would otherwise be fitted to
    rim = np.full(mask.shape, 255, np.uint8)
    cv2.polylines(rim, [hull], True, 0, 1)
    from_rim = cv2.distanceTransform(rim, cv2.DIST_L2, 3)
    on_hull = from_rim[pts[:, 1].astype(int).clip(0, mask.shape[0] - 1), pts[:, 0].astype(int).clip(0, mask.shape[1] - 1)] < 2.0
    lines = []
    for k in range(4):
        a, b = rough[k], rough[(k + 1) % 4]
        side = b - a
        length = float(np.linalg.norm(side))
        if length < 20:
            return None
        # the straight edge is the line most of the side's on-hull points lie on (RANSAC, within a pixel of the
        # twice-size map): a rounded corner's arc has few collinear points, and a wide notch (the hull bridges it)
        # leaves two short shoulders whose points line up; then a least-squares line through those points
        along = (pts - a) @ (side / length)
        off = np.abs((pts - a) @ (np.array([-side[1], side[0]]) / length))  # from this side's chord, not the others'
        candidates = pts[(along > 0.1 * length) & (along < 0.9 * length) & (off < max(16.0, 0.12 * length)) & on_hull]
        if len(candidates) < 10:
            return None
        rng = np.random.default_rng(k)
        best, best_count = None, 0
        for _ in range(150):
            i, j = rng.integers(0, len(candidates), 2)
            p0, p1 = candidates[i], candidates[j]
            span = float(np.linalg.norm(p1 - p0))
            if span < 0.2 * length:
                continue
            if abs(float((p1 - p0) @ side) / (span * length)) < 0.966:  # within 15 degrees of the side
                continue
            normal = np.array([-(p1 - p0)[1], (p1 - p0)[0]]) / span
            inliers = np.abs((candidates - p0) @ normal) < 1.0
            if inliers.sum() > best_count:
                best, best_count = inliers, int(inliers.sum())
        if best is None or best_count < 10:
            return None
        vx, vy, x0, y0 = cv2.fitLine(candidates[best].astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        line = _refined(
            (np.array([x0, y0], float) / 2.0 - 0.25, np.array([vx, vy], float)),
            green,
            a / 2.0 - 0.25,
            b / 2.0 - 0.25,
            rough.mean(axis=0) / 2.0 - 0.25,
        )
        if line is None:
            return None
        line = (line[0] * 2.0, line[1])  # kept in the twice-size map's units until the corners are crossed
        lines.append(line)
    corners = []
    for k in range(4):
        (p, u), (q, v) = lines[k - 1], lines[k]  # the side before this corner and the side after it
        matrix = np.array([u, -v]).T
        if abs(np.linalg.det(matrix)) < 1e-6:
            return None
        t = np.linalg.solve(matrix, q - p)
        corners.append(p + u * t[0])
    return np.array(corners) / 2.0  # the refined lines are the frame's own, carried at twice its size above


def _refined(
    line: tuple[np.ndarray, np.ndarray], green: np.ndarray, a: np.ndarray, b: np.ndarray, centre: np.ndarray
) -> tuple[np.ndarray, np.ndarray] | None:
    """A side's line to a fraction of a pixel, in the frame's own coordinates: the greenness profile sampled across
    the side (bilinear) at a point every pixel along its middle, each profile's crossing of the level half way
    between its inside and its outside found by interpolation, and a line fitted to the crossings. Finding the edge
    through a pixel mask was a quarter to a half pixel off (a traced outline runs through the boundary pixels'
    centres, and the twice-size map's pixel centres are not twice the frame's); profiles that cross away from the
    rough line (a notch, a rounded corner) are left out."""
    point, direction = line
    direction = direction / np.linalg.norm(direction)
    if (b - a) @ direction < 0:
        direction = -direction  # a fitted line's direction has either sign: along the side, from a towards b
    normal = np.array([-direction[1], direction[0]])
    if (centre - point) @ normal > 0:
        normal = -normal  # pointing out of the screen: the screen's centre lies behind the side
    length = float(np.linalg.norm(b - a))
    start = point + direction * ((a - point) @ direction)
    steps = np.arange(0.15 * length, 0.85 * length, 1.0)
    offsets = np.arange(-6.0, 6.01, 0.25)
    if len(steps) < 6:
        return None
    base = start[None, :] + steps[:, None] * direction[None, :]
    xs = (base[:, None, 0] + offsets[None, :] * normal[0]).astype(np.float32)
    ys = (base[:, None, 1] + offsets[None, :] * normal[1]).astype(np.float32)
    profiles = cv2.remap(green, xs, ys, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    found = []
    for k in range(len(steps)):
        profile = profiles[k]  # inside (negative offsets) to outside (positive)
        high, low = float(np.median(profile[:6])), float(np.median(profile[-6:]))  # its inside and outside levels
        if high - low < 40:
            continue
        level = (high + low) / 2
        below = np.nonzero(profile < level)[0]
        if not len(below) or below[0] == 0:
            continue
        j = below[0]
        f = (profile[j - 1] - level) / max(1e-6, profile[j - 1] - profile[j])
        offset = offsets[j - 1] + f * (offsets[j] - offsets[j - 1])
        if abs(offset) > 1.5:
            continue  # a notch or a corner's arc, not the side's edge
        found.append(base[k] + normal * offset)
    if len(found) < 6:
        return None
    vx, vy, x0, y0 = cv2.fitLine(np.array(found, np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
    return np.array([x0, y0], float), np.array([vx, vy], float)


def measure(path: str, frames: int | None = None) -> tuple[list[np.ndarray], list[np.ndarray | None]]:
    """The shot's frames and the green screen's measured corners on each."""
    capture = cv2.VideoCapture(path)
    pictures, quads = [], []
    while frames is None or len(pictures) < frames:
        ok, frame = capture.read()
        if not ok:
            break
        pictures.append(frame)
        quads.append(green_quad(frame))
    capture.release()
    return pictures, quads


def jitter(quads: list[np.ndarray | None], window: int = 7) -> float:
    """The measurement's own noise: its corners' RMS distance from a centred moving average of themselves."""
    known = [i for i, q in enumerate(quads) if q is not None]
    residuals = []
    half = window // 2
    for i in known:
        near = [quads[j] for j in range(i - half, i + half + 1) if 0 <= j < len(quads) and quads[j] is not None]
        if len(near) == window:
            residuals.append(np.linalg.norm(quads[i] - np.mean(near, axis=0), axis=1))
    return float(np.sqrt(np.mean(np.square(residuals)))) if residuals else float("nan")


def grown(quad: np.ndarray, share: float) -> np.ndarray:
    """A quadrilateral grown outward from its centre by share of itself (the search area taking in the bezel)."""
    centre = quad.mean(axis=0)
    return centre + (quad - centre) * (1 + share)


def _side_distances(tracked: np.ndarray, measured: np.ndarray) -> np.ndarray:
    """How far the tracked screen's sides lie from the measured ones: points a quarter, half and three quarters along
    each tracked side, their distance across to the measured side's line (the line through its two measured corners
    is the line fitted to that side). This compares what was measured, the sides; the corners are where the sides'
    lines cross, and in strong perspective the far ones cross at a shallow angle, where a sliver of angle moves them
    a long way, for the measurement as for the track."""
    out = []
    for k in range(4):
        a, b = measured[k], measured[(k + 1) % 4]
        normal = np.array([-(b - a)[1], (b - a)[0]]) / max(1e-9, float(np.linalg.norm(b - a)))
        for f in (0.25, 0.5, 0.75):
            point = tracked[k] + (tracked[(k + 1) % 4] - tracked[k]) * f
            out.append(abs(float((point - a) @ normal)))
    return np.array(out)


def track_and_score(
    path: str, margin: float = 0.08, frames: int | None = None, settings: dict | None = None, ring: float | None = 0.04
) -> dict:
    """formcut's track of the green screen from the first frame, every frame scored against the measured corners.

    The search area is the screen grown by margin (taking in the bezel) less the screen shrunk by ring, as a Mocha
    artist tracks a phone: by its border, the screen itself left out (an add shape and a subtract shape); a screen's
    reflections move over it and mislead a track of its face. ring None tracks the whole grown screen."""
    pictures, quads = measure(path, frames)
    if not pictures or quads[0] is None:
        raise ValueError(f"{path}: no green screen found on the first frame")
    first = quads[0]
    matte = np.zeros(pictures[0].shape[:2], np.uint8)
    cv2.fillPoly(matte, [np.round(grown(first, margin)).astype(np.int32)], 255)
    if ring is not None:
        cv2.fillPoly(matte, [np.round(grown(first, -ring)).astype(np.int32)], 0)
    tracker = PlanarTracker(pictures[0], matte, Settings(**({"perspective": True} | (settings or {}))))
    errors, carried, confidences, sides = [], [first], [], []
    started = time.perf_counter()
    for i in range(1, len(pictures)):
        h, confidence = tracker.step(pictures[i])
        corners = corners_of(h, first)
        carried.append(corners)
        confidences.append(confidence)
        if quads[i] is not None:
            errors.append(np.linalg.norm(corners - quads[i], axis=1))
            sides.append(_side_distances(corners, quads[i]))
    took = (time.perf_counter() - started) / max(1, len(pictures) - 1)
    per_frame = np.array([e.mean() for e in errors]) if errors else np.array([float("nan")])
    every = np.concatenate(errors) if errors else np.array([float("nan")])
    return {
        "shot": path,
        "size": f"{pictures[0].shape[1]}x{pictures[0].shape[0]}",
        "frames": len(pictures),
        "measured": int(sum(q is not None for q in quads)),
        "meanError": round(float(per_frame.mean()), 3),
        "rmsError": round(float(np.sqrt(np.mean(np.square(every)))), 3),
        "worstCorner": round(float(every.max()), 3),
        "sideRms": round(float(np.sqrt(np.mean(np.square(np.concatenate(sides))))) if sides else float("nan"), 3),
        "sideWorst": round(float(np.concatenate(sides).max()) if sides else float("nan"), 3),
        "first30": round(float(per_frame[:30].mean()), 3),
        "last30": round(float(per_frame[-30:].mean()), 3),
        "measurementJitter": round(jitter(quads), 3),
        "minConfidence": round(float(min(confidences)) if confidences else 1.0, 3),
        "msPerFrame": round(took * 1000, 1),
        "corners": [c.round(3).tolist() for c in carried],
        "measuredCorners": [None if q is None else q.round(3).tolist() for q in quads],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("shots", nargs="+")
    parser.add_argument("--margin", type=float, default=0.08, help="the search area: the screen grown by this share")
    parser.add_argument("--ring", type=float, default=0.04, help="the screen shrunk by this share is left out (negative: none)")
    parser.add_argument("--frames", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = []
    for shot in args.shots:
        r = track_and_score(shot, args.margin, args.frames, ring=None if args.ring < 0 else args.ring)
        results.append(r)
        if not args.json:
            print(
                f"{shot}: {r['frames']} frames, {r['measured']} measured | sides: RMS {r['sideRms']} px, worst "
                f"{r['sideWorst']} | corners: mean {r['meanError']} px, RMS {r['rmsError']}, worst {r['worstCorner']} | "
                f"first 30 {r['first30']}, last 30 {r['last30']} | "
                f"measurement jitter {r['measurementJitter']} px | {r['msPerFrame']} ms a frame",
                flush=True,
            )
    if args.json:
        print(json.dumps([{k: v for k, v in r.items() if k not in ("corners", "measuredCorners")} for r in results], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
