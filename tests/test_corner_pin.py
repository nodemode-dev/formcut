"""The corner pin (P3 of the planar tracking plan): a clip's image corners onto four canvas points by a perspective
warp, drawn by the frame renderer on every path (a pinned clip is placed on this side, not left on the device), and
refused by both export graphs so an export draws it as the preview does."""

from __future__ import annotations

import numpy as np
import pytest
from app import fast_export, fast_layers
from app.renderer import CPU_STEPS, FrameRenderer, pin_at
from PIL import Image


def test_a_pin_is_fixed_or_follows_its_samples_held_at_the_ends():
    fixed = {"cornerPin": {"points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]}}
    assert pin_at(fixed, 3.0) == [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
    track = {"cornerPin": {"times": [1.0, 2.0], "points": [[0, 0, 1, 0, 1, 1, 0, 1], [0.2, 0.2, 1.2, 0.2, 1.2, 1.2, 0.2, 1.2]]}}
    assert pin_at(track, 1.5)[0] == pytest.approx((0.1, 0.1))
    assert pin_at(track, 0.0)[2] == (1.0, 1.0) and pin_at(track, 9.0)[0] == pytest.approx((0.2, 0.2))
    assert pin_at({}, 1.0) is None and pin_at({"cornerPin": {"points": [[0, 0]]}}, 1.0) is None


def _project(tmp_path, pin):
    from app.media import ingest_path

    picture = tmp_path / "red.png"
    Image.new("RGB", (200, 100), (230, 20, 20)).save(picture)
    item = ingest_path(picture, "red.png")
    clip = {"id": "c1", "kind": "image", "label": "red", "start": 0, "duration": 2, "mediaId": item["id"], "cornerPin": pin}
    return {"width": 320, "height": 180, "fps": 30, "activeTimeline": 0, "timelines": [{"tracks": [{"clips": [clip]}]}]}


def test_a_pinned_clip_is_drawn_onto_its_four_points(tmp_path):
    quad = [[0.20, 0.15], [0.80, 0.25], [0.75, 0.85], [0.25, 0.80]]  # a perspective quadrilateral
    renderer = FrameRenderer(_project(tmp_path, {"points": quad}), 320)
    try:
        frame = renderer.frame(0.5)
    finally:
        renderer.close()
    rgb = frame[:, :, :3].astype(int)
    red = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] < 80)
    import cv2

    inside = np.zeros(red.shape, np.uint8)
    cv2.fillPoly(inside, [np.round(np.array(quad) * [320, 180]).astype(np.int32)], 1)
    core = cv2.erode(inside, np.ones((5, 5), np.uint8)).astype(bool)
    outside = ~cv2.dilate(inside, np.ones((5, 5), np.uint8)).astype(bool)
    assert red[core].mean() > 0.99 and red[outside].mean() < 0.01  # the picture fills the quad and nothing else


def test_a_pinned_clip_stays_off_the_device_and_both_export_graphs_refuse_it(tmp_path):
    assert "cornerPin" in CPU_STEPS and "cornerPin" in fast_export.ABSENT
    from app.render_document import validate_document

    project = validate_document(_project(tmp_path, {"points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]}))
    assert fast_export.refusal(project) is not None
    assert fast_layers.plan(project, 60) is None
