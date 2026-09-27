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
POOL = 8
CACHE = 4  # pictures that keep static layers (titles, stills) finished across frames
CANVAS_A = WORKING + POOL + CACHE
CANVAS_B = CANVAS_A + 1
PICTURES = CANVAS_B + 1
# The executor's API: 2 takes bytes and returns bytes (1, the first build, moved every byte as a Python int)
API = 7
# Shared by every Recorder: one executor, its kernels by source, the pool of staged layers, the steps pending
_kernels: dict[str, int] = {}
_shared = {"pending": 0}
# The working pictures by slot (the engine's context.buffers[0..4]) and the free pictures. Staging a layer
# renames its picture out of the working set and gives the slot a free one, so a finished layer is never
# copied; the staged pictures come back to the free list when the frame is composed.
_working: list[int] = list(range(WORKING))
_free: list[int] = list(range(WORKING, WORKING + POOL))
_staged: list[int] = []
# static layers kept on the device by key, oldest first; the pictures handed out this frame are not evicted
_cache: dict = {}
_cache_used: set[int] = set()


def _reset_pictures() -> None:
    _working[:] = list(range(WORKING))
    _free[:] = list(range(WORKING, WORKING + POOL))
    _staged.clear()
    _cache.clear()
    _cache_used.clear()


def _u8(array: np.ndarray) -> np.ndarray:
    """A picture or a field as the contiguous uint8 view the executor reads in place."""
    return np.ascontiguousarray(array).view(np.uint8).reshape(-1)


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
        if os.environ.get("FORMCUT_FRAME") == "pyref":
            # the reference executor in Python, the Rust one's semantics exactly: for verifying the recorder
            _status = {"available": True, "adapter": PyFrame(4 * 4 * 16, 2).adapter() + " (python reference executor)"}
            return _status
        if os.environ.get("FORMCUT_FRAME_GL") != "1":
            # On OpenGL even opening the executor's device beside the Python one can abort the process at exit
            # (seen on llvmpipe), so an OpenGL machine is told apart by the Python device's own adapter first.
            from . import gpu

            described = str(gpu.status().get("adapter", {})).lower()
            if "opengl" in described or "'gl'" in described:
                raise RuntimeError("the Rust executor is not used on OpenGL")
        import formcut_native

        probe = formcut_native.GpuFrame(4 * 4 * 16, 2)
        api = probe.api() if hasattr(probe, "api") else 1
        if api < API:
            raise RuntimeError(f"formcut_native is an older build (api {api}, this engine wants {API}); run setup/build_native_gpu")
        name = probe.adapter()
        if "(Gl)" in name and os.environ.get("FORMCUT_FRAME_GL") != "1":
            # On OpenGL the executor's context and the Python device's context are both bound to the thread
            # through EGL, and the two libraries in one process abort each other (seen on llvmpipe). Metal,
            # Vulkan and DX12 have no thread-bound context; OpenGL keeps the Python path.
            raise RuntimeError(f"the Rust executor is not used on OpenGL ({name})")
        _status = {"available": True, "adapter": name}
    except Exception as exc:  # noqa: BLE001 - any failure means the Python path, with the reason kept
        _unavailable = f"{type(exc).__name__}: {exc}"[:200]
        _status = {"available": False, "reason": _unavailable}
    return _status


def executor(height: int, width: int):
    """One executor per process, sized for the largest frame seen so far."""
    global _frame
    need = width * height * 16
    if _frame is None or _frame[0] < need:
        if _frame is not None and _shared["pending"]:
            # growing now would drop what this frame has recorded; this layer takes the CPU path, the next frame grows
            raise RuntimeError("the frame executor cannot grow mid-frame")
        if os.environ.get("FORMCUT_FRAME") == "pyref":
            made = PyFrame(need, PICTURES)
        else:
            import formcut_native

            made = formcut_native.GpuFrame(need, PICTURES)
        _frame = (need, made)
        _kernels.clear()
        _reset_pictures()
    return _frame[1]


class Recorder:
    """The device context the engine's passes run on, recording instead of running. Every Recorder shares the
    one executor, its pictures and its pool; a Recorder is a size, as a context is on the Python path."""

    def __init__(self, height: int, width: int):
        from .gpu_effects import HEADER

        self.h, self.w = height, width
        self.header = HEADER
        executor(height, width)
        self.aux_size = 1 << 40  # anything fits: each pass carries its own aux buffer
        self.light = (0, 0.0)  # after a planar compose: the brightest sixteen-bit code and the mean light in nits

    @property
    def frame(self):
        return _frame[1]

    @property
    def buffers(self) -> list[int]:
        return _working

    def kernel(self, code: str) -> int:
        full = code if code.lstrip().startswith("@group") else self.header + code
        known = _kernels.get(full)
        if known is None:
            known = _kernels[full] = self.frame.kernel(full)
        return known

    def _step(self, code: int, src: int, dst: int, held: int, w: int, h: int, params: list, aux: bytes | None):
        call = getattr(self.frame, "step", None) or getattr(self.frame, "pass")
        call(code, src, dst, held, w, h, params, aux)
        _shared["pending"] += 1

    def _run(self) -> bytes:
        from .gpu_effects import UNPACK16_CODE, UNPACK_CODE

        data = self.frame.run(self.kernel(UNPACK_CODE), self.kernel(UNPACK16_CODE))
        _shared["pending"] = 0
        return data if isinstance(data, (bytes, bytearray)) else bytes(data)

    fuses_upload = True  # a layer's upload may join its fused chain (gpu_effects._fused)

    def run(self, code: str, src, dst, params: list, aux: np.ndarray | None = None, width: int | None = None, height: int | None = None):
        w, h = int(width or self.w), int(height or self.h)
        # every run in the engine passes [w, h, ...] with w and h the dispatch size; the executor prepends them
        from .gpu_effects import RawAux

        if aux is None:
            field = None
        elif isinstance(aux, RawAux):
            field = _u8(aux.data)  # a picture's own bytes, read by the kernel as words
        else:
            field = _u8(np.asarray(aux, dtype=np.float32))
        self._step(self.kernel(code), int(src), int(dst), _working[2], w, h, [float(v) for v in params[2:]], field)

    def upload(self, buffer, image: np.ndarray):
        image = np.asarray(image)
        h, w = image.shape[:2]
        if image.ndim == 2:
            image = np.repeat(image[:, :, None], 4, axis=2)
        if image.dtype not in (np.uint8, np.uint16):
            # the Python context takes float pictures on the 0..255 scale (it divides by 255)
            image = np.clip(np.round(image), 0, 255).astype(np.uint8)
        if image.shape[2] == 3:
            full = 65535 if image.dtype == np.uint16 else 255
            image = np.concatenate([image, np.full((h, w, 1), full, image.dtype)], axis=2)
        self.frame.upload(int(buffer), int(w), int(h), image.dtype == np.uint16, _u8(image))
        _shared["pending"] += 1

    def copy(self, source, target, height: int, width: int):
        self.frame.copy(int(source), int(target), int(width), int(height))
        _shared["pending"] += 1

    def stage(self, picture: int, height: int, width: int) -> int | None:
        """A finished layer handed to the blend by renaming: its picture leaves the working set and the slot takes
        a free one, so nothing is copied; the picture is the layer's handle until the frame is composed."""
        picture = int(picture)
        if not _free or picture not in _working:
            return None
        _working[_working.index(picture)] = _free.pop()
        _staged.append(picture)
        return picture

    def stage_base(self, picture, height: int, width: int) -> int | None:
        """The frame's first layer, already blended over the blank canvas by its own kernel: it becomes the canvas."""
        handle = self.stage(picture, height, width)
        return None if handle is None else BaseLayer(handle)

    def cached(self, key) -> int | None:
        """The picture that holds a static layer finished in an earlier frame, or None."""
        picture = _cache.pop(key, None)
        if picture is None:
            return None
        _cache[key] = picture  # most recent last
        _cache_used.add(picture)
        return picture

    def keep(self, key, picture, height: int, width: int) -> int | None:
        """Copy a finished static layer into a cache picture and hand that picture to the blend."""
        slot = _cache.pop(key, None)
        if slot is None:
            taken = set(_cache.values())
            spare = [p for p in range(WORKING + POOL, WORKING + POOL + CACHE) if p not in taken]
            if spare:
                slot = spare[0]
            else:
                oldest = next((k for k, p in _cache.items() if p not in _cache_used), None)
                if oldest is None:
                    return None
                slot = _cache.pop(oldest)
        self.copy(int(picture), slot, height, width)
        _cache[key] = slot
        _cache_used.add(slot)
        return slot

    def download(self, buffer, height: int, width: int) -> np.ndarray:
        """A working picture's floats, exactly (a CPU-only effect mid-chain): runs what is recorded so far."""
        self.frame.download(int(buffer), self.kernel(PACK_F32_FRAME_CODE), int(width), int(height), int(width) * int(height) * 16)
        return np.frombuffer(self._run(), np.float32).reshape(height, width, 4)  # read-only, not copied

    def download16(self, buffer, height: int, width: int) -> np.ndarray:
        return np.round(np.clip(self.download(buffer, height, width), 0, 1) * 65535).astype(np.uint16)

    def compose(self, canvas: np.ndarray, layers: list, transfer: int, yuv: bool, blank: bool = False) -> np.ndarray:
        """Blend the staged layers over the canvas, in light, and pack the frame: the compositor's job."""
        from .gpu import MODES

        h, w = canvas.shape[:2]
        deep = canvas.dtype == np.uint16
        # a blank canvas is neither uploaded nor cleared: the first blend is told the base is zero and reads nothing
        # the renderer knows a canvas it has not painted (its colour is zero, whatever its alpha); otherwise look
        blank = blank or not canvas.any()
        base, other = CANVAS_A, CANVAS_B
        if layers and isinstance(layers[0][0], BaseLayer):
            # the first layer blended itself over the blank canvas in its own kernel: its picture is the canvas
            base, other, blank = int(layers[0][0]), CANVAS_A, False
            layers = layers[1:]
        elif not blank:
            self.upload(CANVAS_A, canvas)
        elif not layers:
            self.frame.clear(CANVAS_A, w * h * 16)
        blend = self.kernel(BLEND_FRAME_CODE)
        last = None  # the last layer is blended inside the pack: the frame is written once, not written and read
        for n, (layer, mode) in enumerate(layers):
            if isinstance(layer, (int, np.integer)):
                front = int(layer)
            else:
                self.upload(_working[0] if n < len(layers) - 1 else _working[1], layer)
                front = _working[0] if n < len(layers) - 1 else _working[1]
            index = MODES.index(mode.lower()) if mode.lower() in MODES else 0
            settings = [float(index), float(transfer), 1.0 if blank else 0.0]
            if n == len(layers) - 1:
                last = (front, settings)
                break
            self._step(blend, base, other, front, w, h, settings, None)
            blank = False
            base, other = other, base
        planar = bool(yuv) and deep and w % 4 == 0 and h % 2 == 0
        held, settings = (last[0], last[1]) if last else (None, None)
        if planar:
            planes = w * h * 3
            groups = ((w + 15) // 16) * ((h + 15) // 16)
            # P010 (ten bits high in sixteen, chroma interleaved) is what VideoToolbox takes without a conversion
            p010 = yuv == "p010le"
            code = PACK_YUV_FRAME_CODE.replace("TRANSFER", "2u" if transfer == 2 else "1u").replace("P010", "true" if p010 else "false")
            code = _blended(code) if last else code
            self.frame.download(base, self.kernel(code), w, h, planes + groups * 8, held, settings)
        else:
            code = PACK16_FRAME_CODE if deep else PACK_FRAME_CODE
            code = _blended(code) if last else code
            self.frame.download(base, self.kernel(code), w, h, w * h * (8 if deep else 4), held, settings)
        data = self._run()
        _free.extend(_staged)
        _staged.clear()
        _cache_used.clear()
        if planar:
            # the light the pack measured, one (brightest code, light sum) pair a workgroup
            tail = np.frombuffer(data, np.uint32, offset=planes, count=groups * 2).reshape(groups, 2)
            total = float(tail[:, 1].view(np.float32).astype(np.float64).sum())
            self.light = (int(tail[:, 0].max()), total / (w * h))
            return np.frombuffer(data, np.uint8, count=planes)
        # the frame as a read-only view of the bytes the executor returned: a copy of it was 16.6 MB and 3 ms a
        # 1080p sixteen-bit frame on the M5, and nothing writes into a rendered frame
        return np.frombuffer(data, np.uint16 if deep else np.uint8).reshape(h, w, 4)


class BaseLayer(int):
    """A staged layer that is already the canvas (blended over blank by its own kernel)."""


def _blended(pack: str) -> str:
    """A pack kernel that blends the frame's last layer (held) over the canvas (src) as it reads each pixel: the
    compositor's own blend arithmetic, the same to the bit, with the frame written once instead of twice."""
    body = _blend_body().rstrip()
    body = body[: body.rfind("}")].replace("dst[i] = ", "return ")
    function = "fn blend_at(i: i32) -> vec4<f32> {\n    " + body + "\n}\n"
    code = pack.replace("@compute @workgroup_size(16, 16)", _blend_functions() + function + "@compute @workgroup_size(16, 16)", 1)
    code = code.replace("src[y * w + x0 + 1u].rgb", "blend_at(i32(y * w + x0 + 1u)).rgb").replace(
        "src[y * w + x0].rgb", "blend_at(i32(y * w + x0)).rgb"
    )
    code = code.replace("clamp(src[i], vec4<f32>(0.0), vec4<f32>(1.0))", "clamp(blend_at(i32(i)), vec4<f32>(0.0), vec4<f32>(1.0))")
    if "src[" in code.split("fn main", 1)[1]:
        raise RuntimeError("a pack kernel changed shape; the blended pack must follow it")
    return code


def kernel_name(code: int) -> str:
    """A kernel id as the bench prints it: what the kernel does, from its source."""
    from . import gpu_effects

    source = next((src for src, known in _kernels.items() if known == code), "")
    if "fz_step" in source:
        steps = source.count("fz = fz_step")
        head = "a layer's upload, " if "aux_words" in source else ""
        return f"{head}fused chain ({steps} steps)"
    if "blend_at(" in source:
        return "the last blend and the pack" + (" (ten-bit planes)" if "brightest_of" in source else "")
    for module in (gpu_effects, globals_module()):
        for name, value in vars(module).items():
            if name.endswith("_CODE") and isinstance(value, str) and value.strip() and value.strip() in source:
                return name.removesuffix("_CODE").lower().replace("_", " ")
    return f"kernel {code}"


def globals_module():
    import sys

    return sys.modules[__name__]


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
    # p[4] = 1: the base is a blank canvas, so it is zero light and is not read (lin(0) is 0 in every transfer)
    old = "let b = lin(src[i].rgb);"
    if body.count(old) != 1:
        raise RuntimeError("the compositor's blend changed shape; the executor's blend must follow it")
    return body.replace(old, "var b = vec3<f32>(0.0);\n    if (p[4] < 0.5) { b = lin(src[i].rgb); }")


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

# The floats of a picture, exactly, for a mid-frame read.
PACK_F32_FRAME_CODE = (
    _PACK_HEAD
    + """
    let c = src[i];
    packed[i * 4u] = bitcast<u32>(c.x);
    packed[i * 4u + 1u] = bitcast<u32>(c.y);
    packed[i * 4u + 2u] = bitcast<u32>(c.z);
    packed[i * 4u + 3u] = bitcast<u32>(c.w);
}
"""
)

# Ten-bit 4:2:0 planes, one invocation per 4x2 block (the compositor's PACK_YUV_CODE over these bindings), and
# the light for MaxCLL and MaxFALL measured in the same pass: each invocation takes its block's brightest
# channel code and the sum of its pixels' light (the brightest channel through the transfer, in nits), the
# workgroup reduces its 256 in shared memory, and one (brightest, sum) pair a workgroup lands after the planes.
# TRANSFER is 1u for PQ and 2u for HLG, set when the kernel is registered. No early return: the barrier needs
# every invocation.
PACK_YUV_FRAME_CODE = """
@group(0) @binding(0) var<storage, read> src: array<vec4<f32>>;
@group(0) @binding(1) var<storage, read_write> packed: array<u32>;
@group(0) @binding(2) var<storage, read> p: array<f32>;
@group(0) @binding(3) var<storage, read> aux: array<f32>;
@group(0) @binding(4) var<storage, read> held: array<vec4<f32>>;
var<workgroup> brightest_of: array<u32, 256>;
var<workgroup> light_of: array<f32, 256>;
fn luma(c: vec3<f32>) -> f32 { return 0.2627 * c.r + 0.6780 * c.g + 0.0593 * c.b; }
fn code(v: f32, offset: f32, span: f32) -> u32 { return u32(clamp(round((offset + span * v) * 4.0), 0.0, 1023.0)); }
fn nits(v: f32) -> f32 {
    if (TRANSFER == 2u) {
        let a = 0.17883277;
        let b = 0.28466892;
        let c = 0.55991073;
        return select((exp((v - c) / a) + b) / 12.0, v * v / 3.0, v <= 0.5) * 1000.0;
    }
    let m1 = 0.1593017578125;
    let m2 = 78.84375;
    let c1 = 0.8359375;
    let c2 = 18.8515625;
    let c3 = 18.6875;
    let e = pow(clamp(v, 0.0, 1.0), 1.0 / m2);
    return pow(max(e - c1, 0.0) / (c2 - c3 * e), 1.0 / m1) * 10000.0;
}
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>, @builtin(local_invocation_index) li: u32,
        @builtin(workgroup_id) wg: vec3<u32>, @builtin(num_workgroups) nwg: vec3<u32>) {
    let w = u32(p[0]);
    let h = u32(p[1]);
    let bx = id.x * 4u;
    let by = id.y * 2u;
    var brightest = 0.0;
    var light = 0.0;
    if (bx < w && by < h) {
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
                let shift = select(0u, 6u, P010);
                packed[(y * w + x0) / 2u] = (code(y0, 16.0, 219.0) << shift) | ((code(y1, 16.0, 219.0) << shift) << 16u);
                cb[pair] = cb[pair] + ((c0.b - y0) / 1.8814 + (c1.b - y1) / 1.8814) * 0.25;
                cr[pair] = cr[pair] + ((c0.r - y0) / 1.4746 + (c1.r - y1) / 1.4746) * 0.25;
                let m0 = max(c0.r, max(c0.g, c0.b));
                let m1 = max(c1.r, max(c1.g, c1.b));
                brightest = max(brightest, max(m0, m1));
                light = light + nits(m0) + nits(m1);
            }
        }
        let y_words = (w * h) / 2u;
        let u_words = (cw * ch) / 2u;
        let cindex = (by / 2u) * cw + bx / 2u;
        if (P010) {
            // one word a chroma sample: U low, V high, each ten bits in the top of sixteen
            packed[y_words + cindex] = (code(cb[0], 128.0, 224.0) << 6u) | ((code(cr[0], 128.0, 224.0) << 6u) << 16u);
            packed[y_words + cindex + 1u] = (code(cb[1], 128.0, 224.0) << 6u) | ((code(cr[1], 128.0, 224.0) << 6u) << 16u);
        } else {
            packed[y_words + cindex / 2u] = code(cb[0], 128.0, 224.0) | (code(cb[1], 128.0, 224.0) << 16u);
            packed[y_words + u_words + cindex / 2u] = code(cr[0], 128.0, 224.0) | (code(cr[1], 128.0, 224.0) << 16u);
        }
    }
    brightest_of[li] = u32(round(brightest * 65535.0));
    light_of[li] = light;
    workgroupBarrier();
    if (li == 0u) {
        var top = 0u;
        var sum = 0.0;
        for (var k = 0u; k < 256u; k = k + 1u) {
            top = max(top, brightest_of[k]);
            sum = sum + light_of[k];
        }
        let slot = (w * h * 3u) / 4u + (wg.y * nwg.x + wg.x) * 2u;
        packed[slot] = top;
        packed[slot + 1u] = bitcast<u32>(sum);
    }
}
"""


class PyFrame:
    """The Rust executor's semantics in wgpu-py, exactly: the same bind layout (0 read, 1 write, 2 params, 3 aux,
    4 held), one command encoder a run, a compute pass a dispatch at (ceil(w/16), ceil(h/16)), [w, h] prepended to
    a pass's parameters, a 16-byte aux when none is given, the upload through the unpack kernels with the other
    picture as its source and held. FORMCUT_FRAME=pyref selects it; it is how the recorder is verified on a
    machine without the Rust build, and the Rust executor is held to it."""

    def __init__(self, picture_bytes: int, pictures: int):
        import wgpu
        from wgpu.utils import get_default_device

        self.wgpu = wgpu
        self.device = get_default_device()
        ro = {"type": wgpu.BufferBindingType.read_only_storage}
        rw = {"type": wgpu.BufferBindingType.storage}
        self.layout = self.device.create_bind_group_layout(
            entries=[{"binding": b, "visibility": wgpu.ShaderStage.COMPUTE, "buffer": rw if b == 1 else ro} for b in range(5)]
        )
        self.pipeline_layout = self.device.create_pipeline_layout(bind_group_layouts=[self.layout])
        usage = wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC | wgpu.BufferUsage.COPY_DST
        self.pictures = [self.device.create_buffer(size=max(16, picture_bytes), usage=usage) for _ in range(pictures)]
        self.sources: list[str] = []
        self.pipelines: dict[int, object] = {}
        self.steps: list[tuple] = []

    def adapter(self) -> str:
        return str(self.device.adapter.info.get("device", "adapter"))

    def api(self) -> int:
        return API

    def kernel(self, source: str) -> int:
        if source in self.sources:
            return self.sources.index(source)
        self.sources.append(source)
        return len(self.sources) - 1

    def upload(self, picture, width, height, deep, data):
        self.steps.append(("upload", picture, width, height, deep, bytes(data)))

    def step(self, code, src, dst, held, width, height, params, aux=None):
        self.steps.append(("pass", code, src, dst, held, width, height, list(params), aux))

    def copy(self, source, target, width, height):
        self.steps.append(("copy", source, target, width, height))

    def clear(self, picture, nbytes):
        self.steps.append(("clear", picture, nbytes))

    def timings(self):
        return (0.0, 0.0, 0.0)

    def pass_times(self):
        return []

    def download(self, picture, code, width, height, out_bytes, held=None, params=None):
        self.steps.append(("download", picture, code, width, height, out_bytes, picture if held is None else held, list(params or [])))

    def _buffer(self, data: bytes):
        return self.device.create_buffer_with_data(data=data, usage=self.wgpu.BufferUsage.STORAGE)

    def _params(self, values: list) -> object:
        padded = list(values) + [0.0] * max(0, 32 - len(values))
        return self._buffer(np.asarray(padded, np.float32).tobytes())

    def _pipeline(self, code: int):
        if code not in self.pipelines:
            module = self.device.create_shader_module(code=self.sources[code])
            self.pipelines[code] = self.device.create_compute_pipeline(
                layout=self.pipeline_layout, compute={"module": module, "entry_point": "main"}
            )
        return self.pipelines[code]

    def _dispatch(self, encoder, code, bindings, width, height):
        group = self.device.create_bind_group(
            layout=self.layout,
            entries=[{"binding": b, "resource": {"buffer": buf, "offset": 0, "size": buf.size}} for b, buf in enumerate(bindings)],
        )
        step = encoder.begin_compute_pass()
        step.set_pipeline(self._pipeline(code))
        step.set_bind_group(0, group)
        step.dispatch_workgroups((width + 15) // 16, (height + 15) // 16)
        step.end()

    def run(self, unpack_code: int, unpack16_code: int) -> bytes:
        wgpu = self.wgpu
        steps, self.steps = self.steps, []
        encoder = self.device.create_command_encoder()
        readback = None
        for item in steps:
            kind = item[0]
            if kind == "upload":
                _, picture, width, height, deep, data = item
                other = 1 if picture == 0 else 0
                staging = self._buffer(data)
                bindings = [self.pictures[other], self.pictures[picture], self._params([width, height]), staging, self.pictures[other]]
                self._dispatch(encoder, unpack16_code if deep else unpack_code, bindings, width, height)
            elif kind == "pass":
                _, code, src, dst, held, width, height, params, aux = item
                aux_buffer = self._buffer(bytes(aux) if aux is not None else bytes(16))
                bindings = [self.pictures[src], self.pictures[dst], self._params([width, height, *params]), aux_buffer, self.pictures[held]]
                self._dispatch(encoder, code, bindings, width, height)
            elif kind == "clear":
                _, picture, nbytes = item
                encoder.clear_buffer(self.pictures[picture], 0, (nbytes + 3) // 4 * 4)
            elif kind == "copy":
                _, source, target, width, height = item
                encoder.copy_buffer_to_buffer(self.pictures[source], 0, self.pictures[target], 0, width * height * 16)
            else:
                _, picture, code, width, height, out_bytes, held, extra = item
                size = max(16, (out_bytes + 3) // 4 * 4)
                packed = self.device.create_buffer(size=size, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC)
                params = self._params([width, height, *extra])
                bindings = [self.pictures[picture], packed, params, params, self.pictures[held]]
                self._dispatch(encoder, code, bindings, width, height)
                read = self.device.create_buffer(size=size, usage=wgpu.BufferUsage.MAP_READ | wgpu.BufferUsage.COPY_DST)
                encoder.copy_buffer_to_buffer(packed, 0, read, 0, size)
                readback = (read, out_bytes)
        self.device.queue.submit([encoder.finish()])
        if readback is None:
            return b""
        read, out_bytes = readback
        read.map_sync(wgpu.MapMode.READ)
        data = bytes(read.read_mapped())[:out_bytes]
        read.unmap()
        return data
