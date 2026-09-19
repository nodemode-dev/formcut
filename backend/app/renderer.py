from .video_source import acquire, recycle
from .catalogue import GRADES
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import gpu
from .assets import apply_lut, asset_path
from .expressions import evaluate
from .fonts import title_font
from .media import MEDIA_DIR, _find, reversed_path
from .pixel_effects import apply_effects
from .render_document import flatten, validate_document
from .timing import fade_at, property_at, source_time

LEGACY = {"fc.gaussian-blur": "gaussian", "fc.box-blur": "box", "fc.motion-blur": "directional-blur", "fc.mono": "monochrome", "fc.invert": "invert", "fc.warm": "warmth", "fc.cool": "cooling", "fc.vignette-pop": "vignette"}
DEFAULTS = {"scale": 100, "posX": 0, "posY": 0, "rotation": 0, "width": 100, "height": 100, "opacity": 100, "blendMode": "Normal", "flipH": False}


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
        if clip["kind"] == "image":
            if media_id not in self.stills:
                with Image.open(paths[0]) as image:
                    still = ImageOps.exif_transpose(image).convert("RGBA")
                    if self.decode_limit and max(still.size) > self.decode_limit:
                        still.thumbnail((self.decode_limit, self.decode_limit), Image.Resampling.LANCZOS)
                    self.stills[media_id] = np.array(still)
            return self.stills[media_id].copy()
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
            return self.frames[media_id].copy()
        if wanted != current + 1:
            capture.seek(wanted)
        ok, frame = capture.read()
        if not ok:
            raise ValueError("Could not decode source frame")
        result = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        self.frame_numbers[media_id] = wanted
        self.frames[media_id] = result
        return result.copy()

    def text_frame(self, clip: dict) -> np.ndarray:
        text = clip.get("textStyle") or {"content": clip.get("label", "Title")}
        image = Image.new("RGBA", (self.width, self.height))
        size = max(1, round(float(text.get("size", 8)) / 100 * self.height))
        font = title_font(text, size)
        content = str(text.get("content", "Title"))[:10000]
        draw = ImageDraw.Draw(image)
        box = draw.multiline_textbbox((0, 0), content, font=font, spacing=size * 0.2)
        align = text.get("align", "center")
        x = self.width * 0.05 if align == "left" else self.width * 0.95 - (box[2] - box[0]) if align == "right" else (self.width - box[2] + box[0]) / 2
        y = (self.height - box[3] + box[1]) / 2 - box[1]
        draw.multiline_text((x, y), content, font=font, fill=text.get("color", "#ffffff"), align=align, spacing=size * 0.2, stroke_width=max(1, size // 32), stroke_fill="#000000")
        return np.array(image)

    def mask_frame(self, image: np.ndarray, clip: dict) -> np.ndarray:
        out = image.copy()
        h, w = out.shape[:2]
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
            if mask["shape"] == "ellipse":
                cv2.ellipse(alpha, ((x0 + x1) // 2, (y0 + y1) // 2), (max(1, (x1 - x0) // 2), max(1, (y1 - y0) // 2)), 0, 0, 360, 1, -1)
            else:
                cv2.rectangle(alpha, (x0, y0), (x1, y1), 1, -1)
            feather = max(0, float(mask.get("feather", 0))) / 100 * min(w, h)
            if feather > 0:
                alpha = cv2.GaussianBlur(alpha, (0, 0), feather)
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
            effects = list(clip.get("effects") or [])
            if clip.get("effectId"):
                effects.insert(0, {"id": LEGACY.get(clip["effectId"], clip["effectId"]), "amount": 1})
            if clip["kind"] == "filter":
                canvas = apply_effects(canvas, effects, local)
                continue
            if clip["kind"] == "image" and not clip.get("shaderId") and all(entry["id"] in GRADES for entry in effects):
                key = (clip.get("mediaId"), repr(effects), clip.get("lutId"))
                if key not in self.prepared:
                    still = self.media_frame(clip, 0)
                    still = apply_effects(still, effects, 0) if effects else still
                    self.prepared[key] = apply_lut(still, clip["lutId"]) if clip.get("lutId") else still
                image = self.prepared[key].copy()
            else:
                image = self.text_frame(clip) if clip["kind"] == "text" else self.media_frame(clip, source_time(clip, local))
                image = apply_effects(image, effects, local) if effects else image
                if clip.get("lutId"):
                    image = apply_lut(image, clip["lutId"])
            if clip.get("shaderId"):
                image = gpu.custom(image, asset_path(clip["shaderId"], ".wgsl").read_text(), local)
            image = self.mask_frame(image, clip)
            transform = {**DEFAULTS, **(clip.get("transform") or {})}
            for prop in ("scale", "posX", "posY", "rotation", "opacity"):
                transform[prop] = property_at(clip, prop, local, transform[prop])
                expression = (clip.get("expressions") or {}).get(prop)
                if expression:
                    transform[prop] = evaluate(expression, local, clip["duration"], transform[prop])
            h, w = image.shape[:2]
            fit = min(self.width / w, self.height / h)
            sx = fit * transform["scale"] / 100 * transform["width"] / 100 * (-1 if transform["flipH"] else 1)
            sy = fit * transform["scale"] / 100 * transform["height"] / 100
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
