"""The device 3D pass: a device from the library, posed, lit and drawn into an RGBA picture.

It runs on the engine's wgpu device (wgpu.utils.get_default_device), on a GPU or, with none, on a software adapter;
there is no CPU alternative, so unlike the compositor it does not refuse software adapters. The picture is the
device's layer: transparent around it, a contact shadow under it, straight-alpha sRGB like any decoded layer, so the
preview (frames from the engine) and the export are the same pass.
"""

import dataclasses
import math
import threading

import cv2
import numpy as np

from . import device_scene
from .device_assets import Material, asset

SAMPLES = 4
COLOUR = "rgba8unorm-srgb"
DEPTH_COLOUR = "rgba16float"  # each pixel's distance from the camera, for depth of field (resolvable, unlike depth)
_lock = threading.Lock()
_state: dict = {}

SHADER = """
struct Frame {
    view_proj: mat4x4<f32>,
    eye: vec4<f32>,
    look: vec4<f32>,
    glow: vec4<f32>,
    sh: array<vec4<f32>, 9>,
};
struct Draw {
    model: mat4x4<f32>,
    normal: mat4x4<f32>,
    layer: vec4<f32>,
};
struct Material {
    base: vec4<f32>,
    emissive: vec4<f32>,
    pbr: vec4<f32>,
    coat: vec4<f32>,
    spec: vec4<f32>,
    has: vec4<f32>,
    role: vec4<f32>,
    xf_base: vec4<f32>,
    xf_orm: vec4<f32>,
    xf_normal: vec4<f32>,
    xf_occ: vec4<f32>,
    xf_emis: vec4<f32>,
    turn: vec4<f32>,
    turn2: vec4<f32>,
    sets: vec4<f32>,
};
@group(0) @binding(0) var<uniform> frame: Frame;
@group(0) @binding(1) var env: texture_2d_array<f32>;
@group(0) @binding(2) var env_sampler: sampler;
@group(1) @binding(0) var<uniform> draw: Draw;
@group(1) @binding(1) var<uniform> material: Material;
@group(1) @binding(2) var t_base: texture_2d<f32>;
@group(1) @binding(3) var t_orm: texture_2d<f32>;
@group(1) @binding(4) var t_normal: texture_2d<f32>;
@group(1) @binding(5) var t_occ: texture_2d<f32>;
@group(1) @binding(6) var t_emis: texture_2d<f32>;
@group(1) @binding(7) var t_screen: texture_2d<f32>;
@group(1) @binding(8) var tex_sampler: sampler;
@group(1) @binding(9) var screen_sampler: sampler;

struct VIn {
    @location(0) pos: vec3<f32>,
    @location(1) nrm: vec3<f32>,
    @location(2) tan: vec4<f32>,
    @location(3) uv: vec2<f32>,
    @location(4) uv1: vec2<f32>,
};
struct VOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) world: vec3<f32>,
    @location(1) nrm: vec3<f32>,
    @location(2) tan: vec4<f32>,
    @location(3) uv: vec2<f32>,
    @location(4) uv1: vec2<f32>,
};

@vertex
fn vs_main(v: VIn) -> VOut {
    var o: VOut;
    var w = draw.model * vec4<f32>(v.pos, 1.0);
    // The models lay their display layers (border glass, screen, cover glass, lens) in the very plane of the body's
    // front, so the depth test had no winner and the lid's rim came out as marching dashes. A layered surface slides
    // toward the eye along its own sightline: it lands on the same pixel, and its order over the body is certain.
    w = vec4<f32>(w.xyz + normalize(frame.eye.xyz - w.xyz) * draw.layer.x, 1.0);
    o.world = w.xyz;
    o.clip = frame.view_proj * w;
    o.nrm = (draw.normal * vec4<f32>(v.nrm, 0.0)).xyz;
    o.tan = vec4<f32>((draw.model * vec4<f32>(v.tan.xyz, 0.0)).xyz, v.tan.w);
    o.uv = v.uv;
    o.uv1 = v.uv1;
    return o;
}

fn pick(i: VOut, which: f32) -> vec2<f32> {
    return select(i.uv, i.uv1, which > 0.5);
}

fn xf(uv: vec2<f32>, t: vec4<f32>, r: f32) -> vec2<f32> {
    let s = uv * t.zw;
    let c = cos(r);
    let n = sin(r);
    return vec2<f32>(c * s.x - n * s.y, n * s.x + c * s.y) + t.xy;
}

fn env_uv(d: vec3<f32>) -> vec2<f32> {
    let r = frame.look.y;
    let x = d.x * cos(r) - d.z * sin(r);
    let z = d.x * sin(r) + d.z * cos(r);
    return vec2<f32>(atan2(x, -z) / 6.2831853 + 0.5, acos(clamp(d.y, -1.0, 1.0)) / 3.14159265);
}

fn prefiltered(d: vec3<f32>, rough: f32) -> vec3<f32> {
    let top = frame.look.z - 1.0;
    let f = clamp(rough, 0.0, 1.0) * top;
    let i0 = floor(f);
    let i1 = min(i0 + 1.0, top);
    let uv = env_uv(d);
    let a = textureSampleLevel(env, env_sampler, uv, i32(i0), 0.0).rgb;
    let b = textureSampleLevel(env, env_sampler, uv, i32(i1), 0.0).rgb;
    return mix(a, b, f - i0);
}

fn irradiance(n0: vec3<f32>) -> vec3<f32> {
    let r = frame.look.y;
    let n = vec3<f32>(n0.x * cos(r) - n0.z * sin(r), n0.y, n0.x * sin(r) + n0.z * cos(r));
    var e = frame.sh[0].rgb * 0.282095;
    e += frame.sh[1].rgb * 0.488603 * n.y;
    e += frame.sh[2].rgb * 0.488603 * n.z;
    e += frame.sh[3].rgb * 0.488603 * n.x;
    e += frame.sh[4].rgb * 1.092548 * n.x * n.y;
    e += frame.sh[5].rgb * 1.092548 * n.y * n.z;
    e += frame.sh[6].rgb * 0.315392 * (3.0 * n.z * n.z - 1.0);
    e += frame.sh[7].rgb * 1.092548 * n.x * n.z;
    e += frame.sh[8].rgb * 0.546274 * (n.x * n.x - n.y * n.y);
    return max(e, vec3<f32>(0.0));
}

fn env_brdf(f0: vec3<f32>, f90: f32, rough: f32, nv: f32) -> vec3<f32> {
    let c0 = vec4<f32>(-1.0, -0.0275, -0.572, 0.022);
    let c1 = vec4<f32>(1.0, 0.0425, 1.04, -0.04);
    let r = rough * c0 + c1;
    let a004 = min(r.x * r.x, exp2(-9.28 * nv)) * r.x + r.y;
    let ab = vec2<f32>(-1.04, 1.04) * a004 + r.zw;
    return f0 * ab.x + vec3<f32>(f90 * ab.y);
}

fn neutral(c0: vec3<f32>) -> vec3<f32> {
    let start = 0.76;
    let x = min(c0.r, min(c0.g, c0.b));
    let offset = select(0.04, x - 6.25 * x * x, x < 0.08);
    var c = c0 - vec3<f32>(offset);
    let peak = max(c.r, max(c.g, c.b));
    if (peak < start) {
        return c;
    }
    let d = 1.0 - start;
    let top = 1.0 - d * d / (peak + d - start);
    c = c * (top / peak);
    let g = 1.0 - 1.0 / (0.15 * (peak - top) + 1.0);
    return mix(c, vec3<f32>(top), g);
}

// colour, and the pixel's distance from the camera (for depth of field, averaged over the samples like the colour)
struct FOut {
    @location(0) colour: vec4<f32>,
    @location(1) depth: vec4<f32>,
};

@fragment
fn fs_main(i: VOut, @builtin(front_facing) front: bool) -> FOut {
    var n = normalize(i.nrm);
    if (!front) {
        n = -n;
    }
    let v = normalize(frame.eye.xyz - i.world);
    var base = material.base;
    if (material.has.x > 0.5) {
        base = base * textureSample(t_base, tex_sampler, xf(pick(i, material.sets.x), material.xf_base, material.turn.x));
    }
    var metal = material.pbr.x;
    var rough = material.pbr.y;
    if (material.has.y > 0.5) {
        let s = textureSample(t_orm, tex_sampler, xf(pick(i, material.sets.y), material.xf_orm, material.turn.y));
        rough = rough * s.g;
        metal = metal * s.b;
    }
    rough = clamp(rough, 0.03, 1.0);
    // specular anti-aliasing: where the normal turns faster than a pixel can show (thin bevels, chamfers), widen the
    // lobe by the normal's variance across the pixel instead of letting highlights sparkle from sample to sample
    let gn = normalize(i.nrm);
    let variance = 0.5 * (dot(dpdx(gn), dpdx(gn)) + dot(dpdy(gn), dpdy(gn)));
    let widen = min(2.0 * variance, 0.18);
    rough = sqrt(sqrt(clamp(rough * rough * rough * rough + widen, 0.0, 1.0)));
    var t = i.tan.xyz - n * dot(n, i.tan.xyz);
    t = select(vec3<f32>(1.0, 0.0, 0.0), normalize(t), length(t) > 1e-6);
    let b = cross(n, t) * select(1.0, -1.0, i.tan.w < 0.0);
    var nm = n;
    if (material.has.z > 0.5) {
        let s = textureSample(t_normal, tex_sampler, xf(pick(i, material.sets.z), material.xf_normal, material.turn.z)).xyz * 2.0 - 1.0;
        nm = normalize(t * s.x * material.pbr.z + b * s.y * material.pbr.z + n * s.z);
    }
    var ao = 1.0;
    if (material.has.w > 0.5) {
        ao = 1.0 + material.pbr.w * (textureSample(t_occ, tex_sampler, xf(pick(i, material.sets.w), material.xf_occ, material.turn.w)).r - 1.0);
    }
    let nv = clamp(dot(nm, v), 1e-4, 1.0);
    let dielectric = min(vec3<f32>(0.04) * material.spec.rgb, vec3<f32>(1.0)) * material.spec.w;
    let f0 = mix(dielectric, base.rgb, metal);
    let f90 = mix(material.spec.w, 1.0, metal);
    var rn = nm;
    if (material.coat.z > 0.0) {
        let along = normalize(t * cos(material.coat.w) + b * sin(material.coat.w));
        let across = cross(along, v);
        let bent = cross(across, along);
        rn = normalize(mix(nm, bent, material.coat.z * 0.6));
    }
    let r = reflect(-v, rn);
    let spec_occ = clamp(pow(nv + ao, exp2(-16.0 * rough - 1.0)) - 1.0 + ao, 0.0, 1.0);
    var colour = irradiance(nm) * base.rgb * (1.0 - metal) * ao + prefiltered(r, rough) * env_brdf(f0, f90, rough, nv) * spec_occ;
    var emit = material.emissive.rgb * material.emissive.w;
    if (material.role.x > 0.5) {
        emit = emit * textureSample(t_emis, tex_sampler, xf(pick(i, material.turn2.y), material.xf_emis, material.turn2.x)).rgb;
    }
    if (material.role.z > 0.5) {
        emit = emit * frame.glow.rgb * frame.look.w;
    }
    if (material.role.y > 0.5) {
        emit = emit + textureSample(t_screen, screen_sampler, i.uv).rgb * frame.glow.w;
    }
    colour = colour + emit;
    if (material.coat.x > 0.0) {
        let cv = clamp(dot(n, v), 1e-4, 1.0);
        let fc = (0.04 + 0.96 * pow(1.0 - cv, 5.0)) * material.coat.x;
        let cr0 = clamp(material.coat.y, 0.03, 1.0);
        let cr = sqrt(sqrt(clamp(cr0 * cr0 * cr0 * cr0 + widen, 0.0, 1.0)));
        colour = colour * (1.0 - fc) + prefiltered(reflect(-v, n), cr) * fc;
    }
    return FOut(vec4<f32>(neutral(colour * frame.eye.w), 1.0), vec4<f32>(length(frame.eye.xyz - i.world), 0.0, 0.0, 1.0));
}
"""

SHADOW_SHADER = """
struct Frame {
    view_proj: mat4x4<f32>,
    eye: vec4<f32>,
    look: vec4<f32>,
    glow: vec4<f32>,
    sh: array<vec4<f32>, 9>,
};
@group(0) @binding(0) var<uniform> frame: Frame;
@group(1) @binding(0) var shadow_map: texture_2d<f32>;
@group(1) @binding(1) var shadow_sampler: sampler;

struct SOut {
    @builtin(position) clip: vec4<f32>,
    @location(0) uv: vec2<f32>,
};

@vertex
fn vs_shadow(@location(0) pos: vec3<f32>, @location(1) uv: vec2<f32>) -> SOut {
    var o: SOut;
    o.clip = frame.view_proj * vec4<f32>(pos, 1.0);
    o.uv = uv;
    return o;
}

struct ShadowOut {
    @location(0) colour: vec4<f32>,
    @location(1) depth: vec4<f32>,
};

@fragment
fn fs_shadow(i: SOut) -> ShadowOut {
    let a = textureSample(shadow_map, shadow_sampler, i.uv).r * frame.glow.w;
    return ShadowOut(vec4<f32>(0.0, 0.0, 0.0, a), vec4<f32>(0.0));
}
"""


def _gpu():
    if "device" not in _state:
        import wgpu
        from wgpu.utils import get_default_device

        _state["wgpu"] = wgpu
        _state["device"] = get_default_device()
    return _state["wgpu"], _state["device"]


def _mips(image: np.ndarray) -> list[np.ndarray]:
    levels = [image]
    while max(levels[-1].shape[:2]) > 1:
        h, w = levels[-1].shape[:2]
        levels.append(cv2.resize(levels[-1], (max(1, w // 2), max(1, h // 2)), interpolation=cv2.INTER_AREA))
    return levels


def _texture(image: np.ndarray, srgb: bool, mipmapped: bool = True):
    wgpu, device = _gpu()
    levels = _mips(image) if mipmapped else [image]
    h, w = image.shape[:2]
    texture = device.create_texture(
        size=(w, h, 1),
        format=wgpu.TextureFormat.rgba8unorm_srgb if srgb else wgpu.TextureFormat.rgba8unorm,
        usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        mip_level_count=len(levels),
    )
    for level, pixels in enumerate(levels):
        lh, lw = pixels.shape[:2]
        device.queue.write_texture(
            {"texture": texture, "mip_level": level, "origin": (0, 0, 0)},
            np.ascontiguousarray(pixels, dtype=np.uint8),
            {"offset": 0, "bytes_per_row": lw * 4, "rows_per_image": lh},
            (lw, lh, 1),
        )
    return texture


def _shared() -> dict:
    """The pipelines, samplers, the studio's maps and the placeholder textures, once per process."""
    if "pipeline" in _state:
        return _state
    wgpu, device = _gpu()
    module = device.create_shader_module(code=SHADER)
    shadow_module = device.create_shader_module(code=SHADOW_SHADER)
    floats = lambda n, loc, off: {"format": f"float32x{n}", "offset": off, "shader_location": loc}  # noqa: E731
    _state["pipeline"] = device.create_render_pipeline(
        layout="auto",
        vertex={
            "module": module,
            "entry_point": "vs_main",
            "buffers": [
                {"array_stride": 12, "attributes": [floats(3, 0, 0)]},
                {"array_stride": 12, "attributes": [floats(3, 1, 0)]},
                {"array_stride": 16, "attributes": [floats(4, 2, 0)]},
                {"array_stride": 8, "attributes": [floats(2, 3, 0)]},
                {"array_stride": 8, "attributes": [floats(2, 4, 0)]},
            ],
        },
        primitive={"topology": "triangle-list", "cull_mode": "none"},
        depth_stencil={"format": "depth32float", "depth_write_enabled": True, "depth_compare": "less"},
        multisample={"count": SAMPLES},
        fragment={"module": module, "entry_point": "fs_main", "targets": [{"format": COLOUR}, {"format": DEPTH_COLOUR}]},
    )
    premultiplied = {"src_factor": "one", "dst_factor": "one-minus-src-alpha", "operation": "add"}
    _state["shadow_pipeline"] = device.create_render_pipeline(
        layout="auto",
        vertex={
            "module": shadow_module,
            "entry_point": "vs_shadow",
            "buffers": [{"array_stride": 20, "attributes": [floats(3, 0, 0), floats(2, 1, 12)]}],
        },
        primitive={"topology": "triangle-list", "cull_mode": "none"},
        depth_stencil={"format": "depth32float", "depth_write_enabled": False, "depth_compare": "less"},
        multisample={"count": SAMPLES},
        fragment={
            "module": shadow_module,
            "entry_point": "fs_shadow",
            "targets": [
                {"format": COLOUR, "blend": {"color": premultiplied, "alpha": premultiplied}},
                {"format": DEPTH_COLOUR, "write_mask": 0},
            ],
        },
    )
    _state["repeat"] = device.create_sampler(
        address_mode_u="repeat", address_mode_v="repeat", mag_filter="linear", min_filter="linear", mipmap_filter="linear"
    )
    _state["clamp"] = device.create_sampler(
        address_mode_u="clamp-to-edge", address_mode_v="clamp-to-edge", mag_filter="linear", min_filter="linear", mipmap_filter="linear"
    )
    _state["env_sampler"] = device.create_sampler(
        address_mode_u="repeat", address_mode_v="clamp-to-edge", mag_filter="linear", min_filter="linear"
    )
    one = lambda colour: _texture(np.full((1, 1, 4), colour, np.uint8), srgb=False, mipmapped=False).create_view()  # noqa: E731
    _state["blank"] = {"white": one((255, 255, 255, 255)), "normal": one((128, 128, 255, 255)), "black": one((0, 0, 0, 255))}
    _state["frame"] = device.create_buffer(size=256, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)
    return _state


def _env(preset: str) -> tuple:
    """A lighting preset on the GPU (its prefiltered maps as a texture array), its level count and harmonics."""
    key = ("env", preset)
    if key not in _state:
        wgpu, device = _gpu()
        env = device_scene.environment(preset)
        levels = env["levels"]
        count, h, w = levels.shape[:3]
        texture = device.create_texture(
            size=(w, h, count), format=wgpu.TextureFormat.rgba16float, usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST
        )
        rgba = np.concatenate([levels, np.ones((count, h, w, 1), np.float32)], axis=-1).astype(np.float16)
        device.queue.write_texture(
            {"texture": texture, "mip_level": 0, "origin": (0, 0, 0)},
            rgba,
            {"offset": 0, "bytes_per_row": w * 8, "rows_per_image": h},
            (w, h, count),
        )
        _state[key] = (texture.create_view(dimension="2d-array"), count, env["harmonics"])
    return _state[key]


def _material_block(m: Material, screen: bool, legend: bool) -> np.ndarray:
    def xf(slot):
        ref = m.textures.get(slot)
        return [*ref["offset"], *ref["scale"]] if ref else [0.0, 0.0, 1.0, 1.0]

    def turn(slot):
        ref = m.textures.get(slot)
        return ref["rotation"] if ref else 0.0

    def uv_set(slot):
        ref = m.textures.get(slot)
        return float(ref.get("set", 0)) if ref else 0.0

    has = [float(s in m.textures) for s in ("base", "orm", "normal", "occlusion")]
    block = [
        *m.base,
        *m.emissive,
        m.emissive_strength,
        m.metallic,
        m.roughness,
        m.normal_scale,
        m.occlusion_strength,
        m.clearcoat,
        m.clearcoat_roughness,
        m.anisotropy,
        m.anisotropy_rotation,
        *m.specular_colour,
        m.specular,
        *has,
        float("emissive" in m.textures),
        float(screen),
        float(legend),
        0.0,
        *xf("base"),
        *xf("orm"),
        *xf("normal"),
        *xf("occlusion"),
        *xf("emissive"),
        turn("base"),
        turn("orm"),
        turn("normal"),
        turn("occlusion"),
        turn("emissive"),
        uv_set("emissive"),
        0.0,
        0.0,
        uv_set("base"),
        uv_set("orm"),
        uv_set("normal"),
        uv_set("occlusion"),
    ]
    return np.array(block, np.float32)


class _Prepared:
    """A device's GPU resources: vertex and index buffers per primitive, textures, and bind groups per finish."""

    def __init__(self, device_id: str):
        wgpu, device = _gpu()
        self.asset = asset(device_id)
        usage = wgpu.BufferUsage
        self.buffers = []
        for p in self.asset.primitives:
            self.buffers.append(
                {
                    "vertex": [
                        device.create_buffer_with_data(data=np.ascontiguousarray(a), usage=usage.VERTEX)
                        for a in (p.positions, p.normals, p.tangents, p.uvs, p.uvs1)
                    ],
                    "index": device.create_buffer_with_data(data=np.ascontiguousarray(p.indices), usage=usage.INDEX),
                    "count": len(p.indices),
                    "draw": device.create_buffer(size=144, usage=usage.UNIFORM | usage.COPY_DST),
                    "material": device.create_buffer(size=256, usage=usage.UNIFORM | usage.COPY_DST),
                }
            )
        self.textures: dict = {}
        self.groups: dict = {}
        self.screens: dict = {}

    def view(self, image: int, srgb: bool):
        key = (image, srgb)
        if key not in self.textures:
            self.textures[key] = _texture(self.asset.images[image], srgb).create_view()
        return self.textures[key]

    def screen(self, slot: str, picture: np.ndarray | None):
        """The texture a screen slot shows; None turns the screen off."""
        if picture is None:
            return _state["blank"]["black"]
        if picture.shape[2] == 3:
            picture = np.dstack([picture, np.full(picture.shape[:2], 255, np.uint8)])
        h, w = picture.shape[:2]
        held = self.screens.get(slot)
        if held is None or held[1] != (w, h):
            texture = _texture(picture, srgb=True, mipmapped=False)
            self.screens[slot] = (texture, (w, h), texture.create_view())
        else:
            _gpu()[1].queue.write_texture(
                {"texture": held[0], "mip_level": 0, "origin": (0, 0, 0)},
                np.ascontiguousarray(picture),
                {"offset": 0, "bytes_per_row": w * 4, "rows_per_image": h},
                (w, h, 1),
            )
        return self.screens[slot][2]

    def group(self, index: int, material: Material, screen_view):
        _, device = _gpu()
        key = (index, tuple(sorted((k, v["image"]) for k, v in material.textures.items())), id(screen_view))
        if key not in self.groups:

            def tex(slot, srgb, fallback):
                ref = material.textures.get(slot)
                return self.view(ref["image"], srgb) if ref else _state["blank"][fallback]

            entries = [
                {"binding": 0, "resource": {"buffer": self.buffers[index]["draw"], "offset": 0, "size": 144}},
                {"binding": 1, "resource": {"buffer": self.buffers[index]["material"], "offset": 0, "size": 256}},
                {"binding": 2, "resource": tex("base", True, "white")},
                {"binding": 3, "resource": tex("orm", False, "white")},
                {"binding": 4, "resource": tex("normal", False, "normal")},
                {"binding": 5, "resource": tex("occlusion", False, "white")},
                {"binding": 6, "resource": tex("emissive", True, "white")},
                {"binding": 7, "resource": screen_view},
                {"binding": 8, "resource": _state["repeat"]},
                {"binding": 9, "resource": _state["clamp"]},
            ]
            self.groups[key] = device.create_bind_group(layout=_state["pipeline"].get_bind_group_layout(1), entries=entries)
        return self.groups[key]


def _targets(width: int, height: int) -> dict:
    wgpu, device = _gpu()
    key = ("targets", width, height)
    if key not in _state:
        usage = wgpu.TextureUsage
        msaa = device.create_texture(size=(width, height, 1), format=COLOUR, usage=usage.RENDER_ATTACHMENT, sample_count=SAMPLES)
        resolve = device.create_texture(size=(width, height, 1), format=COLOUR, usage=usage.RENDER_ATTACHMENT | usage.COPY_SRC)
        depth = device.create_texture(size=(width, height, 1), format="depth32float", usage=usage.RENDER_ATTACHMENT, sample_count=SAMPLES)
        far = device.create_texture(size=(width, height, 1), format=DEPTH_COLOUR, usage=usage.RENDER_ATTACHMENT, sample_count=SAMPLES)
        far_resolve = device.create_texture(size=(width, height, 1), format=DEPTH_COLOUR, usage=usage.RENDER_ATTACHMENT | usage.COPY_SRC)
        _state[key] = {
            "msaa": msaa.create_view(),
            "resolve": resolve,
            "resolve_view": resolve.create_view(),
            "depth": depth.create_view(),
            "far": far.create_view(),
            "far_resolve": far_resolve,
            "far_resolve_view": far_resolve.create_view(),
        }
    return _state[key]


_DECODE = np.array([((i / 255) / 12.92 if i / 255 <= 0.04045 else ((i / 255 + 0.055) / 1.055) ** 2.4) for i in range(256)], np.float32)


def _straight(premultiplied: np.ndarray) -> np.ndarray:
    """sRGB-encoded premultiplied pixels (as an sRGB target stores them) to straight-alpha sRGB."""
    alpha = premultiplied[..., 3:4].astype(np.float32) / 255
    linear = _DECODE[premultiplied[..., :3]] / np.maximum(alpha, 1e-6)
    linear = np.clip(linear, 0, 1)
    encoded = np.where(linear <= 0.0031308, linear * 12.92, 1.055 * np.power(linear, 1 / 2.4) - 0.055)
    out = np.empty_like(premultiplied)
    out[..., :3] = np.where(alpha > 0, np.round(encoded * 255), 0).astype(np.uint8)
    out[..., 3] = premultiplied[..., 3]
    return out


SUPERSAMPLE = 1.5  # shading is per pixel under MSAA; rendering larger and averaging down settles what MSAA cannot
SUPERSAMPLE_GPU = 2.5  # on a hardware GPU the extra samples cost little and settle the glints of thin bevels


def _supersample(width: int, height: int) -> float:
    """2.5x on a hardware GPU, 1.5x on a CPU adapter (llvmpipe and the like), where every sample costs seconds; never
    less than a full-HD internal picture (a half-size preview's thin rims broke into dots at 1.5x), never more than
    6144 pixels across (a 4K export on a GPU with unified memory)."""
    if "supersample" not in _state:
        adapter = getattr(_gpu()[1], "adapter", None)
        info = getattr(adapter, "info", None) or {}
        kind = str(info.get("adapter_type", "cpu")).lower()
        _state["supersample"] = SUPERSAMPLE if "cpu" in kind else SUPERSAMPLE_GPU
    wide = max(width, height, 1)
    return max(1.0, min(max(_state["supersample"], 1920 / wide), 6144 / wide))


# The models build a display as layers laid on the body's front in one plane (the lid's front face, the border plate
# and the screen all at the same depth), which no depth test can order: in the owner's 4K GPU export the lid's rim
# alternated border and aluminium as marching dashes. Each primitive's layer (device_assets Asset.layers) moves it
# this far toward the eye per step: 0.2 mm, far above depth precision at product distances (micrometres) and far
# below any real gap that should hide a layer (a lid's 6 to 8 mm of aluminium seen from behind).
LAYER_STEP = 0.0002


def _defocus(linear: np.ndarray, alpha: np.ndarray, far: np.ndarray, focus_at: float, dof: float, width: int, height: int):
    """Depth of field, as a lens: each pixel blurred by how far its distance is from the focus, relative to that
    distance, at most 2.5% of the width at full strength. Empty pixels take the blur of the device beside them,
    so an out-of-focus edge softens outward. Blended from progressively blurred copies, one at a time (premultiplied)."""
    if far.shape != (height, width):
        far = cv2.resize(far, (width, height), interpolation=cv2.INTER_AREA)
    has = far > 1e-4
    defocus = np.zeros_like(far)
    defocus[has] = np.abs(far[has] - focus_at) / far[has]
    reach = 0.025 * width
    coc = np.clip(defocus * 2.5, 0, 1) * reach * min(max(dof, 0.0), 1.0)
    spread = max(1, round(reach * min(dof, 1.0)))
    near = cv2.dilate(coc, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * spread + 1, 2 * spread + 1)))
    coc = np.where(has, coc, near)
    scale = width / 1920
    radii = [r * scale for r in (0.0, 1.0, 2.5, 5.0, 10.0, 20.0, 40.0)]
    radii = [r for r in radii if r <= max(float(coc.max()), 1e-6) * 1.001] or [0.0]
    if radii[-1] < coc.max():
        radii.append(float(coc.max()))
    premultiplied = np.dstack([linear, alpha]).astype(np.float32)
    position = np.interp(coc, radii, np.arange(len(radii), dtype=np.float32))
    out = np.zeros_like(premultiplied)
    for i, r in enumerate(radii):
        weight = np.clip(1.0 - np.abs(position - i), 0.0, 1.0)
        if not weight.any():
            continue
        layer = premultiplied if r < 0.5 else cv2.GaussianBlur(premultiplied, (0, 0), r / 2)
        out += layer * weight[..., None]
    return out[..., :3], out[..., 3]


def _finish(
    raw: np.ndarray, width: int, height: int, bloom: float, far: np.ndarray | None = None, focus_at: float = 0.0, dof: float = 0.0
) -> np.ndarray:
    """The supersampled premultiplied sRGB target to the output: lens bloom on bright highlights (two radii, in linear
    light, its glow extending the alpha), area-averaged down to the output size, straight-alpha sRGB bytes."""
    alpha = raw[..., 3].astype(np.float32) / 255
    linear = _DECODE[raw[..., :3]]
    if bloom > 0:
        # only near-white highlights bloom, mostly in a tight halo: a wide strong glow reads as haze, not as a lens
        bright = np.clip((linear.max(axis=2) - 0.9) / 0.1, 0, 1)[..., None] * linear
        sigma = max(1.0, 0.0025 * raw.shape[1])
        halo = cv2.GaussianBlur(bright, (0, 0), sigma) * 0.75 + cv2.GaussianBlur(bright, (0, 0), sigma * 3) * 0.25
        linear = linear + halo * bloom
        alpha = np.maximum(alpha, np.clip(halo.max(axis=2) * bloom, 0, 1))
    if raw.shape[:2] != (height, width):
        linear = cv2.resize(linear, (width, height), interpolation=cv2.INTER_AREA)
        alpha = cv2.resize(alpha, (width, height), interpolation=cv2.INTER_AREA)
    if dof > 0 and far is not None:
        linear, alpha = _defocus(linear, alpha, far, focus_at, dof, width, height)
    straight = np.clip(linear / np.maximum(alpha, 1e-6)[..., None], 0, 1)
    encoded = np.where(straight <= 0.0031308, straight * 12.92, 1.055 * np.power(straight, 1 / 2.4) - 0.055)
    out = np.empty((height, width, 4), np.uint8)
    out[..., :3] = np.where(alpha[..., None] > 0, np.round(encoded * 255), 0).astype(np.uint8)
    out[..., 3] = np.round(np.clip(alpha, 0, 1) * 255).astype(np.uint8)
    return out


def render(
    device_id: str,
    width: int,
    height: int,
    *,
    finish: str | None = None,
    pose: dict | None = None,
    camera: dict | None = None,
    screens: dict | None = None,
    backlight: float = 0.6,
    backlight_colour: tuple = (1.0, 1.0, 1.0),
    screen_brightness: float = 1.0,
    exposure: float = 1.0,
    shadow: float = 0.6,
    light_rotation: float = 0.0,
    lighting: str = "studio",
    bloom: float = 0.18,
    motion: dict | None = None,
    dof: float = 0.0,
    focus: float = 0.0,
) -> np.ndarray:
    """A device as an RGBA picture (height, width, 4), straight-alpha sRGB, transparent around it.

    finish: one of the device's finishes (None for the file's own). pose: articulation name to degrees (lid, fold,
    stand; missing ones at rest). camera: yaw, pitch, distance (1 frames the device), fov, pan, roll. screens: slot
    ("inner", "cover") to an sRGB picture (RGB or RGBA uint8); a slot left out is off. backlight: the keyboard
    legends' glow, 0 (off) to 1 (the file's emission) and above.
    """
    wgpu, device = _gpu()
    with _lock:
        shared = _shared()
        key = ("prepared", device_id)
        if key not in _state:
            _state[key] = _Prepared(device_id)
        prepared: _Prepared = _state[key]
        a = prepared.asset
        materials = a.finished(finish)
        matrices = a.world(pose)
        points = a.points(matrices)
        floor = float(points[:, 1].min())
        # the camera is fitted to the device at rest, so a device moving on its own (motion) moves in a still frame
        view_proj, eye = device_scene.orbit(points, width / height, camera or {})
        if motion and any(float(v) for v in motion.values()):
            low, high = points.min(axis=0), points.max(axis=0)
            root = device_scene.object_matrix(motion, (low + high) / 2, float(np.linalg.norm(high - low)) / 2, eye[:3])
            matrices = [root @ m for m in matrices]
            rest, points = points, a.points(matrices)
            view_proj, eye = device_scene.orbit(rest, width / height, camera or {}, reach=points)
        # in focus: the device's centre where it now is, nearer (negative) or farther by Focus in device sizes
        low_now, high_now = points.min(axis=0), points.max(axis=0)
        focus_at = float(np.linalg.norm(eye[:3] - (low_now + high_now) / 2) + focus * np.linalg.norm(high_now - low_now) / 2)
        frame = np.zeros(64, np.float32)
        frame[0:16] = view_proj.T.reshape(-1)
        frame[16:20] = [*eye, exposure]
        env_view, env_levels, env_harmonics = _env(lighting)
        frame[20:24] = [0.0, math.radians(light_rotation), env_levels, backlight]
        frame[24:28] = [*backlight_colour, screen_brightness]
        frame[28:64] = np.c_[env_harmonics, np.zeros((9, 1), np.float32)].reshape(-1)
        device.queue.write_buffer(shared["frame"], 0, frame.tobytes())
        views = {slot: prepared.screen(slot, (screens or {}).get(slot)) for slot in ("inner", "cover")}

        mask, (x0, z0, x1, z1) = device_scene.contact_shadow(points, floor)
        shadow_key = ("shadow", device_id)
        if shadow_key not in _state:
            _state[shadow_key] = device.create_texture(
                size=(*mask.shape[::-1], 1),
                format=wgpu.TextureFormat.rgba8unorm,
                usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
            )
        shadow_tex = _state[shadow_key]
        rgba = np.zeros((*mask.shape, 4), np.uint8)
        rgba[..., 0] = np.round(mask * 255)
        device.queue.write_texture(
            {"texture": shadow_tex, "mip_level": 0, "origin": (0, 0, 0)},
            rgba,
            {"offset": 0, "bytes_per_row": mask.shape[1] * 4, "rows_per_image": mask.shape[0]},
            (mask.shape[1], mask.shape[0], 1),
        )
        y = floor - 0.0002
        quad = np.array(
            [[x0, y, z0, 0, 0], [x1, y, z0, 1, 0], [x1, y, z1, 1, 1], [x0, y, z0, 0, 0], [x1, y, z1, 1, 1], [x0, y, z1, 0, 1]], np.float32
        )
        quad_buffer = device.create_buffer_with_data(data=quad, usage=wgpu.BufferUsage.VERTEX)
        shadow_frame = device.create_buffer(size=256, usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST)
        shadow_values = frame.copy()
        shadow_values[27] = shadow
        device.queue.write_buffer(shadow_frame, 0, shadow_values.tobytes())

        frame_group = device.create_bind_group(
            layout=shared["pipeline"].get_bind_group_layout(0),
            entries=[
                {"binding": 0, "resource": {"buffer": shared["frame"], "offset": 0, "size": 256}},
                {"binding": 1, "resource": env_view},
                {"binding": 2, "resource": shared["env_sampler"]},
            ],
        )
        shadow_groups = (
            device.create_bind_group(
                layout=shared["shadow_pipeline"].get_bind_group_layout(0),
                entries=[{"binding": 0, "resource": {"buffer": shadow_frame, "offset": 0, "size": 256}}],
            ),
            device.create_bind_group(
                layout=shared["shadow_pipeline"].get_bind_group_layout(1),
                entries=[{"binding": 0, "resource": shadow_tex.create_view()}, {"binding": 1, "resource": shared["clamp"]}],
            ),
        )
        draws = []
        for index, p in enumerate(a.primitives):
            if index in a.hidden:
                continue
            m = materials[p.material]
            if index in a.no_occlusion:
                m = dataclasses.replace(m, textures={k: v for k, v in m.textures.items() if k != "occlusion"})
            model = matrices[p.node]
            normal = np.eye(4)
            normal[:3, :3] = np.linalg.inv(model[:3, :3]).T
            layer = a.layers.get(index, 0) * LAYER_STEP
            device.queue.write_buffer(
                prepared.buffers[index]["draw"],
                0,
                np.concatenate([model.T.reshape(-1), normal.T.reshape(-1), [layer, 0.0, 0.0, 0.0]]).astype(np.float32).tobytes(),
            )
            slot = {"M_Screen": "inner", "M_ScreenCover": "cover"}.get(m.name)
            device.queue.write_buffer(
                prepared.buffers[index]["material"], 0, _material_block(m, slot is not None, m.name == "M_KeyLegend").tobytes()
            )
            draws.append((index, prepared.group(index, m, views[slot] if slot else shared["blank"]["black"])))

        ss = _supersample(width, height)
        iw, ih = max(1, round(width * ss)), max(1, round(height * ss))
        targets = _targets(iw, ih)
        encoder = device.create_command_encoder()
        rp = encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": targets["msaa"],
                    "resolve_target": targets["resolve_view"],
                    "clear_value": (0, 0, 0, 0),
                    "load_op": "clear",
                    "store_op": "discard",
                },
                {
                    "view": targets["far"],
                    "resolve_target": targets["far_resolve_view"],
                    "clear_value": (0, 0, 0, 0),
                    "load_op": "clear",
                    "store_op": "discard",
                },
            ],
            depth_stencil_attachment={
                "view": targets["depth"],
                "depth_clear_value": 1.0,
                "depth_load_op": "clear",
                "depth_store_op": "discard",
            },
        )
        if shadow > 0:
            rp.set_pipeline(shared["shadow_pipeline"])
            rp.set_bind_group(0, shadow_groups[0])
            rp.set_bind_group(1, shadow_groups[1])
            rp.set_vertex_buffer(0, quad_buffer)
            rp.draw(6)
        rp.set_pipeline(shared["pipeline"])
        rp.set_bind_group(0, frame_group)
        for index, group in draws:
            b = prepared.buffers[index]
            rp.set_bind_group(1, group)
            for slot_index, buffer in enumerate(b["vertex"]):
                rp.set_vertex_buffer(slot_index, buffer)
            rp.set_index_buffer(b["index"], wgpu.IndexFormat.uint32)
            rp.draw_indexed(b["count"])
        rp.end()
        device.queue.submit([encoder.finish()])
        raw = device.queue.read_texture(
            {"texture": targets["resolve"], "mip_level": 0, "origin": (0, 0, 0)},
            {"offset": 0, "bytes_per_row": iw * 4, "rows_per_image": ih},
            (iw, ih, 1),
        )
        pixels = np.frombuffer(raw, np.uint8).reshape(ih, iw, 4)
        far = None
        if dof > 0:
            got = device.queue.read_texture(
                {"texture": targets["far_resolve"], "mip_level": 0, "origin": (0, 0, 0)},
                {"offset": 0, "bytes_per_row": iw * 8, "rows_per_image": ih},
                (iw, ih, 1),
            )
            far = np.frombuffer(got, np.float16).reshape(ih, iw, 4)[..., 0].astype(np.float32)
        return _finish(pixels, width, height, bloom, far, focus_at, dof)
