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


STILL_CAMERA = {"device.yaw": 0.0, "device.pitch": 0.0, "device.distance": 1.0, "device.panX": 0.0, "device.panY": 0.0, "device.roll": 0.0}


def _move(rx=0.0, ry=0.0, rz=0.0, mx=0.0, my=0.0, mz=0.0) -> dict:
    """A key of the window's own motion before a still, straight-on camera (every key names every value, so each
    eases from the one before): turns in degrees, moves in window sizes (Z toward the camera)."""
    return {
        **STILL_CAMERA,
        "device.rotateX": float(rx),
        "device.rotateY": float(ry),
        "device.rotateZ": float(rz),
        "device.moveX": float(mx),
        "device.moveY": float(my),
        "device.moveZ": float(mz),
    }


# Browser presets, as in Promocut's and UltraMock's browser templates: the window itself moves before a still camera.
# Each is (finish, [(fraction of the clip, motion)]); see _move for the units.
BROWSER = {
    "scan-lr": ("light", [(0, _move(6, -14, 0, 0.45, 0, 0.55)), (1, _move(6, -14, 0, -0.45, 0, 0.55))]),
    "scan-tb": ("light", [(0, _move(12, 0, 0, 0, -0.35, 0.55)), (1, _move(12, 0, 0, 0, 0.35, 0.55))]),
    "low-pan": ("light", [(0, _move(-22, 6, 0, 0, -0.25, 0.2)), (1, _move(-8, 6, 0, 0, 0.05, 0.2))]),
    "zoom-out": ("light", [(0, _move(4, 0, 0, 0, 0, 0.6)), (1, _move(4, 0, 0, 0, 0, 0))]),
    "overhead": ("dark", [(0, _move(58, 0, 0, 0.35, 0, 0.1)), (1, _move(58, 0, 0, -0.35, 0, 0.1))]),
    "out-back": ("light", [(0, _move(6, -12, 0, 0, 0, 0.45)), (0.5, _move(6, -12, 0, 0, 0, -0.25)), (1, _move(6, -12, 0, 0, 0, 0.45))]),
    "hero-reveal": ("dark", [(0, _move(25, 55, 0, 0, 0, -0.2)), (1, _move(8, 14, 0, 0, 0, 0.1))]),
    "orbit": ("light", [(0, _move(8, -32)), (1, _move(8, 32))]),
    "tilt-up": ("light", [(0, _move(45)), (1, _move(6))]),
    "dolly-in": ("dark", [(0, _move(6, 16, 0, 0, 0, -0.25)), (1, _move(6, 16, 0, 0, 0, 0.6))]),
    "dutch": ("dark", [(0, _move(4, 18, -9)), (1, _move(4, 14, 4))]),
    "float": (
        "light",
        [
            (0, _move(4, -6, 0, 0, 0.03)),
            (1 / 3, _move(-2, 6, 0, 0, -0.02)),
            (2 / 3, _move(6, -4, 0, 0, 0.02)),
            (1, _move(2, 6, 0, 0, -0.03)),
        ],
    ),
    "flip-in": ("dark", [(0, _move(4, 88)), (0.6, _move(4, -4)), (1, _move(4, 0))]),
    "corner-focus": ("light", [(0, _move(6, 18)), (1, _move(6, 18, 0, 0.5, -0.32, 0.75))]),
    "side-glide": ("dark", [(0, _move(6, 42, 0, 0.5)), (1, _move(6, 42, 0, -0.5))]),
}
KINDS.update({name: ("browser",) for name in BROWSER})


def available(info: dict) -> list[str]:
    """The templates that fit a device: every one for its kind, in a stable order."""
    return [name for name, kinds in KINDS.items() if kinds is None or info["kind"] in kinds]


def camera_at(template: str, fraction: float) -> dict:
    """A browser preset's camera part-way through, eased between its keys (for its thumbnail)."""
    from itertools import pairwise

    keys = BROWSER[template][1]
    for (t0, a), (t1, b) in pairwise(keys):
        if t0 <= fraction <= t1:
            s = (fraction - t0) / max(t1 - t0, 1e-9)
            s = s * s * (3 - 2 * s)
            return {k: a[k] + (b[k] - a[k]) * s for k in a}
    return dict(keys[-1][1])


def keyframes(template: str, info: dict, duration: float) -> list[dict]:
    """The template's keyframes over a clip of this length (clip-local seconds)."""
    if template not in available(info):
        raise ValueError(f"{info['id']} has no {template} template; it has {', '.join(available(info))}")
    d = max(0.1, float(duration))
    if template in BROWSER:
        return [{"t": round(d * fraction, 4), "props": dict(camera), "interp": "smooth"} for fraction, camera in BROWSER[template][1]]
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
        made = {"keyframes": keyframes(body.template, info, body.duration)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if body.template in BROWSER:
        made["finish"] = BROWSER[body.template][0]
    return made


def sample_page(dark: bool, width: int = 1440, height: int = 900):
    """A made-up landing page for preset thumbnails: a nav bar, a headline, buttons, a picture, three cards."""
    import cv2
    import numpy as np

    bg, ink, soft, card = (
        ((18, 18, 22), (236, 236, 240), (120, 120, 132), (34, 34, 40))
        if dark
        else ((246, 246, 248), (24, 24, 28), (150, 150, 160), (255, 255, 255))
    )
    page = np.full((height, width, 3), bg, np.uint8)
    cv2.rectangle(page, (0, 0), (width, 72), card, -1)
    cv2.rectangle(page, (48, 24), (150, 48), (255, 122, 26), -1)
    for i in range(4):
        cv2.rectangle(page, (width - 520 + i * 110, 32), (width - 450 + i * 110, 40), soft, -1)
    for i, w in enumerate((620, 540)):
        cv2.rectangle(page, (96, 170 + i * 74), (96 + w, 218 + i * 74), ink, -1)
    for i in range(3):
        cv2.rectangle(page, (96, 340 + i * 26), (96 + 520 - i * 90, 352 + i * 26), soft, -1)
    cv2.rectangle(page, (96, 450), (276, 506), (255, 122, 26), -1)
    cv2.rectangle(page, (300, 450), (480, 506), soft, 2)
    ramp = np.linspace(0, 1, 420, dtype=np.float32)[:, None, None]
    picture = (np.array([255, 150, 40]) * (1 - ramp) + np.array([90, 40, 160]) * ramp).astype(np.uint8)
    page[150:570, 800:1344] = np.broadcast_to(picture, (420, 544, 3))
    for i in range(3):
        x = 96 + i * 424
        cv2.rectangle(page, (x, 640), (x + 392, 860), card, -1)
        cv2.rectangle(page, (x + 28, 670), (x + 92, 734), (255, 122, 26) if i == 1 else soft, -1)
        cv2.rectangle(page, (x + 28, 760), (x + 300, 776), ink, -1)
        cv2.rectangle(page, (x + 28, 796), (x + 340, 806), soft, -1)
    return page


_thumb_lock = __import__("threading").Lock()


@router.get("/{device_id}/templates/{name}/thumbnail")
def template_thumbnail(device_id: str, name: str):
    """A browser preset's picture for the Browser tab: the window at its mid-move pose showing a sample page."""
    from fastapi.responses import FileResponse

    if name not in BROWSER:
        raise HTTPException(404, f"No browser preset {name}")
    try:
        info = device_info(device_id)
    except KeyError:
        raise HTTPException(404, f"No device {device_id}") from None
    import cv2

    from .device_render import render
    from .paths import DATA_DIR

    finish = BROWSER[name][0]
    path = DATA_DIR / "device-thumbnails" / f"{device_id}-{name}-{finish}-v1.png"
    with _thumb_lock:
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            at = camera_at(name, 0.5)
            moving = ("rotateX", "rotateY", "rotateZ", "moveX", "moveY", "moveZ")
            motion = {name: at[f"device.{name}"] for name in moving}
            screen = sample_page(finish == "dark")
            picture = render(
                info["id"], 480, 300, finish=finish, camera={"yaw": 0, "pitch": 0}, screens={"inner": screen}, lighting="photo", motion=motion
            )
            cv2.imwrite(str(path), cv2.cvtColor(picture, cv2.COLOR_RGBA2BGRA))
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "max-age=86400"})
