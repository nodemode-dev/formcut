"""Planar layers' shapes as roto (P5 of the planar tracking plan): one definition for the engine and the renderer, and
the same arithmetic the Track workspace draws with (planar-workspace.ts).

A shape is points in its carrier track's reference frame (the frame's unit square): its own layer's track, or the
layer it is linked to (Link to Track). Points may be keyed on frames (keys: frame -> points, as Autokey makes them on
a roto layer): between keyed frames they run linearly, beyond the first and last they hold, and with no keys the shape
is its points. An X-Spline's points each carry a tension, 0 a sharp corner and 1 a smooth curve through it, after the
handles of Mocha's X-Splines (pulled out to a corner, pushed in to a curve); the curve is a Hermite spline through the
points whose tangent at each is the Catmull-Rom tangent scaled by that point's tension. Each point may carry its own
feather (media pixels): the edge fades from the shape's outline outward over the feather of the outline's nearest
part, interpolated along each side.
"""

from __future__ import annotations

import bisect

import cv2
import numpy as np

SAMPLES = 48  # points a curved side is drawn with


def points_at(shape: dict, frame: int) -> np.ndarray:
    """The shape's points (unit square, its carrier's reference frame) on a frame."""
    keys = shape.get("keys") or {}
    if not keys:
        return np.array(shape["points"], float)
    order = sorted(int(k) for k in keys)
    if frame <= order[0]:
        return np.array(keys[str(order[0])], float)
    if frame >= order[-1]:
        return np.array(keys[str(order[-1])], float)
    at = bisect.bisect_right(order, frame)
    a, b = order[at - 1], order[at]
    f = (frame - a) / (b - a)
    pa, pb = np.array(keys[str(a)], float), np.array(keys[str(b)], float)
    return pa + (pb - pa) * f if pa.shape == pb.shape else pa


def active_at(shape: dict, frame: int) -> tuple[np.ndarray, dict]:
    """The shape's active points on a frame and the shape with per-point values to match: shape["off"] maps a frame
    to the points switched off from it on (Mocha's point activation), held until the next entry."""
    points = points_at(shape, frame)
    off_keys = shape.get("off") or {}
    if not off_keys:
        return points, shape
    order = sorted(int(k) for k in off_keys)
    at = bisect.bisect_right(order, frame)
    if at == 0:
        return points, shape
    off = {int(i) for i in off_keys[str(order[at - 1])]}
    keep = [i for i in range(len(points)) if i not in off]
    if len(keep) < 3 or len(keep) == len(points):
        return points, shape
    trimmed = dict(shape)
    trimmed["points"] = points[keep].tolist()
    trimmed["keys"] = {}
    for name in ("tension", "feather", "handles"):
        values = shape.get(name)
        if values and len(values) == len(points):
            trimmed[name] = [values[i] for i in keep]
    return points[keep], trimmed


def outline(points: np.ndarray, shape: dict) -> tuple[np.ndarray, np.ndarray]:
    """The closed outline the shape draws (same units as points), and for each outline point the index of the shape
    point it comes from (with the fraction along the side, as index + fraction) so per-point values interpolate."""
    n = len(points)
    if shape.get("kind") == "bezier" and n >= 2:
        handles = np.array(shape.get("handles") or [[0.0, 0.0, 0.0, 0.0]] * n, float)
        if handles.shape != (n, 4):
            handles = np.resize(handles, (n, 4))
        ts = np.arange(SAMPLES) / SAMPLES
        u = 1 - ts
        segments = []
        for i in range(n):
            p0, p3 = points[i], points[(i + 1) % n]
            p1, p2 = p0 + handles[i, 2:4], p3 + handles[(i + 1) % n, 0:2]
            segments.append((u**3)[:, None] * p0 + (3 * u * u * ts)[:, None] * p1 + (3 * u * ts * ts)[:, None] * p2 + (ts**3)[:, None] * p3)
        return np.concatenate(segments), np.concatenate([i + ts for i in range(n)])
    if shape.get("kind") != "xspline" or n < 3:
        return points, np.arange(n, dtype=float)
    tension = np.array(shape.get("tension") or [1.0] * n, float)
    if len(tension) != n:
        tension = np.resize(tension, n)
    out, where = [], []
    for i in range(n):
        p0, p1 = points[i], points[(i + 1) % n]
        # Catmull-Rom tangents, scaled by each end's tension: 0 a corner (a straight side), 1 a smooth curve
        m0 = (points[(i + 1) % n] - points[i - 1]) / 2 * tension[i]
        m1 = (points[(i + 2) % n] - points[i]) / 2 * tension[(i + 1) % n]
        for k in range(SAMPLES):
            t = k / SAMPLES
            h00, h10, h01, h11 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t, -2 * t**3 + 3 * t**2, t**3 - t**2
            out.append(h00 * p0 + h10 * m0 + h01 * p1 + h11 * m1)
            where.append(i + t)
    return np.array(out), np.array(where)


def feather_along(shape: dict, where: np.ndarray) -> np.ndarray:
    """Each outline point's feather (media pixels), interpolated between its side's two shape points."""
    n = len(shape["points"]) if not shape.get("keys") else len(next(iter(shape["keys"].values())))
    values = np.array(shape.get("feather") or [0.0] * n, float)
    if len(values) != n:
        values = np.resize(values, n)
    base = np.floor(where).astype(int) % n
    f = where - np.floor(where)
    return values[base] * (1 - f) + values[(base + 1) % n] * f


def coverage(polygon: np.ndarray, w: int, h: int, ss: int = 8) -> np.ndarray:
    """Each pixel's area inside a closed path (pixel coordinates, centres on whole numbers), 0 to 1."""
    p = np.asarray(polygon, np.float64)
    if len(p) >= 3:
        before, after = p - np.roll(p, 1, 0), np.roll(p, -1, 0) - p
        n1 = np.stack([before[:, 1], -before[:, 0]], -1) / np.maximum(np.linalg.norm(before, axis=1, keepdims=True), 1e-12)
        n2 = np.stack([after[:, 1], -after[:, 0]], -1) / np.maximum(np.linalg.norm(after, axis=1, keepdims=True), 1e-12)
        normal = (n1 + n2) / np.maximum(np.linalg.norm(n1 + n2, axis=1, keepdims=True), 1e-12)
        if float(((p - p.mean(0)) * normal).sum()) < 0:
            normal = -normal
        p = p - normal * (0.5 / ss)
    big = np.zeros((h * ss, w * ss), np.uint8)
    fine = np.round(((p + 0.5) * ss - 0.5) * 16).astype(np.int32)
    cv2.fillPoly(big, [fine], 255, lineType=cv2.LINE_8, shift=4)
    return cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def layer_matte(shapes: list[dict], frame: int, carry, size: tuple[int, int], to_pixels) -> np.ndarray:
    """A layer's matte (0 to 1) on a frame: its shapes at the frame, carried by carry (unit points -> media pixels),
    mapped to the picture's pixels by to_pixels, added then subtracted, each point's feather fading its edge outward."""
    w, h = size
    solid = np.zeros((h, w), np.float32)
    soft = np.zeros((h, w), np.float32)
    for wanted in ("add", "subtract"):
        for shape in shapes:
            if (shape.get("mode") == "subtract") != (wanted == "subtract"):
                continue
            live, live_shape = active_at(shape, frame)
            pts, where = outline(live, live_shape)
            media = carry(pts)
            local = to_pixels(media)
            polygon = np.round(local).astype(np.int32)
            covered = coverage(local, w, h)
            if wanted == "subtract":
                solid *= 1 - covered
                soft *= 1 - covered
                continue
            before = solid
            solid = np.maximum(solid, covered)
            feathers = feather_along(live_shape, where)
            if np.abs(feathers).max() <= 0:
                continue
            # the outline drawn with each part's feather; outside the shape, the edge fades over the nearest part's
            scale = float(np.linalg.norm(local[1] - local[0]) / max(1e-9, np.linalg.norm(media[1] - media[0]))) if len(local) > 1 else 1.0
            edge = np.full((h, w), 255, np.uint8)
            widths = np.zeros((h, w), np.float32)
            for k in range(len(polygon)):
                a, b = tuple(polygon[k]), tuple(polygon[(k + 1) % len(polygon)])
                cv2.line(edge, a, b, 0, 1)
                cv2.line(widths, a, b, float(feathers[k] * scale), 1)
            distance, labels = cv2.distanceTransformWithLabels(edge, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
            zero = np.argwhere(edge == 0)
            lookup = np.zeros(labels.max() + 1, np.float32)
            lookup[1 : len(zero) + 1] = widths[zero[:, 0], zero[:, 1]]
            width = lookup[labels]
            fade = np.where(width > 0, np.clip(1 - distance / np.maximum(width, 1e-6), 0, 1), 0).astype(np.float32)
            inside = cv2.fillPoly(np.zeros((h, w), np.uint8), [polygon], 1) > 0
            fade[inside] = 0
            soft = np.maximum(soft, fade)
            inner = inside & (width < 0)
            if inner.any():
                ramp = np.clip(distance / np.maximum(-width, 1e-6), 0, 1).astype(np.float32)
                solid = np.where(inner, np.maximum(before, np.minimum(covered, ramp)), solid)
    return np.maximum(solid, soft)
