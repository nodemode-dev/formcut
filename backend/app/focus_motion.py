"""Focus moves: a camera move composed from areas drawn on a clip, written as ordinary keyframes.

The person draws numbered areas on a clip's picture; this plans a move that frames each in turn and writes it as the
clip's scale, posX and posY keyframes, so it stays editable like any other keyframe. The framing is solved from the
renderer's own placement (`Renderer._matrix`): the picture is fitted to the canvas (fit = min(W / w, H / h)), scaled by
scale percent, its centre at W * (0.5 + posX / 100), H * (0.5 + posY / 100). Keyframe values replace the clip's own;
a keyframe's easing shapes the segment after it (`timing.property_at`).

2D here; 3D (a device clip's camera) comes with the device layer and shares the route and timing below.
"""

import random

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/focus-motion", tags=["focus-motion"])

PROPS = ("scale", "posX", "posY")
# speed -> (move weight, hold weight, easing): a fast move is short and snappy with long holds, a slow one glides
SPEEDS = {"fast": (0.7, 2.0, "easeInOut"), "medium": (1.1, 1.6, "smooth"), "slow": (1.8, 1.2, "smooth")}


def framing(area: list[float], canvas: tuple[float, float], picture: tuple[float, float], base: dict, margin: float) -> dict:
    """The scale and position that put a unit-rectangle area of the picture in the middle of the canvas, its longer
    side filling all but the margin on each side. Along an axis where the picture is then wider than the canvas its
    edges are kept outside the canvas; where it is narrower it keeps the wide shot's position (no new empty edge)."""
    big_w, big_h = canvas
    w, h = picture
    x0, y0, x1, y1 = (min(1.0, max(0.0, float(v))) for v in area)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    uw, uh = max(1e-3, x1 - x0), max(1e-3, y1 - y0)
    fit = min(big_w / w, big_h / h)
    stretch_w, stretch_h = base.get("width", 100) / 100, base.get("height", 100) / 100
    need = max(uw * fit * w * stretch_w / big_w, uh * fit * h * stretch_h / big_h)
    scale = max(base.get("scale", 100), 100 * (1 - 2 * margin) / need)
    shown_w, shown_h = fit * scale / 100 * w * stretch_w, fit * scale / 100 * h * stretch_h
    pos_x = -100 * ((x0 + x1) / 2 - 0.5) * shown_w / big_w
    pos_y = -100 * ((y0 + y1) / 2 - 0.5) * shown_h / big_h
    # the picture's edges stay outside the canvas where it is the bigger; elsewhere it keeps the wide position
    if shown_w >= big_w:
        reach_x = 100 * (shown_w - big_w) / 2 / big_w
        pos_x = max(-reach_x, min(reach_x, pos_x))
    else:
        pos_x = base.get("posX", 0)
    if shown_h >= big_h:
        reach_y = 100 * (shown_h - big_h) / 2 / big_h
        pos_y = max(-reach_y, min(reach_y, pos_y))
    else:
        pos_y = base.get("posY", 0)
    return {"scale": round(scale, 4), "posX": round(pos_x, 4), "posY": round(pos_y, 4)}


def visiting_order(count: int, seed: int | None, previous: list[int] | None = None) -> list[int]:
    """The order the areas are visited: as drawn, or a seeded shuffle that differs from the previous order."""
    order = list(range(count))
    if seed is None or count < 2:
        return order
    generator = random.Random(seed)  # noqa: S311 (a repeatable visiting order, not a secret)
    for _ in range(12):
        candidate = order[:]
        generator.shuffle(candidate)
        if candidate != (previous or order):
            return candidate
    return order[1:] + order[:1]


def compose(
    duration: float,
    canvas: tuple[float, float],
    picture: tuple[float, float],
    areas: list[list[float]],
    base: dict,
    speed: str = "medium",
    loop: bool = False,
    seed: int | None = None,
    margin: float = 0.08,
) -> dict:
    """The move as keyframes over the clip: a wide hold, then a move to and a hold on each area in the visiting order,
    then (loop) a move back to the wide framing, so the clip ends where it began."""
    if not areas:
        raise ValueError("Draw at least one focus area")
    order = visiting_order(len(areas), seed)
    wide = {p: float(base.get(p, 100 if p == "scale" else 0)) for p in PROPS}
    stops = [framing(areas[i], canvas, picture, base, margin + (0.04 * (k % 3) if seed is not None else 0)) for k, i in enumerate(order)]
    return {"keyframes": route(duration, wide, stops, speed, loop), "order": order}


def route(duration: float, wide: dict, stops: list[dict], speed: str, loop: bool) -> list[dict]:
    """Keyframes over the clip: a wide hold, a move to and a hold on each stop, and with loop a move back to wide."""
    move_w, hold_w, ease = SPEEDS.get(speed, SPEEDS["medium"])
    # weights: the opening hold, a move and a hold per area, and for a loop a move back and a closing hold
    segments = [("hold", 1.0)]
    for _ in stops:
        segments += [("move", move_w), ("hold", hold_w)]
    if loop:
        segments += [("move", move_w), ("hold", 1.0)]
    unit = float(duration) / sum(weight for _, weight in segments)
    keys, t, current = [], 0.0, wide
    targets = iter([*stops, wide] if loop else stops)
    for kind, weight in segments:
        if kind == "hold":
            # a hold is keyed at both ends with the same values; the end key carries the easing of the move after it
            keys.append({"t": round(t, 4), "props": dict(current), "interp": "linear"})
            t += weight * unit
            keys.append({"t": round(min(t, float(duration)), 4), "props": dict(current), "interp": ease})
        else:
            current = next(targets)
            t += weight * unit
    # collapse keys a very short clip puts at the same moment
    merged: list[dict] = []
    for key in keys:
        if merged and abs(merged[-1]["t"] - key["t"]) < 1e-6:
            merged[-1] = key
        else:
            merged.append(key)
    return merged


CAMERA_PROPS = ("device.yaw", "device.pitch", "device.distance", "device.panX", "device.panY")
CAMERA_BASE = {"yaw": 25.0, "pitch": 12.0, "distance": 1.0, "panX": 0.0, "panY": 0.0}


def camera_framing(area: list[float], aspect: float, base: dict, margin: float, turn: float) -> dict:
    """The device camera that puts a stage-fraction area in the middle of the frame, filling all but the margin.

    The device layer covers the canvas, so an area drawn on the stage is in canvas fractions. Pan is in framed heights
    at the current distance (device_scene.orbit: the target moves by pan times the half-height at that distance), so
    the area's offset is added at the old distance and the pan rescaled for the new one. turn adds a small orbit."""
    x0, y0, x1, y1 = (min(1.0, max(0.0, float(v))) for v in area)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    size = max(x1 - x0, y1 - y0, 0.02)
    old = float(base["distance"])
    new = min(3.0, max(0.1, old * size / (1 - 2 * margin)))
    pan_x = (float(base["panX"]) - ((x0 + x1) / 2 - 0.5) * 2 * aspect) * old / new
    pan_y = (float(base["panY"]) + ((y0 + y1) / 2 - 0.5) * 2) * old / new
    return {
        "device.yaw": round(float(base["yaw"]) + turn, 3),
        "device.pitch": round(float(base["pitch"]) - abs(turn) * 0.35, 3),
        "device.distance": round(new, 4),
        "device.panX": round(pan_x, 4),
        "device.panY": round(pan_y, 4),
    }


def _centred(stop: dict, area: list[float], base: dict, aspect: float, device_id: str, pose: dict | None) -> dict:
    """The stop with its pan corrected so the device point under the area's centre lands in the frame's centre.

    camera_framing pans in the plane through the device's middle; a point on the screen sits in front of or behind
    it, which perspective turns into an offset that grows as the camera comes close. With the device known, the point
    is found (the front-most device point under the area's centre in the wide view) and the pan corrected in six
    steps through the renderer's own camera (device_scene.orbit)."""
    import numpy as np

    from .device_assets import asset
    from .device_scene import orbit

    shape = asset(device_id)
    points = shape.points(shape.world(pose))

    def view(values: dict) -> tuple[np.ndarray, np.ndarray]:
        cam = {"yaw": values["yaw"], "pitch": values["pitch"], "distance": values["distance"], "pan": (values["panX"], values["panY"])}
        return orbit(points, aspect, cam)

    def stage(matrix: np.ndarray, p: np.ndarray) -> np.ndarray:
        clip = (matrix @ np.c_[p, np.ones(len(p))].T).T
        return np.c_[(clip[:, 0] / clip[:, 3] + 1) / 2, (1 - clip[:, 1] / clip[:, 3]) / 2]

    matrix, eye = view(base)
    wanted = np.array([(area[0] + area[2]) / 2, (area[1] + area[3]) / 2])
    near = np.linalg.norm(stage(matrix, points) - wanted, axis=1)
    candidates = np.nonzero(near <= max(near.min() * 1.5, 0.004))[0]
    if not len(candidates):
        return stop
    anchor = points[candidates[np.argmin(np.linalg.norm(points[candidates] - eye, axis=1))]][None, :]
    values = {k[len("device.") :]: v for k, v in stop.items()}
    for _ in range(6):
        gx, gy = stage(view(values)[0], anchor)[0]
        values["panX"] -= (gx - 0.5) * 2 * aspect
        values["panY"] += (gy - 0.5) * 2
    return {**stop, "device.panX": round(values["panX"], 4), "device.panY": round(values["panY"], 4)}


def compose_camera(
    duration: float,
    areas: list[list[float]],
    camera: dict,
    aspect: float,
    speed: str = "medium",
    loop: bool = False,
    seed: int | None = None,
    margin: float = 0.08,
    device_id: str | None = None,
    pose: dict | None = None,
) -> dict:
    """A focus move for a device clip, as its camera's keyframes: the same route, each area framed in 3D (centred
    exactly on the device point under it when the device is known)."""
    if not areas:
        raise ValueError("Draw at least one focus area")
    base = {k: float((camera or {}).get(k, v)) for k, v in CAMERA_BASE.items()}
    order = visiting_order(len(areas), seed)
    amplitude = {"fast": 8.0, "medium": 12.0, "slow": 16.0}.get(speed, 12.0)
    sign = -1 if seed and seed % 2 else 1
    stops = [camera_framing(areas[i], aspect, base, margin, sign * amplitude * (1 if k % 2 == 0 else -1)) for k, i in enumerate(order)]
    if device_id:
        stops = [_centred(stop, areas[i], base, aspect, device_id, pose) for stop, i in zip(stops, order, strict=True)]
    wide = {f"device.{k}": v for k, v in base.items()}
    return {"keyframes": route(duration, wide, stops, speed, loop), "order": order}


def merged_keyframes(existing: list[dict], made: list[dict], replaced: tuple = PROPS) -> list[dict]:
    """The clip's keyframes with the move's in place of the replaced properties' keyframes; other properties kept."""
    kept = []
    for key in existing or []:
        props = {p: v for p, v in (key.get("props") or {}).items() if p not in replaced}
        if props:
            kept.append({**key, "props": props})
    return sorted([*kept, *made], key=lambda k: k["t"])


class FocusMotionInput(BaseModel):
    duration: float = Field(gt=0)
    canvas: tuple[float, float]
    picture: tuple[float, float]
    areas: list[list[float]] = Field(min_length=1, max_length=12)
    base: dict = {}
    speed: str = "medium"
    loop: bool = False
    seed: int | None = None
    margin: float = Field(default=0.08, ge=0, le=0.4)
    mode: str = "2d"  # "camera": a device clip's camera, areas in canvas fractions
    camera: dict = {}
    device: str | None = None
    pose: dict = {}


@router.post("")
def plan(body: FocusMotionInput) -> dict:
    """The keyframes for a focus move; the interface applies them as one clip edit, so it undoes in one step."""
    if body.mode == "camera":
        aspect = float(body.canvas[0]) / float(body.canvas[1])
        return compose_camera(
            body.duration, body.areas, body.camera, aspect, body.speed, body.loop, body.seed, body.margin, body.device, body.pose
        )
    return compose(body.duration, body.canvas, body.picture, body.areas, body.base, body.speed, body.loop, body.seed, body.margin)
