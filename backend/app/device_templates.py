"""Device templates: a ready animation for a device clip, written as its device.* keyframes.

One definition here serves the interface (POST /api/devices/template) and agents (formcut_device's template), scaled to
the clip's length and to the device's own ranges (a fold opens to its open angle, a 2-in-1's stand to its rest).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .devices import device as device_info

router = APIRouter(prefix="/api/devices", tags=["devices"])

KINDS = {
    "hero": None,
    "push": None,
    "reveal": ("flip", "fold"),
    "opening": ("laptop", "detachable"),
    "stand": ("detachable",),
}


def available(info: dict) -> list[str]:
    """The templates that fit a device: every one for its kind, in a stable order."""
    return [name for name, kinds in KINDS.items() if kinds is None or info["kind"] in kinds]


def keyframes(template: str, info: dict, duration: float) -> list[dict]:
    """The template's keyframes over a clip of this length (clip-local seconds)."""
    if template not in available(info):
        raise ValueError(f"{info['id']} has no {template} template; it has {', '.join(available(info))}")
    d = max(0.1, float(duration))
    ranges = {a["name"]: a for a in info["articulations"]}
    if template == "hero":
        return [
            {"t": 0.0, "props": {"device.yaw": -35.0, "device.pitch": 10.0, "device.distance": 1.0}, "interp": "smooth"},
            {"t": round(d, 4), "props": {"device.yaw": 35.0, "device.pitch": 10.0, "device.distance": 1.0}, "interp": "smooth"},
        ]
    if template == "push":
        return [
            {"t": 0.0, "props": {"device.distance": 1.25, "device.yaw": 25.0}, "interp": "smooth"},
            {"t": round(d, 4), "props": {"device.distance": 0.7, "device.yaw": 25.0}, "interp": "smooth"},
        ]
    if template == "reveal":
        fold = ranges["fold"]
        return [
            {"t": 0.0, "props": {"device.fold": float(fold["closedDeg"]), "device.yaw": 40.0, "device.pitch": 14.0}, "interp": "smooth"},
            {
                "t": round(d * 0.6, 4),
                "props": {"device.fold": float(fold["openDeg"]), "device.yaw": 22.0, "device.pitch": 10.0},
                "interp": "smooth",
            },
            {
                "t": round(d, 4),
                "props": {"device.fold": float(fold["openDeg"]), "device.yaw": 15.0, "device.pitch": 10.0},
                "interp": "smooth",
            },
        ]
    if template == "opening":
        lid = ranges["lid"]
        opening = [
            {"t": 0.0, "props": {"device.lid": float(lid["closedDeg"]), "device.pitch": 30.0, "device.yaw": 25.0}, "interp": "smooth"},
            {
                "t": round(d * 0.6, 4),
                "props": {"device.lid": float(lid["openDeg"]), "device.pitch": 16.0, "device.yaw": 25.0},
                "interp": "smooth",
            },
            {
                "t": round(d, 4),
                "props": {"device.lid": float(lid["openDeg"]), "device.pitch": 14.0, "device.yaw": 22.0},
                "interp": "smooth",
            },
        ]
        if "stand" in ranges:
            # a 2-in-1 shut with its stand out would hover; its stand opens with the lid
            for key, at in zip(opening, (0.0, 1.0, 1.0), strict=True):
                stand = ranges["stand"]
                key["props"]["device.stand"] = float(stand["closedDeg"] + at * (stand["openDeg"] - stand["closedDeg"]))
        return opening
    stand = ranges["stand"]
    return [
        {"t": 0.0, "props": {"device.stand": float(stand["closedDeg"]), "device.yaw": 205.0, "device.pitch": 12.0}, "interp": "smooth"},
        {
            "t": round(d * 0.5, 4),
            "props": {"device.stand": float(stand["openDeg"]), "device.yaw": 180.0, "device.pitch": 10.0},
            "interp": "smooth",
        },
        {
            "t": round(d, 4),
            "props": {"device.stand": float(stand["openDeg"]), "device.yaw": 155.0, "device.pitch": 10.0},
            "interp": "smooth",
        },
    ]


def touched(made: list[dict]) -> set[str]:
    """The properties a template's keyframes set (the ones it replaces on the clip)."""
    return {prop for key in made for prop in key["props"]}


class TemplateInput(BaseModel):
    device: str
    template: str
    duration: float = Field(gt=0, le=86400)


@router.post("/template")
def template(body: TemplateInput) -> dict:
    """A template's keyframes for a clip of this length; the interface applies them as one keyframe replace."""
    try:
        info = device_info(body.device)
    except KeyError:
        raise HTTPException(404, f"No device {body.device}") from None
    try:
        return {"keyframes": keyframes(body.template, info, body.duration)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
