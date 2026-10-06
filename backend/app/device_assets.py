"""A device file as data the 3D pass draws: nodes, primitives, materials, images, finishes and poses.

Finishes follow the generator's own rules (3d-mock-models generator/materials/library.py install): the manifest's
colour tables set each part's colour, metal or not, roughness and coat; non-metal colours are lifted as the generator
lifts them. The file carries its default finish; others are applied to the parsed materials.

Articulations rotate their hinge node about the recorded axis. The contract gives the angles but not which rotation
sign closes, and the library is not uniform (the 2-in-1's stand turns the other way from its lid), so the direction is
found from the geometry once per device: closed, a lid or stand lies against what it is hinged to; half closed, a fold
rises on the side its screen faces.
"""

import copy
import math
import threading
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import devices

SATIN_GAIN, SATIN_LIMIT = 1.6, 0.8
ALBEDO_GAIN, ALBEDO_LIMIT = 2.2, 0.85
BACK_ROUGHNESS = {"gloss": 0.05, "matte": 0.38}
_lock = threading.Lock()
_assets: dict[str, "Asset"] = {}


@dataclass
class Material:
    name: str
    base: list = field(default_factory=lambda: [1.0, 1.0, 1.0, 1.0])
    metallic: float = 1.0
    roughness: float = 1.0
    emissive: list = field(default_factory=lambda: [0.0, 0.0, 0.0])
    emissive_strength: float = 1.0
    normal_scale: float = 1.0
    occlusion_strength: float = 1.0
    clearcoat: float = 0.0
    clearcoat_roughness: float = 0.0
    anisotropy: float = 0.0
    anisotropy_rotation: float = 0.0
    specular: float = 1.0
    specular_colour: list = field(default_factory=lambda: [1.0, 1.0, 1.0])
    textures: dict = field(default_factory=dict)


@dataclass
class Primitive:
    node: int
    material: int
    positions: np.ndarray
    normals: np.ndarray
    tangents: np.ndarray
    uvs: np.ndarray
    indices: np.ndarray
    uvs1: np.ndarray


def _texture_ref(document: dict, info: dict | None) -> dict | None:
    if not info:
        return None
    transform = info.get("extensions", {}).get("KHR_texture_transform", {})
    return {
        "image": document["textures"][info["index"]]["source"],
        "set": int(transform.get("texCoord", info.get("texCoord", 0))),
        "offset": transform.get("offset", [0.0, 0.0]),
        "scale": transform.get("scale", [1.0, 1.0]),
        "rotation": transform.get("rotation", 0.0),
    }


def _material(document: dict, item: dict) -> Material:
    pbr = item.get("pbrMetallicRoughness", {})
    ext = item.get("extensions", {})
    coat = ext.get("KHR_materials_clearcoat", {})
    aniso = ext.get("KHR_materials_anisotropy", {})
    spec = ext.get("KHR_materials_specular", {})
    material = Material(
        name=item.get("name", ""),
        base=list(pbr.get("baseColorFactor", [1.0, 1.0, 1.0, 1.0])),
        metallic=float(pbr.get("metallicFactor", 1.0)),
        roughness=float(pbr.get("roughnessFactor", 1.0)),
        emissive=list(item.get("emissiveFactor", [0.0, 0.0, 0.0])),
        emissive_strength=float(ext.get("KHR_materials_emissive_strength", {}).get("emissiveStrength", 1.0)),
        normal_scale=float(item.get("normalTexture", {}).get("scale", 1.0)),
        occlusion_strength=float(item.get("occlusionTexture", {}).get("strength", 1.0)),
        clearcoat=float(coat.get("clearcoatFactor", 0.0)),
        clearcoat_roughness=float(coat.get("clearcoatRoughnessFactor", 0.0)),
        anisotropy=float(aniso.get("anisotropyStrength", 0.0)),
        anisotropy_rotation=float(aniso.get("anisotropyRotation", 0.0)),
        specular=float(spec.get("specularFactor", 1.0)),
        specular_colour=list(spec.get("specularColorFactor", [1.0, 1.0, 1.0])),
    )
    for slot, info in (
        ("base", pbr.get("baseColorTexture")),
        ("orm", pbr.get("metallicRoughnessTexture")),
        ("normal", item.get("normalTexture")),
        ("occlusion", item.get("occlusionTexture")),
        ("emissive", item.get("emissiveTexture")),
    ):
        ref = _texture_ref(document, info)
        if ref:
            material.textures[slot] = ref
    return material


def _lifted(colour: list) -> list:
    peak = max(colour)
    if peak <= 0:
        return list(colour)
    scale = max(1.0, min(ALBEDO_GAIN, ALBEDO_LIMIT / peak))
    return [c * scale for c in colour]


def rotation(axis: str, degrees: float) -> np.ndarray:
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4)
    if axis == "x":
        m[1:3, 1:3] = [[c, -s], [s, c]]
    elif axis == "y":
        m[0, 0], m[0, 2], m[2, 0], m[2, 2] = c, s, -s, c
    else:
        m[0:2, 0:2] = [[c, -s], [s, c]]
    return m


class Asset:
    """One device, parsed once: the drawing data, the finish rules and the poses."""

    def __init__(self, device_id: str):
        self.info = devices.device(device_id)
        document, blob = devices.read_glb(devices.LIBRARY / self.info["file"])
        self.nodes = document["nodes"]
        self.root = document["scenes"][document.get("scene", 0)]["nodes"][0]
        self.parent = {child: i for i, n in enumerate(self.nodes) for child in n.get("children", [])}
        self.local = [devices.node_matrix(n) for n in self.nodes]
        self.by_name = {n.get("name"): i for i, n in enumerate(self.nodes)}
        self.materials = [_material(document, m) for m in document["materials"]]
        self.images = []
        for image in document.get("images", []):
            view = document["bufferViews"][image["bufferView"]]
            raw = np.frombuffer(blob, np.uint8, count=view["byteLength"], offset=view.get("byteOffset", 0))
            decoded = cv2.imdecode(raw, cv2.IMREAD_UNCHANGED)
            if decoded.ndim == 2:
                decoded = cv2.cvtColor(decoded, cv2.COLOR_GRAY2RGBA)
            elif decoded.shape[2] == 3:
                decoded = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGBA)
            else:
                decoded = cv2.cvtColor(decoded, cv2.COLOR_BGRA2RGBA)
            self.images.append(decoded if decoded.dtype == np.uint8 else (decoded / 257).astype(np.uint8))
        self.primitives = []
        for index, node in enumerate(self.nodes):
            if "mesh" not in node:
                continue
            for p in document["meshes"][node["mesh"]]["primitives"]:
                attrs = p["attributes"]
                positions = devices.accessor(document, blob, attrs["POSITION"]).astype(np.float32)
                count = len(positions)
                normals = devices.accessor(document, blob, attrs["NORMAL"]).astype(np.float32) if "NORMAL" in attrs else np.tile([0, 0, 1], (count, 1)).astype(np.float32)
                tangents = devices.accessor(document, blob, attrs["TANGENT"]).astype(np.float32) if "TANGENT" in attrs else np.tile([1, 0, 0, 1], (count, 1)).astype(np.float32)
                uvs = devices.accessor(document, blob, attrs["TEXCOORD_0"]).astype(np.float32) if "TEXCOORD_0" in attrs else np.zeros((count, 2), np.float32)
                indices = devices.accessor(document, blob, p["indices"]).reshape(-1).astype(np.uint32) if "indices" in p else np.arange(count, dtype=np.uint32)
                uvs1 = devices.accessor(document, blob, attrs["TEXCOORD_1"]).astype(np.float32) if "TEXCOORD_1" in attrs else uvs
                self.primitives.append(Primitive(index, p.get("material", 0), positions, normals, tangents, uvs, indices, uvs1))
        self.signs = {a["name"]: self._direction(a) for a in self.info["articulations"]}
        # Baked occlusion is shared per material, and the parts on a hinge share materials (so one atlas) with the
        # body: the lid's outer face read the deck's darkening round the trackpad. It is also only right in the pose
        # it was baked in. A hinged part's primitives on a material the fixed body also uses draw without it.
        moving: set[int] = set()
        for art in self.info["articulations"]:
            moving |= set(self.subtree(self.by_name[art["node"]]))
        fixed = {p.material for p in self.primitives if p.node not in moving}
        self.no_occlusion = {i for i, p in enumerate(self.primitives) if p.node in moving and p.material in fixed}

    def subtree(self, index: int) -> list[int]:
        out, stack = [], [index]
        while stack:
            i = stack.pop()
            out.append(i)
            stack.extend(self.nodes[i].get("children", []))
        return out

    def world(self, pose: dict | None = None, signs: dict | None = None) -> list[np.ndarray]:
        """Every node's matrix with the articulations turned to the pose's angles (degrees; missing ones at rest)."""
        turns = {}
        for art in self.info["articulations"]:
            target = (pose or {}).get(art["name"])
            if target is None:
                continue
            target = min(max(float(target), art["closedDeg"]), art["maxDeg"])
            sign = (signs or self.signs)[art["name"]]
            turns[self.by_name[art["node"]]] = rotation(art["axis"], sign * (target - art["openDeg"]))
        out: list[np.ndarray] = [np.eye(4)] * len(self.nodes)
        order = self.subtree(self.root)
        for i in order:
            parent = out[self.parent[i]] if i in self.parent else np.eye(4)
            out[i] = parent @ self.local[i] @ turns.get(i, np.eye(4))
        return out

    def points(self, matrices: list[np.ndarray], nodes: set | None = None, stride: int = 3) -> np.ndarray:
        """Posed vertex positions in metres (every stride-th vertex), optionally of some nodes only."""
        chunks = []
        for p in self.primitives:
            if nodes is not None and p.node not in nodes:
                continue
            pts = p.positions[::stride].astype(np.float64)
            chunks.append((matrices[p.node] @ np.c_[pts, np.ones(len(pts))].T).T[:, :3])
        return np.concatenate(chunks) if chunks else np.zeros((0, 3))

    def _direction(self, art: dict) -> int:
        """Which rotation sign closes this articulation, from the geometry."""
        hinge = self.by_name[art["node"]]
        moving = set(self.subtree(hinge))
        if art["name"] == "fold":
            screen = next(p for p in self.primitives if self.nodes[p.node].get("name") == "screen")
            facing = (self.world()[screen.node][:3, :3] @ screen.normals.mean(axis=0).astype(np.float64))
            scores = {}
            for sign in (1, -1):
                half = (art["closedDeg"] + art["openDeg"]) / 2
                m = self.world({art["name"]: half}, {art["name"]: sign})
                scores[sign] = float(self.points(m, moving).mean(axis=0) @ facing)
            return max(scores, key=scores.get)
        owner = self.parent.get(hinge, self.root)
        holder = set(self.subtree(owner)) - moving
        scores = {}
        for sign in (1, -1):
            m = self.world({art["name"]: art["closedDeg"]}, {**self.signs_default(), art["name"]: sign})
            scores[sign] = float(np.linalg.norm(self.points(m, moving).mean(axis=0) - self.points(m, holder).mean(axis=0)))
        return min(scores, key=scores.get)

    def signs_default(self) -> dict:
        return {a["name"]: 1 for a in self.info["articulations"]}

    def finished(self, finish: str | None) -> list[Material]:
        """The materials in a finish (the file's own when None or the default), by the generator's rules."""
        materials = copy.deepcopy(self.materials)
        if not finish or finish == self.info["finish"]:
            return self._photographic(materials)
        spec = self.info["finishes"].get(finish)
        if spec is None:
            raise ValueError(f"{self.info['id']} has no finish {finish}; it has {', '.join(sorted(self.info['finishes']))}")
        default = self.info["finishes"][self.info["finish"]]
        by = {m.name: m for m in materials}
        bead = next(
            (by[n].textures["normal"] for n in ("M_Back", "M_BackInset", "M_Deck") if n in by and "normal" in by[n].textures),
            by["M_Frame"].textures.get("normal") if "M_Frame" in by and self.info["kind"] != "laptop" else None,
        )
        metal = list(spec["frame"])
        surface, fabric = spec["backSurface"], spec["deckSurface"] == "fabric"
        for name in ("M_Frame", "M_Chamfer", "M_LensRing"):
            if name in by:
                by[name].base[:3] = metal
        if "M_Frame" in by and self.info["kind"] != "laptop":
            old = min(SATIN_LIMIT, default["frameRoughness"] * SATIN_GAIN)
            by["M_Frame"].roughness *= min(SATIN_LIMIT, spec["frameRoughness"] * SATIN_GAIN) / max(old, 1e-3)
        metal_roughness = min(SATIN_LIMIT, spec["frameRoughness"] * SATIN_GAIN)
        for name, colour, metal_r, other_r in (("M_Back", spec["back"], metal_roughness, BACK_ROUGHNESS.get(surface, 0.38)), ("M_BackInset", spec["inset"], 0.45, 0.32)):
            if name not in by:
                continue
            m = by[name]
            if surface == "metal":
                m.base[:3], m.metallic, m.roughness, m.clearcoat = list(colour), 1.0, metal_r, 0.0
                if bead:
                    m.textures["normal"] = bead
            else:
                m.base[:3], m.metallic, m.roughness = _lifted(list(colour)), 0.0, other_r
                m.clearcoat = 1.0 if (name == "M_Back" and surface == "gloss") else 0.0
                m.clearcoat_roughness = 0.02
                m.textures.pop("normal", None)
        if "M_Key" in by:
            by["M_Key"].base[:3] = list(spec["key"])
        if "M_Antenna" in by:
            by["M_Antenna"].base[:3] = list(spec["antenna"])
        deck = _lifted(list(spec["deck"])) if fabric else list(spec["deck"])
        if "M_Deck" in by:
            by["M_Deck"].base[:3] = deck
            if fabric:
                by["M_Deck"].metallic, by["M_Deck"].roughness = 0.0, 0.9
                by["M_Deck"].textures = {k: v for k, v in by["M_Deck"].textures.items() if k == "occlusion"}
        if "M_Trackpad" in by:
            by["M_Trackpad"].base[:3] = [c * 0.88 for c in deck]
        return self._photographic(materials)

    def _photographic(self, materials: list[Material]) -> list[Material]:
        """Materials as they read on camera, correcting what the files do at product distances.

        The metals take roughness and metalness from one sixth of a 256 x 256 atlas, about 42 texels across a whole
        lid or deck: magnified that far its variation reads as blotches that repeat. The tile's average replaces it.
        Micro-normal maps at full strength read as a coarse pattern rather than a fine grain, so they are softened.
        The trackpad, matte grey plastic as authored, becomes etched glass: darker, a little glossier, coated."""
        softer = {"M_Frame": 0.3, "M_Deck": 0.35, "M_Back": 0.35, "M_BackInset": 0.35, "M_Trackpad": 0.3}
        for m in materials:
            ref = m.textures.get("orm")
            if ref and m.name in ("M_Frame", "M_Deck", "M_Back", "M_BackInset", "M_Chamfer", "M_LensRing"):
                image = self.images[ref["image"]]
                h, w = image.shape[:2]
                x0, y0 = ref["offset"][0] % 1.0, ref["offset"][1] % 1.0
                x1, y1 = x0 + abs(ref["scale"][0]), y0 + abs(ref["scale"][1])
                tile = image[int(y0 * h) : max(int(y0 * h) + 1, int(min(y1, 1.0) * h)), int(x0 * w) : max(int(x0 * w) + 1, int(min(x1, 1.0) * w))]
                m.roughness *= float(tile[..., 1].mean()) / 255
                m.metallic *= float(tile[..., 2].mean()) / 255
                m.textures.pop("orm")
            if "normal" in m.textures:
                m.normal_scale *= softer.get(m.name, 0.5)
            if m.name == "M_Trackpad":
                m.base[:3] = [c * 0.7 for c in m.base[:3]]
                m.roughness = min(m.roughness, 0.18)
                m.clearcoat, m.clearcoat_roughness = 0.6, 0.08
        return materials


def asset(device_id: str) -> Asset:
    """A device's parsed data, once per process."""
    with _lock:
        if device_id not in _assets:
            _assets[device_id] = Asset(device_id)
        return _assets[device_id]
