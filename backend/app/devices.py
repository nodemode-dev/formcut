"""The device library: ten photoreal device models from 3d-mock-models (CC0-1.0), and what formcut reads from each.

The models follow the generator's contract 2 (its generator/contract.py): one root `device` carrying
`extras.formcut`, screens as meshes with the material M_Screen (the inner display, split over `screen` and
`screen_fold` on folding devices, one picture across both halves through their UVs) and M_ScreenCover (the cover
display), hinges as empty nodes with their ranges in the extras. The contract records the main screen in the extras;
the cover display and the inner halves are found by node and material and measured here from the meshes, as its build
notes direct. Every file is checked against the manifest's SHA-256 before it is used.
"""

import hashlib
import json
import struct
import threading
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

LIBRARY = Path(__file__).resolve().parent / "device_library"
CONTRACT = 2
SCREEN_MATERIALS = {"M_Screen": "inner", "M_ScreenCover": "cover"}
_TYPES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
_COMPONENTS = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_lock = threading.Lock()
_catalogue: dict | None = None

router = APIRouter(prefix="/api/devices", tags=["devices"])


def read_glb(path: Path) -> tuple[dict, bytes]:
    """A binary glTF's JSON document and its binary chunk."""
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise ValueError(f"{path.name} is not a binary glTF")
    length = struct.unpack("<I", data[12:16])[0]
    document = json.loads(data[20 : 20 + length])
    rest = data[20 + length :]
    return document, rest[8:] if len(rest) >= 8 else b""


def accessor(document: dict, blob: bytes, index: int) -> np.ndarray:
    """An accessor's data as an array of shape (count, width), honouring its view's stride."""
    item = document["accessors"][index]
    view = document["bufferViews"][item["bufferView"]]
    width = _TYPES[item["type"]]
    kind = np.dtype(_COMPONENTS[item["componentType"]])
    start = view.get("byteOffset", 0) + item.get("byteOffset", 0)
    stride = view.get("byteStride") or kind.itemsize * width
    rows = np.lib.stride_tricks.as_strided(
        np.frombuffer(blob, np.uint8, count=stride * (item["count"] - 1) + kind.itemsize * width, offset=start),
        shape=(item["count"], kind.itemsize * width),
        strides=(stride, 1),
    )
    return rows.copy().view(kind).reshape(item["count"], width)


def node_matrix(node: dict) -> np.ndarray:
    """A node's local transform as a 4x4 matrix (column vectors)."""
    if "matrix" in node:
        return np.array(node["matrix"], np.float64).reshape(4, 4).T
    x, y, z, w = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    rotation = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )
    matrix = np.eye(4)
    matrix[:3, :3] = rotation * np.array(node.get("scale", [1.0, 1.0, 1.0]))
    matrix[:3, 3] = node.get("translation", [0.0, 0.0, 0.0])
    return matrix


def world_matrices(document: dict) -> dict[int, np.ndarray]:
    """Every node's transform in the device's space, keyed by node index."""
    out: dict[int, np.ndarray] = {}
    stack = [(index, np.eye(4)) for index in document["scenes"][document.get("scene", 0)]["nodes"]]
    while stack:
        index, parent = stack.pop()
        out[index] = parent @ node_matrix(document["nodes"][index])
        stack.extend((child, out[index]) for child in document["nodes"][index].get("children", []))
    return out


def _screen_parts(document: dict, blob: bytes) -> dict[str, list[dict]]:
    """The meshes carrying each screen material, with their extent in millimetres and the UV range they cover."""
    materials = document["materials"]
    matrices = world_matrices(document)
    parts: dict[str, list[dict]] = {}
    for index, node in enumerate(document["nodes"]):
        if "mesh" not in node:
            continue
        for primitive in document["meshes"][node["mesh"]]["primitives"]:
            name = materials[primitive["material"]]["name"] if "material" in primitive else ""
            if name not in SCREEN_MATERIALS:
                continue
            points = accessor(document, blob, primitive["attributes"]["POSITION"]).astype(np.float64)
            uv = accessor(document, blob, primitive["attributes"]["TEXCOORD_0"])
            world = (matrices[index] @ np.c_[points, np.ones(len(points))].T).T[:, :3] * 1000.0
            extent = np.sort(world.max(axis=0) - world.min(axis=0))[::-1]
            parts.setdefault(SCREEN_MATERIALS[name], []).append(
                {
                    "node": node.get("name", ""),
                    "extentMm": [round(float(extent[0]), 2), round(float(extent[1]), 2)],
                    "uv": [round(float(v), 4) for v in (uv[:, 0].min(), uv[:, 1].min(), uv[:, 0].max(), uv[:, 1].max())],
                }
            )
    return parts


def _screens(extras: dict, parts: dict[str, list[dict]]) -> list[dict]:
    """The displays a clip can be shown on: the inner one from the contract, the cover one measured."""
    main = extras["screen"]
    inner = {
        "slot": "inner",
        "material": main["material"],
        "nodes": sorted(part["node"] for part in parts.get("inner", [])),
        "activeMm": main["activeMm"],
        "aspect": main["aspect"],
        "pixels": main["suggestedPixels"],
        "cornerRadiusMm": main["cornerRadiusMm"],
        "cutouts": main["cutouts"],
    }
    screens = [inner]
    for part in parts.get("cover", []):
        # the cover display at the main display's pixel density; its width is the side across the device
        density = main["suggestedPixels"][0] / main["activeMm"][0]
        across, along = sorted(part["extentMm"])
        screens.append(
            {
                "slot": "cover",
                "material": "M_ScreenCover",
                "nodes": [part["node"]],
                "activeMm": [across, along],
                "aspect": round(across / along, 4),
                "pixels": [int(round(across * density / 2) * 2), int(round(along * density / 2) * 2)],
                "cornerRadiusMm": None,
                "cutouts": [],
            }
        )
    return screens


def _articulations(extras: dict) -> list[dict]:
    """The parts a clip can pose, each with its node, axis and range in degrees."""
    out = []
    if extras.get("hinge"):
        name = "fold" if extras["kind"] in ("flip", "fold") else "lid"
        out.append({"name": name, **extras["hinge"]})
    if extras.get("stand"):
        out.append({"name": "stand", **extras["stand"]})
    return out


def _describe(entry: dict) -> dict:
    path = LIBRARY / entry["file"]
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError(f"{entry['file']} does not match the device manifest")
    document, blob = read_glb(path)
    extras = document["nodes"][document["scenes"][document.get("scene", 0)]["nodes"][0]]["extras"]["formcut"]
    if extras.get("contract") != CONTRACT:
        raise ValueError(f"{entry['file']} follows device contract {extras.get('contract')}, formcut reads {CONTRACT}")
    legend = next((m for m in document["materials"] if m.get("name") == "M_KeyLegend"), None)
    from .device_templates import KINDS  # imported here: device_templates reads this module

    return {
        "templates": [name for name, kinds in KINDS.items() if kinds is None or extras["kind"] in kinds],
        "id": extras["id"],
        "kind": extras["kind"],
        "style": extras["style"],
        "file": entry["file"],
        "bytes": entry["bytes"],
        "triangles": entry["triangles"],
        "dimensionsMm": extras["dimensionsMm"],
        "finish": extras["finish"],
        "finishes": entry["finishes"],
        "screens": _screens(extras, _screen_parts(document, blob)),
        "articulations": _articulations(extras),
        "keyboard": extras.get("keyboard"),
        "backlight": {"material": "M_KeyLegend", "color": legend.get("emissiveFactor", [1.0, 1.0, 1.0])} if legend else None,
        "extensions": sorted(document.get("extensionsUsed", [])),
        "license": extras["license"],
        "generator": extras["generator"],
    }


def catalogue() -> dict:
    """The device library, described once per process (each file checked against the manifest on the way)."""
    global _catalogue
    with _lock:
        if _catalogue is None:
            manifest = json.loads((LIBRARY / "manifest.json").read_text(encoding="utf-8"))
            devices = [_describe(entry) for entry in manifest["models"]]
            _catalogue = {
                "version": manifest["version"],
                "blender": manifest["blender"],
                "contract": CONTRACT,
                "devices": sorted(devices, key=lambda d: (d["kind"], d["style"], d["id"])),
            }
        return _catalogue


def device(device_id: str) -> dict:
    """One device's description."""
    for item in catalogue()["devices"]:
        if item["id"] == device_id:
            return item
    raise KeyError(device_id)


@router.get("")
def list_devices() -> dict:
    """The device library: every device with its screens, articulations, backlight and finishes."""
    return catalogue()


_thumb_lock = threading.Lock()


@router.get("/{device_id}/thumbnail")
def thumbnail(device_id: str) -> FileResponse:
    """A device's picture for the library's Devices tab: rendered once by the 3D pass and kept in the data folder."""
    try:
        item = device(device_id)
    except KeyError:
        raise HTTPException(404, f"No device {device_id}") from None
    import cv2

    from .device_render import render
    from .paths import DATA_DIR

    path = DATA_DIR / "device-thumbnails" / f"{device_id}-{str(item.get('sha256', 'v1'))[:12]}.png"
    with _thumb_lock:
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            ramp = np.linspace(0, 1, 360, dtype=np.float32)[:, None, None]
            screen = np.round((np.array([255, 174, 43]) * (1 - ramp) + np.array([40, 24, 70]) * ramp) * 0.9).astype(np.uint8)
            screen = np.ascontiguousarray(np.broadcast_to(screen, (360, 480, 3)))
            pose = {"fold": 140} if item["kind"] in ("fold", "flip") else None
            picture = render(device_id, 480, 320, pose=pose, camera={"yaw": 28, "pitch": 14}, screens={"inner": screen})
            cv2.imwrite(str(path), cv2.cvtColor(picture, cv2.COLOR_RGBA2BGRA))
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "max-age=86400"})


@router.get("/{device_id}/model")
def model_file(device_id: str) -> FileResponse:
    """A device's model file (binary glTF), for the interface's device picker."""
    try:
        item = device(device_id)
    except KeyError:
        raise HTTPException(404, f"No device {device_id}") from None
    return FileResponse(LIBRARY / item["file"], media_type="model/gltf-binary", filename=item["file"])
