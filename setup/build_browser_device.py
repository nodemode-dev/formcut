"""Builds the browser-window device model (device contract 2) and prints its manifest entry.

The ten library models come from the 3d-mock-models generator; this one is built here, in code, so it can be read and
remade: a window 360 x 250 mm (a 16:10 content area under a 25 mm title bar), rounded 10 mm, 4 mm deep, with three
window controls and an address bar. The content area (M_Screen) and the title bar's parts sit 0.35 mm proud of the
body, a real gap rather than layers in one plane. Materials follow the finish rules in device_assets: M_Frame (body
and title bar), M_Back (back), M_BackInset (address bar). Original design, CC0-1.0.

    python setup/build_browser_device.py
"""

import hashlib
import json
import math
import struct
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "backend" / "app" / "device_library" / "browser-window.glb"
W, H, BAR, R, DEPTH, PROUD = 360.0, 250.0, 25.0, 10.0, 4.0, 0.35
MM = 0.001


def outline(x0, y0, x1, y1, radii, segments=12):
    """A rounded rectangle's outline, counter-clockwise; radii for (bottom-left, bottom-right, top-right, top-left)."""
    corners = [(x0, y0, 180), (x1, y0, 270), (x1, y1, 0), (x0, y1, 90)]
    points = []
    for (cx, cy, start), r in zip(corners, radii, strict=True):
        if r <= 0:
            points.append((cx, cy))
            continue
        ox = cx + (r if cx == x0 else -r)
        oy = cy + (r if cy == y0 else -r)
        for k in range(segments + 1):
            a = math.radians(start + 90 * k / segments)
            points.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return np.array(points, np.float64)


def disc(cx, cy, r, segments=32):
    return np.array(
        [(cx + r * math.cos(2 * math.pi * k / segments), cy + r * math.sin(2 * math.pi * k / segments)) for k in range(segments)]
    )


def flat(points, z, facing, uv_box=None):
    """A convex outline as a fan of triangles at depth z facing +z (1) or -z (-1)."""
    centre = points.mean(axis=0)
    pts = np.vstack([centre, points])
    n = len(points)
    tris = []
    for i in range(n):
        a, b = 1 + i, 1 + (i + 1) % n
        tris.append((0, a, b) if facing > 0 else (0, b, a))
    positions = np.c_[pts, np.full(len(pts), z)]
    normals = np.tile([0.0, 0.0, float(facing)], (len(pts), 1))
    if uv_box:
        x0, y0, x1, y1 = uv_box
        uvs = np.c_[(pts[:, 0] - x0) / (x1 - x0), (y1 - pts[:, 1]) / (y1 - y0)]
    else:
        uvs = np.c_[(pts[:, 0] + W / 2) / W, (H / 2 - pts[:, 1]) / H]
    return positions, normals, uvs, np.array(tris, np.uint32).reshape(-1)


def walls(points, z0, z1):
    """The outline extruded from z0 to z1, normals facing outward."""
    n = len(points)
    positions, normals, uvs, tris = [], [], [], []
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        edge = b - a
        normal = np.array([edge[1], -edge[0], 0.0])
        normal /= max(np.linalg.norm(normal), 1e-9)
        base = len(positions)
        for p, z in ((a, z0), (b, z0), (b, z1), (a, z1)):
            positions.append([p[0], p[1], z])
            normals.append(normal)
            uvs.append([0.0, 0.0])
        tris += [base, base + 1, base + 2, base, base + 2, base + 3]
    return np.array(positions), np.array(normals), np.array(uvs), np.array(tris, np.uint32)


def merge(*parts):
    positions, normals, uvs, tris, offset = [], [], [], [], 0
    for p, n, u, t in parts:
        positions.append(p)
        normals.append(n)
        uvs.append(u)
        tris.append(t + offset)
        offset += len(p)
    return np.vstack(positions), np.vstack(normals), np.vstack(uvs), np.concatenate(tris)


def build() -> tuple[bytes, int]:
    x0, y0, x1, y1 = -W / 2, -H / 2, W / 2, H / 2
    body = outline(x0, y0, x1, y1, (R, R, R, R))
    front, back = DEPTH / 2, -DEPTH / 2
    bar_y = y1 - BAR / 2
    content_top = y1 - BAR
    parts = {
        "M_Frame": merge(flat(body, front, 1), walls(body, back, front)),
        "M_Back": merge(flat(body, back, -1)),
        "M_Screen": merge(flat(outline(x0, y0, x1, content_top, (R, R, 0, 0)), front + PROUD, 1, (x0, y0, x1, content_top))),
        "M_BackInset": merge(flat(outline(-65, bar_y - 6.5, 65, bar_y + 6.5, (6.5, 6.5, 6.5, 6.5), 8), front + PROUD, 1)),
        "M_DotClose": merge(flat(disc(x0 + 14, bar_y, 3.2), front + PROUD, 1)),
        "M_DotMinimise": merge(flat(disc(x0 + 25, bar_y, 3.2), front + PROUD, 1)),
        "M_DotZoom": merge(flat(disc(x0 + 36, bar_y, 3.2), front + PROUD, 1)),
    }
    colours = {
        "M_Frame": ([0.92, 0.92, 0.93], 0.0, 0.45),
        "M_Back": ([0.85, 0.85, 0.86], 0.0, 0.55),
        "M_Screen": ([0.0, 0.0, 0.0], 0.0, 0.1),
        "M_BackInset": ([0.80, 0.80, 0.82], 0.0, 0.6),
        "M_DotClose": ([1.0, 0.11, 0.09], 0.0, 0.35),
        "M_DotMinimise": ([0.99, 0.50, 0.03], 0.0, 0.35),
        "M_DotZoom": ([0.02, 0.58, 0.07], 0.0, 0.35),
    }
    blob, views, accessors, primitives, materials = bytearray(), [], [], [], []
    triangles = 0

    def add(array, kind, target, minmax=False):
        data = np.ascontiguousarray(array, np.uint32 if kind == "SCALAR" else np.float32).tobytes()
        while len(blob) % 4:
            blob.append(0)
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target})
        blob.extend(data)
        accessor = {"bufferView": len(views) - 1, "componentType": 5125 if kind == "SCALAR" else 5126, "count": len(array), "type": kind}
        if minmax:
            accessor["min"] = [float(v) for v in np.min(array, axis=0)]
            accessor["max"] = [float(v) for v in np.max(array, axis=0)]
        accessors.append(accessor)
        return len(accessors) - 1

    for index, (name, (p, n, u, t)) in enumerate(parts.items()):
        colour, metallic, roughness = colours[name]
        materials.append(
            {
                "name": name,
                "pbrMetallicRoughness": {"baseColorFactor": [*colour, 1.0], "metallicFactor": metallic, "roughnessFactor": roughness},
            }
        )
        tangents = np.tile([1.0, 0.0, 0.0, 1.0], (len(p), 1))
        primitives.append(
            {
                "attributes": {
                    "POSITION": add(p * MM, "VEC3", 34962, True),
                    "NORMAL": add(n, "VEC3", 34962),
                    "TANGENT": add(tangents, "VEC4", 34962),
                    "TEXCOORD_0": add(u, "VEC2", 34962),
                },
                "indices": add(t, "SCALAR", 34963),
                "material": index,
            }
        )
        triangles += len(t) // 3
    extras = {
        "contract": 2,
        "id": "browser-window",
        "kind": "browser",
        "style": "window",
        "dimensionsMm": [W, H, DEPTH + PROUD],
        "finish": "light",
        "license": "CC0-1.0",
        "generator": "formcut setup/build_browser_device.py",
        "screen": {
            "material": "M_Screen",
            "activeMm": [W, H - BAR],
            "aspect": round(W / (H - BAR), 4),
            "suggestedPixels": [1440, 900],
            "cornerRadiusMm": R,
            "cutouts": [],
        },
    }
    document = {
        "asset": {"version": "2.0", "generator": extras["generator"]},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": "browser", "children": [1], "extras": {"formcut": extras}}, {"name": "window", "mesh": 0}],
        "meshes": [{"name": "window", "primitives": primitives}],
        "materials": materials,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(blob)}],
    }
    text = json.dumps(document, separators=(",", ":")).encode()
    text += b" " * (-len(text) % 4)
    blob += b"\0" * (-len(blob) % 4)
    body_len = 12 + 8 + len(text) + 8 + len(blob)
    glb = struct.pack("<III", 0x46546C67, 2, body_len) + struct.pack("<II", len(text), 0x4E4F534A) + text
    glb += struct.pack("<II", len(blob), 0x004E4942) + bytes(blob)
    return glb, triangles


if __name__ == "__main__":
    glb, triangles = build()
    OUT.write_bytes(glb)
    entry = {
        "id": "browser-window",
        "file": OUT.name,
        "sha256": hashlib.sha256(glb).hexdigest(),
        "bytes": len(glb),
        "triangles": triangles,
        "dimensionsMm": [W, H, DEPTH + PROUD],
        "finish": "light",
        "license": "CC0-1.0",
        "finishes": {
            "light": {
                "antenna": [0.5, 0.5, 0.5], "back": [0.85, 0.85, 0.86], "backSurface": "matte", "deck": [0.9, 0.9, 0.9],
                "deckSurface": "metal", "frame": [0.92, 0.92, 0.93], "frameRoughness": 0.45, "inset": [0.80, 0.80, 0.82],
                "key": [0.1, 0.1, 0.1],
            },
            "dark": {
                "antenna": [0.1, 0.1, 0.1], "back": [0.06, 0.06, 0.065], "backSurface": "matte", "deck": [0.1, 0.1, 0.1],
                "deckSurface": "metal", "frame": [0.11, 0.11, 0.12], "frameRoughness": 0.45, "inset": [0.2, 0.2, 0.22],
                "key": [0.1, 0.1, 0.1],
            },
        },
    }  # fmt: skip
    print(json.dumps(entry))
