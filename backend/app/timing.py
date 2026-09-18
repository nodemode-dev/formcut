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
