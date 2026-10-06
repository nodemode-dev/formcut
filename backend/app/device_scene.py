"""The scene around a device: studio light, camera, contact shadow, and a screen test pattern.

The light is a studio generated in code (no image file): a gradient sky, a large key softbox, two strip lights and a
rim, as an equirectangular map in linear light. Image-based lighting reads it two ways: specular from copies blurred
for each roughness level (a GGX-like lobe, weighted by solid angle), diffuse from its first nine spherical harmonics.
Both are computed once per process.
"""

import math
import threading

import cv2
import numpy as np

ENV_WIDTH, ENV_HEIGHT = 512, 256
ROUGHNESS_LEVELS = tuple(i / 6 for i in range(7))
_lock = threading.Lock()
_environment: dict | None = None

# softboxes: (azimuth deg, elevation deg, width deg, height deg, intensity, warmth)
SOFTBOXES = (
    (-35.0, 55.0, 70.0, 34.0, 5.0, 0.0),
    (-105.0, 18.0, 16.0, 70.0, 2.6, -0.02),
    (100.0, 22.0, 14.0, 64.0, 1.7, 0.02),
    (175.0, 38.0, 60.0, 18.0, 1.4, 0.0),
)


def _directions(width: int, height: int) -> np.ndarray:
    """Unit directions at the centres of an equirectangular grid (+Y up, azimuth 0 toward -Z)."""
    u = (np.arange(width) + 0.5) / width
    v = (np.arange(height) + 0.5) / height
    phi = (u - 0.5) * 2 * math.pi
    theta = v * math.pi
    st = np.sin(theta)[:, None]
    return np.stack(
        [st * np.sin(phi)[None, :], np.cos(theta)[:, None] * np.ones((1, width)), -st * np.cos(phi)[None, :]], axis=-1
    ).astype(np.float32)


def studio_map(width: int = ENV_WIDTH, height: int = ENV_HEIGHT) -> np.ndarray:
    """The studio as linear RGB, shape (height, width, 3)."""
    d = _directions(width, height)
    y = d[..., 1]
    sky = np.where(y > 0, 0.42 + 0.33 * y, 0.42 + 0.24 * y)
    image = np.repeat(sky[..., None], 3, axis=-1).astype(np.float32)
    azimuth = np.degrees(np.arctan2(d[..., 0], -d[..., 2]))
    elevation = np.degrees(np.arcsin(np.clip(y, -1, 1)))
    for az, el, w, h, power, warmth in SOFTBOXES:
        da = (azimuth - az + 180) % 360 - 180
        de = elevation - el
        edge = np.clip(1.6 - 2.0 * np.maximum(np.abs(da) / (w / 2), np.abs(de) / (h / 2)), 0, 1)
        panel = edge * edge * (3 - 2 * edge)
        tint = np.array([1 + warmth, 1.0, 1 - warmth], np.float32)
        image += panel[..., None] * power * tint
    return image


def _solid_angles(width: int, height: int) -> np.ndarray:
    theta = (np.arange(height) + 0.5) / height * math.pi
    return (np.sin(theta) * (math.pi / height) * (2 * math.pi / width)).astype(np.float32)


def _prefilter(image: np.ndarray, roughness: float) -> np.ndarray:
    """The map blurred by a lobe of the given roughness (alpha = roughness squared), at the map's size."""
    if roughness <= 0:
        return image
    size = (128, 64) if roughness < 0.5 else (64, 32)
    small = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    dirs = _directions(*size).reshape(-1, 3)
    weights_in = np.repeat(_solid_angles(*size)[:, None], size[0], axis=1).reshape(-1)
    alpha = max(roughness * roughness, 1e-3)
    power = max(2.0 / (alpha * alpha) - 2.0, 1.0)
    colours = small.reshape(-1, 3)
    out = np.empty_like(colours)
    for start in range(0, len(dirs), 512):
        cos = np.clip(dirs[start : start + 512] @ dirs.T, 0, 1)
        w = np.power(cos, power) * weights_in[None, :]
        out[start : start + 512] = (w @ colours) / np.maximum(w.sum(axis=1, keepdims=True), 1e-8)
    return cv2.resize(out.reshape(size[1], size[0], 3), (image.shape[1], image.shape[0]), interpolation=cv2.INTER_CUBIC)


def _harmonics(image: np.ndarray) -> np.ndarray:
    """Irradiance as nine spherical-harmonic coefficients (RGB), already convolved with the cosine lobe."""
    h, w = image.shape[:2]
    d = _directions(w, h).reshape(-1, 3)
    weight = np.repeat(_solid_angles(w, h)[:, None], w, axis=1).reshape(-1, 1)
    colour = image.reshape(-1, 3) * weight
    x, y, z = d[:, 0], d[:, 1], d[:, 2]
    basis = np.stack(
        [
            np.full_like(x, 0.282095),
            0.488603 * y,
            0.488603 * z,
            0.488603 * x,
            1.092548 * x * y,
            1.092548 * y * z,
            0.315392 * (3 * z * z - 1),
            1.092548 * x * z,
            0.546274 * (x * x - y * y),
        ],
        axis=1,
    )
    coefficients = basis.T @ colour
    band = np.array([math.pi, *[2 * math.pi / 3] * 3, *[math.pi / 4] * 5], np.float32)[:, None]
    return (coefficients * band / math.pi).astype(np.float32)


def environment() -> dict:
    """The studio prepared for lighting: one map per roughness level and the diffuse harmonics."""
    global _environment
    with _lock:
        if _environment is None:
            base = studio_map()
            _environment = {
                "levels": np.stack([_prefilter(base, r) for r in ROUGHNESS_LEVELS]).astype(np.float32),
                "harmonics": _harmonics(cv2.resize(base, (128, 64), interpolation=cv2.INTER_AREA)),
            }
        return _environment


def perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    """A right-handed perspective projection to WebGPU clip space (depth 0 to 1)."""
    f = 1.0 / math.tan(math.radians(fov_deg) / 2)
    m = np.zeros((4, 4))
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = far / (near - far)
    m[2, 3] = far * near / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    forward = target - eye
    forward = forward / np.linalg.norm(forward)
    side = np.cross(forward, up)
    side = side / np.linalg.norm(side)
    upward = np.cross(side, forward)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = side, upward, -forward
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def orbit(points: np.ndarray, aspect: float, camera: dict) -> tuple[np.ndarray, np.ndarray]:
    """The view-projection and eye for an orbit camera around the device, framed so the device fits at distance 1.

    camera: yaw and pitch in degrees (0, 0 looks at the screen side along -Z), distance (1 frames the device),
    fov in degrees, pan as fractions of the framed height, roll in degrees.
    """
    low, high = points.min(axis=0), points.max(axis=0)
    centre = (low + high) / 2
    radius = float(np.linalg.norm(high - low) / 2)
    fov = float(camera.get("fov", 30.0))
    half = math.radians(fov) / 2
    fit = radius / math.sin(min(half, math.atan(math.tan(half) * aspect))) * 1.04
    distance = fit * float(camera.get("distance", 1.0))
    yaw, pitch = math.radians(float(camera.get("yaw", 0.0))), math.radians(float(camera.get("pitch", 0.0)))
    direction = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    pan = camera.get("pan") or (0.0, 0.0)
    span = distance * math.tan(half)
    roll = math.radians(float(camera.get("roll", 0.0)))
    up = np.array([0.0, 1.0, 0.0]) if abs(direction[1]) < 0.999 else np.array([0.0, 0.0, -1.0])
    view = look_at(centre + direction * distance, centre, up)
    side, upward = view[0, :3], view[1, :3]
    target = centre - side * float(pan[0]) * span - upward * float(pan[1]) * span
    eye = target + direction * distance
    view = look_at(eye, target, up)
    if roll:
        r = np.eye(4)
        r[:2, :2] = [[math.cos(roll), -math.sin(roll)], [math.sin(roll), math.cos(roll)]]
        view = r @ view
    near = max(distance - radius * 1.5, distance * 0.02)
    return perspective(fov, aspect, near, distance + radius * 2.0) @ view, eye


def contact_shadow(points: np.ndarray, floor: float, size: int = 256) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """A soft shadow under the device: points near the floor dark and tight, higher points faint and wide.

    Returns an alpha map (size x size, 0 to 1) and its footprint on the floor (x0, z0, x1, z1) in metres.
    """
    low, high = points.min(axis=0), points.max(axis=0)
    reach = max(high[0] - low[0], high[2] - low[2]) * 0.75 + 0.02
    cx, cz = (low[0] + high[0]) / 2, (low[2] + high[2]) / 2
    x0, z0, x1, z1 = cx - reach, cz - reach, cx + reach, cz + reach
    px = np.clip(((points[:, 0] - x0) / (x1 - x0) * size).astype(int), 0, size - 1)
    pz = np.clip(((points[:, 2] - z0) / (z1 - z0) * size).astype(int), 0, size - 1)
    height = points[:, 1] - floor
    tall = max(float(high[1] - floor), 1e-3)
    near_floor = np.zeros((size, size), np.float32)
    np.add.at(near_floor, (pz, px), np.clip(1 - height / (0.15 * tall + 0.004), 0, 1))
    whole = np.zeros((size, size), np.float32)
    np.add.at(whole, (pz, px), 1.0)
    pixel = size / (x1 - x0)
    tight = cv2.GaussianBlur(np.minimum(near_floor, 1), (0, 0), max(0.004 * pixel, 1.0))
    wide = cv2.GaussianBlur(np.minimum(whole, 1), (0, 0), max(0.03 * pixel, 2.0))
    alpha = np.clip(tight * 2.2, 0, 1) * 0.7 + np.clip(wide * 1.6, 0, 1) * 0.35
    return np.clip(alpha, 0, 1).astype(np.float32), (x0, z0, x1, z1)


def test_pattern(width: int, height: int) -> np.ndarray:
    """A screen test card (sRGB, RGBA): a grey ramp, colour bars, a border and corner marks (red top-left, green
    top-right, blue bottom-left), and an arrow pointing up, so orientation and cropping can be read off a render."""
    image = np.zeros((height, width, 4), np.uint8)
    image[..., 3] = 255
    ramp = np.linspace(30, 225, width).astype(np.uint8)
    image[: height // 2, :, :3] = ramp[None, :, None]
    bars = [(235, 235, 235), (235, 235, 16), (16, 235, 235), (16, 235, 16), (235, 16, 235), (235, 16, 16), (16, 16, 235)]
    for i, colour in enumerate(bars):
        image[height // 2 :, i * width // len(bars) : (i + 1) * width // len(bars), :3] = colour
    edge = max(4, min(width, height) // 60)
    image[:edge], image[-edge:], image[:, :edge], image[:, -edge:] = 255, 255, 255, 255
    mark = max(12, min(width, height) // 8)
    image[edge : edge + mark, edge : edge + mark, :3] = (230, 30, 30)
    image[edge : edge + mark, -edge - mark : -edge, :3] = (30, 200, 60)
    image[-edge - mark : -edge, edge : edge + mark, :3] = (40, 80, 230)
    cx, top, span = width // 2, height // 8, min(width, height) // 6
    arrow = np.array([[cx, top], [cx - span, top + span], [cx - span // 3, top + span], [cx - span // 3, top + 2 * span],
                      [cx + span // 3, top + 2 * span], [cx + span // 3, top + span], [cx + span, top + span]], np.int32)
    cv2.fillPoly(image, [arrow], (20, 20, 20, 255))
    return image
