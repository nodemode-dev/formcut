import math

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .expressions import evaluate
from .media import _find
from .render_document import flatten, validate_document
from .renderer import DEFAULTS
from .timing import property_at

router = APIRouter(prefix="/api/render", tags=["render"])


class BrushInput(BaseModel):
    project: dict
    clipId: str
    time: float
    points: list[list[float]]


def _to_source(project: dict, clip: dict, time: float, raw: list[list[float]]) -> list[list[float]]:
    """Canvas points mapped into the clip's own pixels, 0..1, at this moment."""
    media = _find(clip["mediaId"])
    w, h = media["width"], media["height"]
    width, height = project["width"], project["height"]
    local = time - clip["start"]
    transform = {**DEFAULTS, **(clip.get("transform") or {})}
    for prop in ("scale", "posX", "posY", "rotation", "opacity"):
        transform[prop] = property_at(clip, prop, local, transform[prop])
        expression = (clip.get("expressions") or {}).get(prop)
        if expression:
            transform[prop] = evaluate(expression, local, clip["duration"], transform[prop])
    fit = min(width / w, height / h)
    sx = fit * transform["scale"] / 100 * transform["width"] / 100 * (-1 if transform["flipH"] else 1)
    sy = fit * transform["scale"] / 100 * transform["height"] / 100
    angle = math.radians(transform["rotation"])
    cosine, sine = math.cos(angle), math.sin(angle)
    linear = np.array([[cosine * sx, -sine * sy], [sine * sx, cosine * sy]])
    inverse = np.linalg.inv(linear)
    cx = width * (0.5 + transform["posX"] / 100)
    cy = height * (0.5 + transform["posY"] / 100)
    points = []
    for p in raw[:10000]:
        if len(p) != 2 or not all(math.isfinite(v) for v in p):
            raise ValueError("Invalid brush point")
        xy = inverse @ [p[0] * width - cx, p[1] * height - cy]
        points.append([float(xy[0] / w + 0.5), float(xy[1] / h + 0.5)])
    return points


@router.post("/brush")
def source_brush(body: BrushInput):
    try:
        project = validate_document(body.project)
        clip = next(c for c in flatten(project) if c["id"] == body.clipId)
        return {"points": _to_source(project, clip, body.time, body.points)}
    except (ValueError, KeyError, StopIteration, np.linalg.LinAlgError) as exc:
        raise HTTPException(422, "Brush cannot be mapped: " + str(exc)) from exc


@router.post("/smart-brush")
def smart_brush(body: BrushInput):
    """BG5: the stroke as a prompt rather than paint.

    The painted points, mapped into the clip's own pixels, become positive
    SAM 2 point prompts on the frame the stroke was made on, and the region
    the model returns comes back as an outline the matte shaper fills on
    every frame; the stroke keeps that frame's source time.
    """
    from .model_manager import ready as model_ready

    if not model_ready("click-select"):
        raise HTTPException(409, "Download Point to select (SAM 2) in Local models first")
    try:
        project = validate_document(body.project)
        clip = next(c for c in flatten(project) if c["id"] == body.clipId)
        source = _to_source(project, clip, body.time, body.points)
    except (ValueError, KeyError, StopIteration, np.linalg.LinAlgError) as exc:
        raise HTTPException(422, "Brush cannot be mapped: " + str(exc)) from exc
    if not source:
        raise HTTPException(422, "The stroke has no points")
    # Up to five prompts spaced along the stroke say which thing was meant,
    # the way several taps would; the decoder reads them against one
    # encoding of the frame.
    count = min(5, len(source))
    chosen = [source[round(i * (len(source) - 1) / max(1, count - 1))] for i in range(count)]
    from .renderer import FrameRenderer
    from .segmentation import outline, raw_alpha
    from .timing import source_time

    at = source_time(clip, max(0.0, body.time - clip["start"]))
    renderer = FrameRenderer(project, 640)
    try:
        frame = renderer.media_frame(clip, at)
    finally:
        renderer.close()
    try:
        alpha = raw_alpha(frame, "click-select", [{"x": p[0], "y": p[1]} for p in chosen])
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    region = outline(alpha)
    if not region:
        raise HTTPException(422, "The stroke did not land on anything the model could find")
    return {"region": [[p["x"], p["y"]] for p in region], "t": at}
