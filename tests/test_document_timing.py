"""The document every render starts from, and the timing it is drawn with.

`validate_document` is the gate every render and export passes through, and
`flatten` is where transitions become the ramps and extensions the renderer
draws. A slip in either changes every frame, so each rule is checked on its own.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest
from app.render_document import flatten, validate_document
from app.renderer import DEFAULTS, FrameRenderer
from app.timing import fade_at, property_at, source_time
from conftest import make_project, text_clip


def with_track_clips(*clips: dict) -> dict:
    return make_project(clips=list(clips))


def test_missing_size_and_rate_take_their_defaults():
    project = make_project()
    for field in ("width", "height", "fps"):
        del project[field]
    result = validate_document(project)
    assert (result["width"], result["height"], result["fps"]) == (1920, 1080, 30)


def test_a_width_below_sixteen_is_refused():
    with pytest.raises(ValueError, match="Invalid project width"):
        validate_document(make_project(width=8))


def test_a_width_above_8k_is_refused():
    with pytest.raises(ValueError, match="Invalid project width"):
        validate_document(make_project(width=7681))


def test_a_fractional_frame_rate_is_refused():
    with pytest.raises(ValueError, match="Invalid project fps"):
        validate_document(make_project(fps=29.97))


def test_a_zero_frame_rate_is_refused():
    with pytest.raises(ValueError, match="Invalid project fps"):
        validate_document(make_project(fps=0))


def test_a_whole_number_written_as_a_float_becomes_an_integer():
    result = validate_document(make_project(width=1280.0))
    assert result["width"] == 1280 and isinstance(result["width"], int)


def test_a_project_without_timelines_is_refused():
    project = make_project()
    del project["timelines"]
    with pytest.raises(ValueError, match="active timeline"):
        validate_document(project)


def test_an_empty_timeline_list_is_refused():
    project = make_project()
    project["timelines"] = []
    with pytest.raises(ValueError, match="active timeline"):
        validate_document(project)


def test_an_active_timeline_past_the_end_is_refused():
    project = make_project()
    project["activeTimeline"] = 1
    with pytest.raises(ValueError, match="active timeline"):
        validate_document(project)


def test_an_active_timeline_that_is_not_a_number_is_refused():
    project = make_project()
    project["activeTimeline"] = "0"
    with pytest.raises(ValueError, match="active timeline"):
        validate_document(project)


def test_a_timeline_without_a_track_list_is_refused():
    project = make_project()
    del project["timelines"][0]["tracks"]
    with pytest.raises(ValueError, match="track list"):
        validate_document(project)


def test_track_clips_that_are_not_a_list_are_refused():
    project = make_project()
    project["timelines"][0]["tracks"][0]["clips"] = {}
    with pytest.raises(ValueError, match="Track clips"):
        validate_document(project)


def test_a_clip_that_is_not_an_object_is_refused():
    with pytest.raises(ValueError, match="Clip must be an object"):
        validate_document(with_track_clips("clip"))


def test_duplicate_clip_ids_are_refused():
    with pytest.raises(ValueError, match="unique"):
        validate_document(with_track_clips(text_clip(clip_id="a"), text_clip(clip_id="a", start=1.0)))


def test_duplicate_ids_across_timelines_are_refused():
    project = with_track_clips(text_clip(clip_id="a"))
    project["timelines"].append({"id": "t2", "name": "other", "tracks": [{"id": "x", "name": "V", "clips": [text_clip(clip_id="a")]}]})
    with pytest.raises(ValueError, match="unique"):
        validate_document(project)


def test_a_clip_id_that_is_not_text_is_refused():
    with pytest.raises(ValueError, match="unique"):
        validate_document(with_track_clips({**text_clip(), "id": 7}))


def test_a_negative_start_is_refused():
    with pytest.raises(ValueError):
        validate_document(with_track_clips(text_clip(start=-1.0)))


def test_a_zero_length_clip_is_refused():
    with pytest.raises(ValueError):
        validate_document(with_track_clips(text_clip(duration=0.0)))


def test_a_clip_longer_than_a_day_is_refused():
    with pytest.raises(ValueError):
        validate_document(with_track_clips(text_clip(duration=86401.0)))


def test_an_unknown_clip_kind_is_refused():
    with pytest.raises(ValueError):
        validate_document(with_track_clips({**text_clip(), "kind": "hologram"}))


def test_more_than_128_tracks_are_refused():
    project = make_project()
    project["timelines"][0]["tracks"] = [{"id": f"t{i}", "name": "V", "clips": []} for i in range(129)]
    with pytest.raises(ValueError, match="track limit"):
        validate_document(project)


def test_the_active_timelines_format_wins():
    project = make_project(width=1920, height=1080, fps=30)
    project["timelines"][0].update({"width": 1080, "height": 1920, "fps": 60})
    result = validate_document(project)
    assert (result["width"], result["height"], result["fps"]) == (1080, 1920, 60)


def test_a_timeline_with_an_invalid_rate_is_refused():
    project = make_project()
    project["timelines"][0]["fps"] = 500
    with pytest.raises(ValueError, match="Invalid timeline fps"):
        validate_document(project)


def test_the_duration_is_where_the_last_clip_ends():
    result = validate_document(
        with_track_clips(text_clip(clip_id="a", start=0.0, duration=2.0), text_clip(clip_id="b", start=3.0, duration=1.5))
    )
    assert result["duration"] == 4.5


def test_an_empty_timeline_lasts_a_tenth_of_a_second():
    assert validate_document(with_track_clips())["duration"] == 0.1


def test_validation_does_not_change_what_it_was_given():
    project = make_project()
    original = copy.deepcopy(project)
    validate_document(project)
    assert project == original


def test_every_clip_learns_its_track_index():
    project = make_project(clips=[text_clip(clip_id="a")])
    project["timelines"][0]["tracks"].append({"id": "t1", "name": "V2", "clips": [text_clip(clip_id="b")]})
    assert {c["id"]: c["trackIndex"] for c in flatten(project)} == {"a": 0, "b": 1}


def test_a_hidden_track_marks_its_clips_hidden():
    project = make_project()
    project["timelines"][0]["tracks"][0]["hidden"] = True
    assert all(c["trackHidden"] for c in flatten(project))


def test_a_muted_track_mutes_its_clips():
    project = make_project()
    project["timelines"][0]["tracks"][0]["muted"] = True
    assert all(c["muted"] for c in flatten(project))


def test_a_muted_clip_stays_muted_on_a_live_track():
    assert flatten(make_project(clips=[text_clip(muted=True)]))[0]["muted"] is True


def test_clips_come_out_in_start_order():
    project = make_project(clips=[text_clip(clip_id="late", start=2.0, duration=1.0), text_clip(clip_id="early", start=0.0, duration=1.0)])
    assert [c["id"] for c in flatten(project)] == ["early", "late"]


def test_flattening_leaves_the_document_alone():
    project = make_project()
    original = copy.deepcopy(project)
    flatten(project)
    assert project == original


def transition(kind: str, length: float = 0.5, gap: float = 0.0, second: float = 2.0) -> list[dict]:
    first = text_clip(clip_id="a", start=0.0, duration=2.0)
    later = text_clip(clip_id="b", start=2.0 + gap, duration=second, transitionIn={"type": kind, "duration": length})
    return flatten(make_project(clips=[first, later]))


def test_a_crossfade_ramps_the_incoming_clip_in():
    _, incoming = transition("crossfade")
    assert incoming["rampIn"] == 0.5 and incoming["transitionLength"] == 0.5


def test_a_crossfade_keeps_the_outgoing_clip_drawing_through_the_band():
    outgoing, _ = transition("crossfade")
    assert outgoing["extendOut"] == 0.5 and outgoing["transitionOut"] == {"type": "crossfade", "length": 0.5}


def test_a_dip_ramps_each_side_for_half_its_length():
    outgoing, incoming = transition("dip")
    assert incoming["rampIn"] == 0.25 and outgoing["rampOut"] == 0.25 and "transitionLength" not in incoming


def test_a_transition_is_at_most_half_the_incoming_clip():
    _, incoming = transition("crossfade", length=5.0, second=2.0)
    assert incoming["transitionIn"]["duration"] == 1.0


def test_a_transition_is_at_least_a_hundredth_of_a_second():
    _, incoming = transition("crossfade", length=0.0)
    assert incoming["transitionIn"]["duration"] == 0.01


def test_a_clip_across_a_gap_is_not_extended():
    outgoing, _ = transition("crossfade", gap=0.5)
    assert "extendOut" not in outgoing


def test_push_up_carries_the_outgoing_clip_off():
    outgoing, _ = transition("push-up")
    assert outgoing["pushOut"] == 0.5


def test_an_unknown_transition_is_refused():
    with pytest.raises(ValueError, match="Unknown transition"):
        transition("teleport")


def test_source_time_starts_at_the_in_point():
    assert source_time({"sourceIn": 2.0, "duration": 5.0}, 1.5) == pytest.approx(3.5)


def test_source_time_never_goes_before_the_start_of_the_file():
    assert source_time({"sourceIn": 0.0, "duration": 5.0}, -1.0) == 0.0


def test_source_time_before_a_clip_counts_back_from_its_in_point():
    assert source_time({"sourceIn": 2.0, "duration": 5.0}, -1.0) == pytest.approx(1.0)


def test_a_clip_without_fades_is_fully_visible():
    assert fade_at({"duration": 4.0}, 2.0) == 1.0


def test_halfway_through_a_fade_in_is_half_visible():
    assert fade_at({"duration": 4.0, "fadeIn": 1.0}, 0.5) == pytest.approx(0.5)


def test_near_the_end_of_a_fade_out_is_nearly_gone():
    assert fade_at({"duration": 4.0, "fadeOut": 1.0}, 3.9) == pytest.approx(0.1)


def test_a_ramp_in_fades_like_a_fade_in():
    assert fade_at({"duration": 4.0, "rampIn": 2.0}, 1.0) == pytest.approx(0.5)


def test_a_ramp_out_fades_like_a_fade_out():
    assert fade_at({"duration": 4.0, "rampOut": 2.0}, 3.0) == pytest.approx(0.5)


def test_overlapping_fades_take_the_darker():
    assert fade_at({"duration": 1.0, "fadeIn": 1.0, "fadeOut": 1.0}, 0.25) == pytest.approx(0.25)


def test_an_extended_clip_fades_across_its_extension():
    assert fade_at({"duration": 2.0, "extendOut": 1.0}, 2.5) == pytest.approx(0.5)


def test_a_fade_never_goes_below_nothing():
    assert fade_at({"duration": 2.0, "fadeIn": 1.0}, -1.0) == 0.0


def test_a_property_without_keyframes_keeps_its_value():
    assert property_at({"keyframes": []}, "scale", 1.0, 100) == 100


def test_before_the_first_keyframe_the_first_value_holds():
    clip = {"keyframes": [{"t": 1.0, "props": {"scale": 150}}, {"t": 2.0, "props": {"scale": 200}}]}
    assert property_at(clip, "scale", 0.2, 100) == 150


def test_the_neutral_transform_changes_nothing():
    assert DEFAULTS["scale"] == 100 and DEFAULTS["opacity"] == 100 and DEFAULTS["posX"] == 0 and DEFAULTS["blendMode"] == "Normal"


def blank(background=None) -> tuple[FrameRenderer, np.ndarray]:
    renderer = FrameRenderer(validate_document(make_project(background=background)))
    return renderer, np.zeros((renderer.height, renderer.width, 4), np.uint8)


def test_a_colour_background_fills_the_canvas():
    renderer, canvas = blank("#ff0000")
    painted = renderer.paint_background(canvas, 0.0)
    assert tuple(painted[0, 0, :3]) == (255, 0, 0) and tuple(painted[-1, -1, :3]) == (255, 0, 0)


def test_a_gradient_runs_from_top_to_bottom():
    renderer, canvas = blank({"type": "gradient", "from": "#000000", "to": "#ffffff"})
    painted = renderer.paint_background(canvas, 0.0)
    assert tuple(painted[0, 0, :3]) == (0, 0, 0) and tuple(painted[-1, 0, :3]) == (255, 255, 255)


def test_no_background_leaves_the_canvas_black():
    renderer, canvas = blank()
    assert not renderer.paint_background(canvas, 0.0).any()


def test_a_background_that_cannot_be_drawn_never_stops_the_frame():
    renderer, canvas = blank({"type": "sparkles"})
    assert not renderer.paint_background(canvas, 0.0).any()


def test_covering_with_a_wide_image_fills_the_canvas_exactly():
    renderer, _ = blank()
    assert renderer._cover(np.zeros((180, 640, 3), np.uint8)).shape == (renderer.height, renderer.width, 3)


def test_covering_with_a_tall_image_fills_the_canvas_exactly():
    renderer, _ = blank()
    assert renderer._cover(np.zeros((400, 100, 3), np.uint8)).shape == (renderer.height, renderer.width, 3)
