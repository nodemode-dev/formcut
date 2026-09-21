"""Prompts on a clip that moves.

A point or box made while a keyframed or animated clip was on screen is carried
back through where the clip was at that moment, using the renderer's own
transform_at. These check the shared transform, that a pixel the renderer drew
mid-move maps home only with the prompt's time, and that times are validated.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from app.prompt_space import placement, to_source
from app.renderer import DEFAULTS, transform_at
from app.validation import clip_values
from conftest import make_project

MOVE = [{"t": 0, "props": {"posX": -20}}, {"t": 1, "props": {"posX": 20}}]


def moving(**extra) -> dict:
    return {"id": "c", "kind": "image", "start": 0, "duration": 1, "keyframes": MOVE, **extra}


def test_a_plain_clip_is_its_defaults_at_any_time():
    assert transform_at({"id": "c", "kind": "image", "duration": 1}, 0.7) == DEFAULTS


def test_keyframes_move_the_clip_over_its_own_time():
    assert transform_at(moving(), 0.0)["posX"] == pytest.approx(-20)
    assert transform_at(moving(), 1.0)["posX"] == pytest.approx(20)


def test_a_prompt_without_a_time_is_placed_as_the_base_transform():
    assert placement(moving(), (320, 180), (320, 180)) == pytest.approx(placement({"transform": {}}, (320, 180), (320, 180)))


def test_a_prompt_with_a_time_is_placed_where_the_clip_was_then():
    points, _ = to_source(moving(), (320, 180), (320, 180), [{"x": 0.7, "y": 0.5, "t": 1.0}], None)
    assert points[0]["x"] == pytest.approx(0.5) and points[0]["t"] == 1.0


def test_a_box_drawn_at_a_time_is_carried_back_from_then():
    _, box = to_source(moving(), (320, 180), (320, 180), [], {"x0": 0.6, "y0": 0.4, "x1": 0.8, "y1": 0.6, "t": 1.0})
    assert box == pytest.approx({"x0": 0.4, "y0": 0.4, "x1": 0.6, "y1": 0.6})


def test_a_time_that_is_not_a_number_is_no_time():
    points, _ = to_source(moving(), (320, 180), (320, 180), [{"x": 0.7, "y": 0.5, "t": True}], None)
    assert points[0]["x"] == pytest.approx(0.7)


def still(tmp_path) -> dict:
    from app import media

    image = np.zeros((180, 240, 3), np.uint8)
    image[42:49, 57:64] = 255
    path = tmp_path / "marker.png"
    cv2.imwrite(str(path), image)
    return media.ingest_path(path, "marker.png")


def test_a_pixel_drawn_mid_move_maps_home_only_with_its_time(tmp_path):
    from app.render_document import validate_document
    from app.renderer import FrameRenderer

    placed = {**moving(), "label": "m", "mediaId": still(tmp_path)["id"], "transform": {"scale": 80, "rotation": 15}}
    project = validate_document(make_project(width=320, height=180, clips=[placed], duration=1.0))
    frame = FrameRenderer(project).frame(0.8)
    rows, columns = np.nonzero(frame[:, :, :3].max(axis=2) > 128)
    seen = {"x": columns.mean() / 320, "y": rows.mean() / 180}
    timed, _ = to_source(placed, (320, 180), (240, 180), [{**seen, "t": 0.8}], None)
    untimed, _ = to_source(placed, (320, 180), (240, 180), [seen], None)
    assert abs(timed[0]["x"] - 60 / 240) < 0.01 and abs(timed[0]["y"] - 45 / 180) < 0.01
    assert abs(untimed[0]["x"] - 60 / 240) > 0.05


def cutout(**prompt) -> dict:
    return {"id": "c", "kind": "video", "start": 0, "duration": 1, "cutout": {"model": "click-select", **prompt}}


def test_a_point_with_a_time_passes_validation():
    clip_values(cutout(point={"x": 0.5, "y": 0.5, "t": 0.25}))


def test_a_point_with_a_negative_time_is_refused():
    with pytest.raises(ValueError):
        clip_values(cutout(point={"x": 0.5, "y": 0.5, "t": -1}))


def test_a_listed_point_with_a_time_that_is_not_a_number_is_refused():
    with pytest.raises(ValueError):
        clip_values(cutout(points=[{"x": 0.5, "y": 0.5, "t": "soon"}]))


def test_a_box_with_a_time_passes_validation():
    clip_values(cutout(box={"x0": 0.2, "y0": 0.2, "x1": 0.6, "y1": 0.6, "t": 0.5}))


def test_a_box_with_a_time_past_a_day_is_refused():
    with pytest.raises(ValueError):
        clip_values(cutout(box={"x0": 0.2, "y0": 0.2, "x1": 0.6, "y1": 0.6, "t": 90000}))
