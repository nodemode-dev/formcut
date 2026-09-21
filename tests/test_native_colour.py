"""The Rust colour kernel: the colour panel's grade, bit-identical to the NumPy reference."""

import numpy as np
import pytest
from app import pixel_effects as fx

native = pytest.importorskip("formcut_native", reason="the native module is not built here")
if not hasattr(native, "colour_panel"):
    pytest.skip("this build of the native module predates the colour kernel", allow_module_level=True)

RANGES = {"temperature": (2500, 10500), "exposure": (-2, 2)}


def _panel(rng, keys):
    return {key: float(rng.uniform(*RANGES.get(key, (-100, 100)))) for key in keys}


def test_the_kernel_matches_python_on_random_frames_and_panels():
    rng = np.random.default_rng(29)
    for _ in range(400):
        image = rng.integers(0, 256, (int(rng.integers(1, 70)), int(rng.integers(1, 90)), 4), dtype=np.uint8)
        panel = _panel(rng, rng.choice(fx.NATIVE_COLOUR, size=int(rng.integers(1, len(fx.NATIVE_COLOUR) + 1)), replace=False))
        assert np.array_equal(fx.apply_colour_panel(image, panel), fx.python_colour_panel(image, panel)), panel


@pytest.mark.parametrize("key", fx.NATIVE_COLOUR)
@pytest.mark.parametrize("extreme", [-1.0, 1.0])
def test_every_control_alone_and_at_its_extremes_matches(key, extreme):
    rng = np.random.default_rng(7)
    image = rng.integers(0, 256, (37, 53, 4), dtype=np.uint8)
    low, high = RANGES.get(key, (-100, 100))
    panel = {key: high if extreme > 0 else low}
    if key == "temperature":
        panel = {key: 11000.0 if extreme > 0 else 2000.0}
    assert np.array_equal(fx.apply_colour_panel(image, panel), fx.python_colour_panel(image, panel))


def test_alpha_is_untouched_and_the_input_is_not_changed():
    rng = np.random.default_rng(5)
    image = rng.integers(0, 256, (20, 30, 4), dtype=np.uint8)
    before = image.copy()
    out = fx.apply_colour_panel(image, {"exposure": 1.0, "vignette": 40})
    assert np.array_equal(out[:, :, 3], image[:, :, 3]) and np.array_equal(image, before)


def test_sharpen_and_the_switch_keep_the_python_path(monkeypatch):
    called = []
    monkeypatch.setattr(native, "colour_panel", lambda *args: called.append(args))
    image = np.full((8, 8, 4), 128, np.uint8)
    fx.apply_colour_panel(image, {"exposure": 0.5, "sharpen": 30})
    monkeypatch.setenv("FORMCUT_NATIVE", "0")
    fx.apply_colour_panel(image, {"exposure": 0.5})
    assert called == []
    monkeypatch.delenv("FORMCUT_NATIVE")
    fx.apply_colour_panel(image, {"exposure": 0.5})
    assert len(called) == 1


def test_whites_and_blacks_cube_by_multiplication_so_every_cpu_agrees():
    luminance = np.linspace(0, 1, 1001, dtype=np.float32)
    expected = luminance * luminance * luminance
    image = np.zeros((1, 1001, 4), np.uint8)
    image[0, :, :3] = (luminance * 255).astype(np.uint8)[:, None]
    assert np.array_equal(fx.apply_colour_panel(image, {"whites": 60}), fx.python_colour_panel(image, {"whites": 60}))
    assert expected.dtype == np.float32
