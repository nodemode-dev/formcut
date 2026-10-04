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
    move_w, hold_w, ease = SPEEDS.get(speed, SPEEDS["medium"])
    order = visiting_order(len(areas), seed)
    wide = {p: float(base.get(p, 100 if p == "scale" else 0)) for p in PROPS}
    stops = [framing(areas[i], canvas, picture, base, margin + (0.04 * (k % 3) if seed is not None else 0)) for k, i in enumerate(order)]
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
    return {"keyframes": merged, "order": order}


def merged_keyframes(existing: list[dict], made: list[dict]) -> list[dict]:
    """The clip's keyframes with the move's in place of its scale, posX and posY ones; other properties kept."""
    kept = []
    for key in existing or []:
        props = {p: v for p, v in (key.get("props") or {}).items() if p not in PROPS}
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


@router.post("")
def plan(body: FocusMotionInput) -> dict:
    """The keyframes for a focus move; the interface applies them as one clip edit, so it undoes in one step."""
    return compose(body.duration, body.canvas, body.picture, body.areas, body.base, body.speed, body.loop, body.seed, body.margin)
