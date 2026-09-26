import os
import threading

import numpy as np

_lock = threading.RLock()
_status = None

BLEND_CODE = """
@group(0) @binding(0) var<storage, read> background: array<vec4<f32>>;
@group(0) @binding(1) var<storage, read> foreground: array<vec4<f32>>;
@group(0) @binding(2) var<storage, read> options: array<f32>;
@group(0) @binding(3) var<storage, read_write> result: array<vec4<f32>>;
// R24: the blend happens in light. Both operands are decoded through the sRGB
// transfer to linear light, the mode and the opacity mix are computed there,
// and the result is encoded back, so a dissolve between two bright clips does
// not dip and a fade is a fade of light; the CPU reference (composite) does
// the same. Blend modes keep their formulas, applied to light.
// options[1] names the transfer the signal is in: 0 sRGB (SDR), 1 PQ, 2 HLG.
// PQ light is in units of 10000 nits; HLG in units of the nominal peak, both
// kept as the signal's own scale so nothing above white is lost in the blend.
fn lin_srgb(v: vec3<f32>) -> vec3<f32> {
    let low = v / 12.92;
    let high = pow((v + 0.055) / 1.055, vec3<f32>(2.4));
    return select(high, low, v <= vec3<f32>(0.04045));
}
fn enc_srgb(v: vec3<f32>) -> vec3<f32> {
    let c = clamp(v, vec3<f32>(0.0), vec3<f32>(1.0));
    let low = c * 12.92;
    let high = 1.055 * pow(c, vec3<f32>(1.0 / 2.4)) - 0.055;
    return select(high, low, c <= vec3<f32>(0.0031308));
}
fn lin_pq(v: vec3<f32>) -> vec3<f32> {
    let m1 = 0.1593017578125;
    let m2 = 78.84375;
    let c1 = 0.8359375;
    let c2 = 18.8515625;
    let c3 = 18.6875;
    let e = pow(clamp(v, vec3<f32>(0.0), vec3<f32>(1.0)), vec3<f32>(1.0 / m2));
    return pow(max(e - c1, vec3<f32>(0.0)) / (c2 - c3 * e), vec3<f32>(1.0 / m1));
}
fn enc_pq(v: vec3<f32>) -> vec3<f32> {
    let m1 = 0.1593017578125;
    let m2 = 78.84375;
    let c1 = 0.8359375;
    let c2 = 18.8515625;
    let c3 = 18.6875;
    let y = pow(clamp(v, vec3<f32>(0.0), vec3<f32>(1.0)), vec3<f32>(m1));
    return pow((c1 + c2 * y) / (1.0 + c3 * y), vec3<f32>(m2));
}
fn lin_hlg(v: vec3<f32>) -> vec3<f32> {
    let a = 0.17883277;
    let b = 0.28466892;
    let c = 0.55991073;
    let low = v * v / 3.0;
    let high = (exp((v - c) / a) + b) / 12.0;
    return select(high, low, v <= vec3<f32>(0.5));
}
fn enc_hlg(v: vec3<f32>) -> vec3<f32> {
    let a = 0.17883277;
    let b = 0.28466892;
    let c = 0.55991073;
    let l = clamp(v, vec3<f32>(0.0), vec3<f32>(1.0));
    let low = sqrt(3.0 * l);
    let high = a * log(12.0 * l - b) + c;
    return select(high, low, l <= vec3<f32>(1.0 / 12.0));
}
fn lin(v: vec3<f32>) -> vec3<f32> {
    let t = u32(options[1]);
    if (t == 1u) { return lin_pq(v); }
    if (t == 2u) { return lin_hlg(v); }
    return lin_srgb(v);
}
fn enc(v: vec3<f32>) -> vec3<f32> {
    let t = u32(options[1]);
    if (t == 1u) { return enc_pq(v); }
    if (t == 2u) { return enc_hlg(v); }
    return enc_srgb(v);
}
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let i = id.x;
    if (i >= arrayLength(&result)) { return; }
    let b = lin(background[i].rgb);
    let f = lin(foreground[i].rgb);
    let alpha = foreground[i].a;
    var color = f;
    let mode = u32(options[0]);
    if (mode == 1u) { color = b * f; }
    if (mode == 2u) { color = 1.0 - (1.0 - b) * (1.0 - f); }
    if (mode == 3u) { color = select(2.0*b*f, 1.0-2.0*(1.0-b)*(1.0-f), b >= vec3<f32>(0.5)); }
    if (mode == 4u) { color = min(b, f); }
    if (mode == 5u) { color = max(b, f); }
    if (mode == 6u) { color = abs(b-f); }
    if (mode == 7u) { color = min(vec3<f32>(1.0), b+f); }
    if (mode == 8u) { color = max(vec3<f32>(0.0), b-f); }
    if (mode == 9u) { color = (1.0-2.0*f)*b*b+2.0*f*b; }
    // rounded to the byte grid after every blend, as the CPU reference rounds each composite, so a stack of
    // layers lands where the sequential reference lands rather than drifting in the darks
    let grid = select(255.0, 65535.0, u32(options[1]) > 0u);
    result[i] = vec4<f32>(round(enc(mix(b, color, alpha)) * grid) / grid, 1.0);
}
"""

# R7: the frame's bytes cross the bus as bytes. UNPACK spreads four bytes a
# pixel into the vec4<f32> the blend works in; PACK folds the result back to
# bytes on the device, so the readback is a quarter the size and the CPU
# converts nothing on either side. np.round's rounding, kept.
UNPACK_CODE = """
@group(0) @binding(0) var<storage, read> packed: array<u32>;
@group(0) @binding(1) var<storage, read_write> result: array<vec4<f32>>;
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let i = id.x;
    if (i >= arrayLength(&result)) { return; }
    let v = packed[i];
    result[i] = vec4<f32>(f32(v & 255u), f32((v >> 8u) & 255u), f32((v >> 16u) & 255u), f32(v >> 24u)) / 255.0;
}
"""

UNPACK16_CODE = """
@group(0) @binding(0) var<storage, read> packed: array<u32>;
@group(0) @binding(1) var<storage, read_write> result: array<vec4<f32>>;
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let i = id.x;
    if (i >= arrayLength(&result)) { return; }
    let lo = packed[i * 2u];
    let hi = packed[i * 2u + 1u];
    result[i] = vec4<f32>(f32(lo & 65535u), f32(lo >> 16u), f32(hi & 65535u), f32(hi >> 16u)) / 65535.0;
}
"""

PACK16_CODE = """
@group(0) @binding(0) var<storage, read> source: array<vec4<f32>>;
@group(0) @binding(1) var<storage, read_write> packed: array<u32>;
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let i = id.x;
    if (i * 2u + 1u >= arrayLength(&packed)) { return; }
    let c = vec4<u32>(round(clamp(source[i], vec4<f32>(0.0), vec4<f32>(1.0)) * 65535.0));
    packed[i * 2u] = c.x | (c.y << 16u);
    packed[i * 2u + 1u] = c.z | (c.w << 16u);
}
"""

PACK_CODE = """
@group(0) @binding(0) var<storage, read> source: array<vec4<f32>>;
@group(0) @binding(1) var<storage, read_write> packed: array<u32>;
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let i = id.x;
    if (i >= arrayLength(&packed)) { return; }
    let c = vec4<u32>(round(clamp(source[i], vec4<f32>(0.0), vec4<f32>(1.0)) * 255.0));
    packed[i] = c.x | (c.y << 8u) | (c.z << 16u) | (c.w << 24u);
}
"""
MODES = ["normal", "multiply", "screen", "overlay", "darken", "lighten", "difference", "add", "subtract", "soft light"]


def status() -> dict:
    global _status
    with _lock:
        if _status is None:
            try:
                from wgpu.utils import get_default_device

                device = get_default_device()
                _status = {"available": True, "adapter": dict(device.adapter.info)}
            except Exception as exc:
                _status = {"available": False, "reason": str(exc)}
        out = _status.copy()
        out["compositor"] = "stack" if _stack_wanted(out) else "per-layer"
        wanted = os.environ.get("FORMCUT_EFFECTS", "").lower()
        out["passes"] = "device" if (wanted == "gpu" and out.get("available")) or (wanted != "cpu" and _stack_wanted(out)) else "cpu"
        return out


def composite(base: np.ndarray, front: np.ndarray, mode: str, transfer: str = "srgb") -> np.ndarray:
    index = MODES.index(mode.lower()) if mode.lower() in MODES else 0
    deep = base.dtype == np.uint16
    scale = 65535.0 if deep else 255.0
    b, f = base.astype(np.float32) / scale, front.astype(np.float32) / scale
    if index and status()["available"]:
        from wgpu.utils.compute import compute_with_buffers

        with _lock:
            out = compute_with_buffers(
                {0: b, 1: f, 2: np.array([index, TRANSFERS.get(transfer.lower(), 0), 0, 0], np.float32)},
                {3: (b.size, "f")},
                BLEND_CODE,
                n=(b.shape[0] * b.shape[1] + 63) // 64,
            )[3]
        floats = np.frombuffer(out, np.float32).reshape(b.shape)
        return np.round(floats * scale).astype(np.uint16 if deep else np.uint8)
    # R24: in light, as the device blends (see BLEND_CODE); the same transfer both ways.
    rgb_b, rgb_f = _to_linear(b[:, :, :3], transfer), _to_linear(f[:, :, :3], transfer)
    modes = [
        lambda: rgb_f,
        lambda: rgb_b * rgb_f,
        lambda: 1 - (1 - rgb_b) * (1 - rgb_f),
        lambda: np.where(rgb_b < 0.5, 2 * rgb_b * rgb_f, 1 - 2 * (1 - rgb_b) * (1 - rgb_f)),
        lambda: np.minimum(rgb_b, rgb_f),
        lambda: np.maximum(rgb_b, rgb_f),
        lambda: abs(rgb_b - rgb_f),
        lambda: np.minimum(1, rgb_b + rgb_f),
        lambda: np.maximum(0, rgb_b - rgb_f),
        lambda: (1 - 2 * rgb_f) * rgb_b**2 + 2 * rgb_f * rgb_b,
    ]
    alpha = f[:, :, 3:4]
    b[:, :, :3] = _to_display(rgb_b * (1 - alpha) + modes[index]() * alpha, transfer)
    b[:, :, 3] = 1
    if deep:
        return np.round(b * 65535).astype(np.uint16)
    return np.round(b * 255).astype(np.uint8)


_PQ = (0.1593017578125, 78.84375, 0.8359375, 18.8515625, 18.6875)
_HLG = (0.17883277, 0.28466892, 0.55991073)


def _to_linear(v: np.ndarray, transfer: str = "srgb") -> np.ndarray:
    """The signal's transfer decoded to light: sRGB, or PQ (units of 10000 nits) or HLG (units of the nominal peak)."""
    t = transfer.lower()
    if t in ("pq", "smpte2084"):
        m1, m2, c1, c2, c3 = _PQ
        e = np.power(np.clip(v, 0, 1), 1 / m2)
        return np.power(np.maximum(e - c1, 0) / (c2 - c3 * e), 1 / m1).astype(np.float32)
    if t in ("hlg", "arib-std-b67"):
        a, b, c = _HLG
        return np.where(v <= 0.5, v * v / 3, (np.exp((v - c) / a) + b) / 12).astype(np.float32)
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4).astype(np.float32)


def _to_display(v: np.ndarray, transfer: str = "srgb") -> np.ndarray:
    """Light encoded back through the same transfer, clipped to 0..1."""
    c = np.clip(v, 0, 1)
    t = transfer.lower()
    if t in ("pq", "smpte2084"):
        m1, m2, c1, c2, c3 = _PQ
        y = np.power(c, m1)
        return np.power((c1 + c2 * y) / (1 + c3 * y), m2).astype(np.float32)
    if t in ("hlg", "arib-std-b67"):
        a, b, cc = _HLG
        return np.where(c <= 1 / 12, np.sqrt(3 * c), a * np.log(np.maximum(12 * c - b, 1e-9)) + cc).astype(np.float32)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055).astype(np.float32)


# R3: the layer stack composited on the device. The per-pair path above uploads
# the whole canvas and reads it back for every layer; here the canvas goes up
# once, each layer of a run is blended into it on the device through the same
# BLEND_CODE (normal included), and one readback returns the frame. The CPU
# path stays the reference: FORMCUT_COMPOSITE=cpu forces it, =gpu forces this,
# and unset picks this only on a real accelerator, never on a software adapter.
_compositors: dict = {}


def _stack_wanted(state: dict) -> bool:
    wanted = os.environ.get("FORMCUT_COMPOSITE", "").lower()
    if wanted == "cpu" or not state.get("available"):
        return False
    if wanted == "gpu":
        return True
    return state.get("adapter", {}).get("adapter_type", "CPU") not in ("CPU", "cpu")


def stack_active() -> bool:
    return _stack_fuse is None and _stack_wanted(status())


class DeviceLayer:
    """A frame-sized layer that already lives on the device: the buffer that holds it and its shape."""

    __slots__ = ("buffer", "height", "width")

    def __init__(self, buffer, height: int, width: int):
        self.buffer, self.height, self.width = buffer, height, width


class _StackCompositor:
    """One frame size's device state: buffers, pipeline, both bind directions.

    R4: a layer may arrive as a DeviceLayer, a buffer the effect passes left on
    the device; it is copied device-side into a pooled front buffer and never
    read back, so the frame stays on the device from the layer's upload to the
    one readback after the blend.
    """

    def __init__(self, height: int, width: int):
        import wgpu
        from wgpu.utils import get_default_device

        self.device = get_default_device()
        self.count = height * width
        size = self.count * 16  # vec4<f32>
        self.size = size
        usage = wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.COPY_SRC
        self.a = self.device.create_buffer(size=size, usage=usage)
        self.b = self.device.create_buffer(size=size, usage=usage)
        self.front = self.device.create_buffer(size=size, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST)
        self.opts = self.device.create_buffer(size=16, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST)
        # R7: bytes in, bytes out. packed_in takes a canvas or a numpy layer as
        # its own RGBA bytes; packed_out holds the blended frame as bytes; read
        # maps it. Both a quarter of the float buffers.
        # eight bytes a pixel so a deep (sixteen-bit) frame fits; a byte frame uses the first half
        self.packed_in = self.device.create_buffer(size=self.count * 8, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST)
        self.packed_out = self.device.create_buffer(size=self.count * 8, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC)
        self.read = self.device.create_buffer(size=self.count * 8, usage=wgpu.BufferUsage.MAP_READ | wgpu.BufferUsage.COPY_DST)
        module = self.device.create_shader_module(code=BLEND_CODE)
        self.pipeline = self.device.create_compute_pipeline(layout="auto", compute={"module": module, "entry_point": "main"})
        self.layout = self.pipeline.get_bind_group_layout(0)
        unpack = self.device.create_shader_module(code=UNPACK_CODE)
        self.unpack = self.device.create_compute_pipeline(layout="auto", compute={"module": unpack, "entry_point": "main"})
        pack = self.device.create_shader_module(code=PACK_CODE)
        self.pack = self.device.create_compute_pipeline(layout="auto", compute={"module": pack, "entry_point": "main"})
        unpack16 = self.device.create_shader_module(code=UNPACK16_CODE)
        self.unpack16 = self.device.create_compute_pipeline(layout="auto", compute={"module": unpack16, "entry_point": "main"})
        pack16 = self.device.create_shader_module(code=PACK16_CODE)
        self.pack16 = self.device.create_compute_pipeline(layout="auto", compute={"module": pack16, "entry_point": "main"})
        self.unpack16_groups = {
            id(target): self.device.create_bind_group(
                layout=self.unpack16.get_bind_group_layout(0),
                entries=[
                    {"binding": 0, "resource": {"buffer": self.packed_in, "offset": 0, "size": self.count * 8}},
                    {"binding": 1, "resource": {"buffer": target, "offset": 0, "size": size}},
                ],
            )
            for target in (self.a, self.front)
        }
        self.pack16_groups = {
            id(source): self.device.create_bind_group(
                layout=self.pack16.get_bind_group_layout(0),
                entries=[
                    {"binding": 0, "resource": {"buffer": source, "offset": 0, "size": size}},
                    {"binding": 1, "resource": {"buffer": self.packed_out, "offset": 0, "size": self.count * 8}},
                ],
            )
            for source in (self.a, self.b)
        }
        self.transfer = 0
        self.unpack_groups = {
            id(target): self.device.create_bind_group(
                layout=self.unpack.get_bind_group_layout(0),
                entries=[
                    {"binding": 0, "resource": {"buffer": self.packed_in, "offset": 0, "size": self.count * 4}},
                    {"binding": 1, "resource": {"buffer": target, "offset": 0, "size": size}},
                ],
            )
            for target in (self.a, self.front)
        }
        self.pack_groups = {
            id(source): self.device.create_bind_group(
                layout=self.pack.get_bind_group_layout(0),
                entries=[
                    {"binding": 0, "resource": {"buffer": source, "offset": 0, "size": size}},
                    {"binding": 1, "resource": {"buffer": self.packed_out, "offset": 0, "size": self.count * 4}},
                ],
            )
            for source in (self.a, self.b)
        }
        self.ab = self._group(self.a, self.front, self.b)
        self.ba = self._group(self.b, self.front, self.a)
        # Staged device layers: pooled buffers a layer is copied into on the
        # device, with the two bind directions built once per pooled buffer.
        self.pool: list = []
        self.pool_groups: dict = {}
        self.staged = 0

    def _upload(self, image: np.ndarray, target) -> None:
        """A uint8 RGBA image into a float buffer: the bytes go up, the device spreads them."""
        queue = self.device.queue
        if image.dtype == np.uint16 and image.shape[2] == 4:
            queue.write_buffer(self.packed_in, 0, np.ascontiguousarray(image))
            encoder = self.device.create_command_encoder()
            step = encoder.begin_compute_pass()
            step.set_pipeline(self.unpack16)
            step.set_bind_group(0, self.unpack16_groups[id(target)])
            step.dispatch_workgroups((self.count + 63) // 64)
            step.end()
            queue.submit([encoder.finish()])
            return
        if image.dtype == np.uint8 and image.shape[2] == 4:
            queue.write_buffer(self.packed_in, 0, np.ascontiguousarray(image))
            encoder = self.device.create_command_encoder()
            step = encoder.begin_compute_pass()
            step.set_pipeline(self.unpack)
            step.set_bind_group(0, self.unpack_groups[id(target)])
            step.dispatch_workgroups((self.count + 63) // 64)
            step.end()
            queue.submit([encoder.finish()])
            return
        queue.write_buffer(target, 0, np.ascontiguousarray(image.astype(np.float32) / 255))

    def _group(self, back, front, out):
        size = self.size
        entries = [
            {"binding": 0, "resource": {"buffer": back, "offset": 0, "size": size}},
            {"binding": 1, "resource": {"buffer": front, "offset": 0, "size": size}},
            {"binding": 2, "resource": {"buffer": self.opts, "offset": 0, "size": 16}},
            {"binding": 3, "resource": {"buffer": out, "offset": 0, "size": size}},
        ]
        return self.device.create_bind_group(layout=self.layout, entries=entries)

    def stage(self, layer: DeviceLayer) -> int:
        """Copy a device layer into the next pooled buffer, on the device; the index names it in the blend."""
        import wgpu

        index = self.staged
        if index >= len(self.pool):
            usage = wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST
            pooled = self.device.create_buffer(size=self.size, usage=usage)
            self.pool.append(pooled)
            self.pool_groups[index] = (self._group(self.a, pooled, self.b), self._group(self.b, pooled, self.a))
        encoder = self.device.create_command_encoder()
        encoder.copy_buffer_to_buffer(layer.buffer, 0, self.pool[index], 0, min(self.size, layer.height * layer.width * 16))
        self.device.queue.submit([encoder.finish()])
        self.staged += 1
        return index

    def run(self, canvas: np.ndarray, layers: list) -> np.ndarray:
        import wgpu

        queue = self.device.queue
        self._upload(canvas, self.a)
        source_is_a = True
        for layer, mode in layers:
            index = MODES.index(mode.lower()) if mode.lower() in MODES else 0
            if isinstance(layer, int):
                groups = self.pool_groups[layer]
                group = groups[0] if source_is_a else groups[1]
            else:
                self._upload(layer, self.front)
                group = self.ab if source_is_a else self.ba
            queue.write_buffer(self.opts, 0, np.array([index, self.transfer, 0, 0], np.float32))
            encoder = self.device.create_command_encoder()
            step = encoder.begin_compute_pass()
            step.set_pipeline(self.pipeline)
            step.set_bind_group(0, group)
            step.dispatch_workgroups((self.count + 63) // 64)
            step.end()
            queue.submit([encoder.finish()])
            source_is_a = not source_is_a
        self.staged = 0
        final = self.a if source_is_a else self.b
        deep = canvas.dtype == np.uint16
        encoder = self.device.create_command_encoder()
        step = encoder.begin_compute_pass()
        step.set_pipeline(self.pack16 if deep else self.pack)
        step.set_bind_group(0, (self.pack16_groups if deep else self.pack_groups)[id(final)])
        step.dispatch_workgroups((self.count + 63) // 64)
        step.end()
        encoder.copy_buffer_to_buffer(self.packed_out, 0, self.read, 0, self.count * (8 if deep else 4))
        queue.submit([encoder.finish()])
        self.read.map_sync(wgpu.MapMode.READ)
        raw = self.read.read_mapped()
        kind = np.uint16 if deep else np.uint8
        data = np.frombuffer(raw, kind)[: self.count * 4].reshape(canvas.shape[0], canvas.shape[1], 4).copy()
        self.read.unmap()
        return data


def stage_layer(layer: DeviceLayer, height: int, width: int) -> int | None:
    """Hand a device layer to the frame's compositor without a readback; None when the stack is not active."""
    try:
        with _lock:
            key = (height, width)
            if key not in _compositors:
                _compositors[key] = _StackCompositor(*key)
                while len(_compositors) > 3:
                    _compositors.pop(next(iter(_compositors)))
            return _compositors[key].stage(layer)
    except Exception:
        return None


TRANSFERS = {"srgb": 0, "bt709": 0, "pq": 1, "smpte2084": 1, "hlg": 2, "arib-std-b67": 2}


def composite_stack(canvas: np.ndarray, layers: list, transfer: str = "srgb") -> np.ndarray:
    """Blend a run of (layer, mode) onto the canvas in one device pass.

    Falls back layer by layer through composite() if the device path fails,
    so a driver problem degrades to the reference rather than to an error. A
    staged device layer has no bytes on this side to fall back with, so a
    failure with one in the run blows the stack's fuse: this frame keeps the
    layers it can, and every later frame takes the reference path.
    """
    global _stack_fuse
    if not layers:
        return canvas
    try:
        with _lock:
            key = canvas.shape[:2]
            if key not in _compositors:
                _compositors[key] = _StackCompositor(*key)
                while len(_compositors) > 3:
                    _compositors.pop(next(iter(_compositors)))
            _compositors[key].transfer = TRANSFERS.get(transfer.lower(), 0)
            return _compositors[key].run(canvas, layers)
    except Exception as exc:
        if any(isinstance(layer, int) for layer, _ in layers):
            _stack_fuse = f"{type(exc).__name__}: {exc}"[:200]
        for layer, mode in layers:
            if isinstance(layer, int):
                continue
            canvas = composite(canvas, layer, mode)
        return canvas


_stack_fuse: str | None = None


def stack_fault() -> str | None:
    """Why the stack compositor switched itself off, when it did."""
    return _stack_fuse


def custom_values(values: np.ndarray, source: str, time: float, params: list | None = None) -> np.ndarray:
    """A user shader over float RGBA in 0..1; binding 1 carries [w, h, time, 0] and then up to twelve package parameters."""
    if not status()["available"]:
        raise ValueError("Custom WGSL needs a working WebGPU adapter: " + status().get("reason", ""))
    from wgpu.utils.compute import compute_with_buffers

    h, w = values.shape[:2]
    values = np.ascontiguousarray(values, np.float32)
    uniform = np.zeros(16, np.float32)
    uniform[:4] = [w, h, time, 0]
    for n, value in enumerate((params or [])[:12]):
        uniform[4 + n] = float(value)
    with _lock:
        out = compute_with_buffers({0: values, 1: uniform}, {2: (values.size, "f")}, source, n=(w * h + 63) // 64)[2]
    return np.clip(np.frombuffer(out, np.float32).reshape(values.shape), 0, 1)


def custom(image: np.ndarray, source: str, time: float) -> np.ndarray:
    return np.round(custom_values(image.astype(np.float32) / 255, source, time) * 255).astype(np.uint8)


def trial(source: str, params: list | None = None) -> str | None:
    """Compile and run a shader on a 4x4 frame; the reason it cannot be enabled, or None."""
    state = status()
    if not state["available"]:
        return "needs a WebGPU adapter: " + state.get("reason", "")
    try:
        out = custom_values(np.full((4, 4, 4), 0.5, np.float32), source, 0.0, params)
    except Exception as exc:
        return str(exc).strip().splitlines()[0][:300] if str(exc).strip() else exc.__class__.__name__
    if out.shape != (4, 4, 4) or not np.isfinite(out).all():
        return "the shader wrote a frame of the wrong shape or with non-finite values"
    return None
