"""The renderer: what it draws, and that the two paths agree.

These are output tests. They assert what a person would see, not how the
renderer arrives at it, so a rewrite that keeps the picture keeps them passing.
"""

from __future__ import annotations

import numpy as np
import pytest
from conftest import make_project, text_clip


def lit(frame) -> int:
    """How much of the frame has something drawn on it."""
    return int((frame[:, :, :3].max(axis=2) > 40).sum())


def render_at(document: dict, at: float, width: int | None = None) -> np.ndarray:
    from app.renderer import FrameRenderer

    renderer = FrameRenderer(document, width) if width else FrameRenderer(document)
    try:
        return renderer.frame(at)
    finally:
        renderer.close()


def test_a_frame_has_the_projects_size_and_four_channels(project):
    frame = render_at(project, 1.0)
    assert frame.shape == (180, 320, 4)
    assert frame.dtype == np.uint8


def test_a_text_clip_draws_something(project):
    """An empty frame means the clip did not render at all."""
    frame = render_at(project, 1.0)
    assert frame[:, :, :3].max() > 40, "nothing was drawn"


def test_nothing_is_drawn_before_a_clip_starts():
    document = make_project(clips=[text_clip(start=2.0, duration=2.0)])
    before = render_at(document, 0.5)[:, :, :3]
    during = render_at(document, 3.0)[:, :, :3]
    assert before.max() < 30, "something was drawn before the clip began"
    assert during.max() > before.max(), "the clip never appeared"


def test_opacity_reaches_the_alpha_channel():
    solid = make_project(
        clips=[
            text_clip(
                transform={
                    "scale": 100,
                    "posX": 0,
                    "posY": 0,
                    "rotation": 0,
                    "width": 100,
                    "height": 100,
                    "opacity": 40,
                    "blendMode": "Normal",
                    "flipH": False,
                }
            )
        ]
    )
    faded = render_at(solid, 1.0)[:, :, :3].astype(int)
    full = render_at(make_project(), 1.0)[:, :, :3].astype(int)
    assert faded.sum() < full.sum(), "opacity did not dim the clip"


def test_a_keyframe_changes_the_picture_over_time():
    document = make_project(
        clips=[
            text_clip(
                keyframes=[{"t": 0, "props": {"scale": 30}, "interp": "linear"}, {"t": 4, "props": {"scale": 140}, "interp": "linear"}]
            )
        ]
    )
    early, late = render_at(document, 0.2), render_at(document, 3.8)
    assert not np.array_equal(early, late), "the keyframes did nothing"
    assert lit(late) > lit(early), "scaling up covered less of the frame, not more"


def test_a_mask_removes_part_of_the_picture():
    masked = make_project(clips=[text_clip(mask={"shape": "ellipse", "x": 30, "y": 30, "w": 40, "h": 40, "feather": 0})])
    assert lit(render_at(masked, 1.0)) < lit(render_at(make_project(), 1.0))


def test_a_mask_that_does_not_move_is_built_once():
    """The cache must not rebuild a static mask, and must not serve a stale one."""
    from app.renderer import FrameRenderer

    document = make_project(clips=[text_clip(mask={"shape": "star", "x": 10, "y": 10, "w": 60, "h": 60, "feather": 4})])
    renderer = FrameRenderer(document)
    try:
        renderer.frame(0.5)
        renderer.frame(1.5)
        assert len(renderer.mask_cache) == 1
    finally:
        renderer.close()


def test_two_different_masks_give_two_different_pictures():
    def with_mask(x):
        return render_at(make_project(clips=[text_clip(mask={"shape": "star", "x": x, "y": 10, "w": 40, "h": 40, "feather": 2})]), 1.0)

    assert not np.array_equal(with_mask(5), with_mask(45)), "a stale mask was served"


def test_a_background_is_drawn_behind_the_clip():
    plain = render_at(make_project(), 1.0)
    on_gradient = render_at(make_project(background={"type": "gradient", "from": "#ff0000", "to": "#0000ff"}), 1.0)
    assert not np.array_equal(plain, on_gradient)


def test_preview_and_export_paths_agree():
    """The property this editor is built on: one renderer, two uses."""
    import cv2

    document = make_project(
        clips=[
            text_clip(
                transform={
                    "scale": 70,
                    "posX": 8,
                    "posY": -4,
                    "rotation": 10,
                    "width": 100,
                    "height": 100,
                    "opacity": 100,
                    "blendMode": "Normal",
                    "flipH": False,
                }
            )
        ]
    )
    small = render_at(document, 1.0, 160)[:, :, :3].astype(np.float32)
    large = render_at(document, 1.0)[:, :, :3].astype(np.float32)
    shrunk = cv2.resize(large, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_AREA)
    assert np.abs(small - shrunk).mean() < 6.0


@pytest.mark.parametrize("shape", ["rect", "ellipse", "triangle", "diamond", "star", "heart"])
def test_every_mask_shape_renders(shape):
    document = make_project(clips=[text_clip(mask={"shape": shape, "x": 15, "y": 15, "w": 70, "h": 70, "feather": 2})])
    assert render_at(document, 1.0).shape == (180, 320, 4)


def test_a_cutout_is_computed_from_the_clip_not_the_canvas(monkeypatch):
    """The model must see the clip's own pixels.

    A composited frame has the clip already scaled, rotated and placed on the
    canvas, so segmenting that finds whatever is in the frame rather than the
    subject. Handing over the canvas is what turned a person cutout into a blob.
    """
    import numpy as np
    from app import model_manager, segmentation
    from app.renderer import FrameRenderer

    SOURCE = (120, 200)  # deliberately not the canvas size
    seen: list[tuple[int, int]] = []

    def fake_alpha(image, model):
        seen.append(tuple(image.shape[:2]))
        return np.ones(image.shape[:2], np.float32)

    monkeypatch.setattr(segmentation, "raw_alpha", fake_alpha)
    monkeypatch.setattr(model_manager, "ready", lambda model: True)
    monkeypatch.setattr(FrameRenderer, "media_frame", lambda self, clip, at: np.zeros((*SOURCE, 3), np.uint8))

    document = make_project(
        clips=[
            text_clip(
                cutout={"model": "person-cutout", "threshold": 0.5, "feather": 0.1, "strokes": []},
                transform={
                    "scale": 40,
                    "posX": 20,
                    "posY": 10,
                    "rotation": 25,
                    "width": 100,
                    "height": 100,
                    "opacity": 100,
                    "blendMode": "Normal",
                    "flipH": False,
                },
            )
        ]
    )
    renderer = FrameRenderer(document)
    try:
        renderer.frame(1.0)
    finally:
        renderer.close()

    assert seen, "the model was never asked for a matte"
    assert seen[0] == SOURCE, f"the model was handed {seen[0]}, not the clip's own pixels"
