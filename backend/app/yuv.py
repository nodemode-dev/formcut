"""A decoded 4:2:0 frame kept as its planes, converted to RGB by formcut itself.

Revision 8's low item: the conversion of each decoded frame to RGB had been swscale's, on a CPU core, about 3 ms a
1080p frame at sixteen bits. A frame that goes up to the device now goes up as its planes (Y, then U, then V, the
decoder's own code values) and the first pass converts it; a frame the CPU needs is converted here, by the same map,
so the two paths agree as they always have.

The map: chroma upsampled bilinearly to luma resolution as cv2.resize computes it (centre-aligned, the edge samples
held); the code values taken from their range (limited or full) and bit depth through the matrix the stream declares
(BT.709, BT.601, BT.2020 non-constant, SMPTE 240M; an undeclared one BT.709 at 720 lines and up, BT.601 below) onto the
grid of the picture it becomes (bytes, or sixteen bits for an HDR source decoded deep), as one 3 x 4 affine map;
clipped; rounded half up. The CPU runs it through cv2 (resize, merge, transform); the device runs it in yuv_at.
Against swscale, which formcut used before, the difference is its chroma filter: about a byte count on average, at
chroma edges.
"""

from __future__ import annotations

import cv2
import numpy as np

MATRICES = {
    "bt709": (0.2126, 0.0722),
    "smpte170m": (0.299, 0.114),
    "bt470bg": (0.299, 0.114),
    "bt2020nc": (0.2627, 0.0593),
    "smpte240m": (0.212, 0.087),
}
FORMATS = {"yuv420p": (8, False), "yuvj420p": (8, True), "yuv420p10le": (10, False)}


def wanted(stack_active: bool) -> bool:
    """Whether formcut converts the frames itself: where the device path runs (FORMCUT_YUV unset or "auto"), so the
    device and this side's conversions agree; never with FORMCUT_YUV=0; always with FORMCUT_YUV=1 (the bench, which
    compares the two paths like with like). Without a device, swscale converts as before, so an export by the frame
    path stays the pictures of formcut's ffmpeg paths (native cuts, layered), which convert with swscale too."""
    import os

    mode = os.environ.get("FORMCUT_YUV", "auto")
    return mode == "1" or (mode != "0" and stack_active)


def matrix(bits: int, full: bool, kr: float, kb: float, grid: float) -> np.ndarray:
    """The 3 x 4 affine map from (Y, Cb, Cr) code values to R, G, B on the grid, as float32."""
    if full:
        top = float(2**bits - 1)
        yo, yk, co, ck = 0.0, 1.0 / top, float(2 ** (bits - 1)), 1.0 / top
    else:
        scale = float(2 ** (bits - 8))
        yo, yk, co, ck = 16.0 * scale, 1.0 / (219.0 * scale), 128.0 * scale, 1.0 / (224.0 * scale)
    kg = 1.0 - kr - kb
    rcr, bcb = 2.0 * (1.0 - kr), 2.0 * (1.0 - kb)
    gcb, gcr = 2.0 * kb * (1.0 - kb) / kg, 2.0 * kr * (1.0 - kr) / kg
    rows = [
        [yk, 0.0, rcr * ck, -yk * yo - rcr * ck * co],
        [yk, -gcb * ck, -gcr * ck, -yk * yo + (gcb + gcr) * ck * co],
        [yk, bcb * ck, 0.0, -yk * yo - bcb * ck * co],
    ]
    return (np.array(rows, np.float64) * grid).astype(np.float32)


def _into(target: np.ndarray, plane, item) -> np.ndarray:
    """A decoder plane copied once into its place in the frame's one buffer, its row padding (line size) dropped;
    the place, as a (height, width) view, is returned."""
    size = np.dtype(item).itemsize
    view = target.reshape(plane.height, plane.width)
    view[...] = np.frombuffer(plane, item).reshape(plane.height, plane.line_size // size)[:, : plane.width]
    return view


class PlaneFrame:
    """A decoded frame as its planes, with what converts it: shape and dtype are those of the RGBA it becomes."""

    __slots__ = ("_rgba", "bits", "deep", "full", "kb", "kr", "packed", "u", "v", "y")

    def __init__(self, y: np.ndarray, u: np.ndarray, v: np.ndarray, bits: int, full: bool, kr: float, kb: float, deep: bool, packed=None):
        self.y, self.u, self.v = y, u, v
        # the planes one after another in one buffer, padded to whole 32-bit words: what the device reads as it is
        self.packed = packed
        self.bits, self.full, self.kr, self.kb, self.deep = bits, full, kr, kb, deep
        self._rgba = None

    @property
    def shape(self) -> tuple[int, int, int]:
        return (self.y.shape[0], self.y.shape[1], 4)

    @property
    def dtype(self):
        return np.dtype(np.uint16 if self.deep else np.uint8)

    @property
    def grid(self) -> float:
        return 65535.0 if self.deep else 255.0

    def map(self) -> np.ndarray:
        return matrix(self.bits, self.full, self.kr, self.kb, self.grid)

    def rgba(self) -> np.ndarray:
        """The frame as RGBA, converted once and kept (nothing writes into a decoded frame)."""
        if self._rgba is None:
            h, w = self.y.shape
            ycc = cv2.merge(
                [
                    self.y.astype(np.float32),
                    cv2.resize(self.u.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR),
                    cv2.resize(self.v.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR),
                ]
            )
            rgb = cv2.transform(ycc, self.map())
            # clipped to the grid and rounded half up, floor(v + 0.5), as yuv_at rounds (numpy's clip: cv2.min and
            # cv2.max take a scalar as one channel's value and zero for the rest)
            np.clip(rgb, 0.0, self.grid, out=rgb)
            rgb += np.float32(0.5)
            out = np.empty((h, w, 4), self.dtype)
            out[:, :, :3] = rgb
            out[:, :, 3] = int(self.grid)
            self._rgba = out
        return self._rgba

    def aux(self) -> np.ndarray:
        """The planes one after another as float32 code values: the aux of an executor that takes only floats."""
        if self.packed is None:
            return np.concatenate([self.y.ravel(), self.u.ravel(), self.v.ravel()]).astype(np.float32)
        return self.packed[: self.y.size + self.u.size + self.v.size].astype(np.float32)

    def raw(self) -> np.ndarray:
        """The planes' own code values, one buffer in whole 32-bit words: the recorder's aux as it is (RawAux), half
        the size of floats at ten bits, a quarter at eight, and no conversion on this side."""
        if self.packed is None:
            joined = np.concatenate([self.y.ravel(), self.u.ravel(), self.v.ravel()])
            pad = (-joined.nbytes) % 4 // joined.itemsize
            self.packed = np.concatenate([joined, np.zeros(pad, joined.dtype)]) if pad else joined
        return self.packed


def yuv_function(frame: PlaneFrame, raw: bool = False) -> str:
    """yuv_at(i, x, y, w, h), reading the planes from aux (floats) or, raw, from aux_words (the code values as they
    came from the decoder, two ten-bit or four eight-bit samples a word): the device's side of rgba(), the same
    bilinear chroma, the same affine map with the same float32 coefficients, the same clipping and rounding."""
    c = [[f"{float(v)!r}" for v in row] for row in frame.map()]
    grid = f"{frame.grid!r}"
    if not raw:
        sample = "fn yuv_sample(k: i32) -> f32 {\n    return aux[k];\n}\n"
    elif frame.bits > 8:
        sample = (
            "fn yuv_sample(k: i32) -> f32 {\n    let u = u32(k);\n    return f32((aux_words[u >> 1u] >> ((u & 1u) * 16u)) & 65535u);\n}\n"
        )
    else:
        sample = "fn yuv_sample(k: i32) -> f32 {\n    let u = u32(k);\n    return f32((aux_words[u >> 2u] >> ((u & 3u) * 8u)) & 255u);\n}\n"
    return (
        sample + """
fn yuv_axis(d: i32, n: i32) -> vec2<f32> {
    // cv2.resize's bilinear source position for a twofold enlargement: the first sample and its weight, edges held
    let fx = (f32(d) + 0.5) * 0.5 - 0.5;
    var sx = i32(floor(fx));
    var f = fx - floor(fx);
    if (sx < 0) { sx = 0; f = 0.0; }
    if (sx + 1 >= n) { sx = n - 1; f = 0.0; }
    return vec2<f32>(f32(sx), f);
}
fn yuv_plane(base: i32, cw: i32, ch: i32, x: i32, y: i32) -> f32 {
    let ax = yuv_axis(x, cw);
    let ay = yuv_axis(y, ch);
    let x0 = i32(ax.x);
    let y0 = i32(ay.x);
    let x1 = min(x0 + 1, cw - 1);
    let y1 = min(y0 + 1, ch - 1);
    let top = yuv_sample(base + y0 * cw + x0) * (1.0 - ax.y) + yuv_sample(base + y0 * cw + x1) * ax.y;
    let bottom = yuv_sample(base + y1 * cw + x0) * (1.0 - ax.y) + yuv_sample(base + y1 * cw + x1) * ax.y;
    return top * (1.0 - ay.y) + bottom * ay.y;
}
fn yuv_at(i: i32, x: i32, y: i32, w: i32, h: i32) -> vec4<f32> {
    let cw = (w + 1) / 2;
    let ch = (h + 1) / 2;
    let luma = yuv_sample(i);
    let cb = yuv_plane(w * h, cw, ch, x, y);
    let cr = yuv_plane(w * h + cw * ch, cw, ch, x, y);
"""
        f"    let r = luma * {c[0][0]} + cb * {c[0][1]} + cr * {c[0][2]} + {c[0][3]};\n"
        f"    let g = luma * {c[1][0]} + cb * {c[1][1]} + cr * {c[1][2]} + {c[1][3]};\n"
        f"    let b = luma * {c[2][0]} + cb * {c[2][1]} + cr * {c[2][2]} + {c[2][3]};\n"
        f"    return vec4<f32>(floor(clamp(vec3<f32>(r, g, b), vec3<f32>(0.0), vec3<f32>({grid})) + 0.5) / {grid}, 1.0);\n"
        "}\n"
    )


def unpack_code(frame: PlaneFrame, raw: bool = False) -> str:
    """The device pass that turns the planes in aux (or, raw, aux_words) into the picture: yuv_at at every pixel.
    Raw, the caller gives it the bindings that name aux_words (gpu_effects.RAW_BINDINGS)."""
    return (
        yuv_function(frame, raw)
        + """
@compute @workgroup_size(16, 16)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    let w = i32(p[0]);
    let h = i32(p[1]);
    let x = i32(id.x);
    let y = i32(id.y);
    if (x >= w || y >= h) { return; }
    let i = y * w + x;
    dst[i] = yuv_at(i, x, y, w, h);
}
"""
    )


def from_av(frame, deep: bool, matrix_name: str, full_range: bool) -> PlaneFrame | None:
    """A PyAV frame as a PlaneFrame when it is planar 4:2:0 at eight or ten bits; None otherwise (swscale then)."""
    name = frame.format.name
    if name not in FORMATS:
        return None
    bits, full = FORMATS[name]
    item = np.uint16 if bits > 8 else np.uint8
    planes = frame.planes[:3]
    sizes = [plane.width * plane.height for plane in planes]
    total = sum(sizes)
    size = np.dtype(item).itemsize
    packed = np.zeros(total + (-total * size) % 4 // size, item)
    starts = [0, sizes[0], sizes[0] + sizes[1]]
    y, u, v = (_into(packed[a : a + n], plane, item) for a, n, plane in zip(starts, sizes, planes, strict=True))
    kr, kb = MATRICES.get(matrix_name) or (MATRICES["bt709"] if y.shape[0] >= 720 else MATRICES["smpte170m"])
    return PlaneFrame(y, u, v, bits, full or full_range, kr, kb, deep and bits > 8, packed)
