from .video_source import acquire, recycle
from .catalogue import scale_pixel_params, GRADES
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import gpu
from .assets import apply_lut, asset_path
from .expressions import evaluate
from .fonts import title_font
from .media import MEDIA_DIR, _find, reversed_path
from .pixel_effects import apply_effects, apply_colour_panel, COLOUR_PANEL
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
        self.frames = {}
        self.decode_scale = {}
        self.closed = False

    def close(self):
        for source in self.sources.values():
            recycle(source)
        self.sources.clear()
        self.stills.clear()
        self.frames.clear()
        self.closed = True

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
                radius=radius, fill=ImageColor.getrgb(plate) + (alpha,),
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
            elif mask["shape"] == "ellipse":
                cv2.ellipse(alpha, ((x0 + x1) // 2, (y0 + y1) // 2), (max(1, (x1 - x0) // 2), max(1, (y1 - y0) // 2)), 0, 0, 360, 1, -1)
            else:
                cv2.rectangle(alpha, (x0, y0), (x1, y1), 1, -1)
            feather = max(0, float(mask.get("feather", 0))) / 100 * min(w, h)
            if feather > 0:
                alpha = cv2.GaussianBlur(alpha, (0, 0), feather)
            if mask.get("invert"):
                alpha = 1.0 - alpha
            out[:, :, 3] = np.round(out[:, :, 3] * alpha).astype(np.uint8)
        if clip.get("cutout"):
            from .segmentation import cutout_alpha
            alpha = cutout_alpha(out, clip["cutout"])
            out[:, :, 3] = np.round(out[:, :, 3] * alpha).astype(np.uint8)
        return out

    def transition(self, image: np.ndarray, clip: dict, local: float) -> np.ndarray:
        length = clip.get("transitionLength", 0)
        if not length or local >= length:
            return image
        progress = min(1, max(0, local / length))
        kind = clip["transitionIn"]["type"]
        h, w = image.shape[:2]
        if kind.startswith("wipe"):
            if kind == "wipe-left": image[:, int(w * progress):, 3] = 0
            elif kind == "wipe-right": image[:, :int(w * (1 - progress)), 3] = 0
            elif kind == "wipe-up": image[int(h * progress):, :, 3] = 0
            else: image[:int(h * (1 - progress)), :, 3] = 0
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

    def frame(self, time: float) -> np.ndarray:
        canvas = np.zeros((self.height, self.width, 4), np.uint8)
        canvas[:, :, 3] = 255
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
                scaled = self.scaled_effects(effects, clip)
                image = apply_effects(image, scaled, local) if scaled else image
                if clip.get("lutId"):
                    image = apply_lut(image, clip["lutId"], float(clip.get("lutIntensity", 1)))
            if clip.get("shaderId"):
                image = gpu.custom(image, asset_path(clip["shaderId"], ".wgsl").read_text(), local)
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
            if clip.get("pushOut") and local >= clip["duration"]:
                shift = self.height * min(1, (local - clip["duration"]) / clip["pushOut"])
                layer = cv2.warpAffine(layer, np.float32([[1, 0, 0], [0, 1, -shift]]), (self.width, self.height))
            canvas = gpu.composite(canvas, layer, str(transform["blendMode"]))
        return canvas
