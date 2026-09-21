"""The Rust compositing kernel.

It stands in for cv2.warpAffine followed by gpu.composite in the frame path,
and it may only because it matches them to the bit. These check that across
placements, rotations, flips, stretches, edges and opacities; that the renderer
draws the same frames with it and without it; and when it must step aside. The
kernel tests skip where the module has not been built.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest
from app import gpu, renderer
from app.renderer import FrameRenderer, _plainly_blended
from conftest import make_project, text_clip

try:
    import formcut_native
except ImportError:
    formcut_native = None

BUILT = pytest.mark.skipif(formcut_native is None, reason="the native module is not built here")
CANVAS = (360, 640)


def placement(source: tuple[int, int], scale=100.0, px=0.0, py=0.0, rotation=0.0, flip_h=False, flip_v=False, stretch=(100.0, 100.0)):
    (h, w), (height, width) = source, CANVAS
    fit = min(width / w, height / h)
    sx = fit * scale / 100 * stretch[0] / 100 * (-1 if flip_h else 1)
    sy = fit * scale / 100 * stretch[1] / 100 * (-1 if flip_v else 1)
    c, s = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
    a, b, d, e = c * sx, -s * sy, s * sx, c * sy
    cx, cy = width * (0.5 + px / 100), height * (0.5 + py / 100)
    return np.float32([[a, b, cx - a * w / 2 - b * h / 2], [d, e, cy - d * w / 2 - e * h / 2]])


def pictures(source: tuple[int, int], seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    image = rng.integers(0, 256, (*source, 4), dtype=np.uint8)
    image[::7, ::5, 3] = 0
    image[1::9, ::3, 3] = 255
    canvas = rng.integers(0, 256, (*CANVAS, 4), dtype=np.uint8)
    canvas[:, :, 3] = 255
    return image, canvas


def python_path(canvas: np.ndarray, image: np.ndarray, matrix: np.ndarray, alpha: float) -> np.ndarray:
    image = image.copy()
    image[:, :, 3] = np.round(image[:, :, 3] * alpha).astype(np.uint8)
    layer = cv2.warpAffine(image, matrix, (CANVAS[1], CANVAS[0]), flags=cv2.INTER_LINEAR)
    return gpu.composite(canvas, layer, "Normal")


def kernel(canvas: np.ndarray, image: np.ndarray, matrix: np.ndarray, alpha: float) -> np.ndarray:
    out = canvas.copy()
    formcut_native.composite_affine(out, image, [float(v) for v in matrix.ravel()], alpha)
    return out


def identical(source: tuple[int, int], alpha: float = 1.0, seed: int = 1, **place) -> bool:
    image, canvas = pictures(source, seed)
    matrix = placement(source, **place)
    return np.array_equal(python_path(canvas, image, matrix, alpha), kernel(canvas, image, matrix, alpha))


@BUILT
def test_a_layer_in_place_is_bit_identical():
    assert identical((360, 640))


@BUILT
def test_a_scaled_and_moved_layer_is_bit_identical():
    assert identical((180, 320), scale=40, px=21.3, py=-17.7, seed=2)


@BUILT
def test_a_rotated_and_flipped_layer_is_bit_identical():
    assert identical((200, 150), scale=75, rotation=-117, flip_h=True, flip_v=True, py=9.9, seed=3)


@BUILT
def test_a_stretched_layer_is_bit_identical():
    assert identical((180, 320), stretch=(137.0, 61.0), seed=4)


@BUILT
def test_a_layer_over_the_edges_is_bit_identical():
    assert identical((90, 160), scale=180, px=13.1, rotation=12, seed=5)


@BUILT
def test_a_faded_layer_is_bit_identical():
    assert identical((180, 320), alpha=0.37, scale=60, rotation=30, seed=6)


@BUILT
def test_a_layer_off_the_canvas_changes_no_colour():
    image, canvas = pictures((180, 320), 7)
    out = kernel(canvas, image, placement((180, 320), scale=30, px=90), 1.0)
    assert np.array_equal(out, canvas)


@BUILT
def test_an_invisible_layer_changes_no_colour():
    image, canvas = pictures((180, 320), 8)
    assert np.array_equal(kernel(canvas, image, placement((180, 320)), 0.0), canvas)


@BUILT
def test_the_kernel_wants_rgba():
    with pytest.raises(ValueError, match="RGBA"):
        formcut_native.composite_affine(np.zeros((*CANVAS, 3), np.uint8), np.zeros((10, 10, 4), np.uint8), [1, 0, 0, 0, 1, 0], 1.0)


@BUILT
def test_the_kernel_wants_contiguous_pictures():
    source = np.zeros((20, 20, 4), np.uint8)[:, ::2]
    with pytest.raises(ValueError, match="contiguous"):
        formcut_native.composite_affine(np.zeros((*CANVAS, 4), np.uint8), source, [1, 0, 0, 0, 1, 0], 1.0)


def frames(monkeypatch, native: bool) -> list[np.ndarray]:
    if not native:
        monkeypatch.setenv("FORMCUT_NATIVE", "0")
    else:
        monkeypatch.delenv("FORMCUT_NATIVE", raising=False)
    clips = [
        text_clip(clip_id="a", start=0.0, duration=2.0, transform={"scale": 140, "rotation": 17, "posX": 8, "opacity": 80}, fadeIn=0.5),
        text_clip(clip_id="b", start=0.5, duration=1.5, transform={"scale": 60, "posX": -20, "posY": 15, "flipH": True}),
    ]
    project = make_project(clips=clips[:1], background="#203040", duration=2.0)
    project["timelines"][0]["tracks"].append({"id": "t1", "name": "V2", "clips": clips[1:]})
    from app.render_document import validate_document

    drawn = FrameRenderer(validate_document(project))
    try:
        return [drawn.frame(at) for at in (0.1, 0.4, 0.9, 1.6)]
    finally:
        drawn.close()


@BUILT
def test_the_renderer_draws_the_same_frames_with_the_kernel_and_without_it(monkeypatch):
    with_kernel, without = frames(monkeypatch, True), frames(monkeypatch, False)
    assert all(np.array_equal(a, b) for a, b in zip(with_kernel, without, strict=True))


def test_the_kernel_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("FORMCUT_NATIVE", "0")
    assert renderer._native() is None


def plain(**transform) -> dict:
    return {"blendMode": "Normal", **transform}


def test_a_normal_layer_is_plainly_blended():
    assert _plainly_blended({"duration": 2}, 1.0, plain())


def test_another_blend_mode_keeps_the_python_path():
    assert not _plainly_blended({"duration": 2}, 1.0, plain(blendMode="Screen"))


def test_a_layer_mid_transition_keeps_the_python_path():
    clip = {"duration": 2, "transitionLength": 0.5, "transitionIn": {"type": "wipe-left"}}
    assert not _plainly_blended(clip, 0.2, plain()) and _plainly_blended(clip, 0.6, plain())


def test_a_layer_leaving_through_a_transition_keeps_the_python_path():
    clip = {"duration": 2, "transitionOut": {"type": "wipe-left", "length": 0.5}}
    assert not _plainly_blended(clip, 2.1, plain()) and _plainly_blended(clip, 1.5, plain())


def test_a_layer_being_pushed_out_keeps_the_python_path():
    clip = {"duration": 2, "pushOut": 0.5}
    assert not _plainly_blended(clip, 2.2, plain()) and _plainly_blended(clip, 1.0, plain())
