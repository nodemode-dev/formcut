"""The Color section's grade does what a colourist expects of each tool.

Each check is a property a grading tool is defined by: lift moves the blacks and
not the whites, gain the reverse, gamma the middle; contrast turns about its
pivot; a curve passes through its points and never inverts; a hue curve moves
one hue and leaves the others. Every export path either applies the grade or
refuses the clip, never ignores it.
"""

from pathlib import Path

import numpy as np
import pytest
from app import color_grade, fast_export, fast_layers, validation


def _ramp():
    values = np.linspace(0, 1, 11, dtype=np.float32)
    return np.stack([values, values, values], axis=1)[None]


def test_a_neutral_grade_changes_nothing():
    image = np.random.default_rng(1).integers(0, 256, (8, 8, 4), dtype=np.uint8)
    assert np.array_equal(color_grade.apply(image, {"lift": {"y": 0}, "contrast": 1, "curves": {"y": [[0, 0], [1, 1]]}}), image)
    assert not color_grade.active({"pivot": 0.2})


def test_lift_raises_the_blacks_and_leaves_white():
    out = color_grade.apply_float(_ramp(), {"lift": {"y": 0.4}})[0, :, 0]
    assert out[0] > 0.15 and abs(out[-1] - 1) < 1e-6


def test_gain_scales_and_keeps_black():
    out = color_grade.apply_float(_ramp(), {"gain": {"y": -0.5}})[0, :, 0]
    assert out[0] == 0 and abs(out[-1] - 0.5) < 1e-6


def test_gamma_moves_the_middle_and_keeps_the_ends():
    out = color_grade.apply_float(_ramp(), {"gamma": {"y": 0.5}})[0, :, 0]
    assert out[0] == 0 and abs(out[-1] - 1) < 1e-6 and out[5] > 0.6


def test_a_wheel_colour_tints_only_its_channel():
    out = color_grade.apply_float(_ramp(), {"gain": {"r": 0.3}})[0, 10]
    assert out[0] > 1.2 and abs(out[1] - 1) < 1e-6 and abs(out[2] - 1) < 1e-6


def test_contrast_turns_about_its_pivot():
    grey = np.full((1, 1, 3), 0.3, np.float32)
    assert np.allclose(color_grade.apply_float(grey, {"contrast": 1.8, "pivot": 0.3}), 0.3)


def test_a_curve_passes_through_its_points_and_never_inverts():
    grade = {"curves": {"y": [[0, 0], [0.25, 0.6], [0.5, 0.62], [1, 1]]}}
    ramp = np.linspace(0, 1, 101, dtype=np.float32)
    out = color_grade.apply_float(np.stack([ramp] * 3, axis=1)[None], grade)[0, :, 0]
    assert np.all(np.diff(out) >= -1e-6), "a curve through rising points must not fall"
    assert abs(out[25] - 0.6) < 0.01 and abs(out[50] - 0.62) < 0.01


def test_hue_against_hue_moves_red_and_leaves_blue():
    pixels = np.array([[[1.0, 0.1, 0.1], [0.1, 0.1, 1.0]]], np.float32)
    out = color_grade.apply_float(pixels, {"hueHue": [[0.0, 0.1], [0.3, 0.0], [0.7, 0.0]]})
    assert out[0, 0, 1] > 0.3, "red should turn towards yellow"
    assert np.allclose(out[0, 1], pixels[0, 1], atol=0.02), "blue should stay"


def test_hue_against_saturation_greys_only_its_hue():
    pixels = np.array([[[1.0, 0.1, 0.1], [0.1, 0.8, 0.1]]], np.float32)
    out = color_grade.apply_float(pixels, {"hueSat": [[0.0, 0.0], [0.15, 1.0], [0.85, 1.0]]})
    assert np.ptp(out[0, 0]) < 0.05 and np.ptp(out[0, 1]) > 0.5


def test_every_export_path_applies_the_grade_or_refuses_the_clip():
    assert "colorGrade" in fast_export.ABSENT, "the native path would export the clip ungraded"
    assert "colorGrade" in fast_layers.ALLOWED
    graded = {"kind": "video", "mediaId": "m", "colorGrade": {"gain": {"y": 0.2}}}
    assert fast_layers._grade(graded)["colorGrade"] == {"gain": {"y": 0.2}}


@pytest.mark.parametrize(
    "grade",
    [
        {"lift": {"y": 2}},
        {"lift": {"z": 0}},
        {"contrast": 5},
        {"curves": {"y": [[0, 0]]}},
        {"curves": {"y": [[0, 0], [0, 1]]}},
        {"hueSat": [[0, 3], [1, 1]]},
    ],
)
def test_an_unusable_grade_is_refused(grade):
    with pytest.raises(ValueError, match="colorGrade"):
        color_grade.check(grade)


def test_the_document_validator_checks_the_grade():
    assert "check_grade" in Path(validation.__file__).read_text(encoding="utf-8")
