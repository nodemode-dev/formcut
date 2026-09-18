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
        return _status.copy()


def composite(base: np.ndarray, front: np.ndarray, mode: str) -> np.ndarray:
    index = MODES.index(mode.lower()) if mode.lower() in MODES else 0
    b, f = base.astype(np.float32) / 255, front.astype(np.float32) / 255
    if index and status()["available"]:
        from wgpu.utils.compute import compute_with_buffers
        with _lock:
            out = compute_with_buffers({0: b, 1: f, 2: np.array([index], np.float32)}, {3: (b.size, "f")}, BLEND_CODE, n=(b.shape[0] * b.shape[1] + 63) // 64)[3]
        return np.round(np.frombuffer(out, np.float32).reshape(b.shape) * 255).astype(np.uint8)
    rgb_b, rgb_f = b[:, :, :3], f[:, :, :3]
    modes = [lambda: rgb_f, lambda: rgb_b * rgb_f, lambda: 1 - (1 - rgb_b) * (1 - rgb_f),
             lambda: np.where(rgb_b < 0.5, 2 * rgb_b * rgb_f, 1 - 2 * (1 - rgb_b) * (1 - rgb_f)),
             lambda: np.minimum(rgb_b, rgb_f), lambda: np.maximum(rgb_b, rgb_f), lambda: abs(rgb_b - rgb_f),
             lambda: np.minimum(1, rgb_b + rgb_f), lambda: np.maximum(0, rgb_b - rgb_f),
             lambda: (1 - 2 * rgb_f) * rgb_b ** 2 + 2 * rgb_f * rgb_b]
    alpha = f[:, :, 3:4]
    b[:, :, :3] = np.clip(rgb_b * (1 - alpha) + modes[index]() * alpha, 0, 1)
    b[:, :, 3] = 1
    return np.round(b * 255).astype(np.uint8)


def custom(image: np.ndarray, source: str, time: float) -> np.ndarray:
    if not status()["available"]:
        raise ValueError("Custom WGSL needs a working WebGPU adapter: " + status().get("reason", ""))
    from wgpu.utils.compute import compute_with_buffers
    h, w = image.shape[:2]
    values = image.astype(np.float32) / 255
    with _lock:
        out = compute_with_buffers({0: values, 1: np.array([w, h, time, 0], np.float32)}, {2: (values.size, "f")}, source, n=(w * h + 63) // 64)[2]
    return np.round(np.clip(np.frombuffer(out, np.float32).reshape(image.shape), 0, 1) * 255).astype(np.uint8)
