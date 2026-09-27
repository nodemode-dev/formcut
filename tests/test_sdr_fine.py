"""An SDR project keeps its canvas at sixteen bits between blends and rounds to bytes once (revision 8's low item):
a stack of soft layers no longer drifts a count or more from the unrounded blend."""

import numpy as np
from app import gpu


def _stack(canvas, layer, times):
    for _ in range(times):
        canvas = gpu.composite(canvas, layer, "normal", "srgb")
    return canvas


def test_eight_soft_layers_stay_within_half_a_count_of_the_unrounded_blend():
    ramp = np.round(np.linspace(0, 255, 512)).astype(np.uint8)
    canvas = np.zeros((2, 512, 4), np.uint8)
    canvas[..., :3] = ramp[None, :, None]
    canvas[..., 3] = 255
    layer = np.zeros((2, 512, 4), np.uint8)
    layer[..., :3] = (26, 42, 58)
    layer[..., 3] = 31
    b = canvas[..., :3].astype(np.float64) / 255
    f = layer[..., :3].astype(np.float64) / 255
    a = layer[..., 3:4] / 255
    for _ in range(8):
        b = gpu._to_display(gpu._to_linear(b, "srgb") * (1 - a) + gpu._to_linear(f, "srgb") * a, "srgb")
    ideal = b * 255
    fine = _stack(canvas.astype(np.uint16) * 257, layer.astype(np.uint16) * 257, 8)
    once = (fine.astype(np.int64) + 128) // 257
    coarse = _stack(canvas, layer, 8)
    # the final rounding's half a count, plus half a sixteen-bit step (1/514 of a count) at each of the eight blends
    assert np.abs(once[..., :3] - ideal).max() <= 0.5 + 8 / 514
    assert np.abs(coarse[..., :3].astype(float) - ideal).max() > 1.0  # what the byte grid did


def test_a_sixteen_bit_canvas_blends_on_the_sixteen_bit_grid_on_the_cpu():
    canvas = np.full((1, 4, 4), 30000, np.uint16)
    layer = np.full((1, 4, 4), 50000, np.uint16)
    layer[..., 3] = 20000
    out = gpu.composite(canvas, layer, "normal", "srgb")
    assert out.dtype == np.uint16 and np.any(out[..., :3] % 257 != 0)
