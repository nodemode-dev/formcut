"""R26: the frame path through the Rust executor.

The Python engine keeps deciding what a frame is. This module is the device context and the compositor
it talks to when `formcut_native.GpuFrame` is present and FORMCUT_FRAME is not "python": every call the
engine would have made on the wgpu-py device (an upload, a pass, a copy, a blend, the pack) is recorded
as a step in the Rust executor instead, and the frame runs as one command buffer with one submit and one
readback. The kernels are the same WGSL strings; the picture layout is the same; the CPU reference is
the same. What changes is that no Python runs between passes.

A `Recorder` stands in for gpu_effects._Context: five working pictures (0 to 4, `held` is picture 2 as
in the Python context), an aux of any size, run/upload/copy with the same signatures. The pool pictures
(5 onward) hold staged layers; two more hold the compositor's canvas. `compose()` blends the staged
layers over the canvas and packs the frame.
"""

from __future__ import annotations

import os

import numpy as np

_frame = None
_status: dict | None = None
_unavailable: str | None = None

WORKING = 5
POOL = 32
CANVAS_A = WORKING + POOL
CANVAS_B = CANVAS_A + 1
PICTURES = CANVAS_B + 1


def available() -> bool:
    """True when the Rust executor can be used for frames on this machine."""
    return status()["available"]


def status() -> dict:
    global _status, _unavailable
    if _status is not None:
        return _status
    if os.environ.get("FORMCUT_FRAME", "rust") == "python":
        _status = {"available": False, "reason": "FORMCUT_FRAME=python"}
        return _status
    try:
        import formcut_native

        probe = formcut_native.GpuFrame(4 * 4 * 16, 2)
        _status = {"available": True, "adapter": probe.adapter()}
    except Exception as exc:  # noqa: BLE001 - any failure means the Python path, with the reason kept
        _unavailable = f"{type(exc).__name__}: {exc}"[:200]
        _status = {"available": False, "reason": _unavailable}
    return _status


def executor(height: int, width: int):
    """One executor per process, sized for the largest frame seen so far."""
    global _frame
    import formcut_native

    need = width * height * 16
    if _frame is None or _frame[0] < need:
        _frame = (need, formcut_native.GpuFrame(need, PICTURES))
    return _frame[1]


class Recorder:
    """The device context the engine's passes run on, recording instead of running."""

    def __init__(self, height: int, width: int):
        from .gpu_effects import HEADER, UNPACK16_CODE, UNPACK_CODE

        self.h, self.w = height, width
        self.frame = executor(height, width)
        self.buffers = list(range(WORKING))
        self.aux_size = 1 << 40  # anything fits: each pass carries its own aux buffer
        self.header = HEADER
        self.unpack = self.kernel(UNPACK_CODE)
        self.unpack16 = self.kernel(UNPACK16_CODE)
        self.pool_used = 0
        self.steps = 0
        self.light = (0, 0.0)  # after a planar compose: the luma's brightest sixteen-bit code and mean nits

    def kernel(self, code: str) -> int:
        full = code if code.lstrip().startswith("@group") else self.header + code
        return self.frame.kernel(full)

    def run(self, code: str, src, dst, params: list, aux: np.ndarray | None = None, width: int | None = None, height: int | None = None):
        w, h = width or self.w, height or self.h
        aux_bytes = None if aux is None else np.ascontiguousarray(np.asarray(aux).astype(np.float32)).tobytes()
        self.frame.step(self.kernel(code), int(src), int(dst), 2, int(w), int(h), [float(v) for v in params[2:]], aux_bytes)
        self.steps += 1

    def upload(self, buffer, image: np.ndarray):
        h, w = image.shape[:2]
        if image.ndim == 2:
            image = np.repeat(image[:, :, None], 4, axis=2)
        if image.shape[2] == 3:
            image = np.concatenate([image, np.full((h, w, 1), 65535 if image.dtype == np.uint16 else 255, image.dtype)], axis=2)
        deep = image.dtype == np.uint16
        if not deep and image.dtype != np.uint8:
            image = np.round(np.clip(image, 0, 1) * 255).astype(np.uint8)
        self.frame.upload(int(buffer), int(w), int(h), bool(deep), np.ascontiguousarray(image).tobytes())
        self.steps += 1

    def copy(self, source, target, height: int, width: int):
        self.frame.copy(int(source), int(target), int(width), int(height))
        self.steps += 1

    def stage(self, picture: int, height: int, width: int) -> int | None:
        """A finished layer copied into the pool; its pool index is the layer's handle for the blend."""
        if self.pool_used >= POOL:
            return None
        index = WORKING + self.pool_used
        self.pool_used += 1
        self.copy(picture, index, height, width)
        return index

    def download(self, buffer, height: int, width: int) -> np.ndarray:
        """The rare read of a working picture (a CPU-only effect mid-chain): runs what is recorded so far."""
        from .gpu_effects import PACK_CODE

        self.frame.download(int(buffer), self.kernel(PACK_CODE), int(width), int(height), int(width) * int(height) * 4)
        data = self.frame.run(self.unpack, self.unpack16)
        self.steps = 0  # the pictures persist on the device; the staged pool stays as it is
        return np.frombuffer(data, np.uint8).reshape(height, width, 4).astype(np.float32) / 255

    def compose(self, canvas: np.ndarray, layers: list, transfer: int, yuv: bool) -> np.ndarray:
        """Blend the staged layers over the canvas, in light, and pack the frame: the compositor's job."""
        h, w = canvas.shape[:2]
        deep = canvas.dtype == np.uint16
        self.upload(CANVAS_A, canvas)
        base, other = CANVAS_A, CANVAS_B
        blend = self.kernel(BLEND_FRAME_CODE)
        for layer, mode in layers:
            if isinstance(layer, (int, np.integer)):
                front = int(layer)
            else:
                self.upload(0, layer)
                front = 0
            from .gpu import MODES

            index = MODES.index(mode.lower()) if mode.lower() in MODES else 0
            self.frame.step(blend, base, other, front, w, h, [float(index), float(transfer)], None)
            base, other = other, base
            self.steps += 1
        if yuv and deep and w % 4 == 0 and h % 2 == 0:
            self.frame.download(base, self.kernel(PACK_YUV_FRAME_CODE), w, h, w * h * 2 + 2 * (w // 2) * (h // 2) * 2)
        else:
            self.frame.download(base, self.kernel(PACK16_FRAME_CODE if deep else PACK_FRAME_CODE), w, h, w * h * (8 if deep else 4))
        data = self.frame.run(self.unpack, self.unpack16)
        self.steps = 0
        self.pool_used = 0
        if yuv and deep and w % 4 == 0 and h % 2 == 0:
            planes = np.frombuffer(data, np.uint8).copy()
            # the light for MaxCLL and MaxFALL from the luma plane (the Python compositor measures the
            # brightest channel by atomics in its pack; here luma stands in until the executor's pack does the
            # same, and luma is never above the brightest channel, so the values err low, which the record says)
            from .gpu import _to_linear

            y = np.frombuffer(planes, np.uint16, count=w * h)
            codes = np.clip((y.astype(np.float32) - 64.0) / 876.0, 0.0, 1.0)  # limited-range ten-bit luma as a signal fraction
            peak_code = round(float(codes.max()) * 65535)
            name = "pq" if transfer == 1 else "hlg"
            nits = _to_linear(codes[::2], name) * (10000.0 if transfer == 1 else 1000.0)
            self.light = (peak_code, float(nits.mean()))
            return planes
        return np.frombuffer(data, np.uint16 if deep else np.uint8).reshape(h, w, 4).copy()


def _blend_functions() -> str:
    from .gpu import BLEND_CODE

    i = BLEND_CODE.index("fn lin_srgb")
    j = BLEND_CODE.index("@compute")
    return BLEND_CODE[i:j].replace("options[1]", "p[3]")


def _blend_body() -> str:
    """The Python compositor's blend arithmetic, verbatim, over the executor's bindings."""
    from .gpu import BLEND_CODE

    j = BLEND_CODE.index("@compute")
    body = BLEND_CODE[j:]
    head_end = body.index("let b = lin(")
    body = body[head_end:]
    body = body.replace("background[i]", "src[i]").replace("foreground[i]", "held[i]").replace("result[i]", "dst[i]")
    body = body.replace("options[0]", "p[2]").replace("options[1]", "p[3]")
    return body


# The blend in the executor's layout: src is the canvas so far, held the layer, dst the canvas after.
BLEND_FRAME_CODE = (
    """
@group(0) @binding(0) var<storage, read> src: array<vec4<f32>>;
@group(0) @binding(1) var<storage, read_write> dst: array<vec4<f32>>;
@group(0) @binding(2) var<storage, read> p: array<f32>;
@group(0) @binding(3) var<storage, read> aux: array<f32>;
@group(0) @binding(4) var<storage, read> held: array<vec4<f32>>;
"""
    + _blend_functions()
    + """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    """
    + _blend_body()
)

# The packs in the executor's layout: src is the picture, dst the packed words (declared as u32).
_PACK_HEAD = """
@group(0) @binding(0) var<storage, read> src: array<vec4<f32>>;
@group(0) @binding(1) var<storage, read_write> packed: array<u32>;
@group(0) @binding(2) var<storage, read> p: array<f32>;
@group(0) @binding(3) var<storage, read> aux: array<f32>;
@group(0) @binding(4) var<storage, read> held: array<vec4<f32>>;
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = u32(p[0]);
    let h = u32(p[1]);
    if (id.x >= w || id.y >= h) { return; }
    let i = id.y * w + id.x;
"""

PACK_FRAME_CODE = (
    _PACK_HEAD
    + """
    let c = vec4<u32>(round(clamp(src[i], vec4<f32>(0.0), vec4<f32>(1.0)) * 255.0));
    packed[i] = c.x | (c.y << 8u) | (c.z << 16u) | (c.w << 24u);
}
"""
)

PACK16_FRAME_CODE = (
    _PACK_HEAD
    + """
    let c = vec4<u32>(round(clamp(src[i], vec4<f32>(0.0), vec4<f32>(1.0)) * 65535.0));
    packed[i * 2u] = c.x | (c.y << 16u);
    packed[i * 2u + 1u] = c.z | (c.w << 16u);
}
"""
)

# Ten-bit 4:2:0 planes, one invocation per 4x2 block (the compositor's PACK_YUV_CODE, over these bindings);
# the light is measured on the CPU from the planes' luma when the frame comes back this way.
PACK_YUV_FRAME_CODE = """
@group(0) @binding(0) var<storage, read> src: array<vec4<f32>>;
@group(0) @binding(1) var<storage, read_write> packed: array<u32>;
@group(0) @binding(2) var<storage, read> p: array<f32>;
@group(0) @binding(3) var<storage, read> aux: array<f32>;
@group(0) @binding(4) var<storage, read> held: array<vec4<f32>>;
fn luma(c: vec3<f32>) -> f32 { return 0.2627 * c.r + 0.6780 * c.g + 0.0593 * c.b; }
fn code(v: f32, offset: f32, span: f32) -> u32 { return u32(clamp(round((offset + span * v) * 4.0), 0.0, 1023.0)); }
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = u32(p[0]);
    let h = u32(p[1]);
    let bx = id.x * 4u;
    let by = id.y * 2u;
    if (bx >= w || by >= h) { return; }
    let cw = w / 2u;
    let ch = h / 2u;
    var cb = vec2<f32>(0.0);
    var cr = vec2<f32>(0.0);
    for (var row = 0u; row < 2u; row = row + 1u) {
        let y = by + row;
        for (var pair = 0u; pair < 2u; pair = pair + 1u) {
            let x0 = bx + pair * 2u;
            let c0 = clamp(src[y * w + x0].rgb, vec3<f32>(0.0), vec3<f32>(1.0));
            let c1 = clamp(src[y * w + x0 + 1u].rgb, vec3<f32>(0.0), vec3<f32>(1.0));
            let y0 = luma(c0);
            let y1 = luma(c1);
            packed[(y * w + x0) / 2u] = code(y0, 16.0, 219.0) | (code(y1, 16.0, 219.0) << 16u);
            cb[pair] = cb[pair] + ((c0.b - y0) / 1.8814 + (c1.b - y1) / 1.8814) * 0.25;
            cr[pair] = cr[pair] + ((c0.r - y0) / 1.4746 + (c1.r - y1) / 1.4746) * 0.25;
        }
    }
    let y_words = (w * h) / 2u;
    let u_words = (cw * ch) / 2u;
    let cindex = (by / 2u) * cw + bx / 2u;
    packed[y_words + cindex / 2u] = code(cb[0], 128.0, 224.0) | (code(cb[1], 128.0, 224.0) << 16u);
    packed[y_words + u_words + cindex / 2u] = code(cr[0], 128.0, 224.0) | (code(cr[1], 128.0, 224.0) << 16u);
}
"""
