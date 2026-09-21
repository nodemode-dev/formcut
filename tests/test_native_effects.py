"""The effect chain: Rust conversions and cached grids, identical to the NumPy code they replace."""

import numpy as np
import pytest
from app import pixel_effects as fx
from app.catalogue import VIDEO_EFFECTS

try:
    import formcut_native as native
except ImportError:
    native = None

KERNELS = pytest.mark.skipif(native is None or not hasattr(native, "to_bytes"), reason="the native conversion kernels are not built here")


@KERNELS
def test_the_conversions_match_numpy_on_every_value_and_every_tie():
    values = np.clip(np.linspace(-0.001, 1.001, 1 << 20, dtype=np.float32), 0, 1).reshape(512, 512, 4)
    out = np.empty(values.shape, np.uint8)
    native.to_bytes(values, out)
    assert np.array_equal(out, np.round(values * 255).astype(np.uint8))
    ties = np.ascontiguousarray(np.repeat((np.arange(255, dtype=np.float32) + 0.5) / 255, 4).reshape(1, -1, 4))
    rounded = np.empty(ties.shape, np.uint8)
    native.to_bytes(ties, rounded)
    assert np.array_equal(rounded, np.round(ties * 255).astype(np.uint8))
    image = np.arange(256, dtype=np.uint8).repeat(4).reshape(8, 32, 4)
    floats = np.empty(image.shape, np.float32)
    native.unit_float(image, floats)
    assert np.array_equal(floats, image.astype(np.float32) / 255)


@KERNELS
@pytest.mark.parametrize("effect", sorted(VIDEO_EFFECTS))
def test_every_effect_is_identical_with_and_without_the_kernels(effect, monkeypatch):
    image = np.random.default_rng(3).integers(0, 256, (41, 67, 4), dtype=np.uint8)
    chain = [{"id": effect, "amount": 0.8, "params": {}}]
    with_kernels = fx.apply_effects(image, chain, 1.3)
    monkeypatch.setenv("FORMCUT_NATIVE", "0")
    assert np.array_equal(with_kernels, fx.apply_effects(image, chain, 1.3))


def test_the_grids_are_computed_once_per_size_and_read_only():
    first = fx._grid(20, 30)
    assert fx._grid(20, 30)[0] is first[0]
    y, _, u, v = first
    assert y.shape == (20, 30) and float(u[0, 0]) == pytest.approx(0.5 / 30) and float(v[-1, 0]) == pytest.approx(19.5 / 20)
    with pytest.raises(ValueError):
        u[0, 0] = 1
    assert fx._vignette_falloff(20, 30).flags.writeable is False
