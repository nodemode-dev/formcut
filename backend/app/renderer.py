import json
import math

import cv2
import numpy as np
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
CPU_STEPS: tuple[str, ...] = ()

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
                canvas[:, :, :3] = np.array(ImageColor.getrgb(str(fill.get("colour", "#000000"))), np.uint8)
            elif kind == "gradient":
                top = np.array(ImageColor.getrgb(str(fill.get("from", "#000000"))), np.float32)
                bottom = np.array(ImageColor.getrgb(str(fill.get("to", "#ffffff"))), np.float32)
                ramp = np.linspace(0.0, 1.0, self.height, dtype=np.float32)[:, None, None]
                canvas[:, :, :3] = np.clip(top + (bottom - top) * ramp, 0, 255).astype(np.uint8)
            elif kind == "image" and fill.get("mediaId"):
                still = self.media_frame({"kind": "image", "mediaId": str(fill["mediaId"])}, 0)
                canvas[:, :, :3] = self._cover(still[:, :, :3])
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
                    canvas[:, :, :3] = cv2.GaussianBlur(covered, (0, 0), amount)
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

    def as_working(self, frame: np.ndarray) -> np.ndarray:
        """A decoded frame as the working picture: RGBA bytes for an SDR project; for a deep project, a
        deep HDR frame (uint16 RGB in the transfer) gets its alpha, and a byte frame is lifted."""
        if frame.dtype == np.uint16:
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

    def media_frame(self, clip: dict, time: float) -> np.ndarray:
        media_id = clip.get("mediaId")
        if not media_id:
            raise ValueError("Media clip has no source")
        _find(media_id)
        if clip.get("reversed"):
            candidate = reversed_path(media_id)
            if not candidate.is_file():
                raise ValueError("Reversed copy is not prepared yet: " + media_id)
            paths = [candidate]
        else:
            paths = list(MEDIA_DIR.glob(f"{media_id}.*"))
            # P5: a preview may read a proxy; an export never does, because it
            # builds a renderer with no decode limit and this returns None.
            if paths and PROXIES_ENABLED and self.allow_proxy:
                stand_in = proxy_for(media_id, paths[0], self.decode_limit)
                if stand_in is not None:
                    paths = [stand_in]
        if not paths:
            raise ValueError("Media file is missing: " + media_id)
        record = _find(media_id)
        native = max(float(record.get("width") or 0), float(record.get("height") or 0))
        if clip["kind"] == "image":
            if media_id not in self.stills:
                with Image.open(paths[0]) as image:
                    still = ImageOps.exif_transpose(image).convert("RGBA")
                    if self.decode_limit and max(still.size) > self.decode_limit:
                        still.thumbnail((self.decode_limit, self.decode_limit), Image.Resampling.LANCZOS)
                    self.stills[media_id] = np.array(still)
            still = self.stills[media_id]
            if native:
                self.decode_scale[media_id] = max(still.shape[0], still.shape[1]) / native
            return apply_crop(still.copy(), clip)
        cursor = self._cursor(media_id, time, paths[0])
        capture = self.sources[cursor]
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
            if frame is None:
                raise ValueError("Could not decode source frame")
        result = self.as_working(frame)
        self.frame_numbers[cursor] = wanted
        self.frames[cursor] = frame
        if native:
            self.decode_scale[media_id] = max(result.shape[0], result.shape[1]) / native
        return apply_crop(result, clip)

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
        animated = bool(words) and (text.get("wordMode", "none") in ("highlight", "pop", "box") or any(w.get("colour") for w in words))
        if not animated:
            key = (clip.get("id"), json.dumps(text, sort_keys=True, default=str), self.width, self.height)
            cached = self.text_cache.get(key)
            if cached is not None:
                return cached.copy()
            drawn = self._draw_text(clip, text, local)
            if len(self.text_cache) > 24:
                self.text_cache.clear()
            self.text_cache[key] = drawn
            return drawn.copy()
        return self._draw_text(clip, text, local)

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
        if words and (word_mode in ("highlight", "pop", "box") or any(word.get("colour") for word in words)):
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
        if not (clip.get("key") or clip.get("mask") or clip.get("cutout")):
            return image
        out = image.copy()
        h, w = out.shape[:2]
        clip = self.masking_clip(clip)
        key = clip.get("key")
        if key:
            color = np.array([int(key["color"][i : i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
            rgb = out[:, :, :3].astype(np.float32) / 255
            chroma = rgb - rgb.mean(2, keepdims=True)
            target = color - color.mean()
            distance = np.linalg.norm(chroma - target, axis=2) / math.sqrt(2)
            similarity, blend = float(key.get("similarity", 0.25)), max(0.001, float(key.get("blend", 0.05)))
            out[:, :, 3] = np.round(out[:, :, 3] * np.clip((distance - similarity) / blend, 0, 1)).astype(out.dtype)
        mask = clip.get("mask")
        if mask:
            alpha = self.mask_alpha(mask, w, h)
            out[:, :, 3] = np.round(out[:, :, 3] * alpha).astype(out.dtype)
        if clip.get("cutout"):
            matte = self.cutout_alpha(clip, out)
            if matte is not None:
                out[:, :, 3] = np.round(out[:, :, 3] * matte).astype(out.dtype)
        return out

    def transition(self, image: np.ndarray, clip: dict, local: float) -> np.ndarray:
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
        if gpu.stack_active():
            self.pending_layers.append((layer, mode))
            return canvas
        return gpu.composite(canvas, layer, mode, transfer=self.transfer)

    def _flush(self, canvas: np.ndarray) -> np.ndarray:
        if self.pending_layers:
            canvas = gpu.composite_stack(canvas, self.pending_layers, transfer=self.transfer)
            self.pending_layers = []
        return canvas

    def frame(self, time: float) -> np.ndarray:
        canvas = np.zeros((self.height, self.width, 4), np.uint16 if self.deep else np.uint8)
        canvas[:, :, 3] = 255
        # T3: what shows behind footage that does not fill the frame. Black is
        # the default, so a project without a background renders as before.
        canvas = self.paint_background(canvas, time)
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
                canvas = apply_color_grade(apply_colour_panel(canvas, clip.get("colour")), clip.get("colorGrade"))
                if effects:
                    scaled = self.scaled_effects(effects, {"mediaId": "canvas"})
                    on_device = gpu_effects.apply_effects(canvas, scaled, local)
                    canvas = on_device if on_device is not None else apply_effects(canvas, scaled, local)
                if clip.get("lutId"):
                    canvas = apply_lut(canvas, clip["lutId"], float(clip.get("lutIntensity", 1)))
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
                    fields = self._layer_fields(clip, image)
                    staged = gpu_effects.effects_and_warp(
                        image,
                        [],
                        local,
                        self._matrix(image, transform),
                        self._alpha(clip, local, transform),
                        (self.width, self.height),
                        resident=True,
                        lift=self.transfer if self.deep else None,
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
                    image = self.text_frame(clip, local) if clip["kind"] == "text" else self.media_frame(clip, source_time(clip, local))
                image = apply_color_grade(apply_colour_panel(image, clip.get("colour")), clip.get("colorGrade"))
                # Stabilisation needs the clip's place in time, which an effect
                # never sees, so it is applied here from the measured path.
                steady = clip.get("stabilise")
                if steady and clip.get("mediaId"):
                    image = stabilise_frame(image, str(clip["mediaId"]), int(source_time(clip, local) * self.project["fps"]), steady)
                scaled = self.scaled_effects(effects, clip)
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
                    fields = self._layer_fields(clip, image)
                    staged = gpu_effects.effects_and_warp(
                        image,
                        scaled,
                        local,
                        self._matrix(image, transform),
                        self._alpha(clip, local, transform),
                        (self.width, self.height),
                        resident=True,
                        lut=lut,
                        shader=self._shader_of(clip, local),
                        lift=self.transfer if self.deep else None,
                        **fields,
                    )
                    if isinstance(staged, int):
                        self.pending_layers.append((staged, str(transform["blendMode"])))
                        self.resident_layers += 1
                        continue
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
            image = self.mask_frame(image, clip)
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
            native = _native()
            if native is not None and not gpu_effects.active() and _plainly_blended(clip, local, transform):
                # Warp and blend in one Rust pass, identical to the Python path below.
                canvas = self._flush(canvas)
                canvas = np.ascontiguousarray(canvas)
                native.composite_affine(canvas, np.ascontiguousarray(image), [float(v) for v in matrix.ravel()], float(alpha))
                continue
            # R3: the transform as a device pass, the alpha scaled inside it; cv2 stays the reference.
            layer = gpu_effects.warp(image, matrix, alpha, (self.width, self.height))
            if layer is None:
                image[:, :, 3] = np.round(image[:, :, 3] * alpha).astype(image.dtype)
                layer = cv2.warpAffine(image, matrix, (self.width, self.height), flags=cv2.INTER_LINEAR)
            layer = self.transition(layer, clip, local)
            layer = self.transition_out(layer, clip, local)
            if clip.get("pushOut") and local >= clip["duration"]:
                shift = self.height * min(1, (local - clip["duration"]) / clip["pushOut"])
                layer = cv2.warpAffine(layer, np.float32([[1, 0, 0], [0, 1, -shift]]), (self.width, self.height))
            canvas = self._blend(canvas, layer, str(transform["blendMode"]))
        return self._flush(canvas)
