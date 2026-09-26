import functools
import math

import cv2
import numpy as np

from .catalogue import EFFECT_DEFAULTS, GRADES, VIDEO_EFFECTS, clamp_params


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


@functools.lru_cache(maxsize=4)
def _grid(h: int, w: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Pixel coordinates and their 0..1 centres for one frame size.

    They depend on the size alone, yet were rebuilt for every effect on every
    frame, whether the effect used them or not: 9 to 18 ms a frame at 1280x720.
    Computed once, exactly as before, and read-only, so an effect that tried to
    change them in place would fail instead of corrupting later frames.
    """
    y, x = np.mgrid[:h, :w].astype(np.float32)
    u, v = (x + 0.5) / w, (y + 0.5) / h
    for array in (y, x, u, v):
        array.flags.writeable = False
    return y, x, u, v


@functools.lru_cache(maxsize=4)
def _vignette_falloff(h: int, w: int) -> np.ndarray:
    """The vignette's falloff, which depends only on the frame size."""
    _, _, u, v = _grid(h, w)
    falloff = np.clip(1 - ((u - 0.5) ** 2 + (v - 0.5) ** 2) * 2.2, 0, 1)[:, :, None]
    falloff.flags.writeable = False
    return falloff


@functools.lru_cache(maxsize=4)
def _glass_cells(h: int, w: int, cell: int) -> tuple[np.ndarray, np.ndarray]:
    """Stained glass panes for one frame size: each pixel's nearest seed, and the lead between panes."""
    rng = np.random.default_rng(cell)
    seeds = np.ones((h, w), np.uint8)
    for top in range(0, h, cell):
        for left in range(0, w, cell):
            seeds[min(h - 1, top + int(rng.integers(0, cell))), min(w - 1, left + int(rng.integers(0, cell)))] = 0
    _, labels = cv2.distanceTransformWithLabels(seeds, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    edges = np.zeros((h, w), np.uint8)
    edges[:, :-1] |= (labels[:, :-1] != labels[:, 1:]).astype(np.uint8)
    edges[:-1, :] |= (labels[:-1, :] != labels[1:, :]).astype(np.uint8)
    leading = cv2.dilate(edges, np.ones((max(1, cell // 12) * 2 + 1,) * 2, np.uint8)) > 0
    labels.flags.writeable = False
    leading.flags.writeable = False
    return labels, leading


@functools.lru_cache(maxsize=4)
def _fog_field(h: int, w: int) -> np.ndarray:
    """Soft fog density at three scales, twice the frame wide so it can drift."""
    rng = np.random.default_rng(5)
    field = np.zeros((h, w * 2), np.float32)
    for scale, weight in ((16, 0.55), (48, 0.3), (128, 0.15)):
        coarse = rng.random((max(2, h * scale // w // 4 + 2), max(2, scale // 2 + 2))).astype(np.float32)
        field += cv2.resize(coarse, (w * 2, h), interpolation=cv2.INTER_CUBIC) * weight
    field = (field - field.min()) / max(1e-6, float(field.max() - field.min()))
    field.flags.writeable = False
    return field


REMAP_EFFECTS = ("fisheye", "wave", "kaleidoscope", "swirl", "ripple", "pinch", "tile-repeat", "polar-wrap", "heat-haze", "interference")


def remap_maps(effect: str, h: int, w: int, local: float, params: dict) -> tuple[np.ndarray, np.ndarray] | None:
    """The sample coordinates a remap effect reads the picture at, the formulas process() uses, for the device pass (R10)."""
    y, x, u, v = _grid(h, w)
    size = max(1, int(params.get("size", 12)))
    if effect == "fisheye":
        dx, dy = (u - 0.5) * 2, (v - 0.5) * 2
        r = np.sqrt(dx * dx + dy * dy)
        factor = 1 + 0.45 * float(params.get("intensity", 1)) * r * r
        return (dx / factor / 2 + 0.5) * w, (dy / factor / 2 + 0.5) * h
    if effect == "wave":
        return x + np.sin(v * 30 + local * 4) * size, y
    if effect == "kaleidoscope":
        dx, dy = x - w / 2, y - h / 2
        r = np.sqrt(dx * dx + dy * dy)
        wedge = 2 * math.pi / max(2, int(params.get("segments", 6)))
        angle = np.abs(np.mod(np.arctan2(dy, dx), wedge) - wedge / 2)
        return w / 2 + r * np.cos(angle), h / 2 + r * np.sin(angle)
    if effect == "swirl":
        dx, dy = x - w / 2, y - h / 2
        turn = float(params.get("twist", 2.2)) * np.clip(1 - np.sqrt(dx * dx + dy * dy) / (0.5 * min(w, h)), 0, 1) ** 2
        c, s = np.cos(turn), np.sin(turn)
        return w / 2 + dx * c - dy * s, h / 2 + dx * s + dy * c
    if effect == "ripple":
        dx, dy = x - w / 2, y - h / 2
        r = np.sqrt(dx * dx + dy * dy) + 1e-6
        shift = np.sin(r / max(4, size) - local * 6) * size * 0.8
        return x + dx / r * shift, y + dy / r * shift
    if effect == "pinch":
        dx, dy = (u - 0.5) * 2, (v - 0.5) * 2
        factor = 1 + 0.5 * float(params.get("intensity", 1)) * (1 - np.clip(dx * dx + dy * dy, 0, 1))
        return (dx * factor / 2 + 0.5) * w, (dy * factor / 2 + 0.5) * h
    if effect == "tile-repeat":
        tiles = max(1, int(params.get("tiles", 2)))
        return np.mod(x * tiles, w), np.mod(y * tiles, h)
    if effect == "polar-wrap":
        dx, dy = (u - 0.5) * 2, (v - 0.5) * 2
        r = np.clip(np.sqrt(dx * dx + dy * dy), 0, 1)
        return (np.arctan2(dy, dx) / (2 * math.pi) + 0.5) * (w - 1), (1 - r) * (h - 1)
    if effect == "heat-haze":
        return x + np.sin(y / 11 + local * 5) * np.sin(x / 23 + local * 3) * size * 0.6, y + np.cos(x / 13 + local * 4) * size * 0.4
    if effect == "interference":
        return x + np.sin(y / 9 + local * 15) * (np.sin(local * 12) ** 8) * size * 2, y
    if effect == "hex-pixelate":
        s, root = float(size), math.sqrt(3.0)
        q, r = (root / 3 * x - y / 3) / s, (2 / 3 * y) / s
        cube = np.stack([q, -q - r, r])
        rounded = np.round(cube)
        diff = np.abs(rounded - cube)
        rounded[0] = np.where((diff[0] > diff[1]) & (diff[0] > diff[2]), -rounded[1] - rounded[2], rounded[0])
        rounded[2] = np.where(~((diff[0] > diff[1]) & (diff[0] > diff[2])) & ~(diff[1] > diff[2]), -rounded[0] - rounded[1], rounded[2])
        return (s * root * (rounded[0] + rounded[2] / 2)).astype(np.float32), (s * 1.5 * rounded[2]).astype(np.float32)
    return None


FIELD_EFFECTS = (
    "light-leak",
    "lens-flare",
    "aperture-grille",
    "paper-texture",
    "chroma-noise",
    "film-scratches",
    "bokeh-spots",
    "sparkles",
    "snowfall",
)


def field_for(effect: str, h: int, w: int, local: float, params: dict) -> tuple[np.ndarray, np.ndarray, int] | None:
    """For an effect that combines the picture with a field the picture does not feed (R12): the multiply
    field, the add field and the mode, 1 for rgb * mul + add and 2 for a screen with add, from the formulas
    process() uses, so the device pass (FIELD_CODE) and the reference agree."""
    y, x, u, v = _grid(h, w)
    ones = np.ones((h, w, 3), np.float32)
    if effect == "light-leak":
        cx = 0.12 + 0.1 * math.sin(local * 0.7)
        glow = np.clip(1 - np.sqrt((u - cx) ** 2 + (v - 0.15) ** 2) * 1.5, 0, 1) ** 2
        glow = np.clip(glow * float(params.get("intensity", 1)), 0, 1)
        return ones, (glow[:, :, None] * np.float32([1.0, 0.45, 0.12])).astype(np.float32), 2
    if effect == "lens-flare":
        px, py = float(params.get("x", 0.72)) * w, float(params.get("y", 0.22)) * h
        distance = np.hypot(x - px, y - py)
        light = np.exp(-((distance / (w * 0.03)) ** 2)) + np.exp(-((distance / (w * 0.15)) ** 2)) * 0.35
        streak = np.exp(-(((y - py) / max(1.0, h * 0.004)) ** 2)) * np.exp(-np.abs(x - px) / (w * 0.35)) * 0.6
        flare = (light + streak)[:, :, None] * np.array([1.0, 0.9, 0.7], np.float32)
        for step, radius, tint in ((1.4, 0.05, (0.5, 0.8, 1.0)), (1.8, 0.03, (1.0, 0.6, 0.9)), (2.3, 0.08, (0.6, 1.0, 0.7))):
            gx, gy = px + (w / 2 - px) * step, py + (h / 2 - py) * step
            ghost = np.exp(-((np.hypot(x - gx, y - gy) / (w * radius)) ** 4)) * 0.15
            flare = flare + ghost[:, :, None] * np.array(tint, np.float32)
        flare = flare * (0.92 + 0.08 * math.sin(local * 7)) * float(params.get("intensity", 1))
        return ones, np.clip(flare, 0, 1).astype(np.float32), 2
    if effect == "aperture-grille":
        phase = np.mod(x, 3)
        mask = np.stack([phase < 1, (phase >= 1) & (phase < 2), phase >= 2], axis=2).astype(np.float32)
        grille = (0.55 + 0.6 * mask) * (0.85 + 0.15 * np.cos(y * math.pi))[:, :, None]
        return (1 + float(params.get("intensity", 1)) * (grille - 1)).astype(np.float32), np.zeros((h, w, 3), np.float32), 1
    if effect == "paper-texture":
        fibre = cv2.GaussianBlur(np.random.default_rng(1009).random((h, w)).astype(np.float32), (0, 0), 1.2)
        fibre = (fibre - fibre.mean()) / max(1e-6, float(fibre.std()))
        amount = float(params.get("intensity", 1))
        mul = np.repeat((1 + amount * (-0.1 + 0.035 * fibre))[:, :, None], 3, 2).astype(np.float32)
        add = np.broadcast_to(amount * np.float32([0.05, 0.035, 0.0]), (h, w, 3)).astype(np.float32)
        return mul, add, 1
    if effect == "chroma-noise":
        noise = np.random.default_rng(int(local * 1000) % (2**32)).normal(0, 1, (h, w, 3)).astype(np.float32)
        return ones, (cv2.GaussianBlur(noise, (0, 0), 0.8) * float(params.get("strength", 0.15))).astype(np.float32), 1
    if effect == "bokeh-spots":
        spots = np.zeros((h, w, 3), np.float32)
        rng = np.random.default_rng(433)
        scale = float(params.get("scale", 1))
        for px, py, sp in rng.random((78, 3))[: round(26 * float(params.get("density", 1)))]:
            cv2.circle(
                spots, (int(px * w), int((py + local * 0.01) % 1 * h)), max(2, int(w * (0.03 + 0.05 * sp) * scale)), (0.9, 0.7, 0.35), -1
            )
        return ones, (cv2.GaussianBlur(spots, (0, 0), max(1.0, w / 200)) * 0.6).astype(np.float32), 2
    if effect == "sparkles":
        rng = np.random.default_rng(11)
        sky = np.zeros((h, w, 3), np.float32)
        stars = np.stack([rng.random(40), rng.random(40), rng.random(40) * 6.3, 0.5 + rng.random(40)], axis=1)
        wanted = round(40 * float(params.get("density", 1)))
        if wanted > 40:
            more = np.random.default_rng(12).random((wanted - 40, 4)) * [1, 1, 6.3, 1] + [0, 0, 0, 0.5]
            stars = np.concatenate([stars, more])
        size = float(params.get("scale", 1))
        for sx, sy, phase, scale in stars[:wanted]:
            bright = max(0.0, math.sin(local * 4 + phase)) ** 3
            if bright < 0.02:
                continue
            reach, centre = max(2, int(w * 0.02 * scale * size * bright)), (int(sx * w), int(sy * h))
            colour = (bright, bright * 0.95, bright * 0.85)
            cv2.line(sky, (centre[0] - reach, centre[1]), (centre[0] + reach, centre[1]), colour, 1, cv2.LINE_AA)
            cv2.line(sky, (centre[0], centre[1] - reach), (centre[0], centre[1] + reach), colour, 1, cv2.LINE_AA)
        sky = sky + cv2.GaussianBlur(sky, (0, 0), max(1.5, w / 300)) * 2
        return ones, np.clip(sky, 0, 1).astype(np.float32), 2
    if effect == "snowfall":
        # mode 3: rgb * 0.88 + 0.07, then the flakes cover; the cover field is -1 where nothing is drawn
        cover = np.full((h, w, 3), -1.0, np.float32)
        rng = np.random.default_rng(907)
        flakes = rng.random((1080, 3))[: round(360 * float(params.get("density", 1)))]
        scale = float(params.get("scale", 1))
        for px, py, rate in flakes:
            a = int((px + math.sin(local * 1.3 + py * 9) * 0.02) % 1 * w)
            b = int((py + local * (rate * 0.5 + 0.15) * 0.2) % 1 * h)
            cv2.circle(cover, (a, b), max(1, int(w / 320 * (1 + 1.5 * rate) * scale)), (0.95, 0.97, 1.0), -1)
        return np.full((h, w, 3), 0.88, np.float32), cover, 3
    if effect == "film-scratches":
        add = np.broadcast_to(np.float32([0.06, 0.045, 0.02]), (h, w, 3)).astype(np.float32).copy()
        rng = np.random.default_rng(int(local * 12))
        for _ in range(round(14 * float(params.get("density", 1)))):
            col, top, bright = int(rng.random() * w), int(rng.random() * h * 0.6), 0.3 + 0.4 * rng.random()
            add[top:, col : col + max(1, w // 320)] += bright
        return np.full((h, w, 3), 0.9, np.float32), add, 1
    return None


def process(rgb: np.ndarray, effect: str, local: float, params: dict) -> np.ndarray:
    if effect in GRADES:
        return grade(rgb, {**GRADES[effect], **params})
    if effect == "deflicker":
        return deflicker(rgb, params)
    if effect == "denoise-picture":
        return denoise_picture(rgb, params)
    if effect == "colour-match":
        return colour_match(rgb, params)
    h, w = rgb.shape[:2]
    y, x, u, v = _grid(h, w)
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
        spread = 0.1 * float(params.get("intensity", 1))
        return sum(remap(rgb, (x - w / 2) * s + w / 2, (y - h / 2) * s + h / 2) for s in np.linspace(1 - spread, 1 + spread, 9)) / 9
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
        return rgb * (1 - float(params.get("intensity", 1)) * (1 - _vignette_falloff(h, w)))
    if effect == "grain":
        rng = np.random.default_rng(int(local * 1000) % (2**32))
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
        factor = 1 + 0.45 * float(params.get("intensity", 1)) * r * r
        return remap(rgb, (dx / factor / 2 + 0.5) * w, (dy / factor / 2 + 0.5) * h)
    if effect == "wave":
        return remap(rgb, x + np.sin(v * 30 + local * 4) * size, y)
    if effect == "mirror":
        return remap(rgb, np.abs(u - 0.5) * 2 * (w - 1), y)
    if effect == "kaleidoscope":
        dx, dy = x - w / 2, y - h / 2
        r = np.sqrt(dx * dx + dy * dy)
        wedge = 2 * math.pi / max(2, int(params.get("segments", 6)))
        angle = np.abs(np.mod(np.arctan2(dy, dx), wedge) - wedge / 2)
        return remap(rgb, w / 2 + r * np.cos(angle), h / 2 + r * np.sin(angle))
    if effect == "scanlines":
        depth = 0.25 * float(params.get("intensity", 1))
        return rgb * (1 - depth + depth * np.cos(y * math.pi * 2 / max(2.0, float(params.get("spacing", 2)))))[:, :, None]
    if effect == "interference":
        return remap(rgb, x + np.sin(y / 9 + local * 15) * (np.sin(local * 12) ** 8) * size * 2, y)
    if effect == "cartoon":
        smooth = cv2.bilateralFilter(rgb.astype(np.float32), 7, 0.2, 5)
        edges = cv2.Canny((rgb * 255).astype(np.uint8), 80, 140) < 128
        bands = max(2, int(params.get("levels", 5)))
        return np.round(smooth * bands) / bands * edges[:, :, None]
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
        arc = 0.12 * float(params.get("intensity", 1))
        for angle in np.linspace(-arc, arc, 7):
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
        factor = max(1, round(min(w, h) / 360))
        small = cv2.resize(
            np.round(np.clip(rgb, 0, 1) * 255).astype(np.uint8), (max(1, w // factor), max(1, h // factor)), interpolation=cv2.INTER_AREA
        )
        smooth = (
            cv2.resize(
                cv2.edgePreservingFilter(small, flags=cv2.RECURS_FILTER, sigma_s=60, sigma_r=0.45), (w, h), interpolation=cv2.INTER_CUBIC
            ).astype(np.float32)
            / 255
        )
        gray = cv2.cvtColor(smooth, cv2.COLOR_RGB2GRAY)[:, :, None]
        canvas = cv2.GaussianBlur(np.random.default_rng(29).random((h, w)).astype(np.float32), (0, 0), 1.5)[:, :, None]
        return (gray + (smooth - gray) * 1.25) * (0.93 + 0.14 * canvas)
    if effect == "thermal":
        gray = np.round(np.clip(cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY), 0, 1) * 255).astype(np.uint8)
        return cv2.cvtColor(cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    if effect == "night-vision":
        gray = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY)
        noise = np.random.default_rng(int(local * 1000) % (2**32)).normal(0, float(params.get("strength", 0.05)), (h, w))
        lum = np.clip(gray * 1.6 + noise, 0, 1) * np.clip(1.25 - ((u - 0.5) ** 2 + (v - 0.5) ** 2) * 2.4, 0, 1)
        return np.stack([lum * 0.25, lum, lum * 0.3], axis=2).astype(np.float32)
    if effect == "ink-outline":
        gray = np.round(np.clip(cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY), 0, 1) * 255).astype(np.uint8)
        block = max(3, int(params.get("size", 9)) | 1)
        lines = cv2.adaptiveThreshold(cv2.medianBlur(gray, 5), 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, block, 5)
        return np.repeat((lines.astype(np.float32) / 255)[:, :, None], 3, 2)
    if effect == "crosshatch":
        gray = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY)
        period = max(4, size // 2)
        ink = (
            ((np.mod(x + y, period) < 1.2) & (gray < 0.75))
            | ((np.mod(x - y, period) < 1.2) & (gray < 0.5))
            | ((np.mod(x, period) < 1.2) & (gray < 0.28))
        )
        return np.repeat((1 - ink.astype(np.float32) * 0.9)[:, :, None], 3, 2)
    if effect == "swirl":
        dx, dy = x - w / 2, y - h / 2
        turn = float(params.get("twist", 2.2)) * np.clip(1 - np.sqrt(dx * dx + dy * dy) / (0.5 * min(w, h)), 0, 1) ** 2
        c, s = np.cos(turn), np.sin(turn)
        return remap(rgb, w / 2 + dx * c - dy * s, h / 2 + dx * s + dy * c)
    if effect == "ripple":
        dx, dy = x - w / 2, y - h / 2
        r = np.sqrt(dx * dx + dy * dy) + 1e-6
        shift = np.sin(r / max(4, size) - local * 6) * size * 0.8
        return remap(rgb, x + dx / r * shift, y + dy / r * shift)
    if effect == "pinch":
        dx, dy = (u - 0.5) * 2, (v - 0.5) * 2
        factor = 1 + 0.5 * float(params.get("intensity", 1)) * (1 - np.clip(dx * dx + dy * dy, 0, 1))
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
        tiles = max(1, int(params.get("tiles", 2)))
        return remap(rgb, np.mod(x * tiles, w), np.mod(y * tiles, h))
    if effect == "polar-wrap":
        dx, dy = (u - 0.5) * 2, (v - 0.5) * 2
        r = np.clip(np.sqrt(dx * dx + dy * dy), 0, 1)
        return remap(rgb, (np.arctan2(dy, dx) / (2 * math.pi) + 0.5) * (w - 1), (1 - r) * (h - 1))
    if effect == "heat-haze":
        return remap(
            rgb, x + np.sin(y / 11 + local * 5) * np.sin(x / 23 + local * 3) * size * 0.6, y + np.cos(x / 13 + local * 4) * size * 0.4
        )
    if effect == "film-scratches":
        out = rgb * 0.9 + np.float32([0.06, 0.045, 0.02])
        rng = np.random.default_rng(int(local * 12))
        for _ in range(round(14 * float(params.get("density", 1)))):
            col, top, bright = int(rng.random() * w), int(rng.random() * h * 0.6), 0.3 + 0.4 * rng.random()
            out[top:, col : col + max(1, w // 320)] += bright
        return out
    if effect == "light-leak":
        cx = 0.12 + 0.1 * math.sin(local * 0.7)
        glow = np.clip(1 - np.sqrt((u - cx) ** 2 + (v - 0.15) ** 2) * 1.5, 0, 1) ** 2
        glow = np.clip(glow * float(params.get("intensity", 1)), 0, 1)
        return 1 - (1 - rgb) * (1 - glow[:, :, None] * np.float32([1.0, 0.45, 0.12]))
    if effect == "aperture-grille":
        phase = np.mod(x, 3)
        mask = np.stack([phase < 1, (phase >= 1) & (phase < 2), phase >= 2], axis=2).astype(np.float32)
        grille = (0.55 + 0.6 * mask) * (0.85 + 0.15 * np.cos(y * math.pi))[:, :, None]
        return rgb * (1 + float(params.get("intensity", 1)) * (grille - 1))
    if effect == "paper-texture":
        fibre = cv2.GaussianBlur(np.random.default_rng(1009).random((h, w)).astype(np.float32), (0, 0), 1.2)
        fibre = (fibre - fibre.mean()) / max(1e-6, float(fibre.std()))
        amount = float(params.get("intensity", 1))
        return rgb * (1 + amount * (-0.1 + 0.035 * fibre))[:, :, None] + amount * np.float32([0.05, 0.035, 0.0])
    if effect == "snowfall":
        out = rgb * 0.88 + 0.07
        rng = np.random.default_rng(907)
        # Drawn from one longer stream, so the default count is the same flakes as before.
        flakes = rng.random((1080, 3))[: round(360 * float(params.get("density", 1)))]
        scale = float(params.get("scale", 1))
        for px, py, rate in flakes:
            a = int((px + math.sin(local * 1.3 + py * 9) * 0.02) % 1 * w)
            b = int((py + local * (rate * 0.5 + 0.15) * 0.2) % 1 * h)
            cv2.circle(out, (a, b), max(1, int(w / 320 * (1 + 1.5 * rate) * scale)), (0.95, 0.97, 1.0), -1)
        return out
    if effect == "bokeh-spots":
        spots = np.zeros_like(rgb)
        rng = np.random.default_rng(433)
        scale = float(params.get("scale", 1))
        for px, py, s in rng.random((78, 3))[: round(26 * float(params.get("density", 1)))]:
            cv2.circle(
                spots, (int(px * w), int((py + local * 0.01) % 1 * h)), max(2, int(w * (0.03 + 0.05 * s) * scale)), (0.9, 0.7, 0.35), -1
            )
        return 1 - (1 - rgb) * (1 - cv2.GaussianBlur(spots, (0, 0), max(1.0, w / 200)) * 0.6)
    if effect == "chroma-noise":
        noise = np.random.default_rng(int(local * 1000) % (2**32)).normal(0, 1, (h, w, 3)).astype(np.float32)
        return rgb + cv2.GaussianBlur(noise, (0, 0), 0.8) * float(params.get("strength", 0.15))
    if effect == "oil-paint":
        # Kuwahara: each pixel takes the mean of whichever of its four corner
        # windows is flattest, which keeps edges and turns texture into strokes.
        k = max(3, size // 2) + 1
        gray = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY)
        means, spreads = [], []
        for anchor in ((k - 1, k - 1), (0, k - 1), (k - 1, 0), (0, 0)):
            means.append(cv2.boxFilter(rgb.astype(np.float32), -1, (k, k), anchor=anchor, borderType=cv2.BORDER_REFLECT))
            mean_gray = cv2.boxFilter(gray, -1, (k, k), anchor=anchor, borderType=cv2.BORDER_REFLECT)
            spreads.append(cv2.boxFilter(gray * gray, -1, (k, k), anchor=anchor, borderType=cv2.BORDER_REFLECT) - mean_gray**2)
        pick = np.argmin(np.stack(spreads), axis=0)[None, :, :, None]
        return np.take_along_axis(np.stack(means), np.repeat(pick, 3, axis=3), axis=0)[0]
    if effect == "hex-pixelate":
        s, root = float(size), math.sqrt(3.0)
        q, r = (root / 3 * x - y / 3) / s, (2 / 3 * y) / s
        cube = np.stack([q, -q - r, r])
        rounded = np.round(cube)
        diff = np.abs(rounded - cube)
        rounded[0] = np.where((diff[0] > diff[1]) & (diff[0] > diff[2]), -rounded[1] - rounded[2], rounded[0])
        rounded[2] = np.where(~((diff[0] > diff[1]) & (diff[0] > diff[2])) & ~(diff[1] > diff[2]), -rounded[0] - rounded[1], rounded[2])
        cx, cy = s * root * (rounded[0] + rounded[2] / 2), s * 1.5 * rounded[2]
        soft = cv2.GaussianBlur(rgb.astype(np.float32), (0, 0), max(0.5, s / 3))
        return cv2.remap(soft, cx.astype(np.float32), cy.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if effect == "led-wall":
        cols, rows = max(1, w // size), max(1, h // size)
        cells = cv2.resize(
            cv2.resize(rgb.astype(np.float32), (cols, rows), interpolation=cv2.INTER_AREA), (w, h), interpolation=cv2.INTER_NEAREST
        )
        fx, fy = (x * cols / w) % 1 - 0.5, (y * rows / h) % 1 - 0.5
        dots = cells * np.clip((0.42 - np.sqrt(fx * fx + fy * fy)) / 0.08, 0, 1)[:, :, None] * 1.15
        glow = cv2.GaussianBlur(dots, (0, 0), max(1.0, 0.6 * w / cols)) * 0.6
        return 1 - (1 - np.clip(dots, 0, 1)) * (1 - np.clip(glow, 0, 1))
    if effect == "vhs-tape":
        rng = np.random.default_rng(int(local * 30) % (2**32))
        ycc = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2YCrCb)
        ycc[:, :, 0] = cv2.GaussianBlur(ycc[:, :, 0], (0, 0), 0.9)
        bleed = max(1, w // 120) * 2 + 1
        ycc[:, :, 1:] = np.roll(cv2.blur(ycc[:, :, 1:], (bleed, 1)), max(1, w // 200), axis=1)
        tape = cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB)
        band = np.exp(-((((np.arange(h) / h) - ((local * 0.35) % 1.2 - 0.1)) / 0.02) ** 2)).astype(np.float32)
        wear = float(params.get("intensity", 1))
        offsets = ((rng.normal(0, 1.2, h) + band * w * 0.02) * wear).astype(np.float32)
        tape = cv2.remap(
            tape, (x + offsets[:, None]).astype(np.float32), y.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
        )
        noise = rng.normal(0, 1, (h, w)).astype(np.float32) * (0.03 + band[:, None] * 0.25) * wear
        gray = cv2.cvtColor(tape, cv2.COLOR_RGB2GRAY)[:, :, None]
        return gray + (tape - gray) * 0.85 + noise[:, :, None]
    if effect == "neon-edges":
        soft = cv2.GaussianBlur(cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY), (0, 0), 1.0)
        lines = cv2.dilate(cv2.Canny(np.round(np.clip(soft, 0, 1) * 255).astype(np.uint8), 50, 130), np.ones((3, 3), np.uint8))
        hue = np.round(((u * 0.6 + v * 0.4 + local * 0.15) % 1) * 179).astype(np.uint8)
        colour = cv2.cvtColor(np.dstack([hue, np.full_like(hue, 255), np.full_like(hue, 255)]), cv2.COLOR_HSV2RGB).astype(np.float32) / 255
        neon = colour * (lines.astype(np.float32) / 255)[:, :, None]
        glow = np.clip(cv2.GaussianBlur(neon, (0, 0), max(2.0, w / 250)) * 2.2 * float(params.get("intensity", 1)), 0, 1)
        return 1 - (1 - rgb * 0.12) * (1 - np.clip(neon + glow, 0, 1))
    if effect == "pop-art-grid":
        half = cv2.resize(rgb.astype(np.float32), (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA)
        level = np.clip(np.floor(cv2.cvtColor(half, cv2.COLOR_RGB2GRAY) * 3), 0, 2).astype(np.int64)
        palettes = np.array(
            [
                [[0.10, 0.05, 0.35], [0.95, 0.20, 0.55], [1.00, 0.90, 0.20]],
                [[0.05, 0.25, 0.30], [0.10, 0.75, 0.70], [1.00, 0.60, 0.15]],
                [[0.30, 0.02, 0.05], [0.95, 0.35, 0.10], [0.98, 0.95, 0.60]],
                [[0.02, 0.10, 0.30], [0.35, 0.45, 0.95], [0.70, 1.00, 0.40]],
            ],
            np.float32,
        )
        grid = np.vstack([np.hstack([palettes[0][level], palettes[1][level]]), np.hstack([palettes[2][level], palettes[3][level]])])
        return cv2.resize(grid, (w, h), interpolation=cv2.INTER_NEAREST)
    if effect == "stained-glass":
        labels, leading = _glass_cells(h, w, max(8, int(size * 2.5)))
        flat, count = labels.ravel(), int(labels.max()) + 1
        counts = np.maximum(np.bincount(flat, minlength=count), 1)
        panes = np.stack([np.bincount(flat, weights=rgb[:, :, c].ravel(), minlength=count) / counts for c in range(3)], axis=1)
        return (panes[labels] * 1.08 * np.where(leading, 0.08, 1.0)[:, :, None]).astype(np.float32)
    if effect == "bayer-dither":
        step = max(1, size // 4)
        small = cv2.resize(rgb.astype(np.float32), (max(1, w // step), max(1, h // step)), interpolation=cv2.INTER_AREA)
        sh, sw = small.shape[:2]
        matrix = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16
        threshold = np.tile(matrix, (sh // 4 + 1, sw // 4 + 1))[:sh, :sw, None]
        dithered = np.floor(np.clip(small, 0, 1) * 3 + threshold) / 3
        return cv2.resize(dithered.astype(np.float32), (w, h), interpolation=cv2.INTER_NEAREST)
    if effect == "crt-screen":
        nu, nv = (u - 0.5) * 2, (v - 0.5) * 2
        bend = 1 + float(params.get("curvature", 0.12)) * (nu * nu + nv * nv)
        su, sv = nu * bend, nv * bend
        tube = cv2.remap(
            rgb.astype(np.float32),
            ((su / 2 + 0.5) * w - 0.5).astype(np.float32),
            ((sv / 2 + 0.5) * h - 0.5).astype(np.float32),
            cv2.INTER_LINEAR,
        )
        tube *= ((np.abs(su) <= 1) & (np.abs(sv) <= 1))[:, :, None]
        period = max(2, h // 240)
        tube *= np.where((y // max(1, period // 2)) % 2 == 1, 0.72, 1.0)[:, :, None]
        phosphor = np.array([[1.0, 0.86, 0.86], [0.86, 1.0, 0.86], [0.86, 0.86, 1.0]], np.float32)[(x.astype(np.int64) % 3)]
        tube = tube * phosphor * (1 - 0.18 * (nu * nu + nv * nv))[:, :, None]
        return tube + cv2.GaussianBlur(tube, (0, 0), max(1.0, w / 400)) * 0.15
    if effect == "infrared":
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        false = np.stack([g * 1.15 + r * 0.1, r * 0.75 + b * 0.1, b * 0.9 + g * 0.1], axis=2)
        gray = cv2.cvtColor(np.clip(false, 0, 1).astype(np.float32), cv2.COLOR_RGB2GRAY)[:, :, None]
        return gray + (false - gray) * 1.2
    if effect == "block-glitch":
        rng = np.random.default_rng(int(local * 12) % (2**32))
        out = rgb.astype(np.float32).copy()
        for _ in range(round(10 * float(params.get("density", 1)))):
            height = int(rng.integers(max(1, h // 40), max(2, h // 8)))
            top = int(rng.integers(0, max(1, h - height)))
            shift = int(rng.integers(-max(1, w // 12), max(2, w // 12)))
            out[top : top + height] = np.roll(rgb[top : top + height], shift, axis=1)
            if rng.random() < 0.5:
                channel = int(rng.integers(0, 3))
                out[top : top + height, :, channel] = np.roll(rgb[top : top + height, :, channel], shift * 2, axis=1)
        return out
    if effect == "anaglyph":
        offset = max(1, round(w * 0.004 * size / 12))
        gray = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY)
        left, right = np.roll(gray, -offset, axis=1), np.roll(gray, offset, axis=1)
        return np.stack([left, right, right], axis=2)
    if effect == "fog":
        field = _fog_field(h, w)
        drift = int(local * w * 0.03) % w
        density = np.clip(field[:, drift : drift + w] * (0.45 + 0.55 * v) * float(params.get("density", 1)), 0, 1)[:, :, None] * 0.7
        return rgb * (1 - density) + 0.82 * density
    if effect == "lens-flare":
        px, py = float(params.get("x", 0.72)) * w, float(params.get("y", 0.22)) * h
        distance = np.hypot(x - px, y - py)
        light = np.exp(-((distance / (w * 0.03)) ** 2)) + np.exp(-((distance / (w * 0.15)) ** 2)) * 0.35
        streak = np.exp(-(((y - py) / max(1.0, h * 0.004)) ** 2)) * np.exp(-np.abs(x - px) / (w * 0.35)) * 0.6
        flare = (light + streak)[:, :, None] * np.array([1.0, 0.9, 0.7], np.float32)
        for step, radius, tint in ((1.4, 0.05, (0.5, 0.8, 1.0)), (1.8, 0.03, (1.0, 0.6, 0.9)), (2.3, 0.08, (0.6, 1.0, 0.7))):
            gx, gy = px + (w / 2 - px) * step, py + (h / 2 - py) * step
            ghost = np.exp(-((np.hypot(x - gx, y - gy) / (w * radius)) ** 4)) * 0.15
            flare = flare + ghost[:, :, None] * np.array(tint, np.float32)
        flare = flare * (0.92 + 0.08 * math.sin(local * 7)) * float(params.get("intensity", 1))
        return 1 - (1 - rgb) * (1 - np.clip(flare, 0, 1))
    if effect == "sparkles":
        rng = np.random.default_rng(11)
        sky = np.zeros((h, w, 3), np.float32)
        # The first forty are the ones this always drew; more come from a second stream.
        stars = np.stack([rng.random(40), rng.random(40), rng.random(40) * 6.3, 0.5 + rng.random(40)], axis=1)
        wanted = round(40 * float(params.get("density", 1)))
        if wanted > 40:
            more = np.random.default_rng(12).random((wanted - 40, 4)) * [1, 1, 6.3, 1] + [0, 0, 0, 0.5]
            stars = np.concatenate([stars, more])
        size = float(params.get("scale", 1))
        for sx, sy, phase, scale in stars[:wanted]:
            bright = max(0.0, math.sin(local * 4 + phase)) ** 3
            if bright < 0.02:
                continue
            reach, centre = max(2, int(w * 0.02 * scale * size * bright)), (int(sx * w), int(sy * h))
            colour = (bright, bright * 0.95, bright * 0.85)
            cv2.line(sky, (centre[0] - reach, centre[1]), (centre[0] + reach, centre[1]), colour, 1, cv2.LINE_AA)
            cv2.line(sky, (centre[0], centre[1] - reach), (centre[0], centre[1] + reach), colour, 1, cv2.LINE_AA)
        sky = sky + cv2.GaussianBlur(sky, (0, 0), max(1.5, w / 300)) * 2
        return 1 - (1 - rgb) * (1 - np.clip(sky, 0, 1))
    if effect == "clarity":
        blurred = cv2.GaussianBlur(rgb.astype(np.float32), (0, 0), max(2.0, w / 80))
        midtones = 1 - np.abs(cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY) * 2 - 1)
        return rgb + (rgb - blurred) * 0.7 * float(params.get("intensity", 1)) * midtones[:, :, None]
    if effect == "dehaze":
        # The dark channel: haze lifts the darkest channel everywhere, so its
        # local minimum estimates how much air lies between camera and scene.
        dark = cv2.erode(np.min(rgb, axis=2).astype(np.float32), np.ones((max(3, w // 120),) * 2, np.uint8))
        brightest = dark >= np.percentile(dark, 99.9)
        air = rgb[brightest].mean(axis=0) if brightest.any() else np.ones(3, np.float32)
        passing = np.clip(
            cv2.GaussianBlur(
                1 - min(0.95, 0.85 * float(params.get("intensity", 1))) * dark / max(float(air.max()), 1e-3), (0, 0), max(1.0, w / 150)
            ),
            0.35,
            1,
        )
        return (rgb - air) / passing[:, :, None] + air
    if effect == "skin-smooth":
        # A guided filter smooths within skin tones while keeping edges; only
        # pixels whose chroma falls in the skin range are changed.
        guide = cv2.cvtColor(rgb.astype(np.float32), cv2.COLOR_RGB2GRAY)
        radius, eps = (max(2, w // 200) * 2 + 1,) * 2, 0.004
        mean_guide = cv2.boxFilter(guide, -1, radius)
        spread = cv2.boxFilter(guide * guide, -1, radius) - mean_guide**2
        smooth = np.empty_like(rgb, dtype=np.float32)
        for c in range(3):
            channel = rgb[:, :, c].astype(np.float32)
            mean_channel = cv2.boxFilter(channel, -1, radius)
            gain = (cv2.boxFilter(guide * channel, -1, radius) - mean_guide * mean_channel) / (spread + eps)
            smooth[:, :, c] = cv2.boxFilter(gain, -1, radius) * guide + cv2.boxFilter(mean_channel - gain * mean_guide, -1, radius)
        ycc = cv2.cvtColor(np.clip(rgb, 0, 1).astype(np.float32), cv2.COLOR_RGB2YCrCb)
        skin = ((ycc[:, :, 1] > 0.52) & (ycc[:, :, 1] < 0.68) & (ycc[:, :, 2] > 0.30) & (ycc[:, :, 2] < 0.52)).astype(np.float32)
        skin = cv2.GaussianBlur(skin, (0, 0), max(1.0, w / 200))[:, :, None]
        return rgb + (smooth - rgb) * skin * min(1.0, 0.85 * float(params.get("intensity", 1)))
    raise ValueError(f"Unknown visual effect: {effect}")


def _stack_steps(effect_id: str) -> list | None:
    """The steps of a stack package, or None when the id is not one."""
    from .effect_packages import find

    entry = find(effect_id)
    if entry and entry["kind"] == "video" and entry["backend"]["type"] == "stack":
        return entry["backend"]["steps"]
    return None


def _shader_backend(effect_id: str) -> dict | None:
    """A shader package's source, parameter order and defaults, or None when the id is not one."""
    from .effect_packages import find

    entry = find(effect_id)
    if entry and entry["kind"] == "video" and entry["backend"]["type"] == "shader":
        return {"source": entry["backend"]["source"], "order": entry["backend"].get("order", []), "defaults": entry["parameters"]}
    return None


def apply_effects(image: np.ndarray, effects: list[dict], local: float) -> np.ndarray:
    to_float, to_bytes = _native_kernel("unit_float"), _native_kernel("to_bytes")
    if to_float is not None and image.dtype == np.uint8 and image.ndim == 3 and image.flags.c_contiguous:
        # The same float32 values as the NumPy line below, in one parallel pass.
        result = np.empty(image.shape, np.float32)
        to_float(image, result)
    else:
        scale = 65535.0 if image.dtype == np.uint16 else 255.0
        result = image.astype(np.float32) / scale
    for entry in effects:
        amount = max(0.0, min(1.0, float(entry.get("amount", 1))))
        if entry["id"] not in GRADES and entry["id"] not in VIDEO_EFFECTS:
            # A stack package is formcut's own steps: each runs as it would on
            # its own, blended by its strength times the clip's. A shader
            # package is a user kernel, run on the device with its parameters.
            steps = _stack_steps(entry["id"])
            if steps is None:
                shader = _shader_backend(entry["id"])
                if shader is None:
                    raise ValueError("Unknown visual effect: " + entry["id"])
                if amount > 0:
                    from . import gpu

                    given = entry.get("params") or {}
                    values = [given.get(name, shader["defaults"][name]) for name in shader["order"]]
                    changed = gpu.custom_values(result, shader["source"], local, values)[:, :, :3]
                    result[:, :, :3] = np.clip(changed * amount + result[:, :, :3] * (1 - amount), 0, 1)
                continue
            if amount > 0:
                for step in steps:
                    share = amount * max(0.0, min(1.0, float(step.get("amount", 1))))
                    if share <= 0:
                        continue
                    if "grade" in step:
                        changed = grade(result[:, :, :3], step["grade"])
                    else:
                        settings = {**EFFECT_DEFAULTS.get(step["effect"], {}), **(step.get("params") or {})}
                        changed = process(result[:, :, :3], step["effect"], local, clamp_params(settings))
                    result[:, :, :3] = np.clip(changed * share + result[:, :, :3] * (1 - share), 0, 1)
            continue
        # An effect turned all the way down was still being computed in full and
        # then blended away to nothing, so a chain of disabled effects cost as
        # much as a chain of active ones.
        if amount <= 0:
            continue
        # The declared defaults fill what the clip has not set, so an untouched
        # slider shows the value that renders (four effects rendered size 12
        # while their sliders showed 9, 14, 10 and 8).
        settings = {**EFFECT_DEFAULTS.get(entry["id"], {}), **(entry.get("params") or {})}
        changed = process(result[:, :, :3], entry["id"], local, clamp_params(settings))
        if amount >= 1:
            # The common case. The blend below reduces to `changed` here, but
            # spent two full-frame multiplies and an add to arrive at it.
            np.clip(changed, 0, 1, out=changed)
            result[:, :, :3] = changed
            continue
        changed *= amount
        changed += result[:, :, :3] * (1 - amount)
        np.clip(changed, 0, 1, out=changed)
        result[:, :, :3] = changed
    if image.dtype == np.uint16:
        return np.round(np.clip(result, 0, 1) * 65535).astype(np.uint16)
    if to_bytes is not None and result.flags.c_contiguous:
        # np.round(result * 255).astype(np.uint8), to the bit, in one parallel pass.
        out = np.empty(result.shape, np.uint8)
        to_bytes(result, out)
        return out
    return np.round(result * 255).astype(np.uint8)


# K1: the colour panel. A named, keyable correction stage that runs before the
# effect stack. Every control is neutral at its default, and a clip without a
# `colour` object skips the stage entirely, so existing frames are untouched.
COLOUR_PANEL = {
    "temperature": 6500.0,
    "tint": 0.0,
    "saturation": 0.0,
    "exposure": 0.0,
    "brightness": 0.0,
    "contrast": 0.0,
    "highlights": 0.0,
    "shadows": 0.0,
    "whites": 0.0,
    "blacks": 0.0,
    "sharpen": 0.0,
    "fade": 0.0,
    "vignette": 0.0,
}


def colour_active(panel) -> bool:
    """True only when some control has left its neutral value."""
    if not isinstance(panel, dict):
        return False
    return any(abs(float(panel.get(k, v)) - v) > 1e-9 for k, v in COLOUR_PANEL.items())


def _kelvin_gain(kelvin: float) -> np.ndarray:
    """Warm below 6500 K, cool above, neutral at 6500 K."""
    shift = (6500.0 - max(2000.0, min(11000.0, kelvin))) / 4500.0
    return np.array([1.0 + 0.22 * shift, 1.0 + 0.02 * abs(shift) * 0.0, 1.0 - 0.22 * shift], np.float32)


LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def colour_panel(rgb: np.ndarray, panel: dict) -> np.ndarray:
    """Apply the colour panel to linearish RGB in 0..1. Neutral is identity."""
    if not colour_active(panel):
        return rgb

    def value(k):
        return float(panel.get(k, COLOUR_PANEL[k]))

    out = rgb.astype(np.float32, copy=True)
    # Each step below allocates a full frame, so at 1280x720 a panel that ran
    # every stage moved about 165 MB per frame whether the stage did anything
    # or not. Neutral values are now skipped, which is most of them in ordinary
    # use, and the work that remains is done in place.
    temperature = value("temperature")
    if abs(temperature - COLOUR_PANEL["temperature"]) > 1e-6:
        out *= _kelvin_gain(temperature)
    tint = value("tint") / 100.0
    if tint:
        out[:, :, 1] *= 1.0 + 0.25 * tint
        out[:, :, 0] *= 1.0 - 0.10 * tint
        out[:, :, 2] *= 1.0 - 0.10 * tint
    exposure = value("exposure")
    if exposure:
        out *= 2.0**exposure
    brightness = value("brightness") / 100.0
    if brightness:
        out += brightness
    contrast = 1.0 + value("contrast") / 100.0
    if contrast != 1.0:
        out -= 0.5
        out *= contrast
        out += 0.5
    highlights = value("highlights") / 100.0
    shadows = value("shadows") / 100.0
    whites = value("whites") / 100.0
    blacks = value("blacks") / 100.0
    saturation_value = value("saturation")
    needs_luminance = bool(highlights or shadows or whites or blacks) or saturation_value != 0.0
    luminance = None
    if needs_luminance:
        # einsum writes one channel rather than a three-channel temporary that
        # is then summed away.
        luminance = np.einsum("ijk,k->ij", np.clip(out, 0, 4), LUMA).astype(np.float32)[:, :, None]
    if highlights or shadows:
        high = np.clip(luminance - 0.5, 0, None)
        high *= 2.0
        if highlights:
            out += high * highlights
        if shadows:
            low = np.clip(0.5 - luminance, 0, None)
            low *= 2.0
            out += low * shadows
    # Cubes by multiplication, not **3: NumPy computes float32 powers with SVML
    # on AVX-512 machines and libm elsewhere, which differ in the last bit, so
    # a render would depend on the CPU. Plain products are the same everywhere.
    if whites:
        out += (luminance * luminance * luminance) * whites
    if blacks:
        dark = 1.0 - luminance
        out += (dark * dark * dark) * blacks
    saturation = 1.0 + saturation_value / 100.0
    if saturation != 1.0 and luminance is not None:
        out -= luminance
        out *= saturation
        out += luminance
    fade = value("fade") / 100.0
    if fade:
        out = out * (1.0 - 0.35 * fade) + 0.12 * fade
    sharpen = value("sharpen") / 100.0
    if sharpen:
        blurred = cv2.GaussianBlur(out, (0, 0), 1.2)
        out = out + (out - blurred) * (1.5 * sharpen)
    vignette = value("vignette") / 100.0
    if vignette:
        h, w = out.shape[:2]
        y, x = np.mgrid[:h, :w]
        radius = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)
        falloff = np.clip(1.0 - (radius**2) * vignette, 0, 1)[:, :, None]
        out = out * falloff if vignette > 0 else out * (2 - falloff)
    return out


# The Rust kernel's order for the panel's controls. Sharpen is not among them:
# it blurs with OpenCV, so a panel with sharpen on keeps the Python path.
NATIVE_COLOUR = (
    "temperature",
    "tint",
    "exposure",
    "brightness",
    "contrast",
    "highlights",
    "shadows",
    "whites",
    "blacks",
    "saturation",
    "fade",
    "vignette",
)


def _native_kernel(name: str):
    """A Rust kernel by name, unless unbuilt, too old to have it, or switched off with FORMCUT_NATIVE=0."""
    import os

    if os.environ.get("FORMCUT_NATIVE", "").strip() == "0":
        return None
    try:
        import formcut_native
    except ImportError:
        return None
    return getattr(formcut_native, name, None)


def _native_colour():
    """The Rust colour kernel, on the same terms as every native kernel."""
    return _native_kernel("colour_panel")


def apply_colour_panel(image: np.ndarray, panel) -> np.ndarray:
    """RGBA uint8 in, RGBA uint8 out; alpha untouched."""
    if not colour_active(panel):
        return image
    native = _native_colour()
    if native is not None and float(panel.get("sharpen", 0.0)) == 0.0 and image.ndim == 3 and image.shape[2] == 4:
        out = np.array(image, dtype=np.uint8, order="C", copy=True)
        native(out, [float(panel.get(key, COLOUR_PANEL[key])) for key in NATIVE_COLOUR])
        return out
    return python_colour_panel(image, panel)


def python_colour_panel(image: np.ndarray, panel) -> np.ndarray:
    """The colour panel in NumPy: the reference the Rust kernel reproduces to the bit."""
    rgb = image[:, :, :3].astype(np.float32) / 255.0
    graded = colour_panel(rgb, panel)
    out = image.copy()
    out[:, :, :3] = np.clip(graded * 255.0, 0, 255).astype(np.uint8)
    return out


# CapCut breadth: three repairs that work on the picture rather than styling it.
# They live with the other effects so keyframes, masks and the parameter panel
# come for free, and they are cheap enough to run on every frame.


def _luma(rgb: np.ndarray) -> np.ndarray:
    return rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722


def deflicker(rgb: np.ndarray, params: dict) -> np.ndarray:
    """Pull each frame's exposure toward a steady level.

    Flicker is a frame-to-frame swing in overall brightness, so normalising a
    frame's mean luminance toward a target removes it without touching contrast
    within the frame. The target is a fixed mid-grey by default, which is what
    makes this work without knowing the neighbouring frames.
    """
    strength = max(0.0, min(1.0, float(params.get("strength", 0.8))))
    target = max(0.05, min(0.95, float(params.get("level", 0.45))))
    if strength <= 0:
        return rgb
    mean = float(_luma(rgb).mean())
    if mean <= 1e-4:
        return rgb
    gain = 1.0 + (target / mean - 1.0) * strength
    return np.clip(rgb * gain, 0, 1)


def denoise_picture(rgb: np.ndarray, params: dict) -> np.ndarray:
    """Remove picture grain while keeping edges.

    A bilateral filter is the right shape here: it averages neighbours that look
    alike and leaves an edge alone, so noise goes and detail stays.
    """
    strength = max(0.0, min(1.0, float(params.get("strength", 0.5))))
    if strength <= 0:
        return rgb
    # Tuned on structured footage rather than on per-pixel randomness: the
    # first mapping looked weak only because the test signal had nothing to
    # recover. At full strength this takes the error on 8 percent Gaussian
    # noise from 0.064 to about 0.015.
    radius = int(5 + 6 * strength)
    colour_sigma = 0.06 + 0.30 * strength
    smooth = cv2.bilateralFilter(rgb.astype(np.float32), radius, colour_sigma, radius)
    detail = max(0.0, min(1.0, float(params.get("detail", 0.25))))
    # Adding a little of the removed high frequency back keeps it from looking
    # waxy, which is the usual complaint about denoising.
    return np.clip(smooth + (rgb - smooth) * detail, 0, 1)


def colour_match(rgb: np.ndarray, params: dict) -> np.ndarray:
    """Move this frame's colour statistics toward a reference's.

    Mean and spread per channel, matched in proportion: the standard transfer,
    which is enough to make two cameras or two lighting setups sit together.
    The reference numbers are measured once and carried in the parameters, so
    the effect stays a pure function of the frame.
    """
    strength = max(0.0, min(1.0, float(params.get("strength", 1.0))))
    means = params.get("refMean")
    deviations = params.get("refStd")
    if strength <= 0 or not means or not deviations:
        return rgb
    out = rgb.astype(np.float32).copy()
    for channel in range(3):
        source_mean = float(out[:, :, channel].mean())
        source_std = float(out[:, :, channel].std()) or 1e-4
        scale = float(deviations[channel]) / source_std
        moved = (out[:, :, channel] - source_mean) * scale + float(means[channel])
        out[:, :, channel] = out[:, :, channel] * (1 - strength) + moved * strength
    return np.clip(out, 0, 1)


def reference_statistics(rgb: np.ndarray) -> dict:
    """The numbers colour_match needs from a reference frame."""
    return {
        "refMean": [float(rgb[:, :, c].mean()) for c in range(3)],
        "refStd": [float(rgb[:, :, c].std()) for c in range(3)],
    }
