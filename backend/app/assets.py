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


def parse_cube(text: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    size = 0
    low, high = np.zeros(3), np.ones(3)
    rows = []
    for line in text.splitlines():
        parts = line.split("#", 1)[0].split()
        if not parts or parts[0] == "TITLE":
            continue
        if parts[0] == "LUT_3D_SIZE":
            if len(parts) != 2:
                raise ValueError("LUT_3D_SIZE needs one number")
            size = int(parts[1])
            if not 2 <= size <= 65:
                raise ValueError("LUT grid must be between 2 and 65")
        elif parts[0] == "DOMAIN_MIN":
            low = np.array([float(x) for x in parts[1:]])
        elif parts[0] == "DOMAIN_MAX":
            high = np.array([float(x) for x in parts[1:]])
        elif parts[0] == "LUT_3D_INPUT_RANGE":
            if len(parts) != 3:
                raise ValueError("LUT_3D_INPUT_RANGE needs two numbers")
            low, high = np.full(3, float(parts[1])), np.full(3, float(parts[2]))
        elif parts[0].startswith("LUT_1D"):
            raise ValueError("Only 3D .cube LUTs are supported")
        elif parts[0][0].isalpha() and "_" in parts[0]:
            continue
        elif len(parts) == 3:
            rows.append([float(x) for x in parts])
        else:
            raise ValueError("Only 3D .cube LUTs are supported")
    if (
        size < 2
        or len(rows) != size**3
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
    return table.reshape(size, size, size, 3), low, high


@lru_cache(maxsize=16)
def load_cube(asset_id: str):
    return parse_cube(asset_path(asset_id, ".cube").read_text())


def apply_lut(image: np.ndarray, asset_id: str, intensity: float = 1.0) -> np.ndarray:
    table, low, high = load_cube(asset_id)
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
