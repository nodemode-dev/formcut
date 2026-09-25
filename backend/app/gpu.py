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
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let i = id.x;
    if (i >= arrayLength(&result)) { return; }
    let b = background[i].rgb;
    let f = foreground[i].rgb;
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
    result[i] = vec4<f32>(clamp(mix(b, color, alpha), vec3<f32>(0.0), vec3<f32>(1.0)), 1.0);
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


def composite(base: np.ndarray, front: np.ndarray, mode: str) -> np.ndarray:
    index = MODES.index(mode.lower()) if mode.lower() in MODES else 0
    b, f = base.astype(np.float32) / 255, front.astype(np.float32) / 255
    if index and status()["available"]:
        from wgpu.utils.compute import compute_with_buffers

        with _lock:
            out = compute_with_buffers(
                {0: b, 1: f, 2: np.array([index], np.float32)}, {3: (b.size, "f")}, BLEND_CODE, n=(b.shape[0] * b.shape[1] + 63) // 64
            )[3]
        return np.round(np.frombuffer(out, np.float32).reshape(b.shape) * 255).astype(np.uint8)
    rgb_b, rgb_f = b[:, :, :3], f[:, :, :3]
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
    b[:, :, :3] = np.clip(rgb_b * (1 - alpha) + modes[index]() * alpha, 0, 1)
    b[:, :, 3] = 1
    return np.round(b * 255).astype(np.uint8)


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
    return _stack_wanted(status())


class _StackCompositor:
    """One frame size's device state: buffers, pipeline, both bind directions."""

    def __init__(self, height: int, width: int):
        import wgpu
        from wgpu.utils import get_default_device

        self.device = get_default_device()
        self.count = height * width
        size = self.count * 16  # vec4<f32>
        usage = wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.COPY_SRC
        self.a = self.device.create_buffer(size=size, usage=usage)
        self.b = self.device.create_buffer(size=size, usage=usage)
        self.front = self.device.create_buffer(size=size, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST)
        self.opts = self.device.create_buffer(size=16, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST)
        self.read = self.device.create_buffer(size=size, usage=wgpu.BufferUsage.MAP_READ | wgpu.BufferUsage.COPY_DST)
        module = self.device.create_shader_module(code=BLEND_CODE)
        self.pipeline = self.device.create_compute_pipeline(layout="auto", compute={"module": module, "entry_point": "main"})
        layout = self.pipeline.get_bind_group_layout(0)

        def group(back, out):
            entries = [
                {"binding": 0, "resource": {"buffer": back, "offset": 0, "size": size}},
                {"binding": 1, "resource": {"buffer": self.front, "offset": 0, "size": size}},
                {"binding": 2, "resource": {"buffer": self.opts, "offset": 0, "size": 16}},
                {"binding": 3, "resource": {"buffer": out, "offset": 0, "size": size}},
            ]
            return self.device.create_bind_group(layout=layout, entries=entries)

        self.ab = group(self.a, self.b)
        self.ba = group(self.b, self.a)

    def run(self, canvas: np.ndarray, layers: list) -> np.ndarray:
        import wgpu

        queue = self.device.queue
        queue.write_buffer(self.a, 0, np.ascontiguousarray(canvas.astype(np.float32) / 255))
        source_is_a = True
        for layer, mode in layers:
            index = MODES.index(mode.lower()) if mode.lower() in MODES else 0
            queue.write_buffer(self.front, 0, np.ascontiguousarray(layer.astype(np.float32) / 255))
            queue.write_buffer(self.opts, 0, np.array([index, 0, 0, 0], np.float32))
            encoder = self.device.create_command_encoder()
            step = encoder.begin_compute_pass()
            step.set_pipeline(self.pipeline)
            step.set_bind_group(0, self.ab if source_is_a else self.ba)
            step.dispatch_workgroups((self.count + 63) // 64)
            step.end()
            queue.submit([encoder.finish()])
            source_is_a = not source_is_a
        final = self.a if source_is_a else self.b
        encoder = self.device.create_command_encoder()
        encoder.copy_buffer_to_buffer(final, 0, self.read, 0, self.count * 16)
        queue.submit([encoder.finish()])
        self.read.map_sync(wgpu.MapMode.READ)
        data = np.frombuffer(self.read.read_mapped(), np.float32).reshape(canvas.shape[0], canvas.shape[1], 4).copy()
        self.read.unmap()
        return np.round(data * 255).astype(np.uint8)


def composite_stack(canvas: np.ndarray, layers: list) -> np.ndarray:
    """Blend a run of (layer, mode) onto the canvas in one device pass.

    Falls back layer by layer through composite() if the device path fails,
    so a driver problem degrades to the reference rather than to an error.
    """
    if not layers:
        return canvas
    try:
        with _lock:
            key = canvas.shape[:2]
            if key not in _compositors:
                _compositors[key] = _StackCompositor(*key)
                while len(_compositors) > 3:
                    _compositors.pop(next(iter(_compositors)))
            return _compositors[key].run(canvas, layers)
    except Exception:
        for layer, mode in layers:
            canvas = composite(canvas, layer, mode)
        return canvas


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
