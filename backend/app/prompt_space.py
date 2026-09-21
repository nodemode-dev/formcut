"""Where a prompt points, in the clip's own pixels.

A click or a box is stored where the person pointed: fractions of the picture.
The cutout models segment the clip's own pixels, so before a prompt reaches
them it is carried back through the clip's placement on the canvas: the fit,
scale, stretch, flips, rotation and position the renderer draws it with. For a
clip that fills the frame this changes nothing; for one that is scaled, moved
or letterboxed it is what puts the prompt on the subject. A keyframed or
animated transform is placed as its base transform.
"""

from __future__ import annotations

import math

from .renderer import DEFAULTS

Corners = (("x0", "y0"), ("x1", "y0"), ("x0", "y1"), ("x1", "y1"))


def placement(clip: dict, canvas: tuple[float, float], source: tuple[float, float]) -> tuple[float, float, float, float, float, float]:
    """The renderer's map from source pixels to canvas pixels: x' = a x + b y + tx, y' = d x + e y + ty."""
    (canvas_w, canvas_h), (source_w, source_h) = canvas, source
    transform = {**DEFAULTS, **(clip.get("transform") or {})}
    fit = min(canvas_w / source_w, canvas_h / source_h)
    size = fit * float(transform["scale"]) / 100
    sx = size * float(transform["width"]) / 100 * (-1 if transform["flipH"] else 1)
    sy = size * float(transform["height"]) / 100 * (-1 if transform.get("flipV") else 1)
    angle = math.radians(float(transform["rotation"]))
    c, s = math.cos(angle), math.sin(angle)
    a, b, d, e = c * sx, -s * sy, s * sx, c * sy
    cx = canvas_w * (0.5 + float(transform["posX"]) / 100)
    cy = canvas_h * (0.5 + float(transform["posY"]) / 100)
    return a, b, d, e, cx - a * source_w / 2 - b * source_h / 2, cy - d * source_w / 2 - e * source_h / 2


def to_source(
    clip: dict, canvas: tuple[float, float], source: tuple[float, float], points: list[dict], box: dict | None
) -> tuple[list[dict], dict | None]:
    """Points and a box in fractions of the picture, carried back to fractions of the clip's own pixels."""
    a, b, d, e, tx, ty = placement(clip, canvas, source)
    det = a * e - b * d
    if abs(det) < 1e-12:
        return points, box
    (canvas_w, canvas_h), (source_w, source_h) = canvas, source

    def back(x: float, y: float) -> tuple[float, float]:
        px, py = float(x) * canvas_w - tx, float(y) * canvas_h - ty
        u, v = (e * px - b * py) / det, (-d * px + a * py) / det
        return min(1.0, max(0.0, u / source_w)), min(1.0, max(0.0, v / source_h))

    moved = []
    for point in points:
        x, y = back(point.get("x", 0.5), point.get("y", 0.5))
        moved.append({**point, "x": x, "y": y})
    if box is None:
        return moved, None
    corners = [back(box.get(kx, 0), box.get(ky, 0)) for kx, ky in Corners]
    xs, ys = [corner[0] for corner in corners], [corner[1] for corner in corners]
    return moved, {"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys)}
