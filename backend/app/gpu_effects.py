"""R3: a clip's effect chain and transform warp as device passes.

The layer goes up once, every supported effect runs as a WGSL compute pass
between two resident buffers, the affine warp samples it into a frame-sized
buffer, and one readback returns the warped layer for the blend. The CPU
functions in pixel_effects.py and cv2.warpAffine stay the reference: a chain
with an effect this module does not carry returns None and the caller takes
the reference path, and any device failure does the same, frame by frame.
FORMCUT_EFFECTS=cpu forces the reference; =gpu forces this; unset follows the
compositor (gpu.stack_active), so a software adapter never carries it.
"""

import math
import os
import threading

import cv2
import numpy as np

from . import gpu
from .catalogue import EFFECT_DEFAULTS, GRADES, clamp_params
from .pixel_effects import FIELD_EFFECTS, REMAP_EFFECTS, field_for, remap_maps

SUPPORTED = frozenset(
    {
        "fisheye",
        "wave",
        "kaleidoscope",
        "swirl",
        "ripple",
        "pinch",
        "tile-repeat",
        "polar-wrap",
        "heat-haze",
        "solarize",
        "duotone",
        "night-vision",
        "anaglyph",
        "fog",
        "radial-blur",
        "spin-blur",
        "diagonal-blur",
        "ghost-trail",
        "tilt-shift",
        "soft-focus",
        "light-leak",
        "lens-flare",
        "aperture-grille",
        "paper-texture",
        "chroma-noise",
        "film-scratches",
        "camera-shake",
        "crosshatch",
        "halftone",
        "bayer-dither",
        "interference",
        "hex-pixelate",
        "bokeh-spots",
        "sparkles",
        "snowfall",
        "gaussian",
        "box",
        "directional-blur",
        "sharpen",
        "vignette",
        "grain",
        "glow",
        "chromatic",
        "pixelate",
        "mirror",
        "invert",
        "posterize",
        "threshold",
        "scanlines",
    }
)
POINT_MODES = {
    "invert": 1,
    "posterize": 2,
    "threshold": 3,
    "vignette": 4,
    "scanlines": 5,
    "grain": 6,
    "chromatic": 7,
    "mirror": 8,
    "solarize": 9,
    "duotone": 10,
    "night-vision": 11,
    "anaglyph": 12,
    "fog": 13,
}
PARAM_FLOATS = 32

HEADER = """
@group(0) @binding(0) var<storage, read> src: array<vec4<f32>>;
@group(0) @binding(1) var<storage, read_write> dst: array<vec4<f32>>;
@group(0) @binding(2) var<storage, read> p: array<f32>;
@group(0) @binding(3) var<storage, read> aux: array<f32>;
@group(0) @binding(4) var<storage, read> held: array<vec4<f32>>;

fn reflect101(i: i32, n: i32) -> i32 {
    var k = i;
    if (n == 1) { return 0; }
    loop {
        if (k < 0) { k = -k; } else if (k >= n) { k = 2 * n - 2 - k; } else { break; }
    }
    return k;
}
"""

# R7: a layer arrives as its own RGBA bytes, four a pixel, in aux; this pass
# spreads them into the vec4<f32> the chain works in. A full module of its
# own, so aux can be declared as the u32 words the bytes are, not floats.
UNPACK_CODE = """
@group(0) @binding(0) var<storage, read> src: array<vec4<f32>>;
@group(0) @binding(1) var<storage, read_write> dst: array<vec4<f32>>;
@group(0) @binding(2) var<storage, read> p: array<f32>;
@group(0) @binding(3) var<storage, read> aux: array<u32>;
@group(0) @binding(4) var<storage, read> held: array<vec4<f32>>;
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let v = aux[i];
    dst[i] = vec4<f32>(f32(v & 255u), f32((v >> 8u) & 255u), f32((v >> 16u) & 255u), f32(v >> 24u)) / 255.0;
}
"""

# One pointwise pass: p[2] picks the effect, p[3..] its settings.
POINT_CODE = """
fn at(x: i32, y: i32) -> vec4<f32> {
    let w = i32(p[0]);
    let h = i32(p[1]);
    return src[reflect101(y, h) * w + reflect101(x, w)];
}
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let pixel = src[i];
    var rgb = pixel.rgb;
    let mode = i32(p[2]);
    if (mode == 1) { rgb = vec3<f32>(1.0) - rgb; }
    if (mode == 2) {
        let steps = p[3] - 1.0;
        rgb = round(rgb * steps) / steps;
    }
    if (mode == 3) {
        let mean = (rgb.r + rgb.g + rgb.b) / 3.0;
        rgb = select(vec3<f32>(0.0), vec3<f32>(1.0), mean > p[3]);
    }
    if (mode == 4) {
        let u = (f32(x) + 0.5) / p[0] - 0.5;
        let v = (f32(y) + 0.5) / p[1] - 0.5;
        let falloff = clamp(1.0 - (u * u + v * v) * 2.2, 0.0, 1.0);
        rgb = rgb * (1.0 - p[3] * (1.0 - falloff));
    }
    if (mode == 5) {
        let depth = 0.25 * p[3];
        rgb = rgb * (1.0 - depth + depth * cos(f32(y) * 6.283185307179586 / max(2.0, p[4])));
    }
    if (mode == 6) { rgb = rgb + vec3<f32>(aux[i]); }
    if (mode == 7) {
        let s = i32(p[3]);
        var left = x - s;
        var right = x + s;
        loop { if (left < 0) { left = left + w; } else { break; } }
        loop { if (right >= w) { right = right - w; } else { break; } }
        rgb = vec3<f32>(src[y * w + left].r, rgb.g, src[y * w + right].b);
    }
    if (mode == 8) {
        let u = (f32(x) + 0.5) / p[0];
        let sx = abs(u - 0.5) * 2.0 * (p[0] - 1.0);
        let x0 = i32(floor(sx));
        let fx = sx - f32(x0);
        rgb = mix(at(x0, y).rgb, at(x0 + 1, y).rgb, fx);
    }
    // R10: five pointwise effects from pixel_effects.process, mode 9 to 13.
    let grey = dot(rgb, vec3<f32>(0.299, 0.587, 0.114));
    if (mode == 9) {
        // solarize: above the threshold, inverted
        rgb = select(rgb, vec3<f32>(1.0) - rgb, rgb > vec3<f32>(p[3]));
    }
    if (mode == 10) {
        // duotone
        rgb = vec3<f32>(0.07, 0.09, 0.24) * (1.0 - grey) + vec3<f32>(1.0, 0.68, 0.17) * grey;
    }
    if (mode == 11) {
        // night-vision: the noise field in aux, a falloff from the centre
        let u = (f32(x) + 0.5) / p[0];
        let v = (f32(y) + 0.5) / p[1];
        let fall = clamp(1.25 - ((u - 0.5) * (u - 0.5) + (v - 0.5) * (v - 0.5)) * 2.4, 0.0, 1.0);
        let lum = clamp(grey * 1.6 + aux[i], 0.0, 1.0) * fall;
        rgb = vec3<f32>(lum * 0.25, lum, lum * 0.3);
    }
    if (mode == 12) {
        // anaglyph: the grey of the pixels an offset left and right, wrapped as np.roll wraps
        // no i32 modulo here: llvmpipe gets it wrong on negatives (the chromatic pass learned the same)
        let offset = i32(p[3]);
        let w0 = i32(p[0]);
        var xl = x + offset;
        if (xl >= w0) { xl = xl - w0; }
        var xr = x - offset;
        if (xr < 0) { xr = xr + w0; }
        let left = at(xl, y).rgb;
        let right = at(xr, y).rgb;
        let gl = dot(left, vec3<f32>(0.299, 0.587, 0.114));
        let gr = dot(right, vec3<f32>(0.299, 0.587, 0.114));
        rgb = vec3<f32>(gl, gr, gr);
    }
    if (mode == 14) {
        // crosshatch: three hatch families by the grey under them, p[3] the period
        let period = p[3];
        let fx = f32(x);
        let fy = f32(y);
        let d1 = (fx + fy) - floor((fx + fy) / period) * period;
        let d2 = (fx - fy) - floor((fx - fy) / period) * period;
        let d3 = fx - floor(fx / period) * period;
        let ink = (d1 < 1.2 && grey < 0.75) || (d2 < 1.2 && grey < 0.5) || (d3 < 1.2 && grey < 0.28);
        rgb = vec3<f32>(1.0 - select(0.0, 0.9, ink));
    }
    if (mode == 13) {
        // fog: the field slice in aux, denser down the frame, p[3] the density
        let v = (f32(y) + 0.5) / p[1];
        let density = clamp(aux[i] * (0.45 + 0.55 * v) * p[3], 0.0, 1.0) * 0.7;
        rgb = rgb * (1.0 - density) + 0.82 * density;
    }
    dst[i] = vec4<f32>(rgb, pixel.a);
}
"""

# The shared grade (pixel_effects.grade), one pass.
GRADE_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let pixel = src[i];
    var out = pixel.rgb * exp2(p[2]);
    out = (out - 0.5) * p[3] + 0.5 + p[4];
    out = pow(max(out, vec3<f32>(0.0)), vec3<f32>(p[5]));
    let luminance = dot(out, vec3<f32>(0.2126, 0.7152, 0.0722));
    let clipped = clamp(out, vec3<f32>(0.0), vec3<f32>(1.0));
    let spread = max(max(clipped.r, clipped.g), clipped.b) - min(min(clipped.r, clipped.g), clipped.b);
    out = luminance + (out - luminance) * (p[6] + p[7] * (1.0 - spread));
    out = out + vec3<f32>(p[8], -p[9], -p[8]) * 0.35;
    let dark = (1.0 - luminance) * (1.0 - luminance);
    let bright = luminance * luminance;
    out = out + vec3<f32>(p[10], p[11], p[12]) * dark + vec3<f32>(p[13], p[14], p[15]) * bright;
    if (p[16] > 0.0) {
        let sepia = vec3<f32>(
            out.r * 0.393 + out.g * 0.769 + out.b * 0.189,
            out.r * 0.349 + out.g * 0.686 + out.b * 0.168,
            out.r * 0.272 + out.g * 0.534 + out.b * 0.131);
        out = out * (1.0 - p[16]) + sepia * p[16];
    }
    dst[i] = vec4<f32>(out, pixel.a);
}
"""

# One separable convolution pass along (p[2], p[3]) with p[4] taps in aux and
# the anchor at p[5], borders reflected the way OpenCV's default does.
CONV_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let dx = i32(p[2]);
    let dy = i32(p[3]);
    let taps = i32(p[4]);
    let anchor = i32(p[5]);
    var sum = vec3<f32>(0.0);
    for (var k = 0; k < taps; k = k + 1) {
        let o = k - anchor;
        let sx = reflect101(x + o * dx, w);
        let sy = reflect101(y + o * dy, h);
        sum = sum + src[sy * w + sx].rgb * aux[k];
    }
    dst[y * w + x] = vec4<f32>(sum, src[y * w + x].a);
}
"""

# Two-input arithmetic between the current picture and the held one: p[2] picks it.
COMBINE_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let a = src[i];
    let b = held[i].rgb;
    let mode = i32(p[2]);
    var rgb = a.rgb;
    if (mode == 1) { rgb = b * 2.0 - a.rgb; }
    if (mode == 2) { rgb = b + a.rgb; }
    if (mode == 3) { rgb = max(a.rgb - 0.45, vec3<f32>(0.0)); }
    if (mode == 4) { rgb = clamp(mix(b, a.rgb, p[3]), vec3<f32>(0.0), vec3<f32>(1.0)); }
    if (mode == 5) { rgb = clamp(a.rgb, vec3<f32>(0.0), vec3<f32>(1.0)); }
    dst[i] = vec4<f32>(rgb, a.a);
}
"""

# Pixelate: OpenCV's INTER_AREA shrink to (p[2], p[3]) cells, fractional edge
# weights included, then INTER_NEAREST back to the frame, in one pass.
PIXELATE_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let cols = p[2];
    let rows = p[3];
    let cx = i32(floor(f32(x) * cols / p[0]));
    let cy = i32(floor(f32(y) * rows / p[1]));
    let x0 = f32(cx) * p[0] / cols;
    let x1 = f32(cx + 1) * p[0] / cols;
    let y0 = f32(cy) * p[1] / rows;
    let y1 = f32(cy + 1) * p[1] / rows;
    var sum = vec3<f32>(0.0);
    var total = 0.0;
    for (var sy = i32(floor(y0)); sy < min(h, i32(ceil(y1))); sy = sy + 1) {
        let wy = min(f32(sy) + 1.0, y1) - max(f32(sy), y0);
        if (wy <= 0.0) { continue; }
        for (var sx = i32(floor(x0)); sx < min(w, i32(ceil(x1))); sx = sx + 1) {
            let wx = min(f32(sx) + 1.0, x1) - max(f32(sx), x0);
            if (wx <= 0.0) { continue; }
            sum = sum + src[sy * w + sx].rgb * (wx * wy);
            total = total + wx * wy;
        }
    }
    dst[y * w + x] = vec4<f32>(sum / max(total, 1e-9), src[y * w + x].a);
}
"""

# R13: halftone and bayer-dither over the same INTER_AREA cell average as
# pixelate, with the cell addressed the way process() addresses it. Halftone
# reads the grey of cell (x // cell, y // cell) clamped to the small grid and
# draws a dot whose radius follows the darkness; p[2] cols, p[3] rows, p[4]
# the cell. Bayer takes the cell average of colour, adds the 4x4 threshold
# of the cell's position and floors to four levels; p[4] the step.
CELL_CODE = """
fn cell_mean(cx: i32, cy: i32, cols: f32, rows: f32, w: i32, h: i32) -> vec3<f32> {
    let x0 = f32(cx) * p[0] / cols;
    let x1 = f32(cx + 1) * p[0] / cols;
    let y0 = f32(cy) * p[1] / rows;
    let y1 = f32(cy + 1) * p[1] / rows;
    var sum = vec3<f32>(0.0);
    var total = 0.0;
    for (var sy = i32(floor(y0)); sy < min(h, i32(ceil(y1))); sy = sy + 1) {
        let wy = min(f32(sy) + 1.0, y1) - max(f32(sy), y0);
        if (wy <= 0.0) { continue; }
        for (var sx = i32(floor(x0)); sx < min(w, i32(ceil(x1))); sx = sx + 1) {
            let wx = min(f32(sx) + 1.0, x1) - max(f32(sx), x0);
            if (wx <= 0.0) { continue; }
            sum = sum + src[sy * w + sx].rgb * (wx * wy);
            total = total + wx * wy;
        }
    }
    return sum / max(total, 1e-9);
}
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let cols = p[2];
    let rows = p[3];
    let cell = i32(p[4]);
    let cx = min(x / cell, i32(cols) - 1);
    let cy = min(y / cell, i32(rows) - 1);
    let mean = cell_mean(cx, cy, cols, rows, w, h);
    var rgb = vec3<f32>(1.0);
    if (i32(p[5]) == 1) {
        let level = dot(mean, vec3<f32>(0.299, 0.587, 0.114));
        let fx = f32(x % cell) - f32(cell) / 2.0;
        let fy = f32(y % cell) - f32(cell) / 2.0;
        let dot_here = sqrt(fx * fx + fy * fy) < (1.0 - level) * f32(cell) * 0.62;
        rgb = vec3<f32>(select(1.0, 0.0, dot_here));
    } else {
        // the Bayer 4x4 threshold, indexed by the cell's position in the small grid
        let mrow = cy % 4;
        let mcol = cx % 4;
        var t = 0.0;
        if (mrow == 0) { t = select(select(select(0.0, 8.0, mcol == 1), 2.0, mcol == 2), 10.0, mcol == 3); }
        if (mrow == 1) { t = select(select(select(12.0, 4.0, mcol == 1), 14.0, mcol == 2), 6.0, mcol == 3); }
        if (mrow == 2) { t = select(select(select(3.0, 11.0, mcol == 1), 1.0, mcol == 2), 9.0, mcol == 3); }
        if (mrow == 3) { t = select(select(select(15.0, 7.0, mcol == 1), 13.0, mcol == 2), 5.0, mcol == 3); }
        rgb = floor(clamp(mean, vec3<f32>(0.0), vec3<f32>(1.0)) * 3.0 + t / 16.0) / 3.0;
    }
    dst[y * w + x] = vec4<f32>(rgb, src[y * w + x].a);
}
"""

# The transform: dst pixel to source through the inverse affine in p[4..9],
# bilinear with a transparent border, as cv2.warpAffine(INTER_LINEAR) does,
# after the alpha channel is scaled by p[10] on the byte grid.
WARP_CODE = """
fn tap(x: i32, y: i32) -> vec4<f32> {
    let sw = i32(p[2]);
    let sh = i32(p[3]);
    if (x < 0 || y < 0 || x >= sw || y >= sh) { return vec4<f32>(0.0); }
    let s = src[y * sw + x];
    return vec4<f32>(s.rgb, round(s.a * 255.0 * p[10]) / 255.0);
}
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let sx = p[4] * f32(x) + p[5] * f32(y) + p[6];
    let sy = p[7] * f32(x) + p[8] * f32(y) + p[9];
    let x0 = i32(floor(sx));
    let y0 = i32(floor(sy));
    let fx = sx - f32(x0);
    let fy = sy - f32(y0);
    let top = mix(tap(x0, y0), tap(x0 + 1, y0), fx);
    let bottom = mix(tap(x0, y0 + 1), tap(x0 + 1, y0 + 1), fx);
    dst[y * w + x] = mix(top, bottom, fy);
}
"""

_lock = threading.RLock()

# R5: the CPU path rounds a layer to uint8 after its effects and again after
# a mask or a LUT, before the warp interpolates it; this pass rounds the
# same way so the device path lands on the same counts.
QUANTISE_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    dst[i] = round(src[i] * 255.0) / 255.0;
}
"""

# R10: a remap effect samples the picture at coordinates the CPU computed
# (pixel_effects.remap_maps, the same formulas process() uses); aux carries
# x and y interleaved, two floats a pixel; bilinear with reflect-101 borders,
# as cv2.remap samples, in float rather than its five-bit weights.
REMAP_CODE = """
fn tap(x: i32, y: i32) -> vec4<f32> {
    let w = i32(p[0]);
    let h = i32(p[1]);
    return src[reflect101(y, h) * w + reflect101(x, w)];
}
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let sx = aux[i * 2];
    let sy = aux[i * 2 + 1];
    let x0 = i32(floor(sx));
    let y0 = i32(floor(sy));
    let fx = sx - f32(x0);
    let fy = sy - f32(y0);
    let top = mix(tap(x0, y0), tap(x0 + 1, y0), fx);
    let bottom = mix(tap(x0, y0 + 1), tap(x0 + 1, y0 + 1), fx);
    dst[i] = mix(top, bottom, fy);
}
"""

# R11: the accumulating passes the blur family is built from. ACCUM adds the
# source into the destination with a weight (the destination is read and
# written); SCALE multiplies; TILT mixes the held original and the blurred
# source by a band across the middle; SOFT is soft-focus's screen of the
# blurred picture over the original.
ACCUM_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let s = src[i];
    dst[i] = vec4<f32>(dst[i].rgb + s.rgb * p[2], s.a);
}
"""

SCALE_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let s = src[i];
    dst[i] = vec4<f32>(s.rgb * p[2], s.a);
}
"""

TILT_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let v = (f32(y) + 0.5) / p[1];
    let m = clamp((abs(v - 0.5) - 0.12) * 4.0, 0.0, 1.0);
    let o = held[i];
    dst[i] = vec4<f32>(o.rgb * (1.0 - m) + src[i].rgb * m, o.a);
}
"""

SOFT_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let o = held[i];
    dst[i] = vec4<f32>(vec3<f32>(1.0) - (vec3<f32>(1.0) - o.rgb) * (vec3<f32>(1.0) - src[i].rgb * 0.55), o.a);
}
"""

# R12: a field the picture does not feed, computed by the CPU from coordinates
# and noise (pixel_effects.field_for), three floats a pixel in aux, which is
# what the aux buffer holds. Mode 1 multiplies by the field, mode 2 adds it,
# mode 3 screens it over the picture; an effect with both a multiply and an
# add runs two passes.
FIELD_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let s = src[i];
    let b = i * 3;
    let f = vec3<f32>(aux[b], aux[b + 1], aux[b + 2]);
    var rgb = s.rgb * f;
    if (i32(p[2]) == 2) { rgb = s.rgb + f; }
    if (i32(p[2]) == 3) { rgb = vec3<f32>(1.0) - (vec3<f32>(1.0) - s.rgb) * (vec3<f32>(1.0) - f); }
    if (i32(p[2]) == 4) { rgb = select(s.rgb, f, f.r >= 0.0); }
    dst[i] = vec4<f32>(rgb, s.a);
}
"""

# The mask as an alpha field in aux, one float a pixel, multiplied into the
# layer's alpha and rounded as the CPU rounds it.
MASK_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let s = src[i];
    dst[i] = vec4<f32>(s.rgb, round(s.a * 255.0 * aux[i]) / 255.0);
}
"""

# The chroma key as the CPU does it: the pixel's chroma (rgb less its mean)
# against the key colour's, a distance over root two, then a soft threshold
# by similarity and blend, rounded into the alpha. p[2..4] the key colour,
# p[5] similarity, p[6] blend.
KEY_CODE = """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let s = src[i];
    let rgb = s.rgb;
    let chroma = rgb - vec3<f32>((rgb.r + rgb.g + rgb.b) / 3.0);
    let colour = vec3<f32>(p[2], p[3], p[4]);
    let key_chroma = colour - vec3<f32>((colour.r + colour.g + colour.b) / 3.0);
    let distance = length(chroma - key_chroma) / sqrt(2.0);
    let keep = clamp((distance - p[5]) / p[6], 0.0, 1.0);
    dst[i] = vec4<f32>(rgb, round(s.a * 255.0 * keep) / 255.0);
}
"""

# A .cube LUT in aux as flat rgb triplets indexed [b][g][r] on an n-lattice,
# sampled trilinearly, mixed by intensity and rounded, as apply_lut does it.
# p[2] n, p[3..5] the domain's low rgb, p[6..8] its high rgb, p[9] intensity.
LUT_CODE = """
fn lut(r: i32, g: i32, b: i32) -> vec3<f32> {
    let n = i32(p[2]);
    let base = ((b * n + g) * n + r) * 3;
    return vec3<f32>(aux[base], aux[base + 1], aux[base + 2]);
}
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    let s = src[i];
    let n = i32(p[2]);
    let low = vec3<f32>(p[3], p[4], p[5]);
    let high = vec3<f32>(p[6], p[7], p[8]);
    let c = clamp((s.rgb - low) / (high - low), vec3<f32>(0.0), vec3<f32>(1.0)) * f32(n - 1);
    let lo = vec3<i32>(floor(c));
    let hi = min(vec3<i32>(n - 1), lo + vec3<i32>(1));
    let f = c - vec3<f32>(lo);
    let c00 = mix(lut(lo.x, lo.y, lo.z), lut(hi.x, lo.y, lo.z), f.x);
    let c10 = mix(lut(lo.x, hi.y, lo.z), lut(hi.x, hi.y, lo.z), f.x);
    let c01 = mix(lut(lo.x, lo.y, hi.z), lut(hi.x, lo.y, hi.z), f.x);
    let c11 = mix(lut(lo.x, hi.y, hi.z), lut(hi.x, hi.y, hi.z), f.x);
    let graded = clamp(mix(mix(c00, c10, f.y), mix(c01, c11, f.y), f.z), vec3<f32>(0.0), vec3<f32>(1.0));
    let mixed = mix(s.rgb, graded, p[9]);
    dst[i] = vec4<f32>(round(mixed * 255.0) / 255.0, s.a);
}
"""
_contexts: dict = {}


def active() -> bool:
    wanted = os.environ.get("FORMCUT_EFFECTS", "").lower()
    if wanted == "cpu":
        return False
    if wanted == "gpu":
        return gpu.status()["available"]
    return gpu.stack_active()


def supported(effects: list[dict]) -> bool:
    """True when every effect of the chain has a device pass."""
    return all(entry["id"] in SUPPORTED or entry["id"] in GRADES for entry in effects)


class _Context:
    """One frame size's device state: three resident layer buffers, params, aux and the pipelines."""

    def __init__(self, height: int, width: int):
        import wgpu
        from wgpu.utils import get_default_device

        self.device = get_default_device()
        self.height, self.width = height, width
        self.count = height * width
        size = self.count * 16
        usage = wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.COPY_SRC
        self.buffers = [self.device.create_buffer(size=size, usage=usage) for _ in range(3)]
        self.params = self.device.create_buffer(size=PARAM_FLOATS * 4, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST)
        # R6: user kernels compiled in this context, by their source
        self.custom_pipelines: dict = {}
        self.aux_size = max(size, 4096)
        self.aux = self.device.create_buffer(size=self.aux_size, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_DST)
        self.read = self.device.create_buffer(size=size, usage=wgpu.BufferUsage.MAP_READ | wgpu.BufferUsage.COPY_DST)
        storage = {"type": wgpu.BufferBindingType.read_only_storage}
        self.layout = self.device.create_bind_group_layout(
            entries=[
                {"binding": 0, "visibility": wgpu.ShaderStage.COMPUTE, "buffer": storage},
                {"binding": 1, "visibility": wgpu.ShaderStage.COMPUTE, "buffer": {"type": wgpu.BufferBindingType.storage}},
                {"binding": 2, "visibility": wgpu.ShaderStage.COMPUTE, "buffer": storage},
                {"binding": 3, "visibility": wgpu.ShaderStage.COMPUTE, "buffer": storage},
                {"binding": 4, "visibility": wgpu.ShaderStage.COMPUTE, "buffer": storage},
            ]
        )
        self.pipeline_layout = self.device.create_pipeline_layout(bind_group_layouts=[self.layout])
        self.pipelines = {}
        self.groups = {}

    def pipeline(self, code: str):
        if code not in self.pipelines:
            module = self.device.create_shader_module(code=code if code.lstrip().startswith("@group") else HEADER + code)
            self.pipelines[code] = self.device.create_compute_pipeline(
                layout=self.pipeline_layout, compute={"module": module, "entry_point": "main"}
            )
        return self.pipelines[code]

    def group(self, src, dst):
        key = (id(src), id(dst))
        if key not in self.groups:
            entries = [
                {"binding": 0, "resource": {"buffer": src, "offset": 0, "size": src.size}},
                {"binding": 1, "resource": {"buffer": dst, "offset": 0, "size": dst.size}},
                {"binding": 2, "resource": {"buffer": self.params, "offset": 0, "size": self.params.size}},
                {"binding": 3, "resource": {"buffer": self.aux, "offset": 0, "size": self.aux.size}},
                {"binding": 4, "resource": {"buffer": self.buffers[2], "offset": 0, "size": self.buffers[2].size}},
            ]
            self.groups[key] = self.device.create_bind_group(layout=self.layout, entries=entries)
        return self.groups[key]

    def run(self, code: str, src, dst, params: list, aux: np.ndarray | None = None, width: int | None = None, height: int | None = None):
        values = np.zeros(PARAM_FLOATS, np.float32)
        values[: len(params)] = params
        self.device.queue.write_buffer(self.params, 0, values)
        if aux is not None:
            self.device.queue.write_buffer(self.aux, 0, np.ascontiguousarray(aux.astype(np.float32)))
        encoder = self.device.create_command_encoder()
        step = encoder.begin_compute_pass()
        step.set_pipeline(self.pipeline(code))
        step.set_bind_group(0, self.group(src, dst))
        step.dispatch_workgroups(((width or self.width) + 15) // 16, ((height or self.height) + 15) // 16)
        step.end()
        self.device.queue.submit([encoder.finish()])

    def upload(self, buffer, image: np.ndarray):
        """R7: four bytes a pixel over the bus, no conversion on this side; the device unpacks."""
        h, w = image.shape[:2]
        if image.dtype == np.uint8 and image.shape[2] == 4 and h * w * 4 <= self.aux_size:
            self.device.queue.write_buffer(self.aux, 0, np.ascontiguousarray(image))
            # The pass reads aux and writes the target; the source binding is the other chain buffer, unread.
            other = next(b for b in self.buffers if b is not buffer)
            self.run(UNPACK_CODE, other, buffer, [w, h], None, w, h)
            return
        self.device.queue.write_buffer(buffer, 0, np.ascontiguousarray(image.astype(np.float32) / 255))

    def download(self, buffer, height: int, width: int) -> np.ndarray:
        import wgpu

        encoder = self.device.create_command_encoder()
        encoder.copy_buffer_to_buffer(buffer, 0, self.read, 0, height * width * 16)
        self.device.queue.submit([encoder.finish()])
        self.read.map_sync(wgpu.MapMode.READ)
        data = np.frombuffer(self.read.read_mapped(), np.float32)[: height * width * 4].reshape(height, width, 4).copy()
        self.read.unmap()
        return data

    def copy(self, source, target, height: int, width: int):
        encoder = self.device.create_command_encoder()
        encoder.copy_buffer_to_buffer(source, 0, target, 0, height * width * 16)
        self.device.queue.submit([encoder.finish()])


def _context(height: int, width: int) -> _Context:
    key = (height, width)
    if key not in _contexts:
        _contexts[key] = _Context(height, width)
        while len(_contexts) > 3:
            _contexts.pop(next(iter(_contexts)))
    return _contexts[key]


def _grade_params(params: dict) -> list:
    return [
        float(params.get("exposure", 0)),
        float(params.get("contrast", 1)),
        float(params.get("lift", 0)),
        float(params.get("gamma", 1)),
        float(params.get("saturation", 1)),
        float(params.get("vibrance", 0)),
        float(params.get("temperature", 0)),
        float(params.get("tint", 0)),
        *[float(params.get("shadows_" + c, 0)) for c in "rgb"],
        *[float(params.get("highlights_" + c, 0)) for c in "rgb"],
        float(params.get("sepia", 0) or 0),
    ]


def _gaussian_taps(sigma: float) -> np.ndarray:
    size = round(sigma * 4 * 2 + 1) | 1
    return cv2.getGaussianKernel(size, sigma, cv2.CV_32F)[:, 0]


class _Chain:
    """Applies one effect chain to a resident layer; tracks which buffer holds the current picture."""

    def __init__(self, context: _Context, height: int, width: int):
        self.c = context
        self.h, self.w = height, width
        self.current = 0

    def _pass(self, code: str, params: list, aux=None, source: int | None = None, target: int | None = None):
        src = self.c.buffers[self.current if source is None else source]
        dst_index = (self.current + 1) % 2 if target is None else target
        self.c.run(code, src, self.c.buffers[dst_index], [self.w, self.h, *params], aux, self.w, self.h)
        if target is None:
            self.current = dst_index

    def custom(self, source: str, time: float, params: list | None = None) -> None:
        """R6: a package's WGSL kernel as a pass in the chain. The kernel declares its own three bindings
        (0 the input floats, 1 [w, h, time, 0] then its parameters, 2 the output floats) and runs one
        invocation a pixel, as gpu.custom_values runs it; here those bindings are the chain's own buffers,
        so the layer never leaves the device for it. The CPU rounds to uint8 after it; so does this."""
        device = self.c.device
        pipeline = self.c.custom_pipelines.get(source)
        if pipeline is None:
            module = device.create_shader_module(code=source)
            pipeline = device.create_compute_pipeline(layout="auto", compute={"module": module, "entry_point": "main"})
            self.c.custom_pipelines[source] = pipeline
        uniform = np.zeros(16, np.float32)
        uniform[:4] = [self.w, self.h, time, 0]
        for n, value in enumerate((params or [])[:12]):
            uniform[4 + n] = float(value)
        device.queue.write_buffer(self.c.params, 0, uniform)
        src = self.c.buffers[self.current]
        dst = self.c.buffers[(self.current + 1) % 2]
        size = self.w * self.h * 16
        group = device.create_bind_group(
            layout=pipeline.get_bind_group_layout(0),
            entries=[
                {"binding": 0, "resource": {"buffer": src, "offset": 0, "size": size}},
                {"binding": 1, "resource": {"buffer": self.c.params, "offset": 0, "size": 64}},
                {"binding": 2, "resource": {"buffer": dst, "offset": 0, "size": size}},
            ],
        )
        encoder = device.create_command_encoder()
        step = encoder.begin_compute_pass()
        step.set_pipeline(pipeline)
        step.set_bind_group(0, group)
        step.dispatch_workgroups((self.w * self.h + 63) // 64)
        step.end()
        device.queue.submit([encoder.finish()])
        self.current = (self.current + 1) % 2
        self._pass(QUANTISE_CODE, [])

    def _blur(self, taps: np.ndarray, anchor: int | None = None):
        anchor = len(taps) // 2 if anchor is None else anchor
        self._pass(CONV_CODE, [1, 0, len(taps), anchor], taps)
        self._pass(CONV_CODE, [0, 1, len(taps), anchor], taps)

    def _hold(self):
        """Keep the current picture in the third buffer, which every pass sees as held."""
        self.c.copy(self.c.buffers[self.current], self.c.buffers[2], self.h, self.w)

    def _multi_remap(self, maps: list, weights: list) -> None:
        """A weighted sum of remaps of the current picture: the source held, each map sampled into scratch and accumulated."""
        self._hold()
        source, scratch, acc = 2, self.current, (self.current + 1) % 2
        first = True
        for (mx, my), weight in zip(maps, weights, strict=True):
            xy = np.empty((self.h, self.w, 2), np.float32)
            xy[:, :, 0], xy[:, :, 1] = mx, my
            if first:
                self._pass(REMAP_CODE, [], xy, source=source, target=acc)
                if weight != 1.0:
                    self._pass(SCALE_CODE, [float(weight)], source=acc, target=scratch)
                    scratch, acc = acc, scratch
                first = False
                continue
            self._pass(REMAP_CODE, [], xy, source=source, target=scratch)
            self._pass(ACCUM_CODE, [float(weight)], source=scratch, target=acc)
        self.current = acc

    def apply(self, effect: str, local: float, params: dict):
        if effect in GRADES:
            self._pass(GRADE_CODE, _grade_params({**GRADES[effect], **params}))
            return
        radius = max(0.1, min(100, float(params.get("radius", 3))))
        size = max(1, int(params.get("size", 12)))
        if effect in FIELD_EFFECTS:
            mul, add, mode = field_for(effect, self.h, self.w, local, params)
            if mode == 2:
                self._pass(FIELD_CODE, [3], np.ascontiguousarray(add))
                return
            if mode == 3:
                # snowfall: rgb * 0.88 + 0.07, then the flakes cover where the field is drawn
                self._pass(FIELD_CODE, [1], np.ascontiguousarray(mul))
                self._pass(FIELD_CODE, [2], np.full((self.h, self.w, 3), 0.07, np.float32))
                self._pass(FIELD_CODE, [4], np.ascontiguousarray(add))
                return
            if not np.all(mul == 1):
                self._pass(FIELD_CODE, [1], np.ascontiguousarray(mul))
            if np.any(add != 0):
                self._pass(FIELD_CODE, [2], np.ascontiguousarray(add))
            return
        if effect == "hex-pixelate":
            self._blur(_gaussian_taps(max(0.5, float(size) / 3)))
            maps = remap_maps(effect, self.h, self.w, local, params)
            xy = np.empty((self.h, self.w, 2), np.float32)
            xy[:, :, 0], xy[:, :, 1] = maps
            self._pass(REMAP_CODE, [], xy)
            return
        if effect == "halftone":
            cell = max(4, size)
            self._pass(CELL_CODE, [max(1, self.w // cell), max(1, self.h // cell), cell, 1])
            return
        if effect == "bayer-dither":
            step = max(1, size // 4)
            self._pass(CELL_CODE, [max(1, self.w // step), max(1, self.h // step), step, 2])
            return
        if effect == "camera-shake":
            from .pixel_effects import _grid

            y, x, _u, _v = _grid(self.h, self.w)
            xy = np.empty((self.h, self.w, 2), np.float32)
            xy[:, :, 0], xy[:, :, 1] = x + math.sin(local * 27) * size / 2, y + math.sin(local * 19) * size / 2
            self._pass(REMAP_CODE, [], xy)
            return
        if effect in REMAP_EFFECTS:
            maps = remap_maps(effect, self.h, self.w, local, params)
            if maps is None:
                raise ValueError(effect)
            xy = np.empty((self.h, self.w, 2), np.float32)
            xy[:, :, 0], xy[:, :, 1] = maps
            self._pass(REMAP_CODE, [], xy)
            return
        if effect in ("radial-blur", "spin-blur", "diagonal-blur", "ghost-trail"):
            from .pixel_effects import _grid

            y, x, _u, _v = _grid(self.h, self.w)
            w, h = self.w, self.h
            if effect == "radial-blur":
                spread = 0.1 * float(params.get("intensity", 1))
                scales = np.linspace(1 - spread, 1 + spread, 9)
                self._multi_remap([((x - w / 2) * sc + w / 2, (y - h / 2) * sc + h / 2) for sc in scales], [1 / 9] * 9)
            elif effect == "spin-blur":
                dx, dy = x - w / 2, y - h / 2
                arc = 0.12 * float(params.get("intensity", 1))
                maps = []
                for angle in np.linspace(-arc, arc, 7):
                    c, sn = math.cos(angle), math.sin(angle)
                    maps.append((w / 2 + dx * c - dy * sn, h / 2 + dx * sn + dy * c))
                self._multi_remap(maps, [1 / 7] * 7)
            elif effect == "diagonal-blur":
                steps = list(range(-size, size + 1, 2))
                # np.roll wraps: integer coordinates modulo the size, so the taps are exact
                self._multi_remap([(np.mod(x - k, w), np.mod(y - k, h)) for k in steps], [1 / len(steps)] * len(steps))
            else:
                self._multi_remap([(x, y), (np.mod(x - size, w), y), (np.mod(x - size * 2, w), y)], [0.55, 0.27, 0.18])
            return
        if effect == "tilt-shift":
            self._hold()
            self._blur(_gaussian_taps(radius * 2.5))
            self._pass(TILT_CODE, [])
            return
        if effect == "soft-focus":
            self._hold()
            self._blur(_gaussian_taps(radius * 4))
            self._pass(SOFT_CODE, [])
            return
        if effect == "gaussian":
            self._blur(_gaussian_taps(radius))
        elif effect == "box":
            self._blur(np.full(size, 1 / size, np.float32), size // 2)
        elif effect == "directional-blur":
            taps = size | 1
            self._pass(CONV_CODE, [1, 0, taps, taps // 2], np.full(taps, 1 / taps, np.float32))
        elif effect == "sharpen":
            self._hold()
            self._blur(_gaussian_taps(radius))
            self._pass(COMBINE_CODE, [1])
        elif effect == "glow":
            self._hold()
            self._pass(COMBINE_CODE, [3])
            self._blur(_gaussian_taps(radius * 3))
            self._pass(COMBINE_CODE, [2])
        elif effect == "pixelate":
            self._pass(PIXELATE_CODE, [max(1, self.w // size), max(1, self.h // size)])
        elif effect == "grain":
            rng = np.random.default_rng(int(local * 1000) % (2**32))
            self._pass(POINT_CODE, [POINT_MODES[effect]], rng.normal(0, params.get("strength", 0.07), (self.h, self.w)).astype(np.float32))
        elif effect == "crosshatch":
            self._pass(POINT_CODE, [14, float(max(4, size // 2))])
        elif effect == "solarize":
            self._pass(POINT_CODE, [POINT_MODES[effect], float(params.get("threshold", 0.5))])
        elif effect == "duotone":
            self._pass(POINT_CODE, [POINT_MODES[effect]])
        elif effect == "night-vision":
            rng = np.random.default_rng(int(local * 1000) % (2**32))
            self._pass(
                POINT_CODE, [POINT_MODES[effect]], rng.normal(0, float(params.get("strength", 0.05)), (self.h, self.w)).astype(np.float32)
            )
        elif effect == "anaglyph":
            self._pass(POINT_CODE, [POINT_MODES[effect], max(1, round(self.w * 0.004 * size / 12))])
        elif effect == "fog":
            from .pixel_effects import _fog_field

            field = _fog_field(self.h, self.w)
            drift = int(local * self.w * 0.03) % self.w
            self._pass(
                POINT_CODE, [POINT_MODES[effect], float(params.get("density", 1))], np.ascontiguousarray(field[:, drift : drift + self.w])
            )
        elif effect == "posterize":
            self._pass(POINT_CODE, [POINT_MODES[effect], max(2, min(32, int(params.get("levels", 5))))])
        elif effect == "threshold":
            self._pass(POINT_CODE, [POINT_MODES[effect], float(params.get("threshold", 0.5))])
        elif effect in ("vignette", "scanlines"):
            self._pass(POINT_CODE, [POINT_MODES[effect], float(params.get("intensity", 1)), float(params.get("spacing", 2))])
        elif effect == "chromatic":
            self._pass(POINT_CODE, [POINT_MODES[effect], size])
        else:
            self._pass(POINT_CODE, [POINT_MODES[effect]])


def _run_chain(chain: _Chain, effects: list[dict], local: float) -> None:
    for entry in effects:
        amount = max(0.0, min(1.0, float(entry.get("amount", 1))))
        if amount <= 0:
            continue
        settings = clamp_params({**EFFECT_DEFAULTS.get(entry["id"], {}), **(entry.get("params") or {})})
        if amount < 1:
            chain._hold()
        chain.apply(entry["id"], local, settings)
        chain._pass(COMBINE_CODE, [4, amount] if amount < 1 else [5])


def apply_effects(image: np.ndarray, effects: list[dict], local: float) -> np.ndarray | None:
    """The chain on the device, bytes back; None when the chain or the device cannot take it."""
    if not effects or not supported(effects) or not active():
        return None
    try:
        with _lock:
            h, w = image.shape[:2]
            context = _context(h, w)
            chain = _Chain(context, h, w)
            context.upload(context.buffers[0], image)
            _run_chain(chain, effects, local)
            data = context.download(context.buffers[chain.current], h, w)
        return np.round(np.clip(data, 0, 1) * 255).astype(np.uint8)
    except Exception:
        return None


def warp(image: np.ndarray, matrix: np.ndarray, alpha: float, size: tuple[int, int]) -> np.ndarray | None:
    """The transform alone as a device pass; None when the device path is off or fails."""
    return effects_and_warp(image, [], 0.0, matrix, alpha, size)


def effects_and_warp(
    image: np.ndarray,
    effects: list[dict],
    local: float,
    matrix: np.ndarray,
    alpha: float,
    size: tuple[int, int],
    resident: bool = False,
    lut: tuple[np.ndarray, float, float, float] | None = None,
    mask: np.ndarray | None = None,
    key: tuple[tuple[float, float, float], float, float] | None = None,
    matte: np.ndarray | None = None,
    shader: tuple[str, float, list | None] | None = None,
):
    """The chain, a LUT, a key, a mask, a cutout matte and the transform on one resident layer: one upload, then either one readback of the frame-sized layer or, with `resident`, no readback at all: the layer is staged into the frame's compositor on the device and its stage index comes back."""
    if not active() or (effects and not supported(effects)):
        return None
    try:
        with _lock:
            h, w = image.shape[:2]
            frame_w, frame_h = size
            context = _context(max(h, frame_h), max(w, frame_w))
            chain = _Chain(context, h, w)
            context.upload(context.buffers[0], image)
            if effects:
                _run_chain(chain, effects, local)
                # The CPU rounds to uint8 here; so does the device.
                chain._pass(QUANTISE_CODE, [])
            if lut is not None:
                table, low, high, intensity = lut
                n = len(table)
                if n * n * n * 3 * 4 > context.aux_size:
                    return None
                amount = float(max(0.0, min(1.0, intensity)))
                lows = [float(v) for v in np.broadcast_to(np.asarray(low, np.float32), (3,))]
                highs = [float(v) for v in np.broadcast_to(np.asarray(high, np.float32), (3,))]
                chain._pass(LUT_CODE, [n, *lows, *highs, amount], np.ascontiguousarray(table.reshape(-1)))
            if shader is not None:
                chain.custom(shader[0], shader[1], shader[2])
            if key is not None:
                (kr, kg, kb), similarity, blend = key
                chain._pass(KEY_CODE, [float(kr), float(kg), float(kb), float(similarity), float(max(0.001, blend))])
            if mask is not None:
                chain._pass(MASK_CODE, [], np.ascontiguousarray(mask.reshape(-1)))
            if matte is not None:
                chain._pass(MASK_CODE, [], np.ascontiguousarray(np.asarray(matte, np.float32).reshape(-1)))
            inverse = cv2.invertAffineTransform(np.float32(matrix))
            context.run(
                WARP_CODE,
                context.buffers[chain.current],
                context.buffers[(chain.current + 1) % 2],
                [frame_w, frame_h, w, h, *[float(v) for v in inverse.ravel()], float(alpha)],
                None,
                frame_w,
                frame_h,
            )
            result = context.buffers[(chain.current + 1) % 2]
            if resident:
                # R4: the layer never comes back. The compositor copies it on
                # the device into a pooled buffer of its own before this
                # context's buffers are reused by the next layer.
                from .gpu import DeviceLayer, stage_layer

                staged = stage_layer(DeviceLayer(result, frame_h, frame_w), frame_h, frame_w)
                if staged is None:
                    data = context.download(result, frame_h, frame_w)
                    return np.round(np.clip(data, 0, 1) * 255).astype(np.uint8)
                return staged
            data = context.download(result, frame_h, frame_w)
        return np.round(np.clip(data, 0, 1) * 255).astype(np.uint8)
    except Exception:
        return None
