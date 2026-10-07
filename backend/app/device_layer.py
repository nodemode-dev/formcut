"""A device clip: a device from the library as a layer, its screens showing other media or timelines.

The clip's `device` block holds the device id and finish, what each screen shows (`screens.inner`, `screens.cover`:
a media id or a timeline id, a time offset, a fit), the pose (lid, fold, stand in degrees), the camera, the backlight,
the light and shadow. Every number is keyframable through the clip's ordinary keyframes as `device.<name>`, sampled
with the same property_at every other clip property uses. The picture is the 3D pass at the canvas size, transparent
around the device, so it composites, masks, grades and transitions like any layer.
"""

import cv2
import numpy as np

from .devices import device as device_info
from .timing import property_at

# keyframable values: name -> (block in the device settings or None for the top level, key, default)
VALUES = {
    "yaw": ("camera", "yaw", 25.0),
    "pitch": ("camera", "pitch", 12.0),
    "distance": ("camera", "distance", 1.0),
    "fov": ("camera", "fov", 30.0),
    "roll": ("camera", "roll", 0.0),
    "panX": ("camera", "panX", 0.0),
    "panY": ("camera", "panY", 0.0),
    "lid": ("pose", "lid", None),
    "fold": ("pose", "fold", None),
    "stand": ("pose", "stand", None),
    "backlight": (None, "backlight", 0.6),
    "exposure": (None, "exposure", 1.0),
    "light": (None, "light", 0.0),
    "shadow": (None, "shadow", 0.6),
    "screenBrightness": (None, "screenBrightness", 1.0),
    # depth of field: strength (0 off) and focus (device sizes nearer, negative, or farther than the device's centre)
    "dof": (None, "dof", 0.0),
    "focus": (None, "focus", 0.0),
    # the device itself moving before a still camera (degrees; moves in fractions of the device's size, Z toward the
    # camera): the browser presets, a floating device
    "rotateX": ("motion", "rotateX", 0.0),
    "rotateY": ("motion", "rotateY", 0.0),
    "rotateZ": ("motion", "rotateZ", 0.0),
    "moveX": ("motion", "moveX", 0.0),
    "moveY": ("motion", "moveY", 0.0),
    "moveZ": ("motion", "moveZ", 0.0),
}
FITS = ("cover", "contain")


def normalised(block: dict) -> dict:
    """A device block checked against the library: a known device, one of its finishes, poses in range, sources named
    once, fits known. Raises ValueError with what is wrong."""
    if not isinstance(block, dict) or not block.get("id"):
        raise ValueError("A device clip needs device.id (see formcut_devices for the library)")
    try:
        info = device_info(str(block["id"]))
    except KeyError:
        raise ValueError(f"Unknown device {block['id']}") from None
    out = {
        k: v
        for k, v in block.items()
        if k in ("id", "finish", "screens", "pose", "camera", "motion", "fit", "lighting", *[v[1] for v in VALUES.values() if v[0] is None])
    }
    from .device_scene import LIGHTS

    if out.get("lighting", "studio") not in LIGHTS:
        raise ValueError(f"lighting is {' or '.join(LIGHTS)}, not {out['lighting']}")
    finish = out.get("finish") or info["finish"]
    if finish not in info["finishes"]:
        raise ValueError(f"{info['id']} has no finish {finish}; it has {', '.join(sorted(info['finishes']))}")
    out["finish"] = finish
    ranges = {a["name"]: (a["closedDeg"], a["maxDeg"]) for a in info["articulations"]}
    pose = dict(out.get("pose") or {})
    for name, value in pose.items():
        if name not in ranges:
            raise ValueError(f"{info['id']} has no {name} to pose; it has {', '.join(ranges) or 'nothing that moves'}")
        low, high = ranges[name]
        if not low <= float(value) <= high:
            raise ValueError(f"{info['id']} {name} must be {low} to {high} degrees")
    out["pose"] = pose
    slots = {s["slot"] for s in info["screens"]}
    screens = {}
    for slot, source in (out.get("screens") or {}).items():
        if slot not in slots:
            raise ValueError(f"{info['id']} has no {slot} screen; it has {', '.join(sorted(slots))}")
        if source is None:
            continue
        if bool(source.get("mediaId")) == bool(source.get("timelineId")):
            raise ValueError(f"The {slot} screen shows either a mediaId or a timelineId")
        fit = source.get("fit", "cover")
        if fit not in FITS:
            raise ValueError(f"fit is cover or contain, not {fit}")
        screens[slot] = {**source, "fit": fit, "offset": float(source.get("offset", 0.0))}
    out["screens"] = screens
    out["camera"] = dict(out.get("camera") or {})
    return out


def settings_at(clip: dict, local: float) -> dict:
    """The device block's values at a moment of the clip, keyframes applied."""
    block = clip.get("device") or {}
    out = {"camera": dict(block.get("camera") or {}), "pose": dict(block.get("pose") or {}), "motion": dict(block.get("motion") or {})}
    for name, (group, key, default) in VALUES.items():
        base = (block.get(group) or {}).get(key, default) if group else block.get(key, default)
        value = property_at(clip, f"device.{name}", local, base)
        if value is None:
            continue
        if group:
            out[group][key] = float(value)
        else:
            out[key] = float(value)
    return out


def _fitted(rgb: np.ndarray, size: tuple[int, int], fit: str) -> np.ndarray:
    w, h = size
    sh, sw = rgb.shape[:2]
    if fit == "cover":
        scale = max(w / sw, h / sh)
        cw, ch = min(sw, round(w / scale)), min(sh, round(h / scale))
        x0, y0 = (sw - cw) // 2, (sh - ch) // 2
        return cv2.resize(rgb[y0 : y0 + ch, x0 : x0 + cw], (w, h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    scale = min(w / sw, h / sh)
    fw, fh = max(1, round(sw * scale)), max(1, round(sh * scale))
    out = np.zeros((h, w, 3), np.uint8)
    x0, y0 = (w - fw) // 2, (h - fh) // 2
    out[y0 : y0 + fh, x0 : x0 + fw] = cv2.resize(rgb, (fw, fh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    return out


def _rgb_bytes(picture: np.ndarray) -> np.ndarray:
    if picture.dtype == np.uint16:
        picture = (picture >> 8).astype(np.uint8)
    return np.ascontiguousarray(picture[:, :, :3])


def screen_picture(renderer, clip: dict, slot: str, source: dict, local: float, size: tuple[int, int]) -> np.ndarray | None:
    """What a screen shows at a moment, fitted to the screen's pixels; None when the source cannot be read."""
    at = max(0.0, local + float(source.get("offset", 0.0)))
    if source.get("timelineId"):
        frame = renderer.nested_frame({"timelineId": source["timelineId"]}, at)
        if frame is None:
            return None
        picture = renderer.as_working(frame)
    else:
        from .media import _find

        try:
            record = _find(str(source["mediaId"]))
        except (KeyError, ValueError, OSError):
            return None
        stand_in = {
            "id": f"{clip['id']}#{slot}",
            "kind": record.get("kind", "video"),
            "mediaId": source["mediaId"],
            "label": record.get("name", ""),
        }
        picture = renderer.as_working(renderer.media_frame(stand_in, 0.0 if stand_in["kind"] == "image" else at))
    return _fitted(_rgb_bytes(picture), size, source.get("fit", "cover"))


def picture(renderer, clip: dict, local: float) -> np.ndarray:
    """The device clip's layer: RGBA bytes at the canvas size, transparent around the device."""
    from .device_render import render

    block = clip.get("device") or {}
    info = device_info(str(block["id"]))
    values = settings_at(clip, local)
    longest = max(renderer.width, renderer.height)
    screens = {}
    for slot, source in (block.get("screens") or {}).items():
        spec = next((s for s in info["screens"] if s["slot"] == slot), None)
        if spec is None or not source:
            continue
        pw, ph = spec["pixels"]
        shrink = min(1.0, longest / max(pw, ph))
        size = (max(16, round(pw * shrink)), max(16, round(ph * shrink)))
        shown = screen_picture(renderer, clip, slot, source, local, size)
        if shown is not None:
            screens[slot] = shown
    camera = values["camera"]
    camera["pan"] = (camera.pop("panX", 0.0), camera.pop("panY", 0.0))
    return render(
        info["id"],
        renderer.width,
        renderer.height,
        finish=block.get("finish"),
        pose=values["pose"],
        camera=camera,
        motion=values["motion"],
        dof=values.get("dof", 0.0),
        focus=values.get("focus", 0.0),
        screens=screens,
        backlight=values.get("backlight", 0.6),
        screen_brightness=values.get("screenBrightness", 1.0),
        exposure=values.get("exposure", 1.0),
        shadow=values.get("shadow", 0.6),
        light_rotation=values.get("light", 0.0),
        lighting=str(block.get("lighting") or "studio"),
    )
