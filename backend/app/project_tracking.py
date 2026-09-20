import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .brush import BrushInput, source_brush
from .expressions import evaluate
from .media import _find
from .render_document import flatten, validate_document
from .renderer import DEFAULTS
from .timing import property_at, source_time, timeline_time
from .track import TrackBody, track_point

router = APIRouter(prefix="/api/track", tags=["track"])


class ProjectTrackInput(BaseModel):
    project: dict
    target: str
    source: str
    time: float
    point: list[float]


@router.post("/clip")
def track_clip(body: ProjectTrackInput):
    try:
        project = validate_document(body.project)
        clips = flatten(project)
        source = next(c for c in clips if c["id"] == body.source)
        target = next(c for c in clips if c["id"] == body.target)
        media = _find(source["mediaId"])
        start = source_time(source, body.time - source["start"])
        mapped = source_brush(BrushInput(project=project, clipId=source["id"], time=body.time, points=[body.point]))["points"][0]
        if any(v < 0 or v > 1 for v in mapped):
            raise ValueError("Pick a point inside the source video")
        path = track_point(
            TrackBody(
                mediaId=source["mediaId"],
                x=mapped[0] * 100,
                y=mapped[1] * 100,
                source_start=start,
                max_seconds=min(30, source_time(source, source["duration"]) - start),
            )
        )
        width, height = project["width"], project["height"]
        w, h = media["width"], media["height"]
        keys = []
        for point in path["points"]:
            local = timeline_time(source, start + point["t"])
            target_time = source["start"] + local - target["start"]
            if not 0 <= target_time <= target["duration"]:
                continue
            transform = {**DEFAULTS, **(source.get("transform") or {})}
            for prop in ("posX", "posY", "scale", "rotation"):
                transform[prop] = property_at(source, prop, local, transform[prop])
                expression = (source.get("expressions") or {}).get(prop)
                if expression:
                    transform[prop] = evaluate(expression, local, source["duration"], transform[prop])
            fit = min(width / w, height / h) * transform["scale"] / 100
            x = (point["x"] / 100 - 0.5) * w * fit * transform["width"] / 100 * (-1 if transform["flipH"] else 1)
            y = (point["y"] / 100 - 0.5) * h * fit * transform["height"] / 100
            angle = math.radians(transform["rotation"])
            px = (x * math.cos(angle) - y * math.sin(angle)) / width * 100 + transform["posX"]
            py = (x * math.sin(angle) + y * math.cos(angle)) / height * 100 + transform["posY"]
            keys.append({"t": target_time, "props": {"posX": px, "posY": py}, "interp": "linear"})
        if len(keys) < 2:
            raise ValueError("The subject could not be tracked in the target range")
        return {"keyframes": keys}
    except (ValueError, KeyError, StopIteration, IndexError) as exc:
        raise HTTPException(422, str(exc)) from exc
