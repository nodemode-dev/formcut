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


def _masks() -> tuple[str, ...]:
    from .renderer import MASK_SHAPES

    return (*MASK_SHAPES, "linear")


MASKS = _masks()
_lock = threading.Lock()
_base: np.ndarray | None = None


def _is_stack(item: str) -> bool:
    from .effect_packages import find

    entry = find(item)
    return bool(entry and entry["kind"] == "video" and entry["backend"]["type"] == "stack")


def known(kind: str, item: str) -> bool:
    if kind == "look":
        from .assets import ROOT

        return (ROOT / (item + ".cube")).is_file()
    if kind == "title":
        from .presets import TITLE_STYLE_IDS

        return item in TITLE_STYLE_IDS
    if kind == "caption":
        from .presets import CAPTION_STYLE_IDS

        return item in CAPTION_STYLE_IDS
    if kind == "texttemplate":
        from .text_templates import IDS

        return item in IDS
    return (
        (kind == "effect" and (item in GRADES or item in VIDEO_EFFECTS or _is_stack(item)))
        or (kind == "transition" and item in TRANSITIONS)
        or (kind == "mask" and item in MASKS)
        or (kind == "source" and item == "cutout")
        or (kind == "cutout" and any(preset["id"] == item for preset in _cutouts()))
    )


def _cutouts() -> list[dict]:
    from .catalogue import CUTOUT_PRESETS

    return CUTOUT_PRESETS


def base_image() -> np.ndarray:
    global _base
    with _lock:
        if _base is None:
            source = demo_dir() / "effect-example-image.jpg"
            if source.is_file():
                with Image.open(source) as image:
                    fitted = ImageOps.fit(
                        ImageOps.exif_transpose(image).convert("RGBA"), (WIDTH, HEIGHT), Image.Resampling.LANCZOS, centering=(0.5, 0.28)
                    )
                _base = np.array(fitted)
            else:
                y, x = np.mgrid[0:HEIGHT, 0:WIDTH]
                _base = np.dstack([x * 255 // WIDTH, y * 255 // HEIGHT, np.full_like(x, 140), np.full_like(x, 255)]).astype(np.uint8)
        return _base.copy()


def _cutout_preview(image: np.ndarray, preset: dict) -> np.ndarray:
    """A preset's edge on a soft stand-in matte, shaped by the engine's own formula.

    The real matte comes from a model at render time; here a smooth figure
    (head and shoulders for a person, a rounded form for an object) takes its
    place, so tight, loose, soft and hard differ exactly as they will on footage.
    """
    y, x = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
    u, v = x / WIDTH, y / HEIGHT
    if "key" in preset:
        # A backdrop in the key's colour behind the subject, removed where it matches.
        red, green, blue = (int(preset["key"]["color"][i : i + 2], 16) for i in (1, 3, 5))
        # The backdrop in the key's colour: kept on the left, keyed out on the
        # right, so the card shows which colour it removes.
        backdrop = (np.abs(u - 0.5) > 0.3) | (v < 0.12)
        out = image.copy()
        out[backdrop, :3] = (red, green, blue)
        out[backdrop & (u >= 0.5), 3] = 0
        return out
    if preset["model"] == "person-cutout":
        head = np.exp(-(((u - 0.5) / 0.1) ** 2 + ((v - 0.34) / 0.16) ** 2))
        body = np.exp(-(((u - 0.5) / 0.26) ** 2 + ((v - 0.95) / 0.3) ** 2))
        matte = np.clip(np.maximum(head, body) * 1.4, 0, 1)
    else:
        matte = np.clip(np.exp(-(((u - 0.5) / 0.28) ** 2 + ((v - 0.55) / 0.34) ** 2)) * 1.4, 0, 1)
    threshold, feather = float(preset["threshold"]), max(0.005, float(preset["feather"]))
    alpha = np.clip((matte - threshold + feather / 2) / feather, 0, 1)
    out = image.copy()
    out[:, :, 3] = np.round(out[:, :, 3] * alpha).astype(np.uint8)
    return out


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
    project = {
        "title": "p",
        "width": WIDTH,
        "height": HEIGHT,
        "fps": 30,
        "duration": 1,
        "activeTimeline": 0,
        "timelines": [
            {
                "id": "p",
                "name": "p",
                "tracks": [
                    {
                        "id": "t",
                        "name": "V",
                        "clips": [{"id": "p1", "kind": "text", "label": entry["name"], "start": 0, "duration": 1, "textStyle": style}],
                    }
                ],
            }
        ],
    }
    return FrameRenderer(project).frame(0.5)


def caption_style_preview(item: str) -> np.ndarray:
    """Draw a caption look through the renderer's word path, the second word lit."""
    from .presets import CAPTION_STYLES
    from .renderer import FrameRenderer

    entry = next((e for e in CAPTION_STYLES if e["id"] == item), None)
    if entry is None:
        raise HTTPException(404, "Unknown preview")
    words = ["the", "word", "being", "spoken"]
    # The card is 192 px wide, so the look is drawn at twice its real size to
    # read there; the style the panel applies keeps the real one.
    style = {**entry["style"], "content": " ".join(words), "size": min(9.0, float(entry["style"].get("size", 6)) * 1.6)}
    timing = [{"t": i * 0.25, "d": 0.25, "text": word} for i, word in enumerate(words)]
    project = {
        "title": "p",
        "width": WIDTH,
        "height": HEIGHT,
        "fps": 30,
        "duration": 1,
        "activeTimeline": 0,
        "timelines": [
            {
                "id": "p",
                "name": "p",
                "tracks": [
                    {
                        "id": "t",
                        "name": "V",
                        "clips": [
                            {
                                "id": "p1",
                                "kind": "text",
                                "label": style["content"],
                                "start": 0,
                                "duration": 1,
                                "textStyle": style,
                                "words": timing,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    return FrameRenderer(project).frame(0.3)


def render(kind: str, item: str) -> np.ndarray:
    if kind == "look":
        from .assets import apply_lut

        dark = np.zeros_like(base_image())
        dark[:, :, :3] = 28
        return over(apply_lut(base_image(), item), dark)
    if kind == "title":
        return title_style_preview(item)
    if kind == "caption":
        return caption_style_preview(item)
    if kind == "texttemplate":
        # An animated title, drawn through the renderer at the moment that shows it best.
        from .text_templates import hero, project

        return FrameRenderer(project(item, WIDTH, HEIGHT)).frame(hero(item))
    image = base_image()
    dark = np.zeros_like(image)
    dark[:, :, :3] = 28
    if kind == "effect":
        return over(apply_effects(image, [{"id": item, "amount": 1}], 0.5), dark)
    if kind == "mask":
        # The renderer's own shape, so the card shows the mask it applies.
        from .renderer import MASK_SHAPES

        alpha = np.zeros((HEIGHT, WIDTH), np.float32)
        if item == "linear":
            alpha[:] = np.clip((np.arange(WIDTH, dtype=np.float32) / WIDTH - 0.3) / 0.4, 0, 1)[None, :]
        else:
            box = np.array([[WIDTH * (0.16 + 0.68 * x), HEIGHT * (0.14 + 0.72 * y)] for x, y in MASK_SHAPES[item]], np.int32)
            cv2.fillPoly(alpha, [box], 1)
        image[:, :, 3] = np.round(image[:, :, 3] * cv2.GaussianBlur(alpha, (0, 0), 3)).astype(np.uint8)
        return over(image, dark)
    if kind == "cutout":
        return over(_cutout_preview(image, next(p for p in _cutouts() if p["id"] == item)), dark)
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
