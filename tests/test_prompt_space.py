"""Prompts land on the subject, wherever the clip sits on the canvas.

A click or a box is stored as a fraction of the picture, and the cutout models
segment the clip's own pixels. These check the carry-back through the clip's
placement: the geometry, that it agrees with where the renderer actually draws
a pixel, and that both the renderer and the matte job use it.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from app import segmentation
from app.prompt_space import placement, to_source
from conftest import make_project


def clip(**transform) -> dict:
    return {"id": "c", "kind": "image", "transform": transform}


def near(point: dict, x: float, y: float) -> bool:
    return abs(point["x"] - x) < 1e-6 and abs(point["y"] - y) < 1e-6


def test_a_clip_that_fills_the_frame_changes_nothing():
    points, _ = to_source(clip(), (320, 180), (320, 180), [{"x": 0.3, "y": 0.7}], None)
    assert near(points[0], 0.3, 0.7)


def test_a_smaller_source_of_the_same_shape_changes_nothing():
    points, _ = to_source(clip(), (1920, 1080), (640, 360), [{"x": 0.3, "y": 0.7}], None)
    assert near(points[0], 0.3, 0.7)


def test_a_letterboxed_source_is_measured_inside_its_own_picture():
    points, _ = to_source(clip(), (320, 180), (240, 180), [{"x": 100 / 320, "y": 0.5}], None)
    assert near(points[0], 0.25, 0.5)


def test_the_edge_of_a_letterboxed_picture_is_the_edge_of_the_source():
    points, _ = to_source(clip(), (320, 180), (240, 180), [{"x": 40 / 320, "y": 0.5}, {"x": 280 / 320, "y": 0.5}], None)
    assert near(points[0], 0.0, 0.5) and near(points[1], 1.0, 0.5)


def test_a_half_size_clip_maps_its_corners_home():
    points, _ = to_source(clip(scale=50), (320, 180), (320, 180), [{"x": 0.25, "y": 0.25}, {"x": 0.75, "y": 0.75}], None)
    assert near(points[0], 0.0, 0.0) and near(points[1], 1.0, 1.0)


def test_a_moved_clip_is_found_where_it_was_moved_to():
    points, _ = to_source(clip(posX=25), (320, 180), (320, 180), [{"x": 0.75, "y": 0.5}], None)
    assert near(points[0], 0.5, 0.5)


def test_a_flipped_clip_mirrors_the_point():
    points, _ = to_source(clip(flipH=True), (320, 180), (320, 180), [{"x": 0.25, "y": 0.4}], None)
    assert near(points[0], 0.75, 0.4)


def test_a_quarter_turn_maps_through_the_rotation():
    points, _ = to_source(clip(rotation=90), (200, 200), (200, 200), [{"x": 0.9, "y": 0.25}], None)
    assert near(points[0], 0.25, 0.1)


def test_a_point_off_the_clip_is_held_to_its_edge():
    points, _ = to_source(clip(), (320, 180), (240, 180), [{"x": 0.02, "y": 0.5}], None)
    assert near(points[0], 0.0, 0.5)


def test_a_point_keeps_what_else_it_says():
    points, _ = to_source(clip(), (320, 180), (240, 180), [{"x": 0.5, "y": 0.5, "keep": False}], None)
    assert points[0]["keep"] is False


def test_a_box_around_a_letterboxed_picture_is_the_whole_source_wide():
    _, box = to_source(clip(), (320, 180), (240, 180), [], {"x0": 0.125, "y0": 0.25, "x1": 0.875, "y1": 0.75})
    assert box == pytest.approx({"x0": 0.0, "y0": 0.25, "x1": 1.0, "y1": 0.75})


def test_a_box_through_a_rotation_stays_a_box_around_the_same_place():
    _, box = to_source(clip(rotation=90), (200, 200), (200, 200), [], {"x0": 0.6, "y0": 0.2, "x1": 0.9, "y1": 0.3})
    assert box == pytest.approx({"x0": 0.2, "y0": 0.1, "x1": 0.3, "y1": 0.4})


def test_a_clip_scaled_to_nothing_leaves_the_prompt_alone():
    points, box = to_source(clip(scale=0), (320, 180), (320, 180), [{"x": 0.3, "y": 0.7}], None)
    assert near(points[0], 0.3, 0.7) and box is None


def test_the_placement_is_the_renderers_for_a_plain_clip():
    assert placement(clip(), (320, 180), (320, 180)) == pytest.approx((1, 0, 0, 1, 0, 0))


def still(tmp_path, size=(180, 240), marker=(45, 60)) -> dict:
    from app import media

    image = np.zeros((*size, 3), np.uint8)
    y, x = marker
    image[y - 3 : y + 4, x - 3 : x + 4] = 255
    path = tmp_path / "marker.png"
    cv2.imwrite(str(path), image)
    return media.ingest_path(path, "marker.png")


def document(record: dict, transform: dict | None = None, cutout: dict | None = None) -> dict:
    from app.render_document import validate_document

    placed = {"id": "c", "kind": "image", "label": "m", "mediaId": record["id"], "start": 0, "duration": 1}
    if transform:
        placed["transform"] = transform
    if cutout:
        placed["cutout"] = cutout
    return validate_document(make_project(width=320, height=180, clips=[placed], duration=1.0))


def test_a_pixel_the_renderer_draws_maps_back_to_where_it_came_from(tmp_path):
    from app.renderer import FrameRenderer

    transform = {"scale": 70, "posX": 12, "posY": -6, "rotation": 30}
    project = document(still(tmp_path), transform)
    frame = FrameRenderer(project).frame(0.5)
    rows, columns = np.nonzero(frame[:, :, :3].max(axis=2) > 128)
    points, _ = to_source({"transform": transform}, (320, 180), (240, 180), [{"x": columns.mean() / 320, "y": rows.mean() / 180}], None)
    assert abs(points[0]["x"] - 60 / 240) < 0.01 and abs(points[0]["y"] - 45 / 180) < 0.01


def test_the_renderer_hands_sam_the_point_in_the_clips_own_pixels(tmp_path, monkeypatch):
    from app.renderer import FrameRenderer

    asked = []
    monkeypatch.setattr(segmentation, "ready", lambda model: True)
    monkeypatch.setattr(
        segmentation, "raw_alpha", lambda image, model, points=None, box=None: asked.append(points) or np.ones(image.shape[:2], np.float32)
    )
    cutout = {"model": "click-select", "point": {"x": 100 / 320, "y": 0.5}, "threshold": 0.5, "feather": 0.1}
    FrameRenderer(document(still(tmp_path), cutout=cutout)).frame(0.5)
    assert asked and near(asked[0][0], 0.25, 0.5)


def run_matte_job(monkeypatch, record: dict, width: int | None) -> list:
    from app import render_api

    asked = []
    monkeypatch.setattr(render_api.jobs, "submit", lambda kind, operation: operation("j", lambda fraction: None, lambda: False))
    monkeypatch.setattr(
        segmentation, "raw_alpha", lambda image, model, points=None, box=None: asked.append(points) or np.ones(image.shape[:2], np.float32)
    )
    cutout = {"model": "click-select", "point": {"x": 100 / 320, "y": 0.5}, "threshold": 0.5, "feather": 0.1}
    placed = {"id": f"m{width}", "kind": "image", "label": "m", "mediaId": record["id"], "start": 0, "duration": 0.1, "cutout": cutout}
    render_api.build_mattes(render_api.MatteInput(clip=placed, fps=10, width=width, height=180 if width else None))
    return asked


def test_the_matte_job_carries_prompts_back_when_it_knows_the_canvas(tmp_path, monkeypatch):
    asked = run_matte_job(monkeypatch, still(tmp_path), 320)
    assert asked and all(near(points[0], 0.25, 0.5) for points in asked)


def test_the_matte_job_uses_prompts_as_sent_when_it_does_not(tmp_path, monkeypatch):
    asked = run_matte_job(monkeypatch, still(tmp_path), None)
    assert asked and all(near(points[0], 100 / 320, 0.5) for points in asked)
