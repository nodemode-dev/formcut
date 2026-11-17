import json
import re
import uuid
from functools import lru_cache

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from .paths import DATA_DIR

router = APIRouter(prefix="/api/assets", tags=["assets"])
ROOT = DATA_DIR / "assets"


def asset_path(asset_id: str, suffix: str):
    if not re.fullmatch(r"[a-f0-9]{32}", asset_id):
        raise ValueError("Invalid asset id")
    path = ROOT / (asset_id + suffix)
    if not path.is_file():
        raise ValueError("Asset is unavailable")
    return path


INTERPOLATIONS = ("trilinear", "tetrahedral")


def parse_cube(text: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A .cube file as (table, domain low, domain high): a 3D table is size x size x size x 3 indexed [b][g][r],
    a 1D table is size x 3, one column a channel."""
    size, size_1d = 0, 0
    low, high = np.zeros(3), np.ones(3)
    rows = []
    for line in text.splitlines():
        parts = line.split("#", 1)[0].split()
        if not parts or parts[0] == "TITLE":
            continue
        if parts[0] in ("LUT_3D_SIZE", "LUT_1D_SIZE"):
            if len(parts) != 2:
                raise ValueError(f"{parts[0]} needs one number")
            if parts[0] == "LUT_3D_SIZE":
                size = int(parts[1])
                if not 2 <= size <= 65:
                    raise ValueError("LUT grid must be between 2 and 65")
            else:
                size_1d = int(parts[1])
                if not 2 <= size_1d <= 65536:
                    raise ValueError("A 1D LUT must have between 2 and 65536 entries")
        elif parts[0] == "DOMAIN_MIN":
            low = np.array([float(x) for x in parts[1:]])
        elif parts[0] == "DOMAIN_MAX":
            high = np.array([float(x) for x in parts[1:]])
        elif parts[0] in ("LUT_3D_INPUT_RANGE", "LUT_1D_INPUT_RANGE"):
            if len(parts) != 3:
                raise ValueError(f"{parts[0]} needs two numbers")
            low, high = np.full(3, float(parts[1])), np.full(3, float(parts[2]))
        elif parts[0][0].isalpha() and "_" in parts[0]:
            continue
        elif len(parts) == 3:
            rows.append([float(x) for x in parts])
        else:
            raise ValueError("A .cube row needs three numbers")
    if size and size_1d:
        raise ValueError("A .cube with both a 1D and a 3D table is not supported")
    expected = size**3 if size else size_1d
    if (
        expected < 2
        or len(rows) != expected
        or low.shape != (3,)
        or high.shape != (3,)
        or not np.all(np.isfinite(low))
        or not np.all(np.isfinite(high))
        or np.any(high <= low)
    ):
        raise ValueError("LUT size or color domain is invalid")
    table = np.array(rows, np.float32)
    if not np.all(np.isfinite(table)):
        raise ValueError("LUT values must be finite")
    if not size:
        return table, low, high
    return table.reshape(size, size, size, 3), low, high


@lru_cache(maxsize=16)
def load_cube(asset_id: str):
    return parse_cube(asset_path(asset_id, ".cube").read_text())


def _levels_1d(table: np.ndarray, low, high, levels: int) -> np.ndarray:
    """A 1D table evaluated at every input level (levels x 3), linear between its entries."""
    n = len(table)
    signal = np.arange(levels, dtype=np.float64) / (levels - 1)
    out = np.empty((levels, 3), np.float64)
    for channel in range(3):
        position = np.clip((signal - low[channel]) / (high[channel] - low[channel]), 0, 1) * (n - 1)
        out[:, channel] = np.interp(position, np.arange(n), table[:, channel])
    return np.clip(out, 0, 1)


_POOL: list = []


def sample_3d(table: np.ndarray, rgb: np.ndarray, interpolation: str = "trilinear") -> np.ndarray:
    """A 3D table ([b][g][r]) at float32 lattice coordinates rgb (... x 3, each 0 to n - 1), as float32. A large
    picture is sampled in bands on a pool of threads: NumPy's gathers release the interpreter lock, and one band a
    thread made a 4K frame 2 to 5 times faster on a 12-core laptop."""
    if rgb.ndim != 3 or rgb.shape[0] * rgb.shape[1] < 1 << 20:
        return _sample(table, rgb, interpolation)
    import os
    from concurrent.futures import ThreadPoolExecutor

    workers = max(1, min(16, os.cpu_count() or 1))
    if not _POOL:
        _POOL.append(ThreadPoolExecutor(workers, thread_name_prefix="formcut-lut"))
    out = np.empty(rgb.shape, np.float32)
    edges = np.linspace(0, rgb.shape[0], workers * 2 + 1).astype(int)

    def band(k: int) -> None:
        out[edges[k] : edges[k + 1]] = _sample(table, rgb[edges[k] : edges[k + 1]], interpolation)

    list(_POOL[0].map(band, range(len(edges) - 1)))
    return out


def _sample(table: np.ndarray, rgb: np.ndarray, interpolation: str) -> np.ndarray:
    n = len(table)
    flat = np.ascontiguousarray(table, np.float32).reshape(-1, 3)
    lower = np.minimum(rgb.astype(np.int32), n - 2)
    fraction = rgb - lower
    base = (lower[..., 2] * n + lower[..., 1]) * n + lower[..., 0]
    if interpolation == "tetrahedral":
        order = np.argsort(-fraction, axis=-1, kind="stable")
        ranked = np.take_along_axis(fraction, order, axis=-1)
        strides = np.array([1, n, n * n], np.int32)[order]
        first = base + strides[..., 0]
        second = first + strides[..., 1]
        out = flat[base] * (1 - ranked[..., 0:1])
        out += flat[first] * (ranked[..., 0:1] - ranked[..., 1:2])
        out += flat[second] * (ranked[..., 1:2] - ranked[..., 2:3])
        out += flat[base + (n * n + n + 1)] * ranked[..., 2:3]
        return out
    out = np.zeros(rgb.shape, np.float32)
    for db in (0, 1):
        wb = fraction[..., 2] if db else 1 - fraction[..., 2]
        for dg in (0, 1):
            wg = (fraction[..., 1] if dg else 1 - fraction[..., 1]) * wb
            for dr in (0, 1):
                weight = (fraction[..., 0] if dr else 1 - fraction[..., 0]) * wg
                out += flat[base + (db * n + dg) * n + dr] * weight[..., None]
    return out


def apply_cube(image: np.ndarray, cube, intensity: float = 1.0, interpolation: str = "trilinear") -> np.ndarray:
    """A parsed .cube over an RGB or RGBA picture of bytes or sixteen bits, alpha untouched, in float32 and
    rounded once to the picture's own depth."""
    table, low, high = cube
    top = 65535.0 if image.dtype == np.uint16 else 255.0
    amount = max(0.0, min(1.0, float(intensity)))
    if table.ndim == 2:
        levels = _levels_1d(table, low, high, int(top) + 1)
        graded = np.stack([levels[image[..., c], c] for c in range(3)], axis=-1).astype(np.float32)
    else:
        n = len(table)
        source = image[..., :3].astype(np.float32) / np.float32(top)
        span = np.asarray(high - low, np.float32)
        coords = np.clip((source - np.asarray(low, np.float32)) / span, 0, 1) * np.float32(n - 1)
        graded = np.clip(sample_3d(table, coords, interpolation), 0, 1)
    if amount < 1.0:
        graded = image[..., :3].astype(np.float32) / np.float32(top) * (1 - amount) + graded * amount
    out = image.copy()
    out[..., :3] = np.round(graded * np.float32(top)).astype(image.dtype)
    return out


def apply_lut(image: np.ndarray, asset_id: str, intensity: float = 1.0, interpolation: str = "trilinear") -> np.ndarray:
    table, low, high = load_cube(asset_id)
    if image.dtype != np.uint8 or table.ndim != 4 or interpolation != "trilinear":
        return apply_cube(image, (table, low, high), intensity, interpolation)
    n = len(table)
    coords = np.clip((image[:, :, :3] / 255 - low) / (high - low), 0, 1) * (n - 1)
    lower = np.floor(coords).astype(np.int32)
    upper = np.minimum(n - 1, lower + 1)
    fraction = coords - lower
    rgb = np.zeros_like(coords)
    for r in (0, 1):
        for g in (0, 1):
            for b in (0, 1):
                indices = [upper[:, :, i] if flag else lower[:, :, i] for i, flag in enumerate((r, g, b))]
                weight = np.prod([fraction[:, :, i] if flag else 1 - fraction[:, :, i] for i, flag in enumerate((r, g, b))], axis=0)
                rgb += table[indices[2], indices[1], indices[0]] * weight[:, :, None]
    out = image.copy()
    graded = np.clip(rgb, 0, 1) * 255
    amount = max(0.0, min(1.0, float(intensity)))
    if amount < 1.0:
        graded = image[:, :, :3].astype(np.float64) * (1 - amount) + graded * amount
    out[:, :, :3] = np.round(graded).astype(np.uint8)
    return out


@router.get("")
def list_assets() -> list[dict]:
    if not ROOT.exists():
        return []
    return [json.loads(p.read_text()) for p in ROOT.glob("*.json")]


@router.post("/lut", status_code=201)
def upload_lut(file: UploadFile) -> dict:
    raw = file.file.read(8_000_001)
    if len(raw) > 8_000_000:
        raise HTTPException(413, "LUT exceeds 8 MB")
    try:
        text = raw.decode("utf-8-sig")
        parse_cube(text)
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    ROOT.mkdir(parents=True, exist_ok=True)
    asset_id = uuid.uuid4().hex
    name = (file.filename or "Color LUT").rsplit(".", 1)[0][:60] or "Color LUT"
    item = {"id": asset_id, "name": name, "kind": "lut", "look": True}
    (ROOT / (asset_id + ".cube")).write_text(text)
    (ROOT / (asset_id + ".json")).write_text(json.dumps(item))
    return item


class ShaderInput(BaseModel):
    name: str
    source: str


@router.post("/shader", status_code=201)
def upload_shader(body: ShaderInput) -> dict:
    from .gpu import custom

    if len(body.source) > 100_000 or len(body.name) > 100:
        raise HTTPException(422, "Shader exceeds the supported size")
    try:
        custom(np.full((8, 8, 4), 255, np.uint8), body.source, 0)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    ROOT.mkdir(parents=True, exist_ok=True)
    asset_id = uuid.uuid4().hex
    item = {"id": asset_id, "name": body.name, "kind": "shader"}
    (ROOT / (asset_id + ".wgsl")).write_text(body.source)
    (ROOT / (asset_id + ".json")).write_text(json.dumps(item))
    return item
