"""LUT interpolation against values worked by hand, 1D .cube files, and the camera Log curves at the reference
points their manufacturers publish (the documents are cited in backend/HASHOUT_LOG.md)."""

from __future__ import annotations

import numpy as np
import pytest
from app import assets, camera_log


def _cube_2(corner) -> np.ndarray:
    """A 2-point lattice ([b][g][r]) whose eight corners take corner(r, g, b) in every channel."""
    table = np.zeros((2, 2, 2, 3), np.float32)
    for b in (0, 1):
        for g in (0, 1):
            for r in (0, 1):
                table[b, g, r] = corner(r, g, b)
    return table


def _at(table, rgb, interpolation):
    image = np.zeros((1, 1, 3), np.uint16)
    image[0, 0] = np.round(np.asarray(rgb) * 65535)
    out = assets.apply_cube(image, (table, np.zeros(3), np.ones(3)), 1.0, interpolation)
    return out[0, 0].astype(np.float64) / 65535


def test_trilinear_and_tetrahedral_at_a_point_worked_by_hand():
    table = _cube_2(lambda r, g, b: float(r and g and b))  # only the white corner is lit
    point = (0.25, 0.5, 0.75)
    # trilinear weights the white corner by r * g * b; tetrahedral by the smallest fraction
    assert _at(table, point, "trilinear") == pytest.approx([0.25 * 0.5 * 0.75] * 3, abs=2e-5)
    assert _at(table, point, "tetrahedral") == pytest.approx([0.25] * 3, abs=2e-5)
    table = _cube_2(lambda r, g, b: float(r and not g and not b))  # only the red corner is lit
    # tetrahedral path through the order b > g > r: red's corner is never on it
    assert _at(table, point, "tetrahedral") == pytest.approx([0.0] * 3, abs=2e-5)
    assert _at(table, (0.75, 0.5, 0.25), "tetrahedral") == pytest.approx([0.25] * 3, abs=2e-5)


@pytest.mark.parametrize("interpolation", assets.INTERPOLATIONS)
def test_an_affine_lut_is_reproduced_exactly_by_both(interpolation):
    rng = np.random.default_rng(5)
    n = 9
    steps = np.linspace(0, 1, n)
    blue, green, red = np.meshgrid(steps, steps, steps, indexing="ij")
    rgb = np.stack([red, green, blue], axis=-1)
    matrix = np.array([[0.7, 0.2, 0.05], [0.1, 0.6, 0.2], [0.05, 0.15, 0.75]])
    table = (rgb @ matrix.T + 0.02).astype(np.float32)
    image = rng.integers(0, 65536, (64, 64, 4)).astype(np.uint16)
    out = assets.apply_cube(image, (table, np.zeros(3), np.ones(3)), 1.0, interpolation)
    expected = np.clip(image[..., :3] / 65535 @ matrix.T + 0.02, 0, 1) * 65535
    assert np.abs(out[..., :3] - expected).max() <= 2.0
    assert np.array_equal(out[..., 3], image[..., 3])


def test_the_eight_bit_trilinear_lut_is_the_original_arithmetic(monkeypatch):
    rng = np.random.default_rng(6)
    table = rng.random((5, 5, 5, 3)).astype(np.float32)
    monkeypatch.setattr(assets, "load_cube", lambda _id: (table, np.zeros(3), np.ones(3)))
    image = rng.integers(0, 256, (32, 32, 4)).astype(np.uint8)
    ours = assets.apply_lut(image, "x")
    # the float32 sampler agrees with the original float64 byte path to within the last byte's rounding
    sampled = assets.apply_cube(image, (table, np.zeros(3), np.ones(3)))
    assert ours.dtype == np.uint8 and np.abs(ours.astype(int) - sampled.astype(int)).max() <= 1


def test_a_1d_cube_parses_and_applies_per_channel():
    size = 1024
    values = np.linspace(0, 1, size)
    text = 'TITLE "gamma"\nLUT_1D_SIZE 1024\nLUT_1D_INPUT_RANGE 0.0 1.0\n' + "".join(
        f"{v * v:.8f} {v:.8f} {np.sqrt(v):.8f}\n" for v in values
    )
    table, low, high = assets.parse_cube(text)
    assert table.shape == (size, 3) and list(low) == [0, 0, 0] and list(high) == [1, 1, 1]
    image = np.zeros((1, 3, 3), np.uint16)
    image[0, :, :] = np.array([0.3, 0.5, 0.81])[:, None] * 65535
    out = assets.apply_cube(image, (table, low, high)).astype(np.float64) / 65535
    for k, v in enumerate((0.3, 0.5, 0.81)):
        assert out[0, k] == pytest.approx([v * v, v, np.sqrt(v)], abs=3e-5)
    with pytest.raises(ValueError, match="both a 1D and a 3D"):
        assets.parse_cube("LUT_1D_SIZE 2\nLUT_3D_SIZE 2\n" + "0 0 0\n" * 10)
    with pytest.raises(ValueError):
        assets.parse_cube("LUT_1D_SIZE 4\n0 0 0\n1 1 1\n")


def test_the_device_samples_luts_as_the_cpu_does(monkeypatch):
    from app import gpu, gpu_effects

    if not gpu.status().get("available"):
        pytest.skip("no WebGPU adapter on this machine")
    monkeypatch.setenv("FORMCUT_EFFECTS", "gpu")
    rng = np.random.default_rng(7)
    image = rng.integers(0, 65536, (32, 48, 4)).astype(np.uint16)
    image[..., 3] = 65535
    identity = np.float32([[1, 0, 0], [0, 1, 0]])
    cubes = [(rng.random((7, 7, 7, 3)).astype(np.float32), "trilinear"), (rng.random((7, 7, 7, 3)).astype(np.float32), "tetrahedral")]
    cubes.append((np.sort(rng.random((256, 3)).astype(np.float32), axis=0), "trilinear"))
    for table, interpolation in cubes:
        low, high = np.zeros(3), np.ones(3)
        device = gpu_effects.effects_and_warp(image, [], 0.0, identity, 1.0, (48, 32), lut=(table, low, high, 0.8, interpolation))
        cpu = assets.apply_cube(image, (table, low, high), 0.8, interpolation)
        assert device is not None and device.dtype == np.uint16
        assert np.abs(device[..., :3].astype(int) - cpu[..., :3].astype(int)).max() <= 2, interpolation


# The manufacturers' reference points: 10-bit code value -> scene reflectance.
REFERENCE = {
    "slog3": [(95, 0.0), (420, 0.18), (598, 0.90)],
    "vlog": [(128, 0.0), (433, 0.18), (602, 0.90)],
    "logc3": [(0.391 * 1023, 0.18)],
    "canon-log3": [(128, 0.0), (351, 0.18), (577, 0.90), (908, 7.2)],
    "canon-log2": [(95, 0.0), (407, 0.18), (575, 0.90), (797, 7.2)],
}


@pytest.mark.parametrize("name", sorted(REFERENCE))
def test_each_log_curve_meets_its_published_reference_points(name):
    for code, reflectance in REFERENCE[name]:
        found = float(camera_log.to_scene(name, code / 1023))
        # the tables print whole code values, so half a code of slack, as reflectance
        slack = abs(float(camera_log.to_scene(name, (code + 0.5) / 1023)) - float(camera_log.to_scene(name, code / 1023)))
        assert abs(found - reflectance) <= slack + 1e-4, (name, code, found, reflectance)


def test_the_gamut_matrices_match_the_ones_panasonic_and_arri_publish():
    v_gamut = [[1.806576, -0.695697, -0.110879], [-0.170090, 1.305955, -0.135865], [-0.025206, -0.154468, 1.179674]]
    alexa = [[1.617523, -0.537287, -0.080237], [-0.070573, 1.334613, -0.264040], [-0.021102, -0.226954, 1.248056]]
    assert np.abs(camera_log.gamut_matrix("v-gamut") - v_gamut).max() < 2e-6
    assert np.abs(camera_log.gamut_matrix("alexa-wide-gamut") - alexa).max() < 2e-6
    for gamut in camera_log.GAMUTS:
        assert camera_log.gamut_matrix(gamut).sum(axis=1) == pytest.approx([1, 1, 1], abs=1e-6)  # white stays white


def test_grey_and_white_shot_in_s_log3_land_where_a_cameras_rec709_puts_them():
    def shown(code: int, full: bool = True) -> float:
        # Sony records S-Log3 full range; the same code decoded from a video-range file reads (code - 64) / 876
        signal = code / 1023 if full else (code - 64) / 876
        image = np.full((2, 2, 3), round(signal * 65535), np.uint16)
        return float(camera_log.apply(image, "slog3", full)[0, 0, 1]) / 65535

    assert shown(420, full=False) == pytest.approx(shown(420), abs=2e-4)

    assert shown(420) == pytest.approx(1.099 * 0.18**0.45 - 0.099, abs=2e-3)  # 18% grey at 41%
    assert 0.88 < shown(598) < 0.95  # 90% white under the shoulder, not clipped
    assert shown(1019) > shown(940) > shown(598)  # highlights roll off instead of clipping


def test_the_log_transform_keeps_ten_bit_steps_and_alpha():
    ramp = np.round(np.linspace(0.1, 0.3, 4096) * 65535).astype(np.uint16)
    image = np.dstack([np.tile(ramp, (2, 1))] * 3 + [np.full((2, 4096), 65535, np.uint16)])
    out = camera_log.apply(image, "canon-log3")
    assert out.dtype == np.uint16 and len(np.unique(out[0, :, 1])) > 2000 and (out[..., 3] == 65535).all()
    assert camera_log.apply(image, "canon-log3", deep=True).dtype == np.uint8


def test_a_suggestion_comes_from_the_files_own_words(tmp_path):
    assert camera_log.suggest({"format": {"tags": {"comment": "Gamma S-Log3 / S-Gamut3.Cine"}}}) == "slog3"
    assert camera_log.suggest({"streams": [{"tags": {"gamma": "Canon Log 3"}}]}) == "canon-log3"
    assert camera_log.suggest({"format": {"tags": {"comment": "LogC4 AWG4"}}}) is None
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"\0" * 1000 + b'<Item name="CaptureGammaEquation" value="s-log3-cine"/>' + b"\0" * 1000)
    assert camera_log.suggest({}, clip) == "slog3"
    plain = tmp_path / "plain.mp4"
    plain.write_bytes(b"\0" * 4000 + b"vlog s-log3 noise outside any gamma item")
    assert camera_log.suggest({}, plain) is None


def test_the_document_takes_only_known_input_colours_and_interpolations():
    from app.validation import clip_values

    clip_values({"id": "a", "kind": "video", "inputColour": "vlog", "lutInterpolation": "tetrahedral"})
    with pytest.raises(ValueError, match="inputColour"):
        clip_values({"id": "a", "kind": "video", "inputColour": "rec2020"})
    with pytest.raises(ValueError, match="lutInterpolation"):
        clip_values({"id": "a", "kind": "video", "lutInterpolation": "cubic"})
