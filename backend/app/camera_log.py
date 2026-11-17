"""Camera Log input transforms: a clip shot in a camera's Log curve and gamut, taken into the Rec.709 working space.

A clip's `inputColour` names the curve and gamut it was shot in. The decoded signal is read as the camera's
full-range code value (code / 1023, whatever range the file is decoded at), turned into scene light by the
manufacturer's own curve (0.18 is grey), moved from the camera gamut to Rec.709 primaries in linear light, given a
shoulder above `KNEE` so highlights the camera kept roll off instead of clipping, and encoded with the Rec.709
camera curve (BT.709 OETF), the way a camera's own Rec.709 mode lands grey near 41 percent.

The result is sixteen bits a channel (bytes on an HDR timeline, which lifts bytes into its transfer), so a ten-bit
Log source keeps its steps through the transform.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path

import cv2
import numpy as np

KNEE = 0.75
D65 = (0.3127, 0.3290)
REC709 = ((0.640, 0.330), (0.300, 0.600), (0.150, 0.060))
GAMUTS = {
    "cinema": ((0.7400, 0.2700), (0.1700, 1.1400), (0.0800, -0.1000)),
    "s-gamut3-cine": ((0.766, 0.275), (0.225, 0.800), (0.089, -0.087)),
    "v-gamut": ((0.730, 0.280), (0.165, 0.840), (0.100, -0.030)),
    "alexa-wide-gamut": ((0.6840, 0.3130), (0.2210, 0.8480), (0.0861, -0.1020)),
}


def _canon_log3(cv: np.ndarray) -> np.ndarray:
    low = -(np.power(10.0, (0.12783901 - cv) / 0.36726845) - 1) / 14.98325
    middle = (cv - 0.12512219) / 1.9754798
    high = (np.power(10.0, (cv - 0.12240537) / 0.36726845) - 1) / 14.98325
    return 0.9 * np.where(cv < 0.097465473, low, np.where(cv <= 0.15277891, middle, high))


def _canon_log2(cv: np.ndarray) -> np.ndarray:
    low = -(np.power(10.0, (0.092864125 - cv) / 0.24136077) - 1) / 87.099375
    high = (np.power(10.0, (cv - 0.092864125) / 0.24136077) - 1) / 87.099375
    return 0.9 * np.where(cv < 0.092864125, low, high)


def _s_log3(cv: np.ndarray) -> np.ndarray:
    code = cv * 1023
    high = np.power(10.0, (code - 420) / 261.5) * (0.18 + 0.01) - 0.01
    low = (code - 95) * 0.01125 / (171.2102946929 - 95)
    return np.where(code >= 171.2102946929, high, low)


def _v_log(cv: np.ndarray) -> np.ndarray:
    return np.where(cv < 0.181, (cv - 0.125) / 5.6, np.power(10.0, (cv - 0.598206) / 0.241514) - 0.00873)


def _log_c3(cv: np.ndarray) -> np.ndarray:
    a, b, c, d, e, f, cut = 5.555556, 0.052272, 0.247190, 0.385537, 5.367655, 0.092809, 0.010591
    return np.where(cv > e * cut + f, (np.power(10.0, (cv - d) / c) - b) / a, (cv - f) / e)


TRANSFORMS = {
    "canon-log3": (_canon_log3, "cinema"),
    "canon-log2": (_canon_log2, "cinema"),
    "slog3": (_s_log3, "s-gamut3-cine"),
    "vlog": (_v_log, "v-gamut"),
    "logc3": (_log_c3, "alexa-wide-gamut"),
}


def to_scene(name: str, cv) -> np.ndarray:
    """A camera code value (code / 1023) as scene light, 0.18 at grey, by the named curve."""
    return TRANSFORMS[name][0](np.asarray(cv, np.float64))


def _to_xyz(primaries, white=D65) -> np.ndarray:
    xyz = np.array([[x / y, 1.0, (1 - x - y) / y] for x, y in primaries]).T
    wx, wy = white
    scale = np.linalg.solve(xyz, np.array([wx / wy, 1.0, (1 - wx - wy) / wy]))
    return xyz * scale


@functools.lru_cache(maxsize=8)
def gamut_matrix(gamut: str) -> np.ndarray:
    """Linear camera-gamut RGB to linear Rec.709 RGB, from both sets of primaries and D65."""
    matrix = np.linalg.inv(_to_xyz(REC709)) @ _to_xyz(GAMUTS[gamut])
    matrix.flags.writeable = False
    return matrix


def tone(x: np.ndarray) -> np.ndarray:
    """Scene light to Rec.709 display light: unchanged up to KNEE, then a hyperbolic shoulder that nears 1."""
    x = np.maximum(x, 0)
    over = np.maximum(x - KNEE, 0) / (1 - KNEE)
    return np.where(x <= KNEE, x, KNEE + (1 - KNEE) * over / (1 + over))


def encode_709(y: np.ndarray) -> np.ndarray:
    """The BT.709 camera curve (OETF), clipped to 0..1."""
    y = np.clip(y, 0, 1)
    return np.where(y < 0.018, 4.5 * y, 1.099 * np.power(y, 0.45) - 0.099)


@functools.lru_cache(maxsize=16)
def _scene_table(name: str, full_range: bool, levels: int) -> np.ndarray:
    """Every decoded level's scene light: the level read as the camera's code value through its range."""
    signal = np.arange(levels, dtype=np.float64) / (levels - 1)
    cv = signal if full_range else (64 + 876 * signal) / 1023
    table = to_scene(name, cv).astype(np.float32)
    table.flags.writeable = False
    return table


def apply(image: np.ndarray, name: str, full_range: bool = False, deep: bool = False) -> np.ndarray:
    """An RGB or RGBA picture (bytes or sixteen bits) shot in the named Log, as Rec.709: sixteen bits back, or bytes
    when `deep` (an HDR timeline lifts bytes into its own transfer)."""
    if name not in TRANSFORMS:
        return image
    if image.dtype not in (np.uint8, np.uint16):
        image = np.round(np.clip(image, 0, 1) * 65535).astype(np.uint16)
    levels = 65536 if image.dtype == np.uint16 else 256
    scene = _scene_table(name, bool(full_range), levels)[image[..., :3]]
    linear = cv2.transform(scene, gamut_matrix(TRANSFORMS[name][1]).astype(np.float32))
    shown = encode_709(tone(linear))
    top = 255.0 if deep else 65535.0
    kind = np.uint8 if deep else np.uint16
    out = np.empty((*image.shape[:2], image.shape[2]), kind)
    out[..., :3] = np.round(shown * top)
    if image.shape[2] == 4:
        alpha = image[..., 3].astype(np.float32) * (top / (levels - 1))
        out[..., 3] = np.round(alpha)
    return out


# What a file may say about the Log it was shot in, as the strings seen in camera files (none of the manufacturers
# documents them, so these are a suggestion, never applied without the person choosing it). LogC4 is a different
# curve and must not read as LogC3.
_TAGGED = (
    ("canon-log3", re.compile(rb"Canon ?Log ?3|C-?Log ?3", re.IGNORECASE)),
    ("canon-log2", re.compile(rb"Canon ?Log ?2|C-?Log ?2", re.IGNORECASE)),
    ("slog3", re.compile(rb"S-Log ?3", re.IGNORECASE)),
    ("vlog", re.compile(rb"V-Log(?!\s*L\b)", re.IGNORECASE)),
    ("logc3", re.compile(rb"Log ?C(?:3|\b)(?! ?4)", re.IGNORECASE)),
)
SCAN_BYTES = 4 * 1024 * 1024


def _named(text: bytes) -> str | None:
    for name, pattern in _TAGGED:
        if pattern.search(text):
            return name
    return None


def suggest(probe: dict, path: Path | str | None = None) -> str | None:
    """The input colour a file names, from its container and stream tags or the metadata a camera writes near the
    start or end of the file (Sony's NonRealTimeMeta XML among it); None when it names none."""
    tags = [probe.get("format", {}).get("tags") or {}]
    tags += [stream.get("tags") or {} for stream in probe.get("streams", [])]
    words = b" ".join(f"{key} {value}".encode("utf-8", "replace") for group in tags for key, value in group.items())
    found = _named(words)
    if found or path is None:
        return found
    try:
        with open(path, "rb") as handle:
            head = handle.read(SCAN_BYTES)
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(len(head), size - SCAN_BYTES))
            tail = handle.read(SCAN_BYTES)
    except OSError:
        return None
    for chunk in (head, tail):
        for marker in re.findall(rb"(?:CaptureGammaEquation|Gamma|gamma)[^<>]{0,40}", chunk):
            found = _named(marker)
            if found:
                return found
    return None
