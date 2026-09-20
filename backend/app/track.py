"""Point tracking for formcut: template matching with a local search window
over sampled frames, returning the tracked point as percent coordinates per
sample. The spike that shaped this found the degenerate case worth guarding:
a template without variance (a flat patch, like the inside of a solid shape)
matches everywhere with a perfect score, so the template box auto-widens
until it contains edges. The frontend turns the returned path into position
keyframes, so tracking rides the existing keyframe system end to end."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .media import MEDIA_DIR
from .video_source import VideoSource

router = APIRouter(prefix="/api/track", tags=["track"])

MAX_SECONDS = 30.0


class TrackBody(BaseModel):
    mediaId: str
    source_start: float = Field(default=0, ge=0, le=86400)
    x: float
    y: float
    box: float = 0.12
    sample_fps: float = 10.0
    max_seconds: float = MAX_SECONDS


@router.post("")
def track_point(body: TrackBody) -> dict[str, Any]:
    try:
        import cv2
    except ImportError:
        raise HTTPException(status_code=503, detail="OpenCV is not installed on this engine")
    matches = list(MEDIA_DIR.glob(f"{body.mediaId}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="unknown media")
    cap = VideoSource(matches[0])
    fps = cap.fps
    if body.source_start:
        cap.seek(round(body.source_start * fps))
    ok, frame = cap.read()
    if not ok:
        cap.release()
        raise HTTPException(status_code=422, detail="could not read the media's frames")
    h, w = frame.shape[:2]
    px = min(max(body.x, 0.0), 100.0)
    py = min(max(body.y, 0.0), 100.0)
    cx, cy = int(px / 100 * w), int(py / 100 * h)
    gray0 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    box = int(min(w, h) * min(max(body.box, 0.05), 0.4))

    def grab(b: int):
        return gray0[max(0, cy - b // 2):cy + b // 2, max(0, cx - b // 2):cx + b // 2]

    tmpl = grab(box)
    while tmpl.size and tmpl.std() < 8 and box < min(w, h) // 2:
        box = int(box * 1.6)
        tmpl = grab(box)
    if not tmpl.size or tmpl.std() < 2:
        cap.release()
        raise HTTPException(status_code=422, detail="the picked point has no trackable detail")
    points = [{"t": 0.0, "x": round(px, 2), "y": round(py, 2)}]
    sample_fps = min(max(body.sample_fps, 2.0), 15.0)
    step = max(1, round(fps / sample_fps))
    limit = min(max(body.max_seconds, 1.0), MAX_SECONDS)
    n = 0
    while n / fps < limit:
        ok = True
        for _ in range(step):
            ok, frame = cap.read()
            n += 1
            if not ok:
                break
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sw = box * 2
        x0, y0 = max(0, cx - sw), max(0, cy - sw)
        region = gray[y0:y0 + 2 * sw + box, x0:x0 + 2 * sw + box]
        if region.shape[0] <= tmpl.shape[0] or region.shape[1] <= tmpl.shape[1]:
            break
        res = cv2.matchTemplate(region, tmpl, cv2.TM_CCOEFF_NORMED)
        _minv, score, _minl, loc = cv2.minMaxLoc(res)
        if score < 0.35:
            break
        cx = x0 + loc[0] + tmpl.shape[1] // 2
        cy = y0 + loc[1] + tmpl.shape[0] // 2
        points.append({"t": round(n / fps, 2), "x": round(cx / w * 100, 2), "y": round(cy / h * 100, 2)})
    cap.release()
    return {"points": points, "frame": {"w": w, "h": h}}
