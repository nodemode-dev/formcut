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

from .renderer import DEFAULTS, transform_at

Corners = (("x0", "y0"), ("x1", "y0"), ("x0", "y1"), ("x1", "y1"))


def placement(
    clip: dict, canvas: tuple[float, float], source: tuple[float, float], local: float | None = None
) -> tuple[float, float, float, float, float, float]:
    """The renderer's map from source pixels to canvas pixels: x' = a x + b y + tx, y' = d x + e y + ty.

    At a local time the clip's keyframes, expressions and animation slots apply,
    through the same transform_at the renderer draws with; without one the clip
    is placed as its base transform.
    """
    (canvas_w, canvas_h), (source_w, source_h) = canvas, source
    transform = transform_at(clip, local) if local is not None else {**DEFAULTS, **(clip.get("transform") or {})}
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
    (canvas_w, canvas_h), (source_w, source_h) = canvas, source

    def back(x: float, y: float, local: float | None) -> tuple[float, float] | None:
        a, b, d, e, tx, ty = placement(clip, canvas, source, local)
        det = a * e - b * d
        if abs(det) < 1e-12:
            return None
        px, py = float(x) * canvas_w - tx, float(y) * canvas_h - ty
        u, v = (e * px - b * py) / det, (-d * px + a * py) / det
        return min(1.0, max(0.0, u / source_w)), min(1.0, max(0.0, v / source_h))

    def made(prompt: dict) -> float | None:
        """When the prompt was made, in the clip's own seconds, if it says."""
        value = prompt.get("t")
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    moved = []
    for point in points:
        found = back(point.get("x", 0.5), point.get("y", 0.5), made(point))
        moved.append(point if found is None else {**point, "x": found[0], "y": found[1]})
    if box is None:
        return moved, None
    corners = [back(box.get(kx, 0), box.get(ky, 0), made(box)) for kx, ky in Corners]
    if any(corner is None for corner in corners):
        return moved, box
    xs, ys = [corner[0] for corner in corners], [corner[1] for corner in corners]
    return moved, {"x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys)}
