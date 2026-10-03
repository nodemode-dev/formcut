import bisect
import contextlib
import json
import math
import os
import sys
import zlib
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageOps

from . import gpu, gpu_effects
from .assets import apply_lut, asset_path, load_cube
from .catalogue import GRADES, scale_pixel_params
from .color_grade import apply as apply_color_grade
from .expressions import evaluate
from .fonts import title_font
from .media import MEDIA_DIR, _find, reversed_path
from .proxies import usable as proxy_for
from .stabilise import apply as stabilise_frame
from .video_source import acquire, recycle

# Proxies may be switched off wholesale; the switch lives here so one import
# covers both the preview path and the reverse builder.
PROXIES_ENABLED = True
from .pixel_effects import apply_colour_panel, apply_effects
from .render_document import flatten, nested_project, validate_document
from .timing import animation_at, effect_params_at, fade_at, property_at, source_time

LEGACY = {
    "fc.gaussian-blur": "gaussian",
    "fc.box-blur": "box",
    "fc.motion-blur": "directional-blur",
    "fc.mono": "monochrome",
    "fc.invert": "invert",
    "fc.warm": "warmth",
    "fc.cool": "cooling",
    "fc.vignette-pop": "vignette",
}
# R4: a clip carrying any of these takes a CPU step between its effects and
# its blend for every frame, so its layer cannot stay on the device. R5 took
# the LUT and the mask out and made the transitions and the push a matter of
# time; R6 took the key, the cutout and the shader, which is chained into the
# layer's own passes. Nothing is left: every layer can stay on the device.
# a clip carrying any of these is placed on this side, not left on the device: a corner pin is a perspective warp,
# which neither the device's affine pass nor the native warp-and-blend kernel makes (P3 of the planar tracking plan)
CPU_STEPS: tuple[str, ...] = ("cornerPin", "screenCut", "glare", "planarStabilize", "planarReorient")


def _guided(guide: np.ndarray, source: np.ndarray, radius: int, eps: float) -> np.ndarray:
    """He, Sun and Tang's guided filter: source (a matte) fitted to guide (the picture's brightness) by a local linear
    model within radius pixels; eps smooths where the guide is flat. Kept between 0 and 1."""
    size = (2 * radius + 1, 2 * radius + 1)
    mean = lambda x: cv2.boxFilter(x, cv2.CV_32F, size, borderType=cv2.BORDER_REFLECT)  # noqa: E731
    m_i, m_p = mean(guide), mean(source)
    var = mean(guide * guide) - m_i * m_i
    cov = mean(guide * source) - m_i * m_p
    a = cov / (var + eps)
    b = m_p - a * m_i
    return np.clip(mean(a) * guide + mean(b), 0, 1)


def pin_at(clip: dict, local: float) -> list[tuple[float, float]] | None:
    """A clip's corner pin at a local time: its image's four corners (top left, top right, bottom right, bottom left)
    on the canvas, as fractions of the canvas, or None. A pin is four fixed corners ({"points": [[x, y] x 4]}) or a
    track of them ({"times": [local seconds], "points": [[eight numbers] per time]}), interpolated linearly between
    its samples and held before the first and after the last."""
    pin = clip.get("cornerPin")
    if not isinstance(pin, dict):
        return None
    points, times = pin.get("points"), pin.get("times")
    try:
        if not times:
            corners = [(float(x), float(y)) for x, y in points]
            return corners if len(corners) == 4 else None
        if len(times) != len(points) or not times:
            return None
        if local <= times[0]:
            flat = points[0]
        elif local >= times[-1]:
            flat = points[-1]
        else:
            i = bisect.bisect_right(times, local) - 1
            t0, t1 = float(times[i]), float(times[i + 1])
            f = (local - t0) / (t1 - t0) if t1 > t0 else 0.0
            flat = [a + (b - a) * f for a, b in zip(points[i], points[i + 1], strict=True)]
        return [(float(flat[k]), float(flat[k + 1])) for k in range(0, 8, 2)]
    except (TypeError, ValueError, IndexError):
        return None


DEFAULTS = {
    "scale": 100,
    "posX": 0,
    "posY": 0,
    "rotation": 0,
    "width": 100,
    "height": 100,
    "opacity": 100,
    "blendMode": "Normal",
    "flipH": False,
    "flipV": False,
}


def crop_box(clip: dict) -> tuple[float, float, float, float] | None:
    """The clip's edge crop as clamped fractions (left, top, right, bottom), or None."""
    crop = clip.get("crop")
    if not isinstance(crop, dict):
        return None
    left = min(0.45, max(0.0, float(crop.get("left", 0))))
    top = min(0.45, max(0.0, float(crop.get("top", 0))))
    right = min(0.45, max(0.0, float(crop.get("right", 0))))
    bottom = min(0.45, max(0.0, float(crop.get("bottom", 0))))
    if left + top + right + bottom <= 0:
        return None
    return left, top, right, bottom


def apply_crop(image: np.ndarray, clip: dict) -> np.ndarray:
    box = crop_box(clip)
    if not box:
        return image
    left, top, right, bottom = box
    h, w = image.shape[:2]
    x0, x1 = int(w * left), max(int(w * left) + 1, int(w * (1 - right)))
    y0, y1 = int(h * top), max(int(h * top) + 1, int(h * (1 - bottom)))
    return image[y0:y1, x0:x1]


def wrap_text(content: str, font, limit: float) -> str:
    """Wrap each paragraph to a pixel width, keeping deliberate line breaks."""
    lines = []
    for paragraph in content.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and font.getlength(candidate) > limit:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return "\n".join(lines)


def line_width(font, line: str, tracking: float) -> float:
    if not tracking:
        return font.getlength(line)
    return sum(font.getlength(char) for char in line) + tracking * max(0, len(line) - 1)


def measure_text(draw, content: str, font, spacing: float, tracking: float, stroke: int) -> tuple[float, float, float, float]:
    """Pillow's own block box, with the tracked width when tracking applies."""
    box = draw.multiline_textbbox((0, 0), content, font=font, spacing=spacing, stroke_width=stroke)
    if tracking:
        lines = content.split("\n")
        widest = max((line_width(font, line, tracking) for line in lines), default=0.0)
        return (box[0], box[1], widest + stroke * 2, box[3] - box[1])
    return (box[0], box[1], box[2] - box[0], box[3] - box[1])


def paint_text(draw, origin, content: str, font, fill, align: str, spacing: float, tracking: float, stroke: int, stroke_fill) -> None:
    """Draw the block at origin; per-glyph only when tracking asks for it."""
    x, y = origin
    if not tracking:
        draw.multiline_text(
            (x, y), content, font=font, fill=fill, align=align, spacing=spacing, stroke_width=stroke, stroke_fill=stroke_fill
        )
        return
    lines = content.split("\n")
    widest = max((line_width(font, line, tracking) for line in lines), default=0.0)
    step = font.size + spacing
    for index, line in enumerate(lines):
        width = line_width(font, line, tracking)
        start = x if align == "left" else x + widest - width if align == "right" else x + (widest - width) / 2
        cursor = start
        for char in line:
            draw.text((cursor, y + index * step), char, font=font, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill, anchor="la")
            cursor += font.getlength(char) + tracking


# The animated word modes (v2.0.3): the spoken word eases in over its first WORD_EASE seconds, fading in with
# "reveal" (the words after it not drawn yet, their places kept) and rising into place with "rise".
WORD_EASE = 0.15
ANIMATED_WORDS = ("reveal", "rise")


def _with_alpha(colour, alpha: int):
    rgb = ImageColor.getrgb(colour) if isinstance(colour, str) else tuple(colour)
    return (*rgb[:3], alpha)


def paint_words(
    draw,
    origin,
    content: str,
    font,
    style: dict,
    words: list[dict],
    local: float,
    align: str,
    spacing: float,
    tracking: float,
    stroke: int,
    stroke_fill,
    big_font,
) -> None:
    """Draw the block word by word, the word being spoken at `local` in the word style.

    Lines and their placement follow paint_text; the word whose start is the
    latest at or before `local` is the active one, so a gap between words keeps
    the last word lit rather than none. A word count that differs from the
    text's tokens (an edited caption) highlights by position.
    """
    x, y = origin
    word_style = style.get("wordStyle") or {}
    mode = word_style.get("mode") or "none"
    accent = word_style.get("colour") or "#ffd633"
    base = style.get("color", "#ffffff")
    active = -1
    for index, word in enumerate(words):
        if float(word.get("t", 0)) <= local:
            active = index
    if mode == "none":
        active = -1
    eased = 1.0
    if active >= 0 and mode in ANIMATED_WORDS:
        progress = min(1.0, max(0.0, (local - float(words[active].get("t", 0))) / WORD_EASE))
        eased = 1.0 - (1.0 - progress) ** 3
    # Per-word emphasis: a word carrying its own colour keeps it, by position.
    own = [word.get("colour") or None for word in words]
    lines = content.split("\n")
    widest = max((line_width(font, line, tracking) for line in lines), default=0.0)
    step = draw.textbbox((0, 0), "A", font=font, stroke_width=stroke)[3] + stroke + spacing
    space = font.getlength(" ")
    index = 0
    for line_no, line in enumerate(lines):
        tokens = line.split()
        widths = [font.getlength(token) + tracking * len(token) for token in tokens]
        width = sum(widths) + space * max(0, len(tokens) - 1)
        cursor = x if align == "left" else x + widest - width if align == "right" else x + (widest - width) / 2
        top = y + line_no * step
        for token, token_width in zip(tokens, widths, strict=True):
            lit = index == active
            if mode == "reveal" and index > active:
                # not spoken yet: nothing drawn, its place kept, so the line does not move as the words arrive
                cursor += token_width + space
                index += 1
                continue
            if lit and mode == "box":
                pad = font.size * 0.12
                draw.rounded_rectangle(
                    [cursor - pad, top - pad * 0.5, cursor + token_width + pad, top + step - spacing + pad * 0.5],
                    radius=font.size * 0.18,
                    fill=ImageColor.getrgb(accent),
                )
            if lit and mode == "pop":
                big_width = big_font.getlength(token) + tracking * len(token)
                draw.text(
                    (cursor + (token_width - big_width) / 2, top - (big_font.size - font.size) * 0.6),
                    token,
                    font=big_font,
                    fill=accent,
                    stroke_width=stroke,
                    stroke_fill=stroke_fill,
                    anchor="la",
                )
            elif lit and mode in ANIMATED_WORDS:
                shade = round(255 * eased)
                rise = (1.0 - eased) * font.size * 0.4 if mode == "rise" else 0.0
                draw.text(
                    (cursor, top + rise),
                    token,
                    font=font,
                    fill=_with_alpha(accent, shade),
                    stroke_width=stroke,
                    stroke_fill=None if stroke_fill is None else _with_alpha(stroke_fill, shade),
                    anchor="la",
                )
            else:
                mine = own[index] if index < len(own) else None
                draw.text(
                    (cursor, top),
                    token,
                    font=font,
                    fill=accent if lit and mode == "highlight" else (mine or base),
                    stroke_width=stroke,
                    stroke_fill=stroke_fill,
                    anchor="la",
                )
            cursor += token_width + space
            index += 1


# Mask shapes (13 plus a drawn path). Each returns points in a unit square, so
# one routine can scale, rotate and fill any of them; a drawn path carries its
# own anchors and bezier handles instead.
def _regular(sides: int, turn: float = -0.5) -> list[tuple[float, float]]:
    return [
        (0.5 + 0.5 * math.cos(2 * math.pi * (i / sides + turn / sides)), 0.5 + 0.5 * math.sin(2 * math.pi * (i / sides + turn / sides)))
        for i in range(sides)
    ]


def _star(points: int, inner: float) -> list[tuple[float, float]]:
    out = []
    for i in range(points * 2):
        radius = 0.5 if i % 2 == 0 else 0.5 * inner
        angle = math.pi * i / points - math.pi / 2
        out.append((0.5 + radius * math.cos(angle), 0.5 + radius * math.sin(angle)))
    return out


def _heart() -> list[tuple[float, float]]:
    out = []
    for i in range(72):
        t = 2 * math.pi * i / 72
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        out.append((0.5 + x / 34.0, 0.5 - y / 34.0))
    return out


MASK_SHAPES = {
    "rect": [(0, 0), (1, 0), (1, 1), (0, 1)],
    "ellipse": [(0.5 + 0.5 * math.cos(2 * math.pi * i / 64), 0.5 + 0.5 * math.sin(2 * math.pi * i / 64)) for i in range(64)],
    # Odd-sided shapes stand on a flat side with a vertex at the top; the half-step
    # turn that gives even-sided ones a flat top had the triangle and pentagon
    # pointing left.
    "triangle": _regular(3, -0.75),
    "diamond": [(0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5)],
    "pentagon": _regular(5, -1.25),
    "hexagon": _regular(6),
    "octagon": _regular(8),
    "star": _star(5, 0.42),
    "star6": _star(6, 0.55),
    "heart": _heart(),
    "cross": [
        (0.35, 0),
        (0.65, 0),
        (0.65, 0.35),
        (1, 0.35),
        (1, 0.65),
        (0.65, 0.65),
        (0.65, 1),
        (0.35, 1),
        (0.35, 0.65),
        (0, 0.65),
        (0, 0.35),
        (0.35, 0.35),
    ],
    "arrow": [(0, 0.3), (0.6, 0.3), (0.6, 0.05), (1, 0.5), (0.6, 0.95), (0.6, 0.7), (0, 0.7)],
    "chevron": [(0, 0.1), (0.45, 0.5), (0, 0.9), (0.25, 0.9), (0.7, 0.5), (0.25, 0.1)],
    "trapezoid": [(0.2, 0), (0.8, 0), (1, 1), (0, 1)],
}


def _bezier_path(points: list[dict], steps: int = 18) -> list[tuple[float, float]]:
    """A drawn path: cubic segments between anchors, using each anchor's handles."""
    usable = [p for p in points if isinstance(p, dict) and "x" in p and "y" in p]
    if len(usable) < 2:
        return []
    out: list[tuple[float, float]] = []
    for index, anchor in enumerate(usable):
        nxt = usable[(index + 1) % len(usable)]
        if index + 1 == len(usable):
            # An open path is closed straight back to the start, so the fill is
            # always a solid region rather than an outline.
            pass
        x0, y0 = float(anchor["x"]), float(anchor["y"])
        x3, y3 = float(nxt["x"]), float(nxt["y"])
        x1 = x0 + float(anchor.get("outX", 0.0))
        y1 = y0 + float(anchor.get("outY", 0.0))
        x2 = x3 + float(nxt.get("inX", 0.0))
        y2 = y3 + float(nxt.get("inY", 0.0))
        for step in range(steps):
            t = step / steps
            u = 1 - t
            out.append(
                (
                    u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3,
                    u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3,
                )
            )
    return out


def _sharpness(luma: np.ndarray, where: np.ndarray) -> float:
    """Mean edge strength over contrast inside where: how sharp, whatever the brightness."""
    edge = cv2.magnitude(cv2.Sobel(luma, cv2.CV_32F, 1, 0), cv2.Sobel(luma, cv2.CV_32F, 0, 1))
    return float(edge[where].mean() / max(float(luma[where].std()), 1e-6))


def _grain(luma: np.ndarray, where: np.ndarray) -> float:
    """The fine noise's level inside where: the high-passed brightness's median absolute deviation, as a deviation."""
    fine = (luma - cv2.GaussianBlur(luma, (0, 0), 1.0))[where]
    return float(1.4826 * np.median(np.abs(fine - np.median(fine))))


def insert_match(layer: np.ndarray, below: np.ndarray, match: dict, key: str) -> np.ndarray:
    """Mocha Pro's Insert module: an inserted layer matched to the plate under its footprint. light carries the
    plate's shading across the surface onto it; blur softens it to the plate's sharpness; grain adds noise up to the
    plate's level (seeded by key, so a render repeats). Its alpha is left as it is."""
    top = 65535.0 if layer.dtype == np.uint16 else 255.0
    weights = np.array([0.299, 0.587, 0.114], np.float32)
    foot = layer[:, :, 3].astype(np.float32) / top > 0.5
    if foot.sum() < 256:
        return layer
    ys, xs = np.nonzero(foot)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    box = (slice(y0, y1), slice(x0, x1))
    inner = cv2.erode(foot[box].astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    if inner.sum() < 64:
        return layer
    rgb = layer[box][:, :, :3].astype(np.float32) / top
    below_top = 65535.0 if below.dtype == np.uint16 else 255.0 if below.dtype == np.uint8 else 1.0
    plate = (below[box][:, :, :3].astype(np.float32) / below_top) @ weights
    if match.get("light"):
        reach = max(4.0, 0.08 * max(y1 - y0, x1 - x0))
        weight = cv2.GaussianBlur(inner.astype(np.float32), (0, 0), reach)
        shade = cv2.GaussianBlur(plate * inner, (0, 0), reach) / np.maximum(weight, 1e-6)
        rgb *= (shade / max(float(np.median(shade[inner])), 1e-6))[..., None]
    if match.get("blur"):
        target = _sharpness(plate, inner)
        for sigma in np.arange(0.25, 4.01, 0.25):
            if _sharpness(cv2.GaussianBlur(rgb, (0, 0), sigma) @ weights, inner) <= target:
                rgb = cv2.GaussianBlur(rgb, (0, 0), sigma)
                break
    if match.get("grain"):
        want, have = _grain(plate, inner), _grain(rgb @ weights, inner)
        noise = np.random.default_rng(zlib.crc32(key.encode())).standard_normal(rgb.shape[:2]).astype(np.float32)
        level = _grain(noise, inner)
        if want > have and level > 0:
            rgb += (noise * (np.sqrt(want * want - have * have) / level))[..., None]
    out = layer.copy()
    out[box][:, :, :3] = np.round(np.clip(rgb, 0, 1) * top).astype(layer.dtype)
    return out


def mask_points_at(track: list[dict], local: float) -> list[dict]:
    """A tracked mask's anchors at a clip-local time: linear between the track's entries, held before and after."""
    entries = sorted(track, key=lambda e: float(e["t"]))
    if local <= float(entries[0]["t"]):
        return entries[0]["points"]
    if local >= float(entries[-1]["t"]):
        return entries[-1]["points"]
    at = bisect.bisect_right([float(e["t"]) for e in entries], local)
    a, b = entries[at - 1], entries[at]
    f = (local - float(a["t"])) / max(1e-9, float(b["t"]) - float(a["t"]))
    if len(a["points"]) != len(b["points"]):
        return a["points"]
    return [
        {k: float(p.get(k, 0)) + (float(q.get(k, 0)) - float(p.get(k, 0))) * f for k in set(p) | set(q)}
        for p, q in zip(a["points"], b["points"], strict=True)
    ]


def mask_polygon(mask: dict) -> list[tuple[float, float]]:
    """Unit-square points for a mask, whichever kind it is."""
    if mask.get("shape") == "path":
        return _bezier_path(mask.get("points") or [])
    return [tuple(p) for p in MASK_SHAPES.get(str(mask.get("shape")), MASK_SHAPES["rect"])]


_NATIVE: list = []


def _native():
    """The Rust kernels, where built, unless FORMCUT_NATIVE=0 turns them off."""
    from os import environ

    if environ.get("FORMCUT_NATIVE") == "0":
        return None
    if not _NATIVE:
        try:
            import formcut_native
        except ImportError:
            formcut_native = None
        _NATIVE.append(formcut_native)
    return _NATIVE[0]


def _plainly_blended(clip: dict, local: float, transform: dict) -> bool:
    """True when this moment of the layer is only warped and blended normally, which the kernel reproduces to the bit."""
    if str(transform["blendMode"]).lower() != "normal":
        return False
    length = clip.get("transitionLength", 0)
    if length and local < length:
        return False
    out = clip.get("transitionOut")
    if out and float(out.get("length") or 0) > 0 and local >= clip["duration"] - 0.0001:
        return False
    return not (clip.get("pushOut") and local >= clip["duration"])


def transform_at(clip: dict, local: float) -> dict:
    """The clip's transform at a local time: base, then keyframes and expressions, then animation slots.

    One definition for drawing a clip and for carrying a prompt back through
    where the clip was drawn, so the two can never disagree.
    """
    transform = {**DEFAULTS, **(clip.get("transform") or {})}
    for prop in ("scale", "posX", "posY", "rotation", "opacity"):
        transform[prop] = property_at(clip, prop, local, transform[prop])
        expression = (clip.get("expressions") or {}).get(prop)
        if expression:
            transform[prop] = evaluate(expression, local, clip["duration"], transform[prop])
    # K6: animation slots layer on top of the sampled transform
    motion = animation_at(clip, local)
    transform["scale"] *= motion["scale"]
    transform["opacity"] *= motion["opacity"]
    transform["posX"] += motion["posX"]
    transform["posY"] += motion["posY"]
    transform["rotation"] += motion["rotation"]
    return transform


def _revealed(kind: str, h: int, w: int, progress: float) -> np.ndarray:
    """Where the incoming clip shows at this point in a shaped transition; the outgoing one hides there."""
    y, x = np.mgrid[:h, :w].astype(np.float32)
    if kind == "clock-wipe":
        return (np.arctan2(x - w / 2, h / 2 - y) % (2 * math.pi)) <= 2 * math.pi * progress
    if kind == "blinds":
        return ((y / h) * 8) % 1 < progress
    if kind == "diagonal-wipe":
        return (x / w + y / h) / 2 <= progress
    if kind == "diamond":
        return np.abs(x - w / 2) / (w / 2) + np.abs(y - h / 2) / (h / 2) <= 2 * progress
    return np.abs(x - w / 2) <= (w / 2) * progress


def _pixelated(image: np.ndarray, block: int) -> np.ndarray:
    """The picture in square blocks of this many pixels, for the pixel dissolve."""
    if block <= 1:
        return image
    h, w = image.shape[:2]
    small = cv2.resize(image, (max(1, w // block), max(1, h // block)), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


# BT.709 to BT.2020 primaries, in linear light (ITU-R BT.2087).
_709_TO_2020 = np.array([[0.6274, 0.3293, 0.0433], [0.0691, 0.9195, 0.0114], [0.0164, 0.0880, 0.8956]], np.float32)


def _lift_table(transfer: str) -> np.ndarray:
    """The 256 byte values decoded to linear light at SDR white (203 nits as a fraction of the transfer's peak)."""
    v = np.arange(256, dtype=np.float64) / 255
    linear = np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    peak = 10000.0 if transfer == "pq" else 1000.0
    return (linear * 203 / peak).astype(np.float32)


def _encode_transfer(light: np.ndarray, transfer: str) -> np.ndarray:
    """Linear light (a fraction of the transfer's peak) encoded through PQ or HLG, exactly; the reference the
    device's LIFT pass is measured against. A table sampled on linear light was tried first and quantised the
    whole SDR range into eighty steps of PQ, forty counts off; the curve is too steep at the bottom for that."""
    from .gpu import _to_display

    return _to_display(light.astype(np.float32), transfer)


def _to_bytes(frame: np.ndarray) -> np.ndarray:
    """A sixteen-bit SDR frame rounded to bytes once: v / 257 to the nearest (never a tie, 257 being odd)."""
    return cv2.convertScaleAbs(frame, alpha=1.0 / 257.0)


def rolloff_for_display(frame: np.ndarray, transfer: str) -> np.ndarray:
    """A deep frame for an SDR monitor: the transfer decoded to light, rolled off above SDR white with a
    soft knee (BT.2390's shape at a 1000-nit source), encoded through sRGB to bytes. A byte frame passes."""
    if frame.dtype != np.uint16:
        return frame
    v = frame[:, :, :3].astype(np.float32) / 65535
    if transfer == "pq":
        m1, m2, c1, c2, c3 = 0.1593017578125, 78.84375, 0.8359375, 18.8515625, 18.6875
        e = np.power(v, 1 / m2)
        nits = np.power(np.maximum(e - c1, 0) / (c2 - c3 * e), 1 / m1) * 10000
    else:
        a, b, c = 0.17883277, 0.28466892, 0.55991073
        scene = np.where(v <= 0.5, v * v / 3, (np.exp((v - c) / a) + b) / 12)
        nits = scene * 1000
    relative = nits / 203  # 1.0 at SDR white
    knee = 0.8
    peak = 1000 / 203
    over = relative > knee
    rolled = np.where(over, knee + (1 - knee) * (1 - np.exp(-(relative - knee) / max(peak - knee, 1e-6))), relative)
    rolled = np.clip(rolled, 0, 1)
    srgb = np.where(rolled <= 0.0031308, rolled * 12.92, 1.055 * np.power(rolled, 1 / 2.4) - 0.055)
    out = np.empty((frame.shape[0], frame.shape[1], 4), np.uint8)
    out[:, :, :3] = np.round(np.clip(srgb, 0, 1) * 255).astype(np.uint8)
    out[:, :, 3] = (frame[:, :, 3] // 257).astype(np.uint8)
    return out


class MediaUnreadable(ValueError):
    """A clip's media that cannot be read: not in the library, its file missing, or not decodable. Says which, and why."""

    def __init__(self, name: str, reason: str):
        super().__init__(f"{name}: {reason}")
        self.name, self.reason = name, reason


_said_already: set[str] = set()


def _say_once(text: str) -> None:
    """A problem said once in the terminal, not once a frame."""
    if text in _said_already:
        return
    _said_already.add(text)
    with contextlib.suppress(OSError, ValueError, AttributeError):
        print(f"formcut: {text}", file=sys.__stderr__)


def _why(path: Path, capture) -> str:
    """What is wrong with a file that did not decode: gone, a link to nothing, empty, or the decoder's own words."""
    if path.is_symlink() and not path.exists():
        return f"its link points at {os.readlink(path)}, which is not there; relink it from the Media panel"
    if not path.exists():
        return "its file is missing; relink it from the Media panel"
    if path.stat().st_size == 0:
        return "its file is empty"
    said = (getattr(capture, "last_error", "") or "").strip().splitlines()
    return "the decoder could not read it" + (f" ({said[-1][:200]})" if said else "")


def placeholder(width: int, height: int, problem: MediaUnreadable) -> np.ndarray:
    """The card a preview shows for a clip whose media cannot be read: its name and what is wrong."""
    from PIL import ImageDraw, ImageFont

    card = Image.new("RGBA", (int(width), int(height)), (28, 20, 22, 255))
    draw = ImageDraw.Draw(card)
    size = max(12, int(min(width, height) / 22))
    try:
        font, small = ImageFont.load_default(size=size), ImageFont.load_default(size=max(10, int(size * 0.7)))
    except TypeError:  # an older Pillow
        font = small = ImageFont.load_default()
    draw.rectangle((0, 0, width - 1, height - 1), outline=(220, 70, 70, 255), width=max(2, size // 6))
    margin = size
    draw.text((margin, height / 2 - size * 1.6), f"Cannot show {problem.name}", fill=(255, 225, 225, 255), font=font)
    words, line, lines = problem.reason.split(), "", []
    limit = max(16, int((width - 2 * margin) / (size * 0.42)))
    for word in words:
        if len(line) + len(word) + 1 > limit:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    for index, text in enumerate(lines[:4]):
        draw.text((margin, height / 2 + index * size * 0.95), text, fill=(235, 190, 190, 255), font=small)
    return np.array(card)


class FrameRenderer:
    # A renderer built without its constructor (the tail tests do this) is an SDR renderer.
    deep = False
    transfer = "bt709"
    _lift = None

    def __init__(self, project: dict, width: int | None = None):
        self.project = validate_document(project)
        self.width = width or self.project["width"]
        self.height = max(2, round(self.project["height"] * self.width / self.project["width"]))
        self.decode_limit = max(self.width, self.height) if width else None
        # The HDR working space (steps 4 and 5): a project whose output colour is HLG or PQ works deep.
        # Frames are uint16 RGBA in that transfer; an HDR source arrives in it from the decoder with no
        # tone-map, an SDR source, a still, a title or a background is lifted into it once at SDR white
        # (203 nits), and the frame leaves the renderer deep: the export takes it as it is and the
        # monitor rolls it off (rolloff_for_display). An SDR project is bytes, as before.
        self.transfer = str(project.get("outputColour") or "bt709").lower()
        self.deep = self.transfer in ("hlg", "pq")
        # An SDR project keeps its canvas at sixteen bits between blends, as an HDR one does, and rounds to bytes
        # once when the frame is done: rounded after every blend, a stack of soft layers built bands.
        self.fine = not self.deep and os.environ.get("FORMCUT_SDR_FINE", "1") != "0"
        self._lift = _lift_table(self.transfer) if self.deep else None
        self.prepared = {}
        self.nested: dict[str, FrameRenderer] = {}
        self.clips = flatten(self.project)
        self.sources = {}
        self.cursors: dict[str, list[tuple[str, int]]] = {}
        self.cursor_used: dict[tuple[str, int], int] = {}
        self.uses = 0
        self.stills = {}
        self.frame_numbers = {}
        self.tween_pairs = {}
        self.frames = {}
        self.decode_scale = {}
        self.mask_cache: dict = {}
        # P6: a paused still shows what the export will produce, so it reads the
        # original; playback and scrubbing set this and read the proxy.
        self.allow_proxy = False
        self.matte_time = 0.0
        self.pending_layers: list = []
        # R4: how many layers stayed on the device between their passes and the blend, for the reading.
        self.resident_layers = 0
        # R6: package shader sources by asset id, read once.
        self.shader_sources: dict[str, str] = {}
        # R8: static titles rasterised once, by style and frame size.
        self.text_cache: dict = {}
        # The export's planar frame: when set, a deep frame comes back from the device as yuv420p10le planes
        # (bytes) with the light measured there, and nothing is packed as RGBA16 or converted by ffmpeg.
        self._want_planes = False
        self._final_flush = False
        self._last_text_key = None  # the text cache's key of the title drawn last, when it is still
        self.closed = False

    def close(self):
        for source in self.sources.values():
            recycle(source)
        self.sources.clear()
        self.cursors.clear()
        self.stills.clear()
        self.frames.clear()
        self.closed = True

    def paint_background(self, canvas: np.ndarray, time: float) -> np.ndarray:
        """What sits behind footage that does not fill the frame (B8).

        A flat colour, a gradient between two, an image from the library, or a
        blurred, enlarged copy of the clip on screen, which is the one people
        reach for when a vertical phone clip lands in a wide project.
        """
        fill = self.project.get("background")
        if not fill:
            return canvas
        if isinstance(fill, str):
            fill = {"type": "colour", "colour": fill}
        kind = str(fill.get("type") or "colour")
        try:
            if kind == "colour":
                colour = np.broadcast_to(
                    np.array(ImageColor.getrgb(str(fill.get("colour", "#000000"))), np.uint8), (self.height, self.width, 3)
                )
                canvas[:, :, :3] = self._canvas_rgb(canvas, np.ascontiguousarray(colour))
            elif kind == "gradient":
                top = np.array(ImageColor.getrgb(str(fill.get("from", "#000000"))), np.float32)
                bottom = np.array(ImageColor.getrgb(str(fill.get("to", "#ffffff"))), np.float32)
                ramp = np.linspace(0.0, 1.0, self.height, dtype=np.float32)[:, None, None]
                ramped = np.broadcast_to(np.clip(top + (bottom - top) * ramp, 0, 255).astype(np.uint8), (self.height, self.width, 3))
                canvas[:, :, :3] = self._canvas_rgb(canvas, np.ascontiguousarray(ramped))
            elif kind == "image" and fill.get("mediaId"):
                still = self.media_frame({"kind": "image", "mediaId": str(fill["mediaId"])}, 0)
                canvas[:, :, :3] = self._canvas_rgb(canvas, self._cover(still[:, :, :3]))
            elif kind == "blur":
                source = next(
                    (
                        c
                        for c in sorted(self.clips, key=lambda c: -c["trackIndex"])
                        if c["kind"] in ("video", "image")
                        and c.get("mediaId")
                        and c["start"] <= time < c["start"] + c["duration"] + c.get("extendOut", 0)
                    ),
                    None,
                )
                if source is not None:
                    still = self.media_frame(source, source_time(source, time - source["start"]))
                    covered = self._cover(still[:, :, :3])
                    amount = max(1, int(float(fill.get("amount", 40))))
                    canvas[:, :, :3] = self._canvas_rgb(canvas, cv2.GaussianBlur(covered, (0, 0), amount))
        except Exception:
            # A background that cannot be drawn must never stop the frame.
            pass
        return canvas

    def _cover(self, image: np.ndarray) -> np.ndarray:
        """Scale an image to cover the canvas, cropping the overflow."""
        h, w = image.shape[:2]
        scale = max(self.width / w, self.height / h)
        resized = cv2.resize(image, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_LINEAR)
        top = max(0, (resized.shape[0] - self.height) // 2)
        left = max(0, (resized.shape[1] - self.width) // 2)
        return resized[top : top + self.height, left : left + self.width]

    CURSORS = 4

    def _cursor(self, media_id: str, time: float, path) -> tuple[str, int]:
        """The read position of this media that reaches `time` by reading forward.

        One decoder per media meant two clips of one file at different moments,
        a picture in picture of the same shot or a crossfade within one file,
        pulled it back and forth, and each step back restarted ffmpeg from the
        last keyframe: a 1080p picture in picture ran at 436 ms a frame where
        the same layers from one moment ran at 134. Each media now keeps up to
        CURSORS read positions; a request takes the nearest it can reach by
        reading forward within the decoder's two-second window, opens a new one
        when none can, and past the limit restarts the least recently used.
        """
        cursors = self.cursors.setdefault(media_id, [])
        chosen = None
        if cursors:
            fps = self.sources[cursors[0]].fps
            wanted, window = max(0, int(time * fps + 1e-7)), max(1, round(fps * 2))
            forward = [(wanted - self.frame_numbers.get(cursor, -2), cursor) for cursor in cursors]
            forward = [entry for entry in forward if 0 <= entry[0] <= window]
            if forward:
                chosen = min(forward)[1]
            elif len(cursors) >= self.CURSORS:
                chosen = min(cursors, key=lambda cursor: self.cursor_used.get(cursor, 0))
        if chosen is None:
            chosen = (media_id, len(cursors))
            self.sources[chosen] = acquire(path, self.decode_limit, time, deep=self.deep)
            cursors.append(chosen)
        self.uses += 1
        self.cursor_used[chosen] = self.uses
        return chosen

    def _tween(self, capture, cursor, wanted: int, blend: float):
        """The picture partway between two source frames, following the motion."""
        key = (cursor, wanted)
        pair = self.tween_pairs.get(key)
        if pair is None:
            current = self.frame_numbers.get(cursor, -2)
            if wanted != current + 1:
                capture.seek(wanted)
            ok, first = capture.read()
            if not ok:
                return None
            ok, second = capture.read()
            if not ok:
                return None
            self.frame_numbers[cursor] = wanted + 1
            self.frames[cursor] = second
            grey_a = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
            grey_b = cv2.cvtColor(second, cv2.COLOR_BGR2GRAY)
            flow = cv2.calcOpticalFlowFarneback(grey_a, grey_b, None, 0.5, 3, 21, 3, 5, 1.2, 0)
            self.tween_pairs = {key: (first, second, flow)}
            pair = self.tween_pairs[key]
        first, second, flow = pair
        h, w = flow.shape[:2]
        grid_y, grid_x = np.mgrid[:h, :w].astype(np.float32)
        forward_x = (grid_x + flow[:, :, 0] * blend).astype(np.float32)
        forward_y = (grid_y + flow[:, :, 1] * blend).astype(np.float32)
        back_x = (grid_x - flow[:, :, 0] * (1 - blend)).astype(np.float32)
        back_y = (grid_y - flow[:, :, 1] * (1 - blend)).astype(np.float32)
        warped_first = cv2.remap(first, forward_x, forward_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        warped_second = cv2.remap(second, back_x, back_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        mixed = cv2.addWeighted(warped_first, 1 - blend, warped_second, blend, 0)
        return cv2.cvtColor(mixed, cv2.COLOR_BGR2RGBA)

    def nested_frame(self, clip: dict, time: float) -> np.ndarray | None:
        """A compound clip's frame: the referenced timeline at `time`, or None for a cycle; a multicam clip's angle alone."""
        timeline_id = str(clip.get("timelineId") or "")
        angle = clip.get("angle")
        angle = int(angle) if isinstance(angle, (int, float)) and not isinstance(angle, bool) else None
        key = timeline_id if angle is None else f"{timeline_id}@{angle}"
        renderer = self.nested.get(key)
        if renderer is None:
            document = nested_project(self.project, timeline_id, self.project.get("_chain", ()), angle)
            if document is None:
                return None
            renderer = self.nested[key] = FrameRenderer(document, self.width)
        return renderer.frame(max(0.0, min(time, renderer.project["duration"])))

    def frame_planes(self, time: float, layout: str = "yuv420p10le"):
        """A deep frame for the encoder as yuv420p10le planes packed on the device, with (MaxCLL nits, MaxFALL
        nits) measured there; None when the device stack is not active or the frame is not deep, in which
        case the caller takes frame() and converts as before."""
        if not (self.deep and gpu.stack_active()) or self.width % 4 or self.height % 2:
            return None
        self._want_planes = layout
        try:
            out = self.frame(time)
        finally:
            self._want_planes = False
        if out.ndim != 1:
            return None  # the frame did not go through the device compositor (nothing on screen, say)
        code, mean_nits = gpu.stack_light()
        from .render_api import _light_table

        return out, (float(_light_table(self.transfer)[code]), mean_nits)

    def _base_for(self, canvas: np.ndarray, transform: dict) -> tuple[int, int] | None:
        """(blend mode, transfer) when this layer is the frame's first over a canvas nothing has painted: its own
        kernel may then blend it over the blank canvas and hand the result over as the canvas."""
        if self.pending_layers or canvas is not getattr(self, "_fresh_canvas", None):
            return None
        mode = str(transform.get("blendMode", "Normal")).lower()
        return (
            gpu.MODES.index(mode) if mode in gpu.MODES else 0,
            gpu.TRANSFERS.get(self.transfer, 0) if self.deep else 0,
            1 if self.deep or self.fine else 0,
        )

    def _canvas_rgb(self, canvas: np.ndarray, rgb: np.ndarray) -> np.ndarray:
        """Painted colour (bytes, or sixteen bits from a deep source) at the canvas's own depth: bytes lifted into an
        HDR timeline's transfer, or widened to the same signal on an SDR one's sixteen-bit canvas."""
        if canvas.dtype != np.uint16 or rgb.dtype == np.uint16:
            return rgb
        if self.deep:
            rgba = np.concatenate([rgb, np.full((*rgb.shape[:2], 1), 255, np.uint8)], axis=2)
            return self.lift(rgba)[:, :, :3]
        return rgb.astype(np.uint16) * np.uint16(257)

    def _blank_canvas(self) -> np.ndarray:
        kind = np.uint16 if self.deep or self.fine else np.uint8
        blank = getattr(self, "_blank", None)
        if blank is None or blank.shape[:2] != (self.height, self.width) or blank.dtype != kind:
            blank = np.zeros((self.height, self.width, 4), kind)
            blank[:, :, 3] = 65535 if self.fine else 255
            blank.flags.writeable = False
            self._blank = blank
        return blank

    def as_working(self, frame: np.ndarray) -> np.ndarray:
        from .yuv import PlaneFrame

        if isinstance(frame, PlaneFrame):
            return frame.rgba()
        if frame.dtype == np.uint8 and frame.ndim == 3 and frame.shape[2] == 4:
            return frame  # RGBA from formcut's own conversion (yuv.py)
        """A decoded frame as the working picture: RGBA bytes for an SDR project; for a deep project, a
        deep HDR frame (uint16 RGB in the transfer) gets its alpha, and a byte frame is lifted."""
        if frame.dtype == np.uint16:
            if frame.shape[2] == 4:
                return frame  # RGBA64 from the decoder, alpha full
            h, w = frame.shape[:2]
            return np.concatenate([frame, np.full((h, w, 1), 65535, np.uint16)], axis=2)
        # a byte frame stays bytes here: in a deep project the device lifts it in its own chain (LIFT_CODE)
        # and the CPU path lifts it at the blend, so no full-frame lift runs on the CPU per frame
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)

    def lift(self, rgba: np.ndarray) -> np.ndarray:
        """A byte RGBA picture into the deep working space at SDR white, alpha scaled with it; unchanged when the project is bytes."""
        if not self.deep or rgba.dtype != np.uint8:
            return rgba
        # decode to light at SDR white, move the primaries from BT.709 to BT.2020 (the deep timeline's
        # gamut), encode through the transfer: a byte picture lands where an HDR camera would have put it
        light = self._lift[rgba[:, :, :3]]
        wide = np.clip(light @ _709_TO_2020.T, 0, 1)
        out = np.empty(rgba.shape, np.uint16)
        out[:, :, :3] = np.round(_encode_transfer(wide, self.transfer) * 65535).astype(np.uint16)
        out[:, :, 3] = rgba[:, :, 3].astype(np.uint16) * 257
        return out

    def media_frame(self, clip: dict, time: float, planes: bool = False) -> np.ndarray:
        """The clip's frame at a time; with planes, a planar frame comes back as its planes (yuv.PlaneFrame) for the
        device to convert in its first pass, when nothing on this side needs its pixels first."""
        media_id = clip.get("mediaId")
        if not media_id:
            raise ValueError("Media clip has no source")
        if not hasattr(self, "_cpu_only"):
            self._cpu_only = set()
        # a clip's media record and files are looked up once for this renderer's life, not every frame (a glob of
        # the media folder and two reads of the index a frame, about three milliseconds on a full library)
        known = self._media_known.get(media_id) if hasattr(self, "_media_known") else None
        if known is None:
            try:
                record_found = _find(media_id)
            except HTTPException:
                raise MediaUnreadable(
                    clip.get("label") or media_id, "it is not in the media library (media.json lost it, or it was deleted)"
                ) from None
            known = (record_found, [p for p in MEDIA_DIR.glob(f"{media_id}.*") if not p.name.startswith(".")])
            if not hasattr(self, "_media_known"):
                self._media_known = {}
            self._media_known[media_id] = known
        if clip.get("reversed"):
            candidate = reversed_path(media_id)
            if not candidate.is_file():
                raise ValueError("Reversed copy is not prepared yet: " + media_id)
            paths = [candidate]
        else:
            paths = list(known[1])
            # P5: a preview may read a proxy; an export never does, because it
            # builds a renderer with no decode limit and this returns None.
            if paths and PROXIES_ENABLED and self.allow_proxy:
                stand_in = proxy_for(media_id, paths[0], self.decode_limit)
                if stand_in is not None:
                    paths = [stand_in]
        if not paths or not paths[0].exists():
            where = known[0].get("path") or (str(paths[0]) if paths else "")
            raise MediaUnreadable(
                known[0].get("name") or clip.get("label") or media_id,
                f"its file is missing{f' (last at {where})' if where else ''}; relink it from the Media panel",
            )
        record = known[0]
        native = max(float(record.get("width") or 0), float(record.get("height") or 0))
        if clip["kind"] == "image":
            if media_id not in self.stills:
                try:
                    Image.open(paths[0]).close()
                except OSError as exc:
                    raise MediaUnreadable(record.get("name") or media_id, f"it could not be opened as a picture ({exc})") from exc
                with Image.open(paths[0]) as image:
                    still = ImageOps.exif_transpose(image).convert("RGBA")
                    if self.decode_limit and max(still.size) > self.decode_limit:
                        still.thumbnail((self.decode_limit, self.decode_limit), Image.Resampling.LANCZOS)
                    self.stills[media_id] = np.array(still)
            still = self.stills[media_id]
            if native:
                self.decode_scale[media_id] = max(still.shape[0], still.shape[1]) / native
            return apply_crop(still.copy(), clip)
        try:
            cursor = self._cursor(media_id, time, paths[0])
        except (ValueError, OSError) as exc:  # a file that is not a video (damaged, or another file under its name)
            raise MediaUnreadable(record.get("name") or media_id, f"the decoder could not open it ({exc})") from exc
        capture = self.sources[cursor]
        from . import yuv

        capture.own_conversion = yuv.wanted(gpu.stack_active()) and media_id not in self._cpu_only
        capture.want_planes = planes and capture.own_conversion  # planes kept, or converted on the read-ahead's thread
        keep_planes = planes and not crop_box(clip)
        rate = capture.fps
        count = capture.frame_count
        wanted = max(0, int(time * rate + 1e-7))
        if count:
            wanted = min(count - 1, wanted)
        # B6: smooth slow motion. A slowed clip normally shows the same source
        # frame several times over, which is what makes it look stepped. When
        # the clip asks for it, the picture between two source frames is made
        # rather than repeated: dense optical flow gives the motion between
        # them, and each is warped part of the way along it before they are
        # blended, so the movement continues instead of freezing.
        blend = float(time * rate) - wanted
        if clip.get("smoothSlow") and count and 0.02 < blend < 0.98 and wanted + 1 < count:
            made = self._tween(capture, cursor, wanted, blend)
            if made is not None:
                return apply_crop(made, clip)
        current = self.frame_numbers.get(cursor, -2)
        if wanted == current:
            # The cache holds the decoded frame, which nothing writes to; each use
            # converts it afresh, so what a caller receives is its own to change,
            # without copying every frame to protect the cache.
            if keep_planes and hasattr(self.frames[cursor], "aux"):
                return self.frames[cursor]
            return apply_crop(self.as_working(self.frames[cursor]), clip)
        if wanted != current + 1:
            capture.seek(wanted)
        ok, frame = capture.read()
        if not ok:
            # A container's frame count comes from its duration and can promise a
            # frame or two more than the file holds. Past the last real frame, hold
            # it, as a player does, rather than failing the whole render: reuse the
            # frame just read when this one follows it, or step back to one that
            # decodes. Only a source with nothing decodable near here is an error.
            frame = self.frames.get(cursor) if wanted == current + 1 else None
            back = wanted
            while frame is None and back > 0 and wanted - back < 3:
                back -= 1
                capture.seek(back)
                ok, frame = capture.read()
                frame = frame if ok else None
            if frame is None and getattr(capture, "own_conversion", False):
                # the device's colour path could not take this source's frames: read it converted here instead
                self._cpu_only.add(media_id)
                capture.own_conversion = False
                capture.want_planes = False
                capture.seek(wanted)
                ok, frame = capture.read()
                frame = frame if ok else None
                if frame is not None:
                    _say_once(f"{record.get('name', media_id)}: read with formcut's own conversion instead of the device's")
            if frame is None:
                raise MediaUnreadable(record.get("name") or media_id, _why(paths[0], capture))
        result = frame if keep_planes and hasattr(frame, "aux") else self.as_working(frame)
        self.frame_numbers[cursor] = wanted
        self.frames[cursor] = frame
        if native:
            self.decode_scale[media_id] = max(result.shape[0], result.shape[1]) / native
        return result if result is frame else apply_crop(result, clip)

    def scaled_effects(self, effects: list[dict], clip: dict) -> list[dict]:
        """Pixel-measured parameters follow the resolution actually decoded.

        A preview decodes small, so a radius in pixels would cover far more of
        the frame than the same radius does in a full-resolution export. The
        ratio is recorded when the frame is decoded, so both agree.
        """
        scale = self.decode_scale.get(clip.get("mediaId"), 1.0)
        if abs(scale - 1.0) < 1e-6:
            return effects
        out = []
        for entry in effects:
            copy = dict(entry)
            if copy.get("params"):
                copy["params"] = scale_pixel_params(copy["params"], scale)
            out.append(copy)
        return out

    def text_frame(self, clip: dict, local: float = 0.0) -> np.ndarray:
        """A title's pixels. R8: a title whose words do not move with time is rasterised once and served from
        a cache keyed by its style and the frame size; a word-animated title is drawn per frame as before."""
        text = clip.get("textStyle") or {"content": clip.get("label", "Title")}
        words = clip.get("words") or []
        # the word style's mode is read where the text style keeps it (wordStyle.mode): read as "wordMode", which
        # no style has, every karaoke caption was cached as a still, its lit word held through playback and export
        mode = (text.get("wordStyle") or {}).get("mode")
        animated = bool(words) and (mode in ("highlight", "pop", "box", *ANIMATED_WORDS) or any(w.get("colour") for w in words))
        if not animated:
            key = (clip.get("id"), json.dumps(text, sort_keys=True, default=str), self.width, self.height)
            self._last_text_key = ("text", key)
            cached = self.text_cache.get(key)
            if cached is not None:
                # lent read-only, not copied (8 MB a 1080p frame): a layer served from the device's cache never
                # reads it, and the few places that write a layer in place take their own copy first
                return cached
            drawn = self._draw_text(clip, text, local)
            if len(self.text_cache) > 24:
                self.text_cache.clear()
            drawn.flags.writeable = False
            self.text_cache[key] = drawn
            return drawn
        self._last_text_key = None
        return self._draw_text(clip, text, local)

    def _device_key(self, clip: dict, source_key, image: np.ndarray, matrix, alpha: float, fields: dict) -> tuple | None:
        """A key for a layer that is the same every frame (a still title, a still image with nothing moving), so
        the device keeps the finished layer and the next frame blends it without uploading or running anything."""
        if source_key is None or any(value is not None for value in fields.values()):
            return None
        look = json.dumps([clip.get("colour"), clip.get("colorGrade")], sort_keys=True, default=str)
        placed = np.round(np.asarray(matrix, np.float64), 6).tobytes()
        return (source_key, look, image.shape, str(image.dtype), placed, round(float(alpha), 6), self.transfer if self.deep else None)

    def _draw_text(self, clip: dict, text: dict, local: float) -> np.ndarray:
        image = Image.new("RGBA", (self.width, self.height))
        size = max(1, round(float(text.get("size", 8)) / 100 * self.height))
        font = title_font(text, size)
        content = str(text.get("content", "Title"))[:10000]
        spacing = size * (float(text["lineHeight"]) - 1 if text.get("lineHeight") else 0.2)
        wrap = text.get("wrapWidth")
        if wrap:
            content = wrap_text(content, font, max(1, self.width * float(wrap) / 100))
        tracking = float(text.get("letterSpacing", 0)) / 100 * size
        draw = ImageDraw.Draw(image)
        align = text.get("align", "center")
        stroke = max(0, round(float(text["outlineWidth"]) / 100 * size)) if text.get("outlineWidth") is not None else max(1, size // 32)
        stroke_fill = text.get("outlineColor", "#000000")
        box = measure_text(draw, content, font, spacing, tracking, 0)
        plate_box = measure_text(draw, content, font, spacing, tracking, stroke)
        x = self.width * 0.05 if align == "left" else self.width * 0.95 - box[2] if align == "right" else (self.width - box[2]) / 2
        x -= box[0]
        y = (self.height - box[3]) / 2 - box[1]
        plate = text.get("plateColor")
        if plate:
            pad = float(text.get("platePadding", 2)) / 100 * size
            radius = float(text.get("plateRadius", 0)) / 100 * size
            alpha = round(max(0.0, min(1.0, float(text.get("plateOpacity", 1)))) * 255)
            layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).rounded_rectangle(
                [x - pad, y - pad, x + plate_box[2] + pad, y + plate_box[3] + pad],
                radius=radius,
                fill=(*ImageColor.getrgb(plate), alpha),
            )
            image.alpha_composite(layer)
            draw = ImageDraw.Draw(image)
        shadow = text.get("shadowColor")
        if shadow:
            blur = float(text.get("shadowBlur", 0)) / 100 * size
            offset = (float(text.get("shadowX", 0)) / 100 * size, float(text.get("shadowY", 0)) / 100 * size)
            layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            paint_text(ImageDraw.Draw(layer), (x + offset[0], y + offset[1]), content, font, shadow, align, spacing, tracking, 0, None)
            if blur > 0:
                layer = layer.filter(ImageFilter.GaussianBlur(blur))
            image.alpha_composite(layer)
            draw = ImageDraw.Draw(image)
        words = clip.get("words") or []
        word_mode = (text.get("wordStyle") or {}).get("mode")
        # Per-word emphasis: a word with its own colour is drawn in it whether
        # or not it is the one being spoken, so the block takes the word path.
        if words and (word_mode in ("highlight", "pop", "box", *ANIMATED_WORDS) or any(word.get("colour") for word in words)):
            big = title_font(text, round(size * 1.18)) if word_mode == "pop" else font
            paint_words(draw, (x, y), content, font, text, words, local, align, spacing, tracking, stroke, stroke_fill, big)
        else:
            paint_text(draw, (x, y), content, font, text.get("color", "#ffffff"), align, spacing, tracking, stroke, stroke_fill)
        opacity = float(text.get("textOpacity", 1))
        if opacity < 1:
            faded = np.array(image)
            faded[:, :, 3] = np.round(faded[:, :, 3] * max(0.0, min(1.0, opacity))).astype(np.uint8)
            return self.lift(faded)
        return self.lift(np.array(image))

    def mask_alpha(self, mask: dict, w: int, h: int) -> np.ndarray:
        """The mask as an alpha field for a layer of this size, cached by its settings.

        A mask that does not change does not need rebuilding each frame.
        Filling the polygon is cheap; feathering it is not, because the
        sigma is a percentage of the frame, so a soft edge at 720p means a
        blur sigma in the tens of pixels. The key covers everything that
        alters the result, so an animated mask still recomputes. The CPU
        path multiplies it in; the device path uploads it as a pass (R5).
        """
        signature = (json.dumps(mask, sort_keys=True, default=str), w, h)
        alpha = self.mask_cache.get(signature)
        if alpha is None:
            alpha = np.zeros((h, w), np.float32)
            x0, y0 = int(mask["x"] / 100 * w), int(mask["y"] / 100 * h)
            x1, y1 = int((mask["x"] + mask["w"]) / 100 * w), int((mask["y"] + mask["h"]) / 100 * h)
            if mask["shape"] == "linear":
                # K5: a linear mask is a half-plane through the mask's centre at
                # the given angle; feather softens the edge like any other shape.
                angle = math.radians(float(mask.get("angle", 0)))
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                yy, xx = np.mgrid[:h, :w]
                side = (xx - cx) * math.sin(angle) - (yy - cy) * math.cos(angle)
                alpha = (side >= 0).astype(np.float32)
            else:
                # Every other shape, drawn path included, is a polygon in a unit
                # square scaled into the mask's box and turned by its angle, so
                # one routine covers all of them.
                unit = mask_polygon(mask)
                if unit:
                    box_w, box_h = max(1, x1 - x0), max(1, y1 - y0)
                    if mask["shape"] == "path":
                        points = [(px * w, py * h) for px, py in unit]
                        cx, cy = w / 2, h / 2
                    else:
                        points = [(x0 + px * box_w, y0 + py * box_h) for px, py in unit]
                        cx, cy = x0 + box_w / 2, y0 + box_h / 2
                    turn = math.radians(float(mask.get("angle", 0)))
                    if turn:
                        cos_a, sin_a = math.cos(turn), math.sin(turn)
                        points = [
                            (cx + (px - cx) * cos_a - (py - cy) * sin_a, cy + (px - cx) * sin_a + (py - cy) * cos_a) for px, py in points
                        ]
                    cv2.fillPoly(alpha, [np.array(points, np.int32)], 1)
            feather = max(0, float(mask.get("feather", 0))) / 100 * min(w, h)
            if feather > 0:
                alpha = cv2.GaussianBlur(alpha, (0, 0), feather)
            if mask.get("invert"):
                alpha = 1.0 - alpha
            if len(self.mask_cache) > 6:
                self.mask_cache.clear()
            self.mask_cache[signature] = alpha
        return alpha

    @staticmethod
    def masking_clip(clip: dict) -> dict:
        """The clip with its mask and cutout re-expressed inside its crop, so both land where the person drew them on the cropped picture."""
        box = crop_box(clip)
        if box:
            # Mask and stroke coordinates are fractions of the SOURCE frame; the
            # image here is the cropped window, so remap them into it.
            left, top, right, bottom = box
            sx, sy = 1 - left - right, 1 - top - bottom
            clip = dict(clip)
            if clip.get("mask"):
                m = dict(clip["mask"])
                m["x"] = (m["x"] / 100 - left) / sx * 100
                m["y"] = (m["y"] / 100 - top) / sy * 100
                m["w"] = m["w"] / sx
                m["h"] = m["h"] / sy
                clip["mask"] = m
            if clip.get("cutout"):
                options = dict(clip["cutout"])
                strokes = []
                for stroke in options.get("strokes", []) or []:
                    moved = dict(stroke)
                    moved["points"] = [((p[0] - left) / sx, (p[1] - top) / sy) for p in stroke.get("points", [])]
                    moved["radius"] = float(stroke.get("radius", 0.02)) / max(0.1, min(sx, sy))
                    strokes.append(moved)
                options["strokes"] = strokes
                clip["cutout"] = options
        return clip

    def cutout_alpha(self, clip: dict, image: np.ndarray) -> np.ndarray | None:
        """The cutout's feathered matte for this layer, or None when there is none to apply (BG3: the cached matte; a missing one renders unmatted rather than stalling). One builder for the CPU path and the device pass."""
        # BG3: read the cached matte; rendering never runs inference. A clip
        # whose mattes are not ready renders unmatted rather than stalling.
        from .matte_cache import matte_key
        from .matte_cache import read as read_matte
        from .segmentation import feathered

        options = clip["cutout"]
        key = matte_key(str(clip.get("mediaId") or clip["id"]), options.get("model", "object-cutout"), options)
        h2, w2 = image.shape[:2]
        alpha = read_matte(key, self.matte_time, (w2, h2))
        if alpha is None and not self.allow_proxy:
            # No matte has been computed for this moment. Rather than render
            # the clip untouched and leave a person wondering why the cutout
            # does nothing, compute it here and keep it. The precompute pass
            # is a speed-up, not a precondition, and treating it as one is
            # why cutout appeared to be broken while the model sat ready.
            try:
                from .segmentation import cutout_ready as model_ready
                from .segmentation import prompts, raw_alpha

                model = options.get("model", "object-cutout")
                if model_ready(model):
                    # The model must see the clip's own pixels, the way the
                    # precompute pass feeds it: a composited frame has the
                    # clip already scaled, rotated and placed on the canvas,
                    # so segmenting that finds whatever happens to be in the
                    # frame rather than the subject. Feeding it the canvas
                    # is what turned the cutout into a blob.
                    source = self.media_frame(clip, self.matte_time)
                    # Prompts are stored where the person pointed, on the
                    # picture; the model sees the clip's own pixels.
                    from .prompt_space import to_source

                    points, box = to_source(clip, (self.width, self.height), (source.shape[1], source.shape[0]), *prompts(options))
                    found = raw_alpha(source, model, points, box) if model == "click-select" else raw_alpha(source, model)
                    # A click says which of the things the model found was
                    # meant. Without it a frame with two people keeps both.
                    if points and model != "click-select":
                        from .segmentation import pick_region

                        found = pick_region(found, float(points[0]["x"]), float(points[0]["y"]))
                    alpha = cv2.resize(found, (w2, h2), interpolation=cv2.INTER_LINEAR)
            except Exception:
                alpha = None
        if alpha is None and (options.get("strokes") or []):
            # A brush stroke is a person's own instruction, not part of the
            # model's guess, so it has to apply whether or not a matte has
            # been computed. Skipping the whole branch when the matte was
            # missing threw the strokes away silently, which is why cutout
            # and brushes stopped doing anything at all.
            alpha = np.ones((h2, w2), np.float32)
        return feathered(alpha, options) if alpha is not None else None

    def mask_frame(self, image: np.ndarray, clip: dict) -> np.ndarray:
        # Only a key, a mask or a cutout changes the picture below; without them
        # this returned an unchanged copy, 9 ms a 1080p frame for nothing. The
        # one caller replaces its frame with the result, so no one shares it.
        if not (
            clip.get("key")
            or clip.get("mask")
            or clip.get("cutout")
            or clip.get("planarMatte")
            or clip.get("screenCut")
            or clip.get("glare")
        ):
            return image
        out = image.copy()
        h, w = out.shape[:2]
        original = clip  # the tracked matte reads the crop itself; the crop-adjusted copy is the mask's
        if clip.get("glare"):
            return self.glare_layer(out, clip, w, h)
        if clip.get("screenCut"):
            out = self.screen_cut(out, clip, w, h)
        clip = self.masking_clip(clip)
        key = clip.get("key")
        if key:
            color = np.array([int(key["color"][i : i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
            rgb = out[:, :, :3].astype(np.float32) / 255
            chroma = rgb - rgb.mean(2, keepdims=True)
            target = color - color.mean()
            similarity, blend = float(key.get("similarity", 0.25)), max(0.001, float(key.get("blend", 0.05)))
            if key.get("mode") == "difference":
                # a colour-difference key, as screen replacements use: how far the key colour's own channel stands
                # above the larger of the other two, against how far it stands in the key colour itself; similarity and
                # blend are shares of that. Black, grey and white have no difference and a colour leaning away from
                # the key has less than none, so neither can be keyed however wide the key: on the owner's upright
                # phone the hue distance, widened to take a reflection, took the notch, the bezel and the wall by the
                # phone's rounded corners as well (all sit about 0.55 from green in hue), where this key leaves them
                # whole. (A near-white hotspot of a reflection has little difference left, as little as the bezel:
                # no key tells them apart by colour; a tracked matte over the screen's inside does.) The map is
                # softened by a pixel first: compressed video carries its colour at half size, and a key on it alone
                # steps along its edges in 2 x 2 blocks
                lead = int(np.argmax(color))
                others = [c for c in range(3) if c != lead]
                own = float(color[lead] - max(color[others[0]], color[others[1]]))
                excess = (rgb[:, :, lead] - np.maximum(rgb[:, :, others[0]], rgb[:, :, others[1]])) / max(own, 1e-3)
                excess = cv2.GaussianBlur(excess.astype(np.float32), (0, 0), 0.8)
                keep = 1 - np.clip((excess - similarity) / blend, 0, 1)
            else:
                distance = np.linalg.norm(chroma - target, axis=2) / math.sqrt(2)
                keep = np.clip((distance - similarity) / blend, 0, 1)
            refine = int(key.get("refine", 0) or 0)
            if refine > 0:
                # the key's matte refined against the picture's brightness, which video keeps at full size where it
                # keeps colour at half: a guided filter (He, Sun and Tang) fits the matte to the brightness edge within
                # refine pixels, so the edge is smooth and where the picture's edge is on every frame (a key on the
                # colour alone stepped in 2 x 2 blocks along every edge and corner of the owner's screens; a vector
                # outline carried from one frame drifted off the real edge as the phone turned)
                keep = _guided(rgb @ np.array([0.299, 0.587, 0.114], np.float32), keep.astype(np.float32), refine, 1e-4)
            glare_region = key.get("glare")
            if isinstance(glare_region, dict) and glare_region.get("layer"):
                # the screen's glare taken too: inside the tracked screen, kept clear of its edges by inset pixels (a
                # carried outline may drift a pixel), a bright pixel whose two other channels rise evenly is glare on
                # the glass, which no key tells by colour (its lead all but washed out); a glare layer gives its light
                # back smoothly (left in the plate, the near-white core of the owner's upright phone's reflection was
                # an opaque white smudge)
                region = self.planar_alpha(
                    {**original, "planarMatte": {"layers": [glare_region["layer"]], "feather": 0, "invert": False}}, w, h
                )
                if region is not None:
                    inset = int(glare_region.get("inset", 6))
                    region = cv2.GaussianBlur(
                        cv2.erode(region, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * inset + 1, 2 * inset + 1))),
                        (0, 0),
                        max(1.0, inset / 3),
                    )
                    screenness, _, _ = self._screen_parts(rgb, region, "blue" if np.argmax(color) == 2 else "green")
                    keep = np.minimum(keep, 1 - screenness * region)
            if key.get("holdout"):
                # P7: a hold-out (core) matte: inside the chosen tracked layers the key takes nothing away
                held = self.planar_alpha({**original, "planarMatte": {"layers": list(key["holdout"]), "feather": 0, "invert": False}}, w, h)
                if held is not None:
                    keep = np.maximum(keep, held)
            out[:, :, 3] = np.round(out[:, :, 3] * keep).astype(out.dtype)
            spill = float(key.get("spill", 0) or 0)
            if spill > 0:
                # P7: spill suppression: the part of each pixel's colour along the key colour's own direction (its
                # chroma, the colour less its mean) taken off, as much as the amount asks; brightness is untouched
                # because that direction has no mean, and a pixel leaning away from the key is left alone
                top = 65535.0 if out.dtype == np.uint16 else 255.0
                rgb = out[:, :, :3].astype(np.float32) / top
                lean = (rgb - rgb.mean(2, keepdims=True)) @ (target / max(1e-6, float(np.linalg.norm(target))))
                # spill is light from the screen: it fades with distance from what the key took away (a blurred map
                # of it, reaching about 3% of the frame), so a colour merely near the key's elsewhere keeps its hue
                # (on the owner's clip 10 a teal wall far from the phone turned blue under spill applied everywhere)
                taken = (keep < 0.5).astype(np.uint8)
                # what the key took, out to the convex outline of each large keyed area: a patch the key left on the
                # screen (a reflection's palest part on the owner's upright phone) is on the screen, and its green is
                # spill however far from a keyed pixel; without this the middle of a large glare kept a green tint, and
                # filling only enclosed holes missed a hotspot touching the screen's edge (it meets the bezel, which the
                # key leaves too). The wall beside the screen, outside the outline, keeps the falloff
                found, _ = cv2.findContours(taken, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for region in found:
                    if cv2.contourArea(region) > 0.005 * w * h:
                        cv2.fillConvexPoly(taken, cv2.convexHull(region), 1)
                taken = taken.astype(np.float32)
                # (as far as a phone's bezel, about a hundredth of the frame: reaching 3% turned the teal wall round the
                # owner's upright phone blue; glare on the screen is reached by the fill above, not by the reach)
                reach = max(4.0, 0.008 * max(w, h))
                near = np.clip(cv2.GaussianBlur(taken, (0, 0), reach) * 4.0, 0, 1) if taken.any() else taken
                cleaned = rgb - (spill * near * np.maximum(lean, 0))[..., None] * (target / max(1e-6, float(np.linalg.norm(target))))
                out[:, :, :3] = np.round(np.clip(cleaned, 0, 1) * top).astype(out.dtype)
        mask = clip.get("mask")
        if mask:
            alpha = self.mask_alpha(mask, w, h)
            out[:, :, 3] = np.round(out[:, :, 3] * alpha).astype(out.dtype)
        if clip.get("cutout"):
            matte = self.cutout_alpha(clip, out)
            if matte is not None:
                out[:, :, 3] = np.round(out[:, :, 3] * matte).astype(out.dtype)
        planar = self.planar_alpha(original, w, h)
        if planar is not None:
            out[:, :, 3] = np.round(out[:, :, 3] * planar).astype(out.dtype)
        return out

    def _screen_parts(self, rgb: np.ndarray, matte: np.ndarray, screen: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """A screen's pixels, told from what is in front of it: the screen's channel's lead over the other two, and the
        light a reflection adds (white light raises the other two together, over their floor on the screen)."""
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        lead, one, two = (b, r, g) if screen == "blue" else (g, r, b)
        lead_over = lead - np.maximum(one, two)
        inside = matte > 0.5
        floor = np.percentile(np.stack([one, two], -1)[inside], 20, axis=0) if inside.any() else np.zeros(2, np.float32)
        ea, eb = one - floor[0], two - floor[1]
        # white light: its two rise alike, within a few levels on compressed video (skin: red well above blue); fully
        # even up to 5 levels, as compositing in linear light shows a tenth of a bright pixel left at a third of its
        # brightness (a hotspot judged 90% screen for 2 levels of difference stayed a pale blotch)
        even = np.clip(1 - np.maximum(np.abs(ea - eb) - 0.02, 0) / 0.06, 0, 1)
        light = np.clip(np.minimum(ea, eb), 0, 1) * even
        # the screen: its colour leads (glare washed or not), or inside it a bright even pixel (the glare's hottest part)
        # (a screen leads by 0.9, washed by glare by 0.3; skin lit by it by 0.1 at most, so the screen's range is 0.15
        # to 0.25: from 0.04 a green-lit finger came out a quarter see-through)
        # and inside it, a pixel whose other two rise evenly by any real amount is glare on the glass (the brightest
        # glare's lead drops into that range; asking it to be brighter left the owner's upright phone's hotspot as a pale
        # green blotch), where something in front is warm or cool, not even
        screenness = np.maximum(np.clip((lead_over - 0.15) / 0.1, 0, 1), even * np.clip((np.minimum(ea, eb) - 0.08) / 0.08, 0, 1) * inside)
        return screenness, light, lead_over

    def fitted_path(
        self, clip: dict, layer_id: str, luma: np.ndarray, w: int, h: int, reach: float = 5.0, bias: float = 1.0
    ) -> np.ndarray | None:
        """The screen's outline as a vector path fitted to this frame: carried by its track, each point moved along its
        outward normal to where the brightness crosses from screen to bezel, the moves smoothed along the path."""
        layer = next((one for one in (clip.get("planar") or {}).get("layers", []) if one.get("id") == layer_id and one.get("shapes")), None)
        if layer is None:
            return None
        from .planar_shapes import active_at

        left, top, right, bottom = crop_box(clip) or (0.0, 0.0, 0.0, 0.0)
        full_w, full_h = w / max(1e-6, 1 - left - right), h / max(1e-6, 1 - top - bottom)
        track = self._planar_track(str(layer.get("link") or layer["id"]))
        homography, media_w, media_h, index = np.eye(3), full_w, full_h, 0
        if track is not None:
            order, frames, fps, (media_w, media_h) = track
            index = round(self.matte_time * fps)
            at = bisect.bisect_left(order, index)
            nearest = min((order[k] for k in (at - 1, at) if 0 <= k < len(order)), key=lambda f: abs(f - index))
            homography = frames[nearest]
        scale = full_w / max(1.0, float(media_w))
        pts = active_at(layer["shapes"][0], index)[0] * [float(media_w), float(media_h)]
        pts = cv2.perspectiveTransform(pts.reshape(-1, 1, 2).astype(np.float64), homography).reshape(-1, 2)
        pts = pts * scale - [left * full_w, top * full_h]
        if len(pts) < 8:
            return pts
        tangent = np.roll(pts, -1, 0) - np.roll(pts, 1, 0)
        tangent /= np.maximum(np.linalg.norm(tangent, axis=1, keepdims=True), 1e-9)
        normal = np.stack([tangent[:, 1], -tangent[:, 0]], -1)
        if float(((pts - pts.mean(0)) * normal).sum()) < 0:
            normal = -normal
        steps = np.arange(-reach, reach + 1e-6, 0.25)
        xs = (pts[:, None, 0] + steps[None, :] * normal[:, None, 0]).astype(np.float32)
        ys = (pts[:, None, 1] + steps[None, :] * normal[:, None, 1]).astype(np.float32)
        profiles = cv2.remap(luma.astype(np.float32), xs, ys, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        offsets = np.zeros(len(pts))
        inner = steps <= -reach + 1.5
        for k, profile in enumerate(profiles):
            high, low = float(np.median(profile[inner])), float(profile[steps >= -1.0].min())
            if high - low < 0.08:
                continue
            level = (high + low) / 2
            below = np.nonzero((profile < level) & (steps >= -reach + 1.0))[0]
            if not len(below) or below[0] == 0:
                continue
            j = below[0]
            f = (profile[j - 1] - level) / max(1e-6, profile[j - 1] - profile[j])
            offsets[k] = steps[j - 1] + f * (steps[j] - steps[j - 1])
        wrapped = np.concatenate([offsets[-4:], offsets, offsets[:4]])
        offsets = np.median(np.lib.stride_tricks.sliding_window_view(wrapped, 9), axis=1)
        taps = np.exp(-0.5 * (np.arange(-12, 13) / 4.0) ** 2)
        taps /= taps.sum()
        offsets = np.convolve(np.concatenate([offsets[-12:], offsets, offsets[:12]]), taps, mode="valid") + bias
        return pts + offsets[:, None] * normal

    def planar_warp(self, image: np.ndarray, clip: dict) -> np.ndarray:
        """Mocha Pro's Stabilize and ReOrient modules on the frame, by a layer's planar track at the matte time:
        planarStabilize {layer} warps the frame back to the reference by the inverse of the track's motion, so the
        tracked plane holds still; planarReorient {layer, surface} warps the surface (four corners, the reference's
        unit square) to its reference box square-on and still. Outside the picture is transparent."""
        spec = clip.get("planarStabilize") or clip.get("planarReorient") or {}
        track = self._planar_track(str(spec.get("layer") or ""))
        if track is None:
            return image
        order, frames, fps, (media_w, media_h) = track
        index = round(self.matte_time * fps)
        at = bisect.bisect_left(order, index)
        nearest = min((order[k] for k in (at - 1, at) if 0 <= k < len(order)), key=lambda f: abs(f - index))
        h, w = image.shape[:2]
        scale = np.diag([w / max(1.0, float(media_w)), h / max(1.0, float(media_h)), 1.0])
        moved = scale @ np.asarray(frames[nearest], np.float64) @ np.linalg.inv(scale)
        if clip.get("planarStabilize"):
            warp = np.linalg.inv(moved)
        else:
            surface = np.array(spec.get("surface") or [[0, 0], [1, 0], [1, 1], [0, 1]], np.float64) * [w, h]
            now = cv2.perspectiveTransform(surface.reshape(-1, 1, 2), moved).reshape(-1, 2)
            (x0, y0), (x1, y1) = surface.min(0), surface.max(0)
            square = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float64)
            warp = cv2.getPerspectiveTransform(now.astype(np.float32), square.astype(np.float32)).astype(np.float64)
        return cv2.warpPerspective(image, warp, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    def screen_cut(self, out: np.ndarray, clip: dict, w: int, h: int) -> np.ndarray:
        """A phone's screen cut out of the clip (screenCut: layer, grow, dark, bright, spill): a screen is bright inside
        a black bezel, and the picture's brightness is kept at full size (its colour at half). Inside the screen's
        tracked outline, grown by grow pixels so a pixel of drift never leaves screen outside it, everything brighter
        than the bezel goes: the screen, its glare, a glare's white core and the glass's pale rim alike, the edge being
        the picture's own brightness edge, smooth and where it is on every frame; the dark bezel and notch stay. What is
        in front of the screen stays too: skin and the like are warm or cool, where the screen and white glare are
        even in red and blue. The screen's green is taken off what stays near it. The reflection comes back as light
        from a glare layer. (Telling glare by colour per pixel flickered across the video's 8 x 8 blocks into specks;
        a vector outline alone drifted off the real edge as the phone turned.)"""
        spec = clip.get("screenCut") or {}
        top = 65535.0 if out.dtype == np.uint16 else 255.0
        luma_in = (out[:, :, :3].astype(np.float32) / top) @ np.array([0.299, 0.587, 0.114], np.float32)
        path = self.fitted_path(clip, str(spec.get("layer")), luma_in, w, h, float(spec.get("snap", 5.0)), float(spec.get("bias", 1.0)))
        if path is None:
            return out
        from .planar_shapes import coverage

        matte = coverage(path, w, h)
        if float(spec.get("edge_soft", 0) or 0) > 0:
            matte = cv2.GaussianBlur(matte, (0, 0), float(spec["edge_soft"]))
        grow = max(0, round(float(spec.get("grow", 2.0))))
        inside = cv2.dilate(matte, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1))) if grow else matte
        rgb = out[:, :, :3].astype(np.float32) / top
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        luma = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
        green_screen = spec.get("screen") != "blue"
        one, two = (r, b) if green_screen else (r, g)
        lead = (g if green_screen else b) - np.maximum(one, two)
        # in front: uneven in red and blue (skin), or not led by the screen's colour at all (a nail, a highlight on skin:
        # on a green screen even white glare keeps green at or above red and blue; a fingernail's pale pink does not,
        # and was cut through on the owner's perspective shot)
        uneven = np.clip((np.abs(one - two) - 0.06) / 0.06, 0, 1) * np.clip((0.2 - lead) / 0.1, 0, 1)
        rim_px = max(1, int(spec.get("rim", 6)))
        core = cv2.erode(matte, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rim_px + 1, 2 * rim_px + 1)))
        in_front = np.maximum(uneven, np.clip((0.005 - lead) / 0.03, 0, 1) * core)
        front_soft = float(spec.get("front_soft", 0) or 0)
        close_px = int(spec.get("front_close", 5))
        if close_px > 0:
            in_front = cv2.morphologyEx(
                in_front.astype(np.float32),
                cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * close_px + 1, 2 * close_px + 1)),
            )
        if front_soft > 0:
            in_front = np.clip((cv2.GaussianBlur(in_front.astype(np.float32), (0, 0), front_soft) - 0.25) / 0.5, 0, 1)
            in_front = in_front * in_front * (3 - 2 * in_front)
        cut = matte * (1 - in_front)
        reach_green = int(spec.get("green_reach", 0) or 0)
        if reach_green > 0:
            around = cv2.dilate(matte, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * reach_green + 1, 2 * reach_green + 1)))
            clearly = np.clip((((g if green_screen else b) - np.maximum(one, two)) - 0.12) / 0.1, 0, 1)
            cut = np.maximum(cut, around * clearly * (1 - in_front))
        if spec.get("soften"):
            cut = _guided(luma, cut.astype(np.float32), int(spec["soften"]), 1e-4)
        # the screen's light on what stays, taken off and given back in the new screen's colour (light: a hex, the
        # replacement's average): only a lead of the screen's own colour is touched, so a teal wall, a wooden desk or a
        # white one are left as they are however far it reaches, and fingers over the screen lose their green (a reach
        # of a bezel's width left the fingers above the owner's perspective phone lit green)
        reach = float(spec.get("reach", 0) or 0) or max(6.0, 0.04 * max(w, h))
        near = np.clip(cv2.GaussianBlur(inside, (0, 0), reach) * 3.0, 0, 1)
        # despill: "max" holds the screen's colour to the larger of the other two (a teal wall untouched), "average" to
        # their mean, which takes the yellow a green screen casts on skin (green risen, still below red) as well
        limit = (one + two) / 2 if spec.get("despill") == "average" else np.maximum(one, two)
        thrown = np.clip((g if green_screen else b) - limit, 0, 1) * near * float(spec.get("spill", 1.0))
        rgb[:, :, 1 if green_screen else 2] -= thrown
        light = str(spec.get("light") or "").lstrip("#")
        if len(light) == 6:
            colour = np.array([int(light[k : k + 2], 16) for k in (0, 2, 4)], np.float32) / 255
            luma_of = float(colour @ np.array([0.299, 0.587, 0.114], np.float32))
            weight = 0.587 if green_screen else 0.114  # the luminance of the light taken off
            given = np.minimum(thrown, float(spec.get("light_cap", 0.12)))
            rgb += (given * weight)[..., None] * (colour / max(luma_of, 1e-3))[None, None, :]
        out[:, :, :3] = np.round(np.clip(rgb, 0, 1) * top).astype(out.dtype)
        out[:, :, 3] = np.round(out[:, :, 3].astype(np.float32) * (1 - cut)).astype(out.dtype)
        return out

    def glare_layer(self, out: np.ndarray, clip: dict, w: int, h: int) -> np.ndarray:
        """A screen's reflection as light of its own (glare: layer, screen, strength, smooth): what white light adds to
        the screen's other two channels, smoothed within the screen (finer than that is the video's compression), as a
        neutral grey on the screen and nothing elsewhere, kept off what is in front; the clip is meant to go on top with
        the Screen blend, which adds light as a reflection on glass does and keeps the picture's contrast (the glare
        left as the plate's own washed pixels over the picture read as a grey film, fake)."""
        spec = clip.get("glare") or {}
        top = 65535.0 if out.dtype == np.uint16 else 255.0
        matte = self.planar_alpha({**clip, "planarMatte": {"layers": [spec.get("layer")], "feather": 0, "invert": False}}, w, h)
        result = np.zeros_like(out)
        if matte is None:
            return result
        inset = int(spec.get("inset", 0) or 0)
        if inset > 0:
            # kept inside the screen by inset pixels and faded there: the glare is light on the glass, never the edge's
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * inset + 1, 2 * inset + 1))
            matte = cv2.GaussianBlur(cv2.erode(matte, k), (0, 0), inset / 2)
        rgb = out[:, :, :3].astype(np.float32) / top
        screenness, light, _ = self._screen_parts(rgb, matte, str(spec.get("screen", "green")))
        weight = matte * screenness
        soft = float(spec.get("smooth", 0) or 0) or max(3.0, 0.015 * max(w, h))
        spread = cv2.GaussianBlur(weight, (0, 0), soft)
        glare = cv2.GaussianBlur(light * weight, (0, 0), soft) / np.maximum(spread, 1e-4)
        glare = np.clip(glare * float(spec.get("strength", 0.8)), 0, 1) * np.clip(spread * 2, 0, 1)
        grey = np.round(glare * matte * screenness * top).astype(out.dtype)
        result[:, :, 0] = result[:, :, 1] = result[:, :, 2] = grey
        result[:, :, 3] = np.round(matte * top).astype(out.dtype)
        return result

    def _planar_track(self, layer_id: str) -> tuple[list[int], dict, float, tuple[int, int]] | None:
        """A planar layer's track from the engine's store (planar-tracks/<layer>.json), read again only when it
        changes: its frames in order, their homographies, the media's frame rate and size."""
        from .planar_api import STORE

        path = STORE / f"{layer_id}.json"
        try:
            stamp = path.stat().st_mtime_ns
        except OSError:
            return None
        cache = self.__dict__.setdefault("planar_tracks", {})
        known = cache.get(layer_id)
        if known is None or known[0] != stamp:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                follow = data.get("adjusted") or data["frames"]  # the adjusted track where the layer has one (P4)
                frames = {int(i): np.array(v, float).reshape(3, 3) for i, v in follow.items()}
                known = (stamp, sorted(frames), frames, float(data["fps"]), tuple(data["size"]))
            except (OSError, ValueError, KeyError, TypeError):
                return None
            cache[layer_id] = known
        return known[1], known[2], known[3], known[4]

    def planar_alpha(self, clip: dict, w: int, h: int) -> np.ndarray | None:
        """A clip's tracked matte, as Mocha AE's Apply Matte gives it (P3 of the planar tracking plan): the chosen
        planar layers' shapes (each adding to or cutting from its layer) carried by their tracks to the clip's source
        frame (self.matte_time; the nearest tracked frame held outside the track), in the decoded image's own pixels
        (its crop and decode scale accounted for), the layers together, feathered, inverted if asked. None without
        one."""
        spec = clip.get("planarMatte")
        if not isinstance(spec, dict):
            return None
        blur = spec.get("motionBlur") or {}
        samples = max(1, int(blur.get("samples", 1) or 1)) if blur else 1
        if samples > 1:
            span = float(blur.get("shutter", 180)) / 360 / float(self.project["fps"])
            centre, total = self.matte_time, None
            try:
                for k in range(samples):
                    self.matte_time = centre + (k / (samples - 1) - 0.5) * span
                    one = self.planar_alpha({**clip, "planarMatte": {**spec, "motionBlur": None}}, w, h)
                    if one is not None:
                        total = one if total is None else total + one
            finally:
                self.matte_time = centre
            return total / samples if total is not None else None
        wanted = set(spec.get("layers") or [])
        layers = [one for one in (clip.get("planar") or {}).get("layers", []) if one.get("id") in wanted and one.get("shapes")]
        if not layers:
            return None
        from .planar_shapes import layer_matte

        left, top, right, bottom = crop_box(clip) or (0.0, 0.0, 0.0, 0.0)
        full_w, full_h = w / max(1e-6, 1 - left - right), h / max(1e-6, 1 - top - bottom)
        alpha = np.zeros((h, w), np.float32)
        scale = 1.0
        for layer in reversed(layers):
            live_from, live_to = layer.get("inTime"), layer.get("outTime")
            before_in = live_from is not None and self.matte_time < float(live_from) - 1e-6
            after_out = live_to is not None and self.matte_time > float(live_to) + 1e-6
            if before_in or after_out:
                continue
            # Link to Track: the shapes ride the linked layer's track (adjusted where it has one), else their own
            track = self._planar_track(str(layer.get("link") or layer["id"]))
            homography = np.eye(3)
            media_w, media_h = full_w, full_h
            index = 0
            if track is not None:
                order, frames, fps, (media_w, media_h) = track
                index = round(self.matte_time * fps)
                at = bisect.bisect_left(order, index)
                nearest = min((order[k] for k in (at - 1, at) if 0 <= k < len(order)), key=lambda f: abs(f - index))
                homography = frames[nearest]
            scale = full_w / max(1.0, float(media_w))
            size = (float(media_w), float(media_h))

            def carry(pts, homography=homography, size=size):
                return cv2.perspectiveTransform((pts * list(size)).reshape(-1, 1, 2), homography).reshape(-1, 2)

            def to_pixels(media, scale=scale):
                return media * scale - [left * full_w, top * full_h]

            matte = layer_matte(layer["shapes"], index, carry, (w, h), to_pixels)
            if layer.get("invert"):
                matte = 1.0 - matte
            alpha = alpha * (1.0 - matte) if layer.get("blend") == "subtract" else np.maximum(alpha, matte)
        feather = float(spec.get("feather", 0) or 0) * scale
        if feather > 0:
            alpha = cv2.GaussianBlur(alpha, (0, 0), feather)
        return 1.0 - alpha if spec.get("invert") else alpha

    def transition(self, image: np.ndarray, clip: dict, local: float) -> np.ndarray:
        if not image.flags.writeable:
            image = image.copy()
        length = clip.get("transitionLength", 0)
        if not length or local >= length:
            return image
        progress = min(1, max(0, local / length))
        kind = clip["transitionIn"]["type"]
        h, w = image.shape[:2]
        if kind.startswith("wipe"):
            if kind == "wipe-left":
                image[:, int(w * progress) :, 3] = 0
            elif kind == "wipe-right":
                image[:, : int(w * (1 - progress)), 3] = 0
            elif kind == "wipe-up":
                image[int(h * progress) :, :, 3] = 0
            else:
                image[: int(h * (1 - progress)), :, 3] = 0
        elif kind in ("slide-left", "slide-right", "push-up"):
            dx = int(w * (1 - progress)) * (1 if kind == "slide-left" else -1) if kind != "push-up" else 0
            dy = int(h * (1 - progress)) if kind == "push-up" else 0
            image = cv2.warpAffine(image, np.float32([[1, 0, dx], [0, 1, dy]]), (w, h))
        elif kind == "zoom":
            matrix = cv2.getRotationMatrix2D((w / 2, h / 2), 0, max(0.001, progress))
            image = cv2.warpAffine(image, matrix, (w, h))
        elif kind == "iris":
            y, x = np.mgrid[:h, :w]
            alpha = ((x - w / 2) ** 2 + (y - h / 2) ** 2) <= (math.hypot(w, h) / 2 * progress) ** 2
            image[:, :, 3] *= alpha
        elif kind == "dissolve":
            y, x = np.mgrid[:h, :w]
            threshold = np.mod(np.sin(x * 12.9898 + y * 78.233) * 43758.5453, 1)
            image[:, :, 3] *= threshold < progress
        elif kind in ("push-down", "cover-left", "cover-up"):
            dx = int(w * (1 - progress)) if kind == "cover-left" else 0
            dy = -int(h * (1 - progress)) if kind == "push-down" else int(h * (1 - progress)) if kind == "cover-up" else 0
            image = cv2.warpAffine(image, np.float32([[1, 0, dx], [0, 1, dy]]), (w, h))
        elif kind in ("clock-wipe", "blinds", "diagonal-wipe", "diamond", "barn-door"):
            image[:, :, 3] *= _revealed(kind, h, w, progress)
        elif kind == "pixel-dissolve":
            image = _pixelated(image, round((1 - progress) * min(w, h) / 12))
            image[:, :, 3] = (image[:, :, 3].astype(np.float32) * progress).astype(image.dtype)
        elif kind == "blur-fade":
            if progress < 1:
                image = cv2.GaussianBlur(image, (0, 0), max(0.1, (1 - progress) * min(w, h) / 30))
            image[:, :, 3] = (image[:, :, 3].astype(np.float32) * progress).astype(image.dtype)
        elif kind == "spin":
            image = cv2.warpAffine(image, cv2.getRotationMatrix2D((w / 2, h / 2), -(1 - progress) * 180, max(0.001, progress)), (w, h))
        return image

    def transition_out(self, image: np.ndarray, clip: dict, local: float) -> np.ndarray:
        if not image.flags.writeable:
            image = image.copy()
        """The outgoing half of a transition (T1).

        The incoming clip is revealed by `transition`; this moves or hides the
        clip underneath it over the same band, so both sides animate. Each kind
        is the mirror of its incoming counterpart: a wipe hides what the
        incoming clip has already covered, a slide leaves in the same direction,
        a zoom grows away, an iris closes, a dissolve thins out.
        """
        out = clip.get("transitionOut")
        if not out:
            return image
        length = float(out.get("length") or 0)
        duration = clip["duration"]
        if length <= 0 or local < duration - 0.0001:
            return image
        progress = min(1.0, max(0.0, (local - duration) / length))
        kind = out["type"]
        h, w = image.shape[:2]
        if kind.startswith("wipe"):
            if kind == "wipe-left":
                image[:, : int(w * progress), 3] = 0
            elif kind == "wipe-right":
                image[:, int(w * (1 - progress)) :, 3] = 0
            elif kind == "wipe-up":
                image[: int(h * progress), :, 3] = 0
            else:
                image[int(h * (1 - progress)) :, :, 3] = 0
        elif kind in ("slide-left", "slide-right", "push-up"):
            dx = int(w * progress) * (-1 if kind == "slide-left" else 1) if kind != "push-up" else 0
            dy = -int(h * progress) if kind == "push-up" else 0
            image = cv2.warpAffine(image, np.float32([[1, 0, dx], [0, 1, dy]]), (w, h))
        elif kind == "zoom":
            matrix = cv2.getRotationMatrix2D((w / 2, h / 2), 0, 1 + progress)
            image = cv2.warpAffine(image, matrix, (w, h))
        elif kind == "iris":
            y, x = np.mgrid[:h, :w]
            image[:, :, 3] *= ((x - w / 2) ** 2 + (y - h / 2) ** 2) >= (math.hypot(w, h) / 2 * progress) ** 2
        elif kind == "dissolve":
            y, x = np.mgrid[:h, :w]
            threshold = np.mod(np.sin(x * 12.9898 + y * 78.233) * 43758.5453, 1)
            image[:, :, 3] *= threshold >= progress
        elif kind == "push-down":
            image = cv2.warpAffine(image, np.float32([[1, 0, 0], [0, 1, int(h * progress)]]), (w, h))
        elif kind in ("clock-wipe", "blinds", "diagonal-wipe", "diamond", "barn-door"):
            image[:, :, 3] *= ~_revealed(kind, h, w, progress)
        elif kind == "pixel-dissolve":
            image = _pixelated(image, round(progress * min(w, h) / 12))
        elif kind == "blur-fade" and progress > 0:
            image = cv2.GaussianBlur(image, (0, 0), max(0.1, progress * min(w, h) / 30))
        elif kind == "spin":
            image = cv2.warpAffine(image, cv2.getRotationMatrix2D((w / 2, h / 2), progress * 180, max(0.001, 1 - progress)), (w, h))
        return image

    def _matrix(self, image: np.ndarray, transform: dict) -> np.ndarray:
        """The affine that places a layer on the canvas; one definition for the device and the CPU paths."""
        h, w = image.shape[:2]
        fit = min(self.width / w, self.height / h)
        sx = fit * transform["scale"] / 100 * transform["width"] / 100 * (-1 if transform["flipH"] else 1)
        sy = fit * transform["scale"] / 100 * transform["height"] / 100 * (-1 if transform.get("flipV") else 1)
        angle = math.radians(transform["rotation"])
        c, s = math.cos(angle), math.sin(angle)
        a, b, d, e = c * sx, -s * sy, s * sx, c * sy
        cx = self.width * (0.5 + transform["posX"] / 100)
        cy = self.height * (0.5 + transform["posY"] / 100)
        return np.float32([[a, b, cx - a * w / 2 - b * h / 2], [d, e, cy - d * w / 2 - e * h / 2]])

    def _alpha(self, clip: dict, local: float, transform: dict) -> float:
        visual_fade = {**clip, "extendOut": 0}
        return max(0, min(1, transform["opacity"] / 100)) * fade_at(visual_fade, min(local, clip["duration"]))

    def _layer_fields(self, clip: dict, image: np.ndarray) -> dict:
        """The key, the mask and the cutout matte for a layer as the device passes take them, from the crop-adjusted clip, built by the same helpers the CPU path uses."""
        adjusted = self.masking_clip(clip)
        h, w = image.shape[:2]
        fields: dict = {}
        key = adjusted.get("key")
        if key:
            colour = tuple(int(key["color"][i : i + 2], 16) / 255 for i in (1, 3, 5))
            fields["key"] = (colour, float(key.get("similarity", 0.25)), float(key.get("blend", 0.05)))
        if adjusted.get("mask"):
            fields["mask"] = self.mask_alpha(adjusted["mask"], w, h)
        if adjusted.get("cutout"):
            matte = self.cutout_alpha(adjusted, image)
            if matte is not None:
                fields["matte"] = matte
        planar = self.planar_alpha(clip, w, h)
        if planar is not None:
            # the tracked matte joins the mask the device already takes as one alpha
            fields["mask"] = planar * fields["mask"] if "mask" in fields else planar
        return fields

    def _shader_of(self, clip: dict, local: float) -> tuple[str, float, list | None] | None:
        """A package shader as the device pass takes it: its source, the local time, its parameters; the source is read once and cached by asset."""
        if not clip.get("shaderId"):
            return None
        source = self.shader_sources.get(clip["shaderId"])
        if source is None:
            source = self.shader_sources[clip["shaderId"]] = asset_path(clip["shaderId"], ".wgsl").read_text()
        return (source, local, None)

    @staticmethod
    def _device_resident(clip: dict, scaled: list, local: float = 0.0) -> bool:
        """Whether nothing between a layer's effects and its blend needs the bytes on this side at this local time.

        R9: an effect chain without a device pass no longer disqualifies the layer; the chain runs on the CPU
        before the one upload and everything after it (LUT, shader, key, mask, matte, transform, blend) stays
        on the device, so such a layer costs its effect and no readback."""
        if any(clip.get(key) for key in CPU_STEPS):
            return False
        keyed = clip.get("key") or {}
        if keyed.get("spill") or keyed.get("holdout") or keyed.get("mode") == "difference" or keyed.get("refine"):
            return False  # the device's key pass has no spill, hold-out or colour difference: the key is made on this side
        # A transition and a push change the layer only while they run; the
        # rest of the clip's frames stay on the device.
        entering = clip.get("transitionIn") or {}
        if entering and local < float(entering.get("duration", entering.get("length", 0)) or 0):
            return False
        leaving = clip.get("transitionOut") or {}
        if leaving and local > float(clip["duration"]) - float(leaving.get("length", leaving.get("duration", 0)) or 0):
            return False
        return not (clip.get("pushOut") and local >= float(clip["duration"]))

    def _blend(self, canvas: np.ndarray, layer: np.ndarray, mode: str) -> np.ndarray:
        """One layer onto the canvas: batched for the device, or blended now.

        R3: with the stack compositor active, consecutive layers gather into a
        run and go up in one pass through gpu.composite_stack, the canvas
        uploaded once and read back once. Anything that reads the canvas
        mid-frame flushes first, so both paths see identical state.
        """
        if self.deep and layer.dtype == np.uint8:
            layer = self.lift(layer)  # a byte layer that reached the blend on the CPU path
        elif self.fine and layer.dtype == np.uint8:
            layer = layer.astype(np.uint16) * np.uint16(257)  # the same signal on the sixteen-bit canvas
        if gpu.stack_active():
            self.pending_layers.append((layer, mode))
            return canvas
        return gpu.composite(canvas, layer, mode, transfer=self.transfer)

    def _flush(self, canvas: np.ndarray) -> np.ndarray:
        if self.pending_layers:
            canvas = gpu.composite_stack(
                canvas,
                self.pending_layers,
                transfer=self.transfer,
                yuv=self._want_planes if self._final_flush else False,
                blank=canvas is getattr(self, "_fresh_canvas", None),
                as_bytes=self.fine and self._final_flush,
            )
            self.pending_layers = []
        return canvas

    def frame(self, time: float) -> np.ndarray:
        if self.project.get("background"):
            canvas = np.zeros((self.height, self.width, 4), np.uint16 if self.deep or self.fine else np.uint8)
            canvas[:, :, 3] = 65535 if self.fine else 255
        else:
            # nothing will be painted before the layers: one read-only blank canvas serves every frame (the M5
            # profile showed a 16 MB zeros a frame); anything that would write into it gets its own copy
            canvas = self._blank_canvas()
        # T3: what shows behind footage that does not fill the frame. Black is
        # the default, so a project without a background renders as before.
        canvas = self.paint_background(canvas, time)
        # nothing painted: the compositor may take the base as zero light without reading it
        self._fresh_canvas = canvas if not self.project.get("background") else None
        for clip in sorted(self.clips, key=lambda c: (-c["trackIndex"], c["start"])):
            local = time - clip["start"]
            if clip.get("trackHidden") or clip["kind"] == "audio" or local < 0 or local >= clip["duration"] + clip.get("extendOut", 0):
                continue
            # An effect switched off keeps its settings in the project and is left
            # out here, the one place a clip's visual effects are read.
            effects = [dict(entry) for entry in (clip.get("effects") or []) if entry.get("enabled", True) is not False]
            for entry in effects:
                if entry.get("keys"):
                    # K3: keyed parameters resolve per frame before the stack runs
                    entry["params"] = effect_params_at(entry, local)
            # The clip's own keyframes may name an effect's parameter or amount
            # as fx.<index>.<name>, which is how the timeline graph keys them;
            # they resolve here with the same easing as the transform keys.
            fx_props = {key for frame in clip.get("keyframes") or [] for key in (frame.get("props") or {}) if str(key).startswith("fx.")}
            if fx_props:
                all_effects = clip.get("effects") or []
                enabled_index = [i for i, entry in enumerate(all_effects) if entry.get("enabled", True) is not False]
                for key in fx_props:
                    _, index, name = key.split(".", 2)
                    if int(index) not in enabled_index:
                        continue
                    entry = effects[enabled_index.index(int(index))]
                    if name == "amount":
                        entry["amount"] = property_at(clip, key, local, float(entry.get("amount", 1)))
                    else:
                        params = dict(entry.get("params") or {})
                        params[name] = property_at(clip, key, local, float(params.get(name, 0)))
                        entry["params"] = params
                # Pixel-measured parameters follow the decoded resolution, so a
                # preview and its export agree on how strong an effect looks.
            if clip.get("effectId"):
                effects.insert(0, {"id": LEGACY.get(clip["effectId"], clip["effectId"]), "amount": 1})
            if clip["kind"] == "filter":
                canvas = self._flush(canvas)
                self.decode_scale.setdefault("canvas", self.width / self.project["width"])
                fine_canvas = self.fine and canvas.dtype == np.uint16
                if fine_canvas:
                    canvas = _to_bytes(canvas)  # an adjustment clip grades bytes, as it always has
                canvas = apply_color_grade(apply_colour_panel(canvas, clip.get("colour")), clip.get("colorGrade"))
                if effects:
                    scaled = self.scaled_effects(effects, {"mediaId": "canvas"})
                    on_device = gpu_effects.apply_effects(canvas, scaled, local)
                    canvas = on_device if on_device is not None else apply_effects(canvas, scaled, local)
                if clip.get("lutId"):
                    canvas = apply_lut(canvas, clip["lutId"], float(clip.get("lutIntensity", 1)))
                if fine_canvas:
                    canvas = canvas.astype(np.uint16) * np.uint16(257)
                continue
            if clip["kind"] == "image" and not clip.get("shaderId") and all(entry["id"] in GRADES for entry in effects):
                key = (
                    clip.get("mediaId"),
                    repr(effects),
                    clip.get("lutId"),
                    clip.get("lutIntensity", 1),
                    crop_box(clip),
                    repr(clip.get("colour")),
                    repr(clip.get("colorGrade")),
                )
                if key not in self.prepared:
                    still = self.media_frame(clip, 0)
                    still = apply_color_grade(apply_colour_panel(still, clip.get("colour")), clip.get("colorGrade"))
                    scaled = self.scaled_effects(effects, clip)
                    still = apply_effects(still, scaled, 0) if scaled else still
                    self.prepared[key] = apply_lut(still, clip["lutId"], float(clip.get("lutIntensity", 1))) if clip.get("lutId") else still
                image = self.prepared[key].copy()
                if gpu.stack_active() and self._device_resident(clip, [], local):
                    transform = transform_at(clip, local)
                    self.matte_time = source_time(clip, local)
                    fields = self._layer_fields(clip, image)
                    placed, alpha = self._matrix(image, transform), self._alpha(clip, local, transform)
                    staged = gpu_effects.effects_and_warp(
                        image,
                        [],
                        local,
                        placed,
                        alpha,
                        (self.width, self.height),
                        resident=True,
                        lift=self.transfer if self.deep else None,
                        base=self._base_for(canvas, transform),
                        device_key=self._device_key(clip, ("still", key), image, placed, alpha, fields),
                        **fields,
                    )
                    if isinstance(staged, int):
                        self.pending_layers.append((staged, str(transform["blendMode"])))
                        self.resident_layers += 1
                        continue
            else:
                if clip["kind"] == "timeline":
                    nested_image = self.nested_frame(clip, source_time(clip, local))
                    if nested_image is None:
                        continue
                    image = nested_image
                else:
                    # A video layer that goes straight to the device, with nothing on this side needing its pixels
                    # first, takes its frame as planes, and the device converts it (yuv.py)
                    early = self.scaled_effects(effects, clip) if clip["kind"] == "video" else []
                    straight = (
                        clip["kind"] == "video"
                        and gpu.stack_active()
                        and not clip.get("colour")
                        and not clip.get("colorGrade")
                        and not clip.get("stabilise")
                        and not clip.get("smoothSlow")
                        and (not early or gpu_effects.supported(early))
                        and self._device_resident(clip, early, local)
                    )
                    try:
                        image = (
                            self.text_frame(clip, local)
                            if clip["kind"] == "text"
                            else self.media_frame(clip, source_time(clip, local), planes=straight)
                        )
                    except MediaUnreadable as problem:
                        # the preview draws the clip as a card saying what is wrong, and the rest of the frame goes on;
                        # an export (no decode limit) stops, naming the file and the reason
                        if not self.decode_limit:
                            raise
                        _say_once(str(problem))
                        image = placeholder(self.width, self.height, problem)
                if hasattr(image, "aux"):
                    pass  # planes for the device: no colour, grade or stabilisation to apply on this side
                else:
                    image = apply_color_grade(apply_colour_panel(image, clip.get("colour")), clip.get("colorGrade"))
                # Stabilisation needs the clip's place in time, which an effect
                # never sees, so it is applied here from the measured path.
                steady = clip.get("stabilise")
                if steady and clip.get("mediaId"):
                    image = stabilise_frame(image, str(clip["mediaId"]), int(source_time(clip, local) * self.project["fps"]), steady)
                scaled = self.scaled_effects(effects, clip)
                if hasattr(image, "aux") and not (gpu.stack_active() and self._device_resident(clip, scaled, local)):
                    image = image.rgba()  # planes only go on to the device's path; anything else needs the pixels
                # R4: a layer with nothing between its effects and the blend
                # that needs bytes on this side (no LUT, shader, mask, key,
                # cutout, transition or push) stays on the device from its one
                # upload to the frame's single readback after the blend.
                if gpu.stack_active() and self._device_resident(clip, scaled, local):
                    transform = transform_at(clip, local)
                    if scaled and not gpu_effects.supported(scaled):
                        # R9: the chain has a CPU-only effect; run the whole chain here, in order, then go up once.
                        image = apply_effects(image, scaled, local)
                        scaled = []
                    lut = None
                    if clip.get("lutId"):
                        table, low, high = load_cube(clip["lutId"])
                        lut = (table, low, high, float(clip.get("lutIntensity", 1)))
                    self.matte_time = source_time(clip, local)
                    fields = self._layer_fields(clip, image)
                    placed, alpha = self._matrix(image, transform), self._alpha(clip, local, transform)
                    shader = self._shader_of(clip, local)
                    still_title = clip["kind"] == "text" and not scaled and lut is None and shader is None
                    staged = gpu_effects.effects_and_warp(
                        image,
                        scaled,
                        local,
                        placed,
                        alpha,
                        (self.width, self.height),
                        resident=True,
                        lut=lut,
                        shader=shader,
                        lift=self.transfer if self.deep else None,
                        base=self._base_for(canvas, transform),
                        device_key=self._device_key(clip, self._last_text_key, image, placed, alpha, fields) if still_title else None,
                        **fields,
                    )
                    if isinstance(staged, int):
                        self.pending_layers.append((staged, str(transform["blendMode"])))
                        self.resident_layers += 1
                        continue
                    if hasattr(image, "aux"):
                        image = image.rgba()  # the device did not take the planes: this side converts them after all
                    if staged is not None:
                        image = staged  # the compositor could not take it; the bytes came back placed, blend as a layer
                        layer = self.transition(image, clip, local)
                        canvas = self._blend(canvas, layer, str(transform["blendMode"]))
                        continue
                if scaled:
                    # R3: the chain as device passes when every effect has one; the CPU stays the reference.
                    on_device = gpu_effects.apply_effects(image, scaled, local)
                    image = on_device if on_device is not None else apply_effects(image, scaled, local)
                if clip.get("lutId"):
                    image = apply_lut(image, clip["lutId"], float(clip.get("lutIntensity", 1)))
            if clip.get("shaderId"):
                image = gpu.custom(image, asset_path(clip["shaderId"], ".wgsl").read_text(), local)
            self.matte_time = source_time(clip, local)
            if clip.get("planarStabilize") or clip.get("planarReorient"):
                image = self.planar_warp(image, clip)
            mask_track = (clip.get("mask") or {}).get("track")
            masked = {**clip, "mask": {**clip["mask"], "points": mask_points_at(mask_track, local)}} if mask_track else clip
            image = self.mask_frame(image, masked)
            transform = transform_at(clip, local)
            h, w = image.shape[:2]
            fit = min(self.width / w, self.height / h)
            sx = fit * transform["scale"] / 100 * transform["width"] / 100 * (-1 if transform["flipH"] else 1)
            sy = fit * transform["scale"] / 100 * transform["height"] / 100 * (-1 if transform.get("flipV") else 1)
            angle = math.radians(transform["rotation"])
            c, s = math.cos(angle), math.sin(angle)
            a, b, d, e = c * sx, -s * sy, s * sx, c * sy
            cx = self.width * (0.5 + transform["posX"] / 100)
            cy = self.height * (0.5 + transform["posY"] / 100)
            matrix = np.float32([[a, b, cx - a * w / 2 - b * h / 2], [d, e, cy - d * w / 2 - e * h / 2]])
            visual_fade = {**clip, "extendOut": 0}
            alpha = max(0, min(1, transform["opacity"] / 100)) * fade_at(visual_fade, min(local, clip["duration"]))
            pinned = pin_at(clip, local)
            if pinned is not None:
                # a corner pin: the image's corners onto the four canvas points by a homography (the clip's own place,
                # size and turn give way to it, as a corner pin does; its opacity, fades and blend stay)
                src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
                image = image if image.flags.writeable else image.copy()
                image[:, :, 3] = np.round(image[:, :, 3] * alpha).astype(image.dtype)
                blur = (clip.get("cornerPin") or {}).get("motionBlur") or {}
                samples = max(1, int(blur.get("samples", 1) or 1)) if blur else 1
                span = float(blur.get("shutter", 180)) / 360 / float(self.project["fps"]) if samples > 1 else 0.0
                top = 65535.0 if image.dtype == np.uint16 else 255.0
                total = np.zeros((self.height, self.width, 4), np.float32)
                for k in range(samples if samples > 1 else 0):
                    at = local + (k / (samples - 1) - 0.5) * span if samples > 1 else local
                    corners = pin_at(clip, at) or pinned
                    dst = np.float32([[x * self.width, y * self.height] for x, y in corners])
                    warped = cv2.warpPerspective(
                        image,
                        cv2.getPerspectiveTransform(src, dst),
                        (self.width, self.height),
                        flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=0,
                    )
                    warped = warped.astype(np.float32) / top
                    total[:, :, :3] += warped[:, :, :3] * warped[:, :, 3:4]
                    total[:, :, 3] += warped[:, :, 3]
                if samples > 1:
                    total /= samples
                    colour = total[:, :, :3] / np.maximum(total[:, :, 3:4], 1e-6)
                    layer = np.round(np.clip(np.dstack([colour, total[:, :, 3:4]]), 0, 1) * top).astype(image.dtype)
                else:
                    dst = np.float32([[x * self.width, y * self.height] for x, y in pinned])
                    layer = cv2.warpPerspective(
                        image,
                        cv2.getPerspectiveTransform(src, dst),
                        (self.width, self.height),
                        flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,
                        borderValue=0,
                    )
                match = (clip.get("cornerPin") or {}).get("match") or {}
                if any(match.get(k) for k in ("light", "grain", "blur")):
                    canvas = self._flush(canvas)
                    layer = insert_match(layer, np.asarray(canvas), match, f"{clip.get('id')}:{round(local * 1000)}")
                layer = self.transition(layer, clip, local)
                layer = self.transition_out(layer, clip, local)
                canvas = self._blend(canvas, layer, str(transform["blendMode"]))
                continue
            native = _native()
            # The Rust warp-and-blend kernel blends in gamma; since R24 every blend is in light, so the kernel is
            # used only once a build says it blends in light (LINEAR_LIGHT), and never on a deep (sixteen-bit)
            # frame. The golden frames caught it once formcut_native was installed beside the engine.
            if (
                native is not None
                and getattr(native, "LINEAR_LIGHT", False)
                and canvas.dtype == np.uint8
                and image.dtype == np.uint8
                and not gpu_effects.active()
                and _plainly_blended(clip, local, transform)
            ):
                # Warp and blend in one Rust pass, identical to the Python path below.
                canvas = self._flush(canvas)
                canvas = np.array(canvas) if not canvas.flags.writeable else np.ascontiguousarray(canvas)
                native.composite_affine(canvas, np.ascontiguousarray(image), [float(v) for v in matrix.ravel()], float(alpha))
                continue
            # R3: the transform as a device pass, the alpha scaled inside it; cv2 stays the reference.
            layer = gpu_effects.warp(image, matrix, alpha, (self.width, self.height))
            if layer is None:
                image = image if image.flags.writeable else image.copy()
                image[:, :, 3] = np.round(image[:, :, 3] * alpha).astype(image.dtype)
                layer = cv2.warpAffine(image, matrix, (self.width, self.height), flags=cv2.INTER_LINEAR)
            layer = self.transition(layer, clip, local)
            layer = self.transition_out(layer, clip, local)
            if clip.get("pushOut") and local >= clip["duration"]:
                shift = self.height * min(1, (local - clip["duration"]) / clip["pushOut"])
                layer = cv2.warpAffine(layer, np.float32([[1, 0, 0], [0, 1, -shift]]), (self.width, self.height))
            canvas = self._blend(canvas, layer, str(transform["blendMode"]))
        self._final_flush = True
        try:
            done = self._flush(canvas)
            # a sixteen-bit SDR canvas leaves as bytes (the device packs them itself; otherwise converted here)
            return _to_bytes(done) if self.fine and done.dtype == np.uint16 else done
        finally:
            self._final_flush = False
