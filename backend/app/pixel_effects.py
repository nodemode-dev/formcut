import math

import cv2
import numpy as np

from .catalogue import GRADES, VIDEO_EFFECTS


def grade(rgb: np.ndarray, params: dict) -> np.ndarray:
    out = rgb.copy()
    out *= 2 ** float(params.get("exposure", 0))
    out = (out - 0.5) * params.get("contrast", 1) + 0.5 + params.get("lift", 0)
    out = np.maximum(out, 0) ** params.get("gamma", 1)
    luminance = np.sum(out * [0.2126, 0.7152, 0.0722], axis=2, keepdims=True)
    saturation = params.get("saturation", 1)
    vibrance = params.get("vibrance", 0)
    out = luminance + (out - luminance) * (saturation + vibrance * (1 - np.ptp(np.clip(out, 0, 1), axis=2, keepdims=True)))
    out += np.array([params.get("temperature", 0), -params.get("tint", 0), -params.get("temperature", 0)]) * 0.35
    for i, channel in enumerate("rgb"):
        out[:, :, i] += params.get("shadows_" + channel, 0) * (1 - luminance[:, :, 0]) ** 2
        out[:, :, i] += params.get("highlights_" + channel, 0) * luminance[:, :, 0] ** 2
    if params.get("sepia"):
        sepia = out @ np.array([[0.393, 0.349, 0.272], [0.769, 0.686, 0.534], [0.189, 0.168, 0.131]])
        out = out * (1 - params["sepia"]) + sepia * params["sepia"]
    return out


def remap(rgb: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return cv2.remap(rgb, x.astype(np.float32), y.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def process(rgb: np.ndarray, effect: str, local: float, params: dict) -> np.ndarray:
    if effect in GRADES:
        return grade(rgb, {**GRADES[effect], **params})
    h, w = rgb.shape[:2]
    y, x = np.mgrid[:h, :w].astype(np.float32)
    u, v = (x + 0.5) / w, (y + 0.5) / h
    radius = max(0.1, min(100, float(params.get("radius", 3))))
    size = max(1, int(params.get("size", 12)))
    if effect == "gaussian":
        return cv2.GaussianBlur(rgb, (0, 0), radius)
    if effect == "box":
        return cv2.blur(rgb, (size, size))
    if effect == "directional-blur":
        kernel = np.zeros((size | 1, size | 1), np.float32)
        kernel[len(kernel) // 2, :] = 1 / len(kernel)
        return cv2.filter2D(rgb, -1, kernel)
    if effect == "radial-blur":
        return sum(remap(rgb, (x - w / 2) * s + w / 2, (y - h / 2) * s + h / 2) for s in np.linspace(0.9, 1.1, 9)) / 9
    if effect == "sharpen":
        return rgb * 2 - cv2.GaussianBlur(rgb, (0, 0), radius)
    if effect == "edge":
        return np.repeat((cv2.Canny((rgb * 255).astype(np.uint8), 70, 150) / 255)[:, :, None], 3, 2)
    if effect == "emboss":
        return cv2.filter2D(rgb, -1, np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]], np.float32)) + 0.5
    if effect == "invert":
        return 1 - rgb
    if effect == "posterize":
        levels = max(2, min(32, int(params.get("levels", 5))))
        return np.round(rgb * (levels - 1)) / (levels - 1)
    if effect == "threshold":
        return np.repeat((rgb.mean(2) > params.get("threshold", 0.5))[:, :, None], 3, 2).astype(np.float32)
    if effect == "solarize":
        return np.where(rgb > params.get("threshold", 0.5), 1 - rgb, rgb)
    if effect == "pixelate":
        small = cv2.resize(rgb, (max(1, w // size), max(1, h // size)), interpolation=cv2.INTER_AREA)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    if effect == "vignette":
        f = np.clip(1 - ((u - 0.5) ** 2 + (v - 0.5) ** 2) * 2.2, 0, 1)
        return rgb * f[:, :, None]
    if effect == "grain":
        rng = np.random.default_rng(int(local * 1000) % (2 ** 32))
        return rgb + rng.normal(0, params.get("strength", 0.07), (h, w, 1))
    if effect == "glow":
        return rgb + cv2.GaussianBlur(np.maximum(rgb - 0.45, 0), (0, 0), radius * 3)
    if effect == "chromatic":
        out = rgb.copy()
        out[:, :, 0] = np.roll(rgb[:, :, 0], size, axis=1)
        out[:, :, 2] = np.roll(rgb[:, :, 2], -size, axis=1)
        return out
    if effect == "fisheye":
        dx, dy = (u - 0.5) * 2, (v - 0.5) * 2
        r = np.sqrt(dx * dx + dy * dy)
        factor = 1 + 0.45 * r * r
        return remap(rgb, (dx / factor / 2 + 0.5) * w, (dy / factor / 2 + 0.5) * h)
    if effect == "wave":
        return remap(rgb, x + np.sin(v * 30 + local * 4) * size, y)
    if effect == "mirror":
        return remap(rgb, np.abs(u - 0.5) * 2 * (w - 1), y)
    if effect == "kaleidoscope":
        dx, dy = x - w / 2, y - h / 2
        r = np.sqrt(dx * dx + dy * dy)
        angle = np.abs(np.mod(np.arctan2(dy, dx), math.pi / 3) - math.pi / 6)
        return remap(rgb, w / 2 + r * np.cos(angle), h / 2 + r * np.sin(angle))
    if effect == "scanlines":
        return rgb * (0.75 + 0.25 * np.cos(y * math.pi))[:, :, None]
    if effect == "interference":
        return remap(rgb, x + np.sin(y / 9 + local * 15) * (np.sin(local * 12) ** 8) * size * 2, y)
    if effect == "cartoon":
        smooth = cv2.bilateralFilter(rgb.astype(np.float32), 7, 0.2, 5)
        edges = cv2.Canny((rgb * 255).astype(np.uint8), 80, 140) < 128
        return np.round(smooth * 5) / 5 * edges[:, :, None]
    if effect == "pencil":
        gray = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY)
        inv = cv2.GaussianBlur(1 - gray, (0, 0), radius)
        return np.repeat(np.minimum(1, gray / np.maximum(0.001, 1 - inv))[:, :, None], 3, 2)
    if effect in ("rain", "dust"):
        out = rgb.copy()
        rng = np.random.default_rng(712)
        for px, py, rate in rng.random((80, 3)):
            a = int((px + (local * 0.02 if effect == "rain" else 0)) % 1 * w)
            b = int((py + local * (rate + 0.2) * 0.25) % 1 * h)
            if effect == "rain":
                cv2.line(out, (a, b), (a - 3, b + max(4, h // 50)), (0.7, 0.8, 0.9), 1)
            else:
                cv2.circle(out, (a, b), max(1, w // 400), (0.8, 0.75, 0.6), -1)
        return out
    if effect == "camera-shake":
        return remap(rgb, x + math.sin(local * 27) * size / 2, y + math.sin(local * 19) * size / 2)
    raise ValueError(f"Unknown visual effect: {effect}")


def apply_effects(image: np.ndarray, effects: list[dict], local: float) -> np.ndarray:
    result = image.astype(np.float32) / 255
    for entry in effects:
        amount = max(0.0, min(1.0, float(entry.get("amount", 1))))
        if entry["id"] not in GRADES and entry["id"] not in VIDEO_EFFECTS:
            raise ValueError("Unknown visual effect: " + entry["id"])
        changed = process(result[:, :, :3], entry["id"], local, entry.get("params") or {})
        result[:, :, :3] = np.clip(result[:, :, :3] * (1 - amount) + changed * amount, 0, 1)
    return np.round(result * 255).astype(np.uint8)
