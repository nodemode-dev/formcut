import io
import threading

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from PIL import Image, ImageOps

from .catalogue import GRADES, PREVIEW_VERSION, TRANSITIONS, VIDEO_EFFECTS
from .demo import demo_dir
from .paths import DATA_DIR
from .pixel_effects import apply_effects
from .renderer import FrameRenderer

router = APIRouter(prefix="/api/catalogue/preview", tags=["catalogue"])
CACHE = DATA_DIR / "catalogue-previews"
WIDTH, HEIGHT = 192, 144
MASKS = ("rect", "ellipse")
_lock = threading.Lock()
_base: np.ndarray | None = None


def known(kind: str, item: str) -> bool:
    if kind == "title":
        from .presets import TITLE_STYLE_IDS
        return item in TITLE_STYLE_IDS
    return (
        (kind == "effect" and (item in GRADES or item in VIDEO_EFFECTS))
        or (kind == "transition" and item in TRANSITIONS)
        or (kind == "mask" and item in MASKS)
        or (kind == "source" and item == "cutout")
    )


def base_image() -> np.ndarray:
    global _base
    with _lock:
        if _base is None:
            source = demo_dir() / "effect-example-image.jpg"
            if source.is_file():
                with Image.open(source) as image:
                    fitted = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGBA"), (WIDTH, HEIGHT), Image.Resampling.LANCZOS, centering=(0.5, 0.28))
                _base = np.array(fitted)
            else:
                y, x = np.mgrid[0:HEIGHT, 0:WIDTH]
                _base = np.dstack([x * 255 // WIDTH, y * 255 // HEIGHT, np.full_like(x, 140), np.full_like(x, 255)]).astype(np.uint8)
        return _base.copy()


def over(layer: np.ndarray, ground: np.ndarray) -> np.ndarray:
    alpha = layer[:, :, 3:4].astype(np.float32) / 255
    rgb = layer[:, :, :3].astype(np.float32) * alpha + ground[:, :, :3].astype(np.float32) * (1 - alpha)
    return np.dstack([np.clip(rgb.round(), 0, 255).astype(np.uint8), np.full((HEIGHT, WIDTH), 255, np.uint8)])


def title_style_preview(item: str) -> np.ndarray:
    """Draw the built-in style through the renderer's own title path."""
    from .presets import TITLE_STYLES
    from .renderer import FrameRenderer
    entry = next((e for e in TITLE_STYLES if e["id"] == item), None)
    if entry is None:
        raise HTTPException(404, "Unknown preview")
    style = {**entry["style"], "content": entry["name"]}
    project = {"title": "p", "width": WIDTH, "height": HEIGHT, "fps": 30, "duration": 1, "activeTimeline": 0,
               "timelines": [{"id": "p", "name": "p", "tracks": [{"id": "t", "name": "V", "clips": [
                   {"id": "p1", "kind": "text", "label": entry["name"], "start": 0, "duration": 1, "textStyle": style}]}]}]}
    return FrameRenderer(project).frame(0.5)


def render(kind: str, item: str) -> np.ndarray:
    if kind == "title":
        return title_style_preview(item)
    image = base_image()
    dark = np.zeros_like(image)
    dark[:, :, :3] = 28
    if kind == "effect":
        return over(apply_effects(image, [{"id": item, "amount": 1}], 0.5), dark)
    if kind == "mask":
        alpha = np.zeros((HEIGHT, WIDTH), np.float32)
        if item == "ellipse":
            cv2.ellipse(alpha, (WIDTH // 2, HEIGHT // 2), (int(WIDTH * 0.34), int(HEIGHT * 0.36)), 0, 0, 360, 1, -1)
        else:
            cv2.rectangle(alpha, (int(WIDTH * 0.16), int(HEIGHT * 0.14)), (int(WIDTH * 0.84), int(HEIGHT * 0.86)), 1, -1)
        image[:, :, 3] = np.round(image[:, :, 3] * cv2.GaussianBlur(alpha, (0, 0), 3)).astype(np.uint8)
        return over(image, dark)
    if kind == "transition":
        outgoing = dark.copy()
        outgoing[:, :, :3] = np.round(image[:, :, :3].mean(axis=2, keepdims=True) * 0.4).astype(np.uint8)
        if item == "crossfade":
            image[:, :, 3] = 128
        elif item == "dip":
            return over(image, dark) // np.array([2, 2, 2, 1], np.uint8)
        else:
            image = FrameRenderer.transition(None, image, {"transitionLength": 1.0, "transitionIn": {"type": item}}, 0.5)
        return over(image, outgoing)
    return over(image, dark)


@router.get("/{kind}/{item}")
def preview(kind: str, item: str) -> Response:
    if not known(kind, item):
        raise HTTPException(404, "Unknown preview")
    path = CACHE / f"{PREVIEW_VERSION}-{kind}-{item}.png"
    if path.is_file():
        data = path.read_bytes()
    else:
        output = io.BytesIO()
        Image.fromarray(render(kind, item)).save(output, format="PNG", optimize=True)
        data = output.getvalue()
        CACHE.mkdir(parents=True, exist_ok=True)
        staged = path.with_name(f"{path.name}.{threading.get_ident()}.tmp")
        staged.write_bytes(data)
        staged.replace(path)
    return Response(data, media_type="image/png", headers={"Cache-Control": "max-age=86400"})
