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


@router.post("/brush")
def source_brush(body: BrushInput):
    try:
        project = validate_document(body.project)
        clip = next(c for c in flatten(project) if c["id"] == body.clipId)
        media = _find(clip["mediaId"])
        w, h = media["width"], media["height"]
        width, height = project["width"], project["height"]
        local = body.time - clip["start"]
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
        for p in body.points[:10000]:
            if len(p) != 2 or not all(math.isfinite(v) for v in p):
                raise ValueError("Invalid brush point")
            xy = inverse @ [p[0] * width - cx, p[1] * height - cy]
            points.append([float(xy[0] / w + 0.5), float(xy[1] / h + 0.5)])
        return {"points": points}
    except (ValueError, KeyError, StopIteration, np.linalg.LinAlgError) as exc:
        raise HTTPException(422, "Brush cannot be mapped: " + str(exc)) from exc
