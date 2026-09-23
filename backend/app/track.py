"""Point tracking for formcut: template matching with a local search window
over sampled frames, returning the tracked point as percent coordinates per
sample. The spike that shaped this found the degenerate case worth guarding:
a template without variance (a flat patch, like the inside of a solid shape)
matches everywhere with a perfect score, so the template box auto-widens
until it contains edges. The frontend turns the returned path into position
keyframes, so tracking rides the existing keyframe system end to end.

With transform set, the subject's size and angle are followed too, so a title
pinned to it grows and tilts with it: feature points inside the picked area are
followed by pyramidal Lucas-Kanade optical flow, each checked by tracking it
back (a point that does not return within a pixel is dropped), and a RANSAC
similarity (move, uniform scale, rotation) is estimated at each step and
accumulated. Points are topped up inside the subject's current area when too
few survive, and tracking stops where too little is left to trust.
"""

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
    transform: bool = False


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
        return gray0[max(0, cy - b // 2) : cy + b // 2, max(0, cx - b // 2) : cx + b // 2]

    tmpl = grab(box)
    while tmpl.size and tmpl.std() < 8 and box < min(w, h) // 2:
        box = int(box * 1.6)
        tmpl = grab(box)
    if not tmpl.size or tmpl.std() < 2:
        cap.release()
        raise HTTPException(status_code=422, detail="the picked point has no trackable detail")
    sample_fps = min(max(body.sample_fps, 2.0), 15.0)
    step = max(1, round(fps / sample_fps))
    limit = min(max(body.max_seconds, 1.0), MAX_SECONDS)
    if body.transform:
        try:
            return {"points": _follow_transform(cap, cv2, gray0, px, py, box, fps, step, limit), "frame": {"w": w, "h": h}}
        finally:
            cap.release()
    points = [{"t": 0.0, "x": round(px, 2), "y": round(py, 2)}]
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
        region = gray[y0 : y0 + 2 * sw + box, x0 : x0 + 2 * sw + box]
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


def _features(cv2, gray, cx: float, cy: float, size: float, avoid=None):
    import numpy as np

    mask = np.zeros_like(gray)
    half = max(4, int(size / 2))
    cv2.rectangle(mask, (int(cx) - half, int(cy) - half), (int(cx) + half, int(cy) + half), 255, -1)
    if avoid is not None:
        for x, y in avoid.reshape(-1, 2):
            cv2.circle(mask, (int(x), int(y)), 4, 0, -1)
    found = cv2.goodFeaturesToTrack(gray, maxCorners=80, qualityLevel=0.01, minDistance=3, mask=mask)
    return found.astype(np.float32) if found is not None else np.empty((0, 1, 2), np.float32)


def _follow_transform(cap, cv2, gray, px: float, py: float, box: int, fps: float, step: int, limit: float) -> list[dict]:
    """The picked point's path with the subject's scale (1 at the start) and rotation (degrees, clockwise)."""
    import math

    import numpy as np

    h, w = gray.shape[:2]
    start = np.array([px / 100 * w, py / 100 * h, 1.0])
    pts = _features(cv2, gray, start[0], start[1], box)
    if len(pts) < 6:
        raise HTTPException(status_code=422, detail="the picked area has too little detail to follow its size and angle")
    total = np.eye(3)
    path = [{"t": 0.0, "x": round(px, 2), "y": round(py, 2), "scale": 1.0, "rotation": 0.0}]
    flow = {"winSize": (21, 21), "maxLevel": 3}
    n = 0
    while n / fps < limit:
        ok, frame = True, None
        for _ in range(step):
            ok, frame = cap.read()
            n += 1
            if not ok:
                break
        if not ok:
            break
        nxt_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        nxt, found, _err = cv2.calcOpticalFlowPyrLK(gray, nxt_gray, pts, None, **flow)
        back, returned, _err = cv2.calcOpticalFlowPyrLK(nxt_gray, gray, nxt, None, **flow)
        good = (found.ravel() == 1) & (returned.ravel() == 1) & (np.linalg.norm((back - pts).reshape(-1, 2), axis=1) < 1.0)
        if good.sum() < 6:
            break
        step_matrix, inliers = cv2.estimateAffinePartial2D(pts[good], nxt[good], method=cv2.RANSAC, ransacReprojThreshold=2.0)
        if step_matrix is None or inliers is None or int(inliers.sum()) < 6:
            break
        total = np.vstack([step_matrix, [0.0, 0.0, 1.0]]) @ total
        cx, cy, _one = total @ start
        if not (0 <= cx < w and 0 <= cy < h):
            break
        scale = math.hypot(total[0, 0], total[1, 0])
        path.append(
            {
                "t": round(n / fps, 2),
                "x": round(float(cx) / w * 100, 2),
                "y": round(float(cy) / h * 100, 2),
                "scale": round(float(scale), 4),
                "rotation": round(math.degrees(math.atan2(float(total[1, 0]), float(total[0, 0]))), 2),
            }
        )
        kept = nxt[good][inliers.ravel() == 1].reshape(-1, 1, 2)
        if len(kept) < 25:
            kept = np.concatenate([kept, _features(cv2, nxt_gray, cx, cy, box * scale, kept)])
        gray, pts = nxt_gray, kept
    return path
