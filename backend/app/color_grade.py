"""The Color section's grade: wheels, primaries and curves, as a colourist uses them.

`clip.colorGrade` runs after the basic colour panel, in the order a grading node
does: the four wheels (offset, gain, lift, gamma: a colour balance and a master
level each), contrast about a pivot, colour boost and hue, the custom curves
(master, then red, green and blue), and the hue and luminance curves (hue against
hue, hue against saturation, luminance against saturation).

Every step maps a colour to a colour and nothing else, so a whole grade is also a
3D LUT: the layered export bakes it with the basic panel and applies exactly what
preview shows. Only the steps that differ from neutral run.

Curves are monotone cubic (Fritsch and Carlson): smooth through every point and
never overshooting between two of them, so a curve cannot invert a tonal range by
accident. The hue curves wrap, so red at 0 and at 1 is one point on the circle.
"""

from __future__ import annotations

import functools

import cv2
import numpy as np

WHEELS = ("offset", "gain", "lift", "gamma")
CHANNELS = ("r", "g", "b", "y")
CURVES = ("y", "r", "g", "b")
HUE_CURVES = {"hueHue": (-0.5, 0.5, 0.0), "hueSat": (0.0, 2.0, 1.0), "lumSat": (0.0, 2.0, 1.0)}
PRIMARIES = {"contrast": (0.0, 2.0, 1.0), "pivot": (0.0, 1.0, 0.435), "boost": (-1.0, 1.0, 0.0), "hue": (-180.0, 180.0, 0.0)}
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)
MAX_POINTS = 16


def _pchip(xs: np.ndarray, ys: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Monotone cubic interpolation through (xs, ys), evaluated at grid."""
    h = np.diff(xs)
    delta = np.diff(ys) / h
    slopes = np.zeros_like(ys)
    if len(xs) > 2:
        same = delta[:-1] * delta[1:] > 0
        w1, w2 = 2 * h[1:] + h[:-1], h[1:] + 2 * h[:-1]
        with np.errstate(divide="ignore", invalid="ignore"):
            harmonic = (w1 + w2) / (w1 / delta[:-1] + w2 / delta[1:])
        slopes[1:-1] = np.where(same, harmonic, 0.0)
    slopes[0], slopes[-1] = delta[0], delta[-1]
    index = np.clip(np.searchsorted(xs, grid) - 1, 0, len(xs) - 2)
    t = (grid - xs[index]) / h[index]
    t2, t3 = t * t, t * t * t
    return (
        (2 * t3 - 3 * t2 + 1) * ys[index]
        + (t3 - 2 * t2 + t) * h[index] * slopes[index]
        + (-2 * t3 + 3 * t2) * ys[index + 1]
        + (t3 - t2) * h[index] * slopes[index + 1]
    )


@functools.lru_cache(maxsize=64)
def _curve_table(points: tuple, periodic: bool, size: int = 1024) -> np.ndarray:
    xs, ys = np.array([p[0] for p in points], np.float64), np.array([p[1] for p in points], np.float64)
    if periodic:
        xs, ys = np.concatenate([xs - 1, xs, xs + 1]), np.concatenate([ys, ys, ys])
    grid = np.linspace(0, 1, size)
    table = _pchip(xs, ys, grid).astype(np.float32)
    table.flags.writeable = False
    return table


def _points(value) -> tuple:
    return tuple(sorted((float(x), float(y)) for x, y in value))


def _curve_active(points, neutral_y=None) -> bool:
    if not points:
        return False
    if neutral_y is not None:
        return any(abs(y - neutral_y) > 1e-9 for _, y in points)
    return any(abs(x - y) > 1e-9 for x, y in points)


def active(grade) -> bool:
    """True when anything in the grade differs from neutral."""
    if not isinstance(grade, dict):
        return False
    if any(abs(float((grade.get(w) or {}).get(c, 0))) > 1e-9 for w in WHEELS for c in CHANNELS):
        return True
    if any(abs(float(grade.get(k, n)) - n) > 1e-9 for k, (_, _, n) in PRIMARIES.items() if k != "pivot"):
        return True
    if any(_curve_active((grade.get("curves") or {}).get(c)) for c in CURVES):
        return True
    return any(_curve_active(grade.get(k), n) for k, (_, _, n) in HUE_CURVES.items())


def apply_float(rgb: np.ndarray, grade: dict) -> np.ndarray:
    """The grade over an H x W x 3 float picture (0 to 1), as float."""
    out = rgb.astype(np.float32, copy=True)
    level = {
        w: np.array([float((grade.get(w) or {}).get(c, 0)) for c in "rgb"], np.float32) + float((grade.get(w) or {}).get("y", 0))
        for w in WHEELS
    }
    if np.any(level["gain"]):
        out *= 1 + level["gain"]
    if np.any(level["lift"]):
        out += level["lift"] * 0.5 * (1 - out)
    if np.any(level["gamma"]):
        out = np.maximum(out, 0) ** (2.0 ** (-level["gamma"] * 1.2))
    if np.any(level["offset"]):
        out += level["offset"] * 0.5
    contrast, pivot = float(grade.get("contrast", 1)), float(grade.get("pivot", 0.435))
    if abs(contrast - 1) > 1e-9:
        out = (out - pivot) * contrast + pivot
    boost = float(grade.get("boost", 0))
    if abs(boost) > 1e-9:
        luma = out @ LUMA
        spread = np.ptp(np.clip(out, 0, 1), axis=2)
        out = luma[..., None] + (out - luma[..., None]) * (1 + boost * (1 - spread))[..., None]
    hue = float(grade.get("hue", 0))
    if abs(hue) > 1e-9:
        luma = out @ LUMA
        cb, cr = (out[..., 2] - luma) / 1.8556, (out[..., 0] - luma) / 1.5748
        angle = np.radians(hue)
        cb, cr = cb * np.cos(angle) - cr * np.sin(angle), cb * np.sin(angle) + cr * np.cos(angle)
        red, blue = luma + 1.5748 * cr, luma + 1.8556 * cb
        green = (luma - LUMA[0] * red - LUMA[2] * blue) / LUMA[1]
        out = np.stack([red, green, blue], axis=2)
    curves = grade.get("curves") or {}
    for index, channel in enumerate(CURVES):
        points = curves.get(channel)
        if not _curve_active(points):
            continue
        table = _curve_table(_points(points), False)
        grid = np.linspace(0, 1, len(table), dtype=np.float32)
        if channel == "y":
            out = np.interp(np.clip(out, 0, 1), grid, table).astype(np.float32)
        else:
            out[..., index - 1] = np.interp(np.clip(out[..., index - 1], 0, 1), grid, table)
    if any(_curve_active(grade.get(k), n) for k, (_, _, n) in HUE_CURVES.items()):
        luma = np.clip(out @ LUMA, 0, 1)
        hsv = cv2.cvtColor(np.clip(out, 0, 1).astype(np.float32), cv2.COLOR_RGB2HSV)
        grid = np.linspace(0, 1, 1024, dtype=np.float32)
        position = hsv[..., 0] / 360.0
        if _curve_active(grade.get("hueHue"), 0.0):
            shift = np.interp(position, grid, _curve_table(_points(grade["hueHue"]), True))
            hsv[..., 0] = (hsv[..., 0] + shift * 360.0) % 360.0
        if _curve_active(grade.get("hueSat"), 1.0):
            hsv[..., 1] *= np.interp(position, grid, _curve_table(_points(grade["hueSat"]), True))
        if _curve_active(grade.get("lumSat"), 1.0):
            hsv[..., 1] *= np.interp(luma, grid, _curve_table(_points(grade["lumSat"]), False))
        hsv[..., 1] = np.clip(hsv[..., 1], 0, 1)
        out = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return out


LATTICE = 33  # the same lattice the layered export bakes, so both sample one grid


@functools.lru_cache(maxsize=8)
def _lattice(key: str) -> np.ndarray:
    """The grade over every lattice colour, laid out as a LATTICE x LATTICE**2 picture.

    Red runs along each LATTICE-wide block, green down, blue selects the block,
    so a bilinear lookup in one block is the red-green step of a trilinear one.
    """
    import json

    grade = json.loads(key)
    steps = np.linspace(0, 1, LATTICE, dtype=np.float32)
    blue, green, red = np.meshgrid(steps, steps, steps, indexing="ij")
    colours = np.stack([red, green, blue], axis=-1).reshape(1, -1, 3)
    graded = np.clip(apply_float(colours, grade), 0, 1).reshape(LATTICE, LATTICE, LATTICE, 3)
    flat = np.ascontiguousarray(graded.transpose(1, 0, 2, 3).reshape(LATTICE, LATTICE * LATTICE, 3))
    flat.flags.writeable = False
    return flat


def apply(image: np.ndarray, grade) -> np.ndarray:
    """The grade over a uint8 RGB or RGBA picture, alpha untouched.

    The grade maps colours to colours, so it runs once over a 33-point lattice
    (cached per grade) and each frame is a trilinear lookup: two bilinear
    remaps, one per neighbouring blue slice, blended along blue. Every stage at
    1920x1080 took 1.45 s per frame computed directly on one slow core.
    """
    if not active(grade):
        return image
    import json

    flat = _lattice(json.dumps(grade, sort_keys=True))
    scaled = image[..., :3].astype(np.float32) * ((LATTICE - 1) / 255.0)
    red, green, blue = scaled[..., 0], scaled[..., 1], scaled[..., 2]
    slice_index = np.minimum(np.floor(blue), LATTICE - 2)
    along = (blue - slice_index)[..., None]
    x = red + slice_index * LATTICE
    below = cv2.remap(flat, x, green, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    above = cv2.remap(flat, x + LATTICE, green, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    out = image.copy()
    out[..., :3] = np.round(np.clip(below + (above - below) * along, 0, 1) * 255.0).astype(np.uint8)
    return out


def check(grade) -> None:
    """Raise ValueError naming what makes a grade unusable."""
    if grade is None:
        return
    if not isinstance(grade, dict):
        raise ValueError("colorGrade must be an object")
    for wheel in WHEELS:
        values = grade.get(wheel)
        if values is None:
            continue
        if not isinstance(values, dict) or set(values) - set(CHANNELS):
            raise ValueError(f"colorGrade {wheel} takes r, g, b and y")
        for channel, value in values.items():
            if not isinstance(value, (int, float)) or not -1 <= value <= 1:
                raise ValueError(f"colorGrade {wheel} {channel} must be between -1 and 1")
    for key, (low, high, _) in PRIMARIES.items():
        if grade.get(key) is not None and (not isinstance(grade[key], (int, float)) or not low <= grade[key] <= high):
            raise ValueError(f"colorGrade {key} must be between {low:g} and {high:g}")

    def points(value, name, low, high):
        if not isinstance(value, list) or not 2 <= len(value) <= MAX_POINTS:
            raise ValueError(f"colorGrade {name} needs two to {MAX_POINTS} points")
        xs = []
        for point in value:
            if not isinstance(point, list) or len(point) != 2 or not all(isinstance(v, (int, float)) for v in point):
                raise ValueError(f"colorGrade {name} points are [x, y] pairs")
            if not 0 <= point[0] <= 1 or not low <= point[1] <= high:
                raise ValueError(f"colorGrade {name} has a point out of range")
            xs.append(float(point[0]))
        if len(set(xs)) != len(xs):
            raise ValueError(f"colorGrade {name} has two points at one position")

    curves = grade.get("curves") or {}
    if not isinstance(curves, dict) or set(curves) - set(CURVES):
        raise ValueError("colorGrade curves are y, r, g and b")
    for channel, value in curves.items():
        points(value, f"curve {channel}", 0, 1)
    for key, (low, high, _) in HUE_CURVES.items():
        if grade.get(key) is not None:
            points(grade[key], key, low, high)
