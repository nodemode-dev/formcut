import math

import cv2
import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageOps

from . import gpu
from .assets import apply_lut, asset_path
from .catalogue import GRADES, scale_pixel_params
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
from .render_document import flatten, validate_document
from .timing import animation_at, effect_params_at, fade_at, property_at, source_time

LEGACY = {"fc.gaussian-blur": "gaussian", "fc.box-blur": "box", "fc.motion-blur": "directional-blur", "fc.mono": "monochrome", "fc.invert": "invert", "fc.warm": "warmth", "fc.cool": "cooling", "fc.vignette-pop": "vignette"}
DEFAULTS = {"scale": 100, "posX": 0, "posY": 0, "rotation": 0, "width": 100, "height": 100, "opacity": 100, "blendMode": "Normal", "flipH": False, "flipV": False}


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
        draw.multiline_text((x, y), content, font=font, fill=fill, align=align, spacing=spacing,
                            stroke_width=stroke, stroke_fill=stroke_fill)
        return
    lines = content.split("\n")
    widest = max((line_width(font, line, tracking) for line in lines), default=0.0)
    step = font.size + spacing
    for index, line in enumerate(lines):
        width = line_width(font, line, tracking)
        start = x if align == "left" else x + widest - width if align == "right" else x + (widest - width) / 2
        cursor = start
        for char in line:
            draw.text((cursor, y + index * step), char, font=font, fill=fill,
                      stroke_width=stroke, stroke_fill=stroke_fill, anchor="la")
            cursor += font.getlength(char) + tracking


# Mask shapes (13 plus a drawn path). Each returns points in a unit square, so
# one routine can scale, rotate and fill any of them; a drawn path carries its
# own anchors and bezier handles instead.
def _regular(sides: int, turn: float = -0.5) -> list[tuple[float, float]]:
    return [(0.5 + 0.5 * math.cos(2 * math.pi * (i / sides + turn / sides)),
             0.5 + 0.5 * math.sin(2 * math.pi * (i / sides + turn / sides))) for i in range(sides)]


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
    "triangle": _regular(3),
    "diamond": [(0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5)],
    "pentagon": _regular(5),
    "hexagon": _regular(6),
    "octagon": _regular(8),
    "star": _star(5, 0.42),
    "star6": _star(6, 0.55),
    "heart": _heart(),
    "cross": [(0.35, 0), (0.65, 0), (0.65, 0.35), (1, 0.35), (1, 0.65), (0.65, 0.65),
              (0.65, 1), (0.35, 1), (0.35, 0.65), (0, 0.65), (0, 0.35), (0.35, 0.35)],
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
            out.append((u ** 3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * x3,
                        u ** 3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y3))
    return out


def mask_polygon(mask: dict) -> list[tuple[float, float]]:
    """Unit-square points for a mask, whichever kind it is."""
    if mask.get("shape") == "path":
        return _bezier_path(mask.get("points") or [])
    return [tuple(p) for p in MASK_SHAPES.get(str(mask.get("shape")), MASK_SHAPES["rect"])]


class FrameRenderer:
    def __init__(self, project: dict, width: int | None = None):
        self.project = validate_document(project)
        self.width = width or self.project["width"]
        self.height = max(2, round(self.project["height"] * self.width / self.project["width"]))
        self.decode_limit = max(self.width, self.height) if width else None
        self.prepared = {}
        self.clips = flatten(self.project)
        self.sources = {}
        self.stills = {}
        self.frame_numbers = {}
        self.tween_pairs = {}
        self.frames = {}
        self.decode_scale = {}
        # P6: a paused still shows what the export will produce, so it reads the
        # original; playback and scrubbing set this and read the proxy.
        self.allow_proxy = False
        self.matte_time = 0.0
        self.closed = False

    def close(self):
        for source in self.sources.values():
            recycle(source)
        self.sources.clear()
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
                source = next((c for c in sorted(self.clips, key=lambda c: -c["trackIndex"])
                               if c["kind"] in ("video", "image") and c.get("mediaId")
                               and c["start"] <= time < c["start"] + c["duration"] + c.get("extendOut", 0)), None)
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
        return resized[top:top + self.height, left:left + self.width]

    def _tween(self, capture, media_id: str, wanted: int, blend: float):
        """The picture partway between two source frames, following the motion."""
        key = (media_id, wanted)
        pair = self.tween_pairs.get(key)
        if pair is None:
            current = self.frame_numbers.get(media_id, -2)
            if wanted != current + 1:
                capture.seek(wanted)
            ok, first = capture.read()
            if not ok:
                return None
            ok, second = capture.read()
            if not ok:
                return None
            self.frame_numbers[media_id] = wanted + 1
            self.frames[media_id] = cv2.cvtColor(second, cv2.COLOR_BGR2RGBA)
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
        if media_id not in self.sources:
            self.sources[media_id] = acquire(paths[0], self.decode_limit, time)
        capture = self.sources[media_id]
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
            made = self._tween(capture, media_id, wanted, blend)
            if made is not None:
                return apply_crop(made, clip)
        current = self.frame_numbers.get(media_id, -2)
        if wanted == current:
            return apply_crop(self.frames[media_id].copy(), clip)
        if wanted != current + 1:
            capture.seek(wanted)
        ok, frame = capture.read()
        if not ok:
            raise ValueError("Could not decode source frame")
        result = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        self.frame_numbers[media_id] = wanted
        self.frames[media_id] = result
        if native:
            self.decode_scale[media_id] = max(result.shape[0], result.shape[1]) / native
        return apply_crop(result.copy(), clip)

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

    def text_frame(self, clip: dict) -> np.ndarray:
        text = clip.get("textStyle") or {"content": clip.get("label", "Title")}
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
                radius=radius, fill=(*ImageColor.getrgb(plate), alpha),
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
        paint_text(draw, (x, y), content, font, text.get("color", "#ffffff"), align, spacing, tracking, stroke, stroke_fill)
        opacity = float(text.get("textOpacity", 1))
        if opacity < 1:
            faded = np.array(image)
            faded[:, :, 3] = np.round(faded[:, :, 3] * max(0.0, min(1.0, opacity))).astype(np.uint8)
            return faded
        return np.array(image)

    def mask_frame(self, image: np.ndarray, clip: dict) -> np.ndarray:
        out = image.copy()
        h, w = out.shape[:2]
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
        key = clip.get("key")
        if key:
            color = np.array([int(key["color"][i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
            rgb = out[:, :, :3].astype(np.float32) / 255
            chroma = rgb - rgb.mean(2, keepdims=True)
            target = color - color.mean()
            distance = np.linalg.norm(chroma - target, axis=2) / math.sqrt(2)
            similarity, blend = float(key.get("similarity", 0.25)), max(0.001, float(key.get("blend", 0.05)))
            out[:, :, 3] = np.round(out[:, :, 3] * np.clip((distance - similarity) / blend, 0, 1)).astype(np.uint8)
        mask = clip.get("mask")
        if mask:
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
                        points = [(cx + (px - cx) * cos_a - (py - cy) * sin_a,
                                   cy + (px - cx) * sin_a + (py - cy) * cos_a) for px, py in points]
                    cv2.fillPoly(alpha, [np.array(points, np.int32)], 1)
            feather = max(0, float(mask.get("feather", 0))) / 100 * min(w, h)
            if feather > 0:
                alpha = cv2.GaussianBlur(alpha, (0, 0), feather)
            if mask.get("invert"):
                alpha = 1.0 - alpha
            out[:, :, 3] = np.round(out[:, :, 3] * alpha).astype(np.uint8)
        if clip.get("cutout"):
            # BG3: read the cached matte; rendering never runs inference. A clip
            # whose mattes are not ready renders unmatted rather than stalling.
            from .matte_cache import matte_key
            from .matte_cache import read as read_matte
            from .segmentation import feathered
            options = clip["cutout"]
            key = matte_key(str(clip.get("mediaId") or clip["id"]), options.get("model", "object-cutout"), options)
            h2, w2 = out.shape[:2]
            alpha = read_matte(key, self.matte_time, (w2, h2))
            if alpha is None and (options.get("strokes") or []):
                # A brush stroke is a person's own instruction, not part of the
                # model's guess, so it has to apply whether or not a matte has
                # been computed. Skipping the whole branch when the matte was
                # missing threw the strokes away silently, which is why cutout
                # and brushes stopped doing anything at all.
                alpha = np.ones((h2, w2), np.float32)
            if alpha is not None:
                out[:, :, 3] = np.round(out[:, :, 3] * feathered(alpha, options)).astype(np.uint8)
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
                image[:, int(w * progress):, 3] = 0
            elif kind == "wipe-right":
                image[:, :int(w * (1 - progress)), 3] = 0
            elif kind == "wipe-up":
                image[int(h * progress):, :, 3] = 0
            else:
                image[:int(h * (1 - progress)), :, 3] = 0
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
                image[:, :int(w * progress), 3] = 0
            elif kind == "wipe-right":
                image[:, int(w * (1 - progress)):, 3] = 0
            elif kind == "wipe-up":
                image[:int(h * progress), :, 3] = 0
            else:
                image[int(h * (1 - progress)):, :, 3] = 0
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
        return image

    def frame(self, time: float) -> np.ndarray:
        canvas = np.zeros((self.height, self.width, 4), np.uint8)
        canvas[:, :, 3] = 255
        # T3: what shows behind footage that does not fill the frame. Black is
        # the default, so a project without a background renders as before.
        canvas = self.paint_background(canvas, time)
        for clip in sorted(self.clips, key=lambda c: (-c["trackIndex"], c["start"])):
            local = time - clip["start"]
            if clip.get("trackHidden") or clip["kind"] == "audio" or local < 0 or local >= clip["duration"] + clip.get("extendOut", 0):
                continue
            effects = [dict(entry) for entry in (clip.get("effects") or [])]
            for entry in effects:
                if entry.get("keys"):
                    # K3: keyed parameters resolve per frame before the stack runs
                    entry["params"] = effect_params_at(entry, local)
                # Pixel-measured parameters follow the decoded resolution, so a
                # preview and its export agree on how strong an effect looks.
            if clip.get("effectId"):
                effects.insert(0, {"id": LEGACY.get(clip["effectId"], clip["effectId"]), "amount": 1})
            if clip["kind"] == "filter":
                canvas = apply_effects(canvas, effects, local)
                continue
            if clip["kind"] == "image" and not clip.get("shaderId") and all(entry["id"] in GRADES for entry in effects):
                key = (clip.get("mediaId"), repr(effects), clip.get("lutId"), clip.get("lutIntensity", 1), crop_box(clip), repr(clip.get("colour")))
                if key not in self.prepared:
                    still = self.media_frame(clip, 0)
                    still = apply_colour_panel(still, clip.get("colour"))
                    scaled = self.scaled_effects(effects, clip)
                    still = apply_effects(still, scaled, 0) if scaled else still
                    self.prepared[key] = apply_lut(still, clip["lutId"], float(clip.get("lutIntensity", 1))) if clip.get("lutId") else still
                image = self.prepared[key].copy()
            else:
                image = self.text_frame(clip) if clip["kind"] == "text" else self.media_frame(clip, source_time(clip, local))
                image = apply_colour_panel(image, clip.get("colour"))
                # Stabilisation needs the clip's place in time, which an effect
                # never sees, so it is applied here from the measured path.
                steady = clip.get("stabilise")
                if steady and clip.get("mediaId"):
                    image = stabilise_frame(image, str(clip["mediaId"]),
                                            int(source_time(clip, local) * self.project["fps"]), steady)
                scaled = self.scaled_effects(effects, clip)
                image = apply_effects(image, scaled, local) if scaled else image
                if clip.get("lutId"):
                    image = apply_lut(image, clip["lutId"], float(clip.get("lutIntensity", 1)))
            if clip.get("shaderId"):
                image = gpu.custom(image, asset_path(clip["shaderId"], ".wgsl").read_text(), local)
            self.matte_time = source_time(clip, local)
            image = self.mask_frame(image, clip)
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
            image[:, :, 3] = np.round(image[:, :, 3] * alpha).astype(np.uint8)
            layer = cv2.warpAffine(image, matrix, (self.width, self.height), flags=cv2.INTER_LINEAR)
            layer = self.transition(layer, clip, local)
            layer = self.transition_out(layer, clip, local)
            if clip.get("pushOut") and local >= clip["duration"]:
                shift = self.height * min(1, (local - clip["duration"]) / clip["pushOut"])
                layer = cv2.warpAffine(layer, np.float32([[1, 0, 0], [0, 1, -shift]]), (self.width, self.height))
            canvas = gpu.composite(canvas, layer, str(transform["blendMode"]))
        return canvas
