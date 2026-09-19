import bisect
import math


def curve_points(clip: dict) -> list[tuple[float, float]]:
    points = {}
    for p in clip.get("speedCurve") or []:
        t, speed = float(p["t"]), float(p["speed"])
        if not math.isfinite(t) or not math.isfinite(speed):
            raise ValueError("Speed points must be finite")
        points[max(0.0, t)] = max(0.05, min(16.0, speed))
    return sorted(points.items()) or [(0.0, float(clip.get("speed") or 1.0))]


def speed_at(clip: dict, local: float) -> float:
    points = curve_points(clip)
    i = bisect.bisect_right([p[0] for p in points], local)
    if i == 0:
        return points[0][1]
    if i == len(points):
        return points[-1][1]
    a, b = points[i - 1], points[i]
    return a[1] + (b[1] - a[1]) * (local - a[0]) / (b[0] - a[0])


def source_delta(clip: dict, local: float) -> float:
    if local <= 0:
        return local * speed_at(clip, 0)
    breaks = [0.0] + [p[0] for p in curve_points(clip) if 0 < p[0] < local] + [local]
    return sum((b - a) * (speed_at(clip, a) + speed_at(clip, b)) / 2 for a, b in zip(breaks, breaks[1:]))


def source_time(clip: dict, local: float) -> float:
    return max(0.0, float(clip.get("sourceIn") or 0) + source_delta(clip, local))


def timeline_time(clip: dict, source: float) -> float:
    low, high = 0.0, float(clip["duration"])
    for _ in range(48):
        mid = (low + high) / 2
        if source_time(clip, mid) < source:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def ease(p: float, mode: str) -> float:
    p = max(0.0, min(1.0, p))
    if mode == "hold":
        return 0.0
    if mode == "easeIn":
        return p * p
    if mode == "easeOut":
        return 1 - (1 - p) ** 2
    if mode == "ease":
        return p * p * (3 - 2 * p)
    return p


def property_at(clip: dict, prop: str, local: float, default: float) -> float:
    points = sorted((k for k in clip.get("keyframes", []) if prop in k.get("props", {})), key=lambda k: k["t"])
    if not points:
        return default
    if local <= points[0]["t"]:
        return points[0]["props"][prop]
    for a, b in zip(points, points[1:]):
        if local < b["t"]:
            p = ease((local - a["t"]) / max(1e-9, b["t"] - a["t"]), a.get("interp", "linear"))
            return a["props"][prop] + (b["props"][prop] - a["props"][prop]) * p
    return points[-1]["props"][prop]


def fade_at(clip: dict, local: float) -> float:
    result = 1.0
    duration = float(clip["duration"])
    for key in ("fadeIn", "rampIn"):
        value = float(clip.get(key) or 0)
        if value > 0:
            result = min(result, local / value)
    for key in ("fadeOut", "rampOut"):
        value = float(clip.get(key) or 0)
        if value > 0:
            result = min(result, (duration - local) / value)
    extend = float(clip.get("extendOut") or 0)
    if extend and local > duration:
        result = min(result, 1 - (local - duration) / extend)
    return max(0.0, min(1.0, result))


def keyed_value(points, local: float, default: float) -> float:
    """Sample a list of {t, value, interp} points, the same easing as transform keys."""
    usable = sorted((p for p in (points or []) if isinstance(p, dict) and "t" in p and "value" in p), key=lambda p: p["t"])
    if not usable:
        return default
    if local <= usable[0]["t"]:
        return float(usable[0]["value"])
    for a, b in zip(usable, usable[1:]):
        if local < b["t"]:
            p = ease((local - a["t"]) / max(1e-9, b["t"] - a["t"]), a.get("interp", "linear"))
            return float(a["value"]) + (float(b["value"]) - float(a["value"])) * p
    return float(usable[-1]["value"])


def effect_params_at(entry: dict, local: float) -> dict:
    """K3: an effect entry's parameters at a clip-local time.

    `entry["keys"]` maps a parameter name to its points; a parameter without
    points keeps its static value, so an unkeyed effect costs nothing.
    """
    params = dict(entry.get("params") or {})
    for name, points in (entry.get("keys") or {}).items():
        params[name] = keyed_value(points, local, float(params.get(name, 0)))
    return params


def volume_at(clip: dict, local: float) -> float:
    """K4: the clip's volume at a local time, keyed or static."""
    return keyed_value(clip.get("volumeKeys"), local, float(clip.get("volume", 1)))


# K6: animation slots. A clip may carry an In, an Out and a Combo animation by
# name; they layer on top of transform keys and are expressed as multipliers and
# offsets, so trimming a clip rescales them instead of baking new keyframes.
IN_PRESETS = ("fade", "zoom-in", "zoom-out", "slide-up", "slide-down", "slide-left", "slide-right", "spin", "pop")
COMBO_PRESETS = ("pulse", "shake", "sway", "float", "bounce", "drift", "swing")


def _in_shape(preset: str, p: float) -> dict:
    """Progress 0 at the clip edge, 1 when the animation has finished."""
    eased = ease(p, "ease")
    if preset == "fade":
        return {"opacity": eased}
    if preset == "zoom-in":
        return {"scale": 0.6 + 0.4 * eased, "opacity": eased}
    if preset == "zoom-out":
        return {"scale": 1.6 - 0.6 * eased, "opacity": eased}
    if preset == "slide-up":
        return {"posY": (1 - eased) * 40, "opacity": eased}
    if preset == "slide-down":
        return {"posY": -(1 - eased) * 40, "opacity": eased}
    if preset == "slide-left":
        return {"posX": (1 - eased) * 40, "opacity": eased}
    if preset == "slide-right":
        return {"posX": -(1 - eased) * 40, "opacity": eased}
    if preset == "spin":
        return {"rotation": (1 - eased) * -180, "opacity": eased}
    if preset == "pop":
        overshoot = 1.15 if p < 0.7 else 1.0
        return {"scale": (0.4 + 0.6 * eased) * overshoot, "opacity": eased}
    return {}


def _combo_shape(preset: str, local: float, duration: float) -> dict:
    cycles = max(1.0, duration)
    phase = 2 * math.pi * local
    if preset == "pulse":
        return {"scale": 1 + 0.05 * math.sin(phase * 1.5)}
    if preset == "shake":
        return {"posX": 0.8 * math.sin(phase * 9), "posY": 0.6 * math.cos(phase * 11)}
    if preset == "sway":
        return {"rotation": 2.5 * math.sin(phase * 0.7)}
    if preset == "float":
        return {"posY": 1.6 * math.sin(phase * 0.6)}
    if preset == "bounce":
        return {"posY": -abs(2.5 * math.sin(phase * 1.2))}
    if preset == "drift":
        return {"posX": 2.0 * math.sin(phase * 0.35), "posY": 1.2 * math.cos(phase * 0.28)}
    if preset == "swing":
        return {"rotation": 4.0 * math.sin(phase * 1.1), "posX": 1.2 * math.sin(phase * 1.1)}
    return {}


def animation_at(clip: dict, local: float) -> dict:
    """Multipliers and offsets from the clip's animation slots at a local time.

    Returned as {"scale": m, "opacity": m, "posX": dx, "posY": dy, "rotation": d}
    with neutral values when no slot applies. Durations clamp to the clip, so a
    trimmed clip keeps an In that still completes.
    """
    out = {"scale": 1.0, "opacity": 1.0, "posX": 0.0, "posY": 0.0, "rotation": 0.0}
    animations = clip.get("animations") or {}
    duration = float(clip.get("duration", 0)) or 1e-9

    def merge(shape: dict) -> None:
        for key, value in shape.items():
            if key in ("scale", "opacity"):
                out[key] *= value
            else:
                out[key] += value

    entry = animations.get("in")
    if entry and entry.get("preset") in IN_PRESETS:
        length = min(float(entry.get("seconds", 1)), duration)
        if length > 0 and local < length:
            merge(_in_shape(entry["preset"], local / length))
    entry = animations.get("out")
    if entry and entry.get("preset") in IN_PRESETS:
        length = min(float(entry.get("seconds", 1)), duration)
        if length > 0 and local > duration - length:
            merge(_in_shape(entry["preset"], (duration - local) / length))
    entry = animations.get("combo")
    if entry and entry.get("preset") in COMBO_PRESETS:
        merge(_combo_shape(entry["preset"], local, duration))
    return out
