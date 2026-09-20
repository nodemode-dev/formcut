"""Timing: speed, keyframes, easing and where a clip is in its source."""

from __future__ import annotations

import pytest
from conftest import text_clip


def test_a_clip_at_normal_speed_maps_time_straight_through():
    from app.timing import source_time

    clip = text_clip(duration=4.0)
    assert source_time(clip, 0.0) == pytest.approx(0.0)
    assert source_time(clip, 2.0) == pytest.approx(2.0, abs=0.01)


def test_double_speed_reads_the_source_twice_as_fast():
    from app.timing import source_time

    clip = text_clip(duration=4.0, speed=2.0)
    assert source_time(clip, 1.0) == pytest.approx(2.0, abs=0.02)


def test_half_speed_reads_the_source_half_as_fast():
    from app.timing import source_time

    clip = text_clip(duration=4.0, speed=0.5)
    assert source_time(clip, 2.0) == pytest.approx(1.0, abs=0.02)


@pytest.mark.parametrize("speed", [0.05, 0.5, 1.0, 16.0, 100.0])
def test_the_whole_speed_range_is_accepted(speed):
    from app.render_document import validate_document
    from conftest import make_project

    document = validate_document(make_project(clips=[text_clip(speed=speed)]))
    assert document["timelines"][0]["tracks"][0]["clips"][0]["speed"] == pytest.approx(speed)


def test_a_property_between_two_keyframes_is_between_their_values():
    from app.timing import property_at

    clip = text_clip(keyframes=[{"t": 0, "props": {"scale": 0}, "interp": "linear"}, {"t": 4, "props": {"scale": 100}, "interp": "linear"}])
    assert property_at(clip, "scale", 2.0, 100) == pytest.approx(50, abs=1)


def test_easing_is_not_a_straight_line():
    from app.timing import ease

    assert ease(0.5, "ease") != pytest.approx(0.5, abs=0.02)
    assert ease(0.5, "linear") == pytest.approx(0.5)


def test_a_bezier_handle_changes_the_curve():
    from app.timing import ease

    shaped = ease(0.5, "bezier", [0.9, 0.0, 1.0, 0.35])
    assert shaped < 0.2, "the handles did not shape the curve"


def test_a_held_keyframe_does_not_interpolate():
    from app.timing import property_at

    clip = text_clip(keyframes=[{"t": 0, "props": {"scale": 20}, "interp": "hold"}, {"t": 4, "props": {"scale": 90}, "interp": "linear"}])
    assert property_at(clip, "scale", 3.9, 100) == pytest.approx(20)


def test_a_fade_starts_silent_and_reaches_full():
    from app.timing import fade_at

    clip = text_clip(duration=4.0, fadeIn=1.0)
    assert fade_at(clip, 0.0) < 0.1
    assert fade_at(clip, 2.0) == pytest.approx(1.0, abs=0.01)
