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
    if effect == "tilt-shift":
        mask = np.clip((np.abs(v - 0.5) - 0.12) * 4, 0, 1)[:, :, None]
        return rgb * (1 - mask) + cv2.GaussianBlur(rgb, (0, 0), radius * 2.5) * mask
    if effect == "spin-blur":
        dx, dy = x - w / 2, y - h / 2
        total = np.zeros_like(rgb)
        for angle in np.linspace(-0.12, 0.12, 7):
            c, s = math.cos(angle), math.sin(angle)
            total += remap(rgb, w / 2 + dx * c - dy * s, h / 2 + dx * s + dy * c)
        return total / 7
    if effect == "lens-blur":
        r = max(1, int(radius * 2))
        disc = np.zeros((2 * r + 1, 2 * r + 1), np.float32)
        cv2.circle(disc, (r, r), r, 1.0, -1)
        small = cv2.resize(np.clip(rgb, 0, 1).astype(np.float32), (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA) ** 2.2
        return cv2.resize(cv2.filter2D(small, -1, disc / disc.sum()) ** (1 / 2.2), (w, h), interpolation=cv2.INTER_LINEAR)
    if effect == "median-soften":
        k = max(5, int(radius * 3.4) | 1)
        return cv2.medianBlur(np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8), k).astype(np.float32) / 255
    if effect == "soft-focus":
        return 1 - (1 - rgb) * (1 - cv2.GaussianBlur(rgb, (0, 0), radius * 4) * 0.55)
    if effect == "diagonal-blur":
        steps = range(-size, size + 1, 2)
        return sum(np.roll(rgb, (k, k), axis=(0, 1)) for k in steps) / len(steps)
    if effect == "ghost-trail":
        return rgb * 0.55 + np.roll(rgb, size, axis=1) * 0.27 + np.roll(rgb, size * 2, axis=1) * 0.18
    if effect == "halftone":
        cell = max(4, size)
        gray = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY)
        small = cv2.resize(gray, (max(1, w // cell), max(1, h // cell)), interpolation=cv2.INTER_AREA)
        level = small[np.minimum(y.astype(int) // cell, small.shape[0] - 1), np.minimum(x.astype(int) // cell, small.shape[1] - 1)]
        cx, cy = np.mod(x, cell) - cell / 2, np.mod(y, cell) - cell / 2
        dots = np.sqrt(cx * cx + cy * cy) < (1 - level) * cell * 0.62
        return np.repeat((~dots).astype(np.float32)[:, :, None], 3, 2)
    if effect == "duotone":
        gray = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY)[:, :, None]
        return np.float32([0.07, 0.09, 0.24]) * (1 - gray) + np.float32([1.0, 0.68, 0.17]) * gray
    if effect == "paint-wash":
        small = cv2.resize(np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8), (max(1, w // 4), max(1, h // 4)), interpolation=cv2.INTER_AREA)
        return cv2.resize(cv2.stylization(small, sigma_s=20, sigma_r=0.4), (w, h), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255
    if effect == "thermal":
        gray = np.round(np.clip(cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY), 0, 1) * 255).astype(np.uint8)
        return cv2.cvtColor(cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    if effect == "night-vision":
        gray = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY)
        noise = np.random.default_rng(int(local * 1000) % (2 ** 32)).normal(0, 0.05, (h, w))
        lum = np.clip(gray * 1.6 + noise, 0, 1) * np.clip(1.25 - ((u - 0.5) ** 2 + (v - 0.5) ** 2) * 2.4, 0, 1)
        return np.stack([lum * 0.25, lum, lum * 0.3], axis=2).astype(np.float32)
    if effect == "ink-outline":
        gray = np.round(np.clip(cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY), 0, 1) * 255).astype(np.uint8)
        lines = cv2.adaptiveThreshold(cv2.medianBlur(gray, 5), 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 5)
        return np.repeat((lines.astype(np.float32) / 255)[:, :, None], 3, 2)
    if effect == "crosshatch":
        gray = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY)
        period = max(4, size // 2)
        ink = ((np.mod(x + y, period) < 1.2) & (gray < 0.75)) | ((np.mod(x - y, period) < 1.2) & (gray < 0.5)) | ((np.mod(x, period) < 1.2) & (gray < 0.28))
        return np.repeat((1 - ink.astype(np.float32) * 0.9)[:, :, None], 3, 2)
    if effect == "swirl":
        dx, dy = x - w / 2, y - h / 2
        turn = 2.2 * np.clip(1 - np.sqrt(dx * dx + dy * dy) / (0.5 * min(w, h)), 0, 1) ** 2
        c, s = np.cos(turn), np.sin(turn)
        return remap(rgb, w / 2 + dx * c - dy * s, h / 2 + dx * s + dy * c)
    if effect == "ripple":
        dx, dy = x - w / 2, y - h / 2
        r = np.sqrt(dx * dx + dy * dy) + 1e-6
        shift = np.sin(r / max(4, size) - local * 6) * size * 0.8
        return remap(rgb, x + dx / r * shift, y + dy / r * shift)
    if effect == "pinch":
        dx, dy = (u - 0.5) * 2, (v - 0.5) * 2
        factor = 1 + 0.5 * (1 - np.clip(dx * dx + dy * dy, 0, 1))
        return remap(rgb, (dx * factor / 2 + 0.5) * w, (dy * factor / 2 + 0.5) * h)
    if effect == "slice-glitch":
        rng = np.random.default_rng(int(local * 8))
        rows = h // 12 + 1
        offsets = rng.integers(-size * 3, size * 3 + 1, rows) * (rng.random(rows) < 0.55)
        shift = np.repeat(offsets, 12)[:h].astype(np.float32)[:, None]
        out = remap(rgb, x + shift, y)
        out[:, :, 0] = remap(rgb, x + shift * 1.4, y)[:, :, 0]
        return out
    if effect == "tile-repeat":
        return remap(rgb, np.mod(x * 2, w), np.mod(y * 2, h))
    if effect == "polar-wrap":
        dx, dy = (u - 0.5) * 2, (v - 0.5) * 2
        r = np.clip(np.sqrt(dx * dx + dy * dy), 0, 1)
        return remap(rgb, (np.arctan2(dy, dx) / (2 * math.pi) + 0.5) * (w - 1), (1 - r) * (h - 1))
    if effect == "heat-haze":
        return remap(rgb, x + np.sin(y / 11 + local * 5) * np.sin(x / 23 + local * 3) * size * 0.6, y + np.cos(x / 13 + local * 4) * size * 0.4)
    if effect == "film-scratches":
        out = rgb * 0.9 + np.float32([0.06, 0.045, 0.02])
        rng = np.random.default_rng(int(local * 12))
        for _ in range(14):
            col, top, bright = int(rng.random() * w), int(rng.random() * h * 0.6), 0.3 + 0.4 * rng.random()
            out[top:, col:col + max(1, w // 320)] += bright
        return out
    if effect == "light-leak":
        cx = 0.12 + 0.1 * math.sin(local * 0.7)
        glow = np.clip(1 - np.sqrt((u - cx) ** 2 + (v - 0.15) ** 2) * 1.5, 0, 1) ** 2
        return 1 - (1 - rgb) * (1 - glow[:, :, None] * np.float32([1.0, 0.45, 0.12]))
    if effect == "aperture-grille":
        phase = np.mod(x, 3)
        mask = np.stack([phase < 1, (phase >= 1) & (phase < 2), phase >= 2], axis=2).astype(np.float32)
        return rgb * (0.55 + 0.6 * mask) * (0.85 + 0.15 * np.cos(y * math.pi))[:, :, None]
    if effect == "paper-texture":
        fibre = cv2.GaussianBlur(np.random.default_rng(1009).random((h, w)).astype(np.float32), (0, 0), 1.2)
        fibre = (fibre - fibre.mean()) / max(1e-6, float(fibre.std()))
        return rgb * (0.9 + 0.035 * fibre)[:, :, None] + np.float32([0.05, 0.035, 0.0])
    if effect == "snowfall":
        out = rgb * 0.88 + 0.07
        rng = np.random.default_rng(907)
        for px, py, rate in rng.random((360, 3)):
            a = int((px + math.sin(local * 1.3 + py * 9) * 0.02) % 1 * w)
            b = int((py + local * (rate * 0.5 + 0.15) * 0.2) % 1 * h)
            cv2.circle(out, (a, b), max(1, int(w / 320 * (1 + 1.5 * rate))), (0.95, 0.97, 1.0), -1)
        return out
    if effect == "bokeh-spots":
        spots = np.zeros_like(rgb)
        rng = np.random.default_rng(433)
        for px, py, s in rng.random((26, 3)):
            cv2.circle(spots, (int(px * w), int((py + local * 0.01) % 1 * h)), max(2, int(w * (0.03 + 0.05 * s))), (0.9, 0.7, 0.35), -1)
        return 1 - (1 - rgb) * (1 - cv2.GaussianBlur(spots, (0, 0), max(1.0, w / 200)) * 0.6)
    if effect == "chroma-noise":
        noise = np.random.default_rng(int(local * 1000) % (2 ** 32)).normal(0, 1, (h, w, 3)).astype(np.float32)
        return rgb + cv2.GaussianBlur(noise, (0, 0), 0.8) * float(params.get("strength", 0.15))
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
